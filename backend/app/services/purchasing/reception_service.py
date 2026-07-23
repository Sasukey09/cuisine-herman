"""Réception de marchandise : contrôle des écarts et validation.

Deux principes gouvernent ce module, et ils expliquent la plupart des choix
qu'on y trouve :

**Une réception est un événement.** Tant qu'elle est en brouillon elle se
corrige librement ; une fois validée elle est figée. Une correction ultérieure
prend la forme d'une nouvelle réception corrective, jamais d'une réécriture.
C'est ce qui permet, trois semaines plus tard, de dire ce qui avait été
constaté le jour de la livraison.

**Les écarts se calculent, ils ne se stockent pas.** Les deux entrées du calcul
sont immuables — les lignes de commande ne sont modifiées par aucun endpoint,
et une réception validée est gelée. Un écart recalculé donne donc toujours le
même résultat. Le stocker créerait une seconde vérité, donc une dérive : ce
projet a déjà payé deux fois ce type de bug.

Le cœur (``compare_reception``) est **pur** : il prend des dictionnaires et rend
des dictionnaires. Les enveloppes qui parlent à Postgres sont en bas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
    ReceiptLine,
    StockMovement,
)
from app.services.purchasing import order_service

# --- états d'une ligne reçue ------------------------------------------------
OK = "ok"
MISSING = "missing"
EXTRA = "extra"
SUBSTITUTED = "substituted"
DAMAGED = "damaged"
REJECTED = "rejected"

CONDITIONS = (OK, MISSING, EXTRA, SUBSTITUTED, DAMAGED, REJECTED)

CONDITION_LABELS = {
    OK: "Conforme",
    MISSING: "Manquant",
    EXTRA: "Hors commande",
    SUBSTITUTED: "Remplacé",
    DAMAGED: "Abîmé",
    REJECTED: "Refusé",
}

DRAFT = "draft"
CHECKED = "checked"

_QTY_EPSILON = 0.001
_PRICE_EPSILON = 0.005


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def counts_toward_stock(condition: Optional[str]) -> bool:
    """Une marchandise refusée repart : elle n'entre pas en stock.

    Une marchandise abîmée, elle, est bien là — elle entrera puis sortira en
    perte quand le module Stock existera. Confondre les deux fausserait
    l'inventaire dès le premier jour."""
    return condition != REJECTED


# --------------------------------------------------------------------------- #
# Pur : le contrôle de réception
# --------------------------------------------------------------------------- #
def compare_reception(
    order_lines: List[Dict[str, Any]],
    receipt_lines: List[Dict[str, Any]],
    order_supplier_id: Optional[str] = None,
    receipt_supplier_id: Optional[str] = None,
    previously_received: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Confronte ce qui était commandé à ce qui arrive.

    ``previously_received`` porte ce que les réceptions ANTÉRIEURES ont déjà
    apporté par ligne de commande. Sans lui, une commande livrée en deux fois
    afficherait deux livraisons partielles au lieu d'une livraison complète.

    Rend, par ligne : commandé, déjà reçu, reçu maintenant, restant, et la
    nature de l'écart. Plus, au niveau du document, les anomalies qui ne se
    lisent pas ligne par ligne — le fournisseur qui n'est pas celui commandé.
    """
    prior = dict(previously_received or {})
    by_order_line: Dict[Any, List[Dict[str, Any]]] = {}
    extras: List[Dict[str, Any]] = []

    for r in receipt_lines:
        key = r.get("order_line_id")
        if key is None:
            extras.append(r)
        else:
            by_order_line.setdefault(key, []).append(r)

    lines: List[Dict[str, Any]] = []
    for o in order_lines:
        key = o.get("id")
        ordered = _f(o.get("qty_ordered")) or 0.0
        already = float(prior.get(key, 0.0) or 0.0)
        rows = by_order_line.get(key, [])

        now = sum(_f(r.get("qty_received")) or 0.0 for r in rows)
        # Le refusé est bien arrivé physiquement, mais il repart : il ne compte
        # pas comme livré face à la commande.
        accepted_now = sum(
            _f(r.get("qty_received")) or 0.0
            for r in rows
            if r.get("condition") != REJECTED
        )
        total = already + accepted_now
        remaining = round(ordered - total, 4)

        conditions = sorted(
            {r.get("condition") for r in rows if r.get("condition") and r["condition"] != OK}
        )
        anomalies: List[str] = []

        # Écart de PRIX : le bon de livraison n'annonce pas ce que la commande
        # avait retenu. Ce n'est pas encore une facture, mais c'est le premier
        # endroit où ça se voit.
        ordered_price = _f(o.get("unit_price"))
        for r in rows:
            got_price = _f(r.get("unit_price"))
            if (
                ordered_price is not None
                and got_price is not None
                and abs(got_price - ordered_price) > _PRICE_EPSILON
            ):
                anomalies.append("price")
                break

        # Écart de CONDITIONNEMENT : même nombre de lignes, quantité réelle
        # différente.
        ordered_pack = (o.get("pack_size") or "").strip().lower()
        for r in rows:
            got_pack = (r.get("pack_size") or "").strip().lower()
            if ordered_pack and got_pack and got_pack != ordered_pack:
                anomalies.append("pack_size")
                break

        # Écart de PRODUIT : on a livré autre chose.
        for r in rows:
            if r.get("substituted_product_id") or r.get("condition") == SUBSTITUTED:
                anomalies.append("product")
                break

        # Le statut se lit sur ce qui a été ACCEPTÉ, pas sur la présence d'une
        # ligne de réception. Une livraison entièrement refusée a bien eu lieu,
        # mais elle n'a rien apporté : l'annoncer « partielle » ferait croire
        # qu'une partie est en réserve. Le refus lui-même reste visible dans
        # `conditions`, il ne disparaît pas.
        if ordered <= _QTY_EPSILON:
            # Rien n'était dû : la ligne n'a pas à retenir la commande. Sans
            # cette sortie, une ligne saisie sans quantité resterait « en
            # attente » pour toujours et la commande ne pourrait jamais se
            # clore.
            status = OK
        elif total <= _QTY_EPSILON:
            status = "pending"
        elif abs(remaining) <= _QTY_EPSILON:
            status = OK
        elif remaining > 0:
            status = "partial"
        else:
            status = "over"

        lines.append(
            {
                "order_line_id": key,
                "product_id": o.get("product_id"),
                "description": o.get("description"),
                "qty_ordered": ordered or None,
                "qty_received_before": round(already, 4),
                "qty_received_now": round(now, 4),
                "qty_received_total": round(total, 4),
                "qty_remaining": max(remaining, 0.0),
                "unit_price": ordered_price,
                # Ce qu'on oppose au fournisseur est un montant, pas un compte.
                "missing_value": (
                    round(remaining * (ordered_price or 0.0), 2) if remaining > 0 else 0.0
                ),
                "conditions": conditions,
                "anomalies": sorted(set(anomalies)),
                "status": status,
            }
        )

    for r in extras:
        lines.append(
            {
                "order_line_id": None,
                "product_id": r.get("product_id"),
                "description": r.get("description"),
                "qty_ordered": None,
                "qty_received_before": 0.0,
                "qty_received_now": _f(r.get("qty_received")) or 0.0,
                "qty_received_total": _f(r.get("qty_received")) or 0.0,
                "qty_remaining": 0.0,
                "unit_price": _f(r.get("unit_price")),
                "missing_value": 0.0,
                "conditions": [r.get("condition")] if r.get("condition") else [],
                "anomalies": ["unordered"],
                "status": EXTRA,
            }
        )

    document_anomalies: List[str] = []
    # Écart de FOURNISSEUR : livré par quelqu'un d'autre que celui commandé.
    if (
        order_supplier_id
        and receipt_supplier_id
        and str(order_supplier_id) != str(receipt_supplier_id)
    ):
        document_anomalies.append("supplier")

    ordered_only = [l for l in lines if l["status"] != EXTRA]
    complete = bool(ordered_only) and all(l["status"] == OK for l in ordered_only)
    nothing = all(l["qty_received_total"] <= _QTY_EPSILON for l in ordered_only) if ordered_only else True

    return {
        "lines": lines,
        "document_anomalies": document_anomalies,
        "issue_count": sum(
            1
            for l in lines
            if l["status"] not in (OK,) or l["conditions"] or l["anomalies"]
        )
        + len(document_anomalies),
        "missing_value": round(sum(l["missing_value"] for l in lines), 2),
        "extra_count": sum(1 for l in lines if l["status"] == EXTRA),
        "is_complete": complete,
        "nothing_received": nothing,
        "suggested_status": (
            order_service.RECEIVED
            if complete
            else (None if nothing else order_service.PARTIALLY_RECEIVED)
        ),
    }


# --------------------------------------------------------------------------- #
# Enveloppes base de données
# --------------------------------------------------------------------------- #
def _order_lines(db: Session, tenant_id: str, order_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": str(l.id),
            "product_id": str(l.product_id) if l.product_id else None,
            "description": l.description,
            "qty_ordered": l.qty_ordered,
            "unit_id": l.unit_id,
            "unit_price": l.unit_price,
            "pack_size": l.pack_size,
        }
        for l in db.query(PurchaseOrderLine)
        .filter(
            PurchaseOrderLine.tenant_id == tenant_id,
            PurchaseOrderLine.order_id == order_id,
        )
        .order_by(PurchaseOrderLine.created_at)
        .all()
    ]


def _receipt_lines(db: Session, tenant_id: str, receipt_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": str(l.id),
            "order_line_id": str(l.order_line_id) if l.order_line_id else None,
            "product_id": str(l.product_id) if l.product_id else None,
            "description": l.description,
            "qty_received": l.qty_received,
            "unit_price": l.unit_price,
            "pack_size": l.pack_size,
            "condition": l.condition,
            "substituted_product_id": str(l.substituted_product_id)
            if l.substituted_product_id
            else None,
            "notes": l.notes,
            "photo_url": l.photo_url,
        }
        for l in db.query(ReceiptLine)
        .filter(ReceiptLine.tenant_id == tenant_id, ReceiptLine.receipt_id == receipt_id)
        .order_by(ReceiptLine.created_at)
        .all()
    ]


def received_by_order_line(
    db: Session,
    tenant_id: str,
    order_id: str,
    exclude_receipt_id: Optional[str] = None,
) -> Dict[str, float]:
    """Ce que les réceptions de cette commande ont déjà apporté, par ligne.

    ``exclude_receipt_id`` écarte la réception en cours de contrôle, pour ne pas
    compter deux fois ce qu'elle apporte. Nul quand on veut le total (c'est le
    cas du pré-remplissage d'un nouveau brouillon).

    Le refusé est exclu : il est reparti, la commande reste due.
    """
    q = (
        db.query(ReceiptLine)
        .join(Receipt, Receipt.id == ReceiptLine.receipt_id)
        .filter(
            ReceiptLine.tenant_id == tenant_id,
            Receipt.order_id == order_id,
            ReceiptLine.condition != REJECTED,
        )
    )
    if exclude_receipt_id:
        # Comparer un UUID à une chaîne vide ferait échouer Postgres à
        # l'exécution : le filtre ne se pose que s'il y a quelque chose à exclure.
        q = q.filter(Receipt.id != exclude_receipt_id)
    rows = q.all()
    out: Dict[str, float] = {}
    for r in rows:
        if r.order_line_id is None:
            continue
        out[str(r.order_line_id)] = out.get(str(r.order_line_id), 0.0) + float(
            r.qty_received or 0
        )
    return out


def control(db: Session, tenant_id: str, receipt: Receipt) -> Dict[str, Any]:
    """Le contrôle de cette réception, face à sa commande."""
    if receipt.order_id is None:
        # Livraison sans commande : tout est hors commande, par définition.
        return compare_reception(
            [], _receipt_lines(db, tenant_id, str(receipt.id)), None, None
        )
    order = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.id == receipt.order_id)
        .first()
    )
    return compare_reception(
        _order_lines(db, tenant_id, str(receipt.order_id)),
        _receipt_lines(db, tenant_id, str(receipt.id)),
        order_supplier_id=str(order.supplier_id) if order and order.supplier_id else None,
        receipt_supplier_id=str(receipt.supplier_id) if receipt.supplier_id else None,
        previously_received=received_by_order_line(
            db, tenant_id, str(receipt.order_id), exclude_receipt_id=str(receipt.id)
        ),
    )


def validate(
    db: Session, tenant_id: str, receipt: Receipt, user_id: Optional[str]
) -> Dict[str, Any]:
    """Fige la réception, écrit les mouvements de stock, avance la commande.

    Les mouvements naissent ici et pas au brouillon : une quantité mal saisie
    dans un brouillon entrerait sinon au stock, et il faudrait un mouvement
    compensatoire pour la reprendre. Une réception validée, elle, est un fait.
    """
    receipt.status = CHECKED
    receipt.checked_at = datetime.now()
    receipt.checked_by = user_id

    for line in (
        db.query(ReceiptLine)
        .filter(ReceiptLine.tenant_id == tenant_id, ReceiptLine.receipt_id == receipt.id)
        .all()
    ):
        qty = float(line.qty_received or 0)
        if qty <= 0 or line.product_id is None:
            continue
        if not counts_toward_stock(line.condition):
            continue
        db.add(
            StockMovement(
                tenant_id=tenant_id,
                product_id=line.product_id,
                qty=line.qty_received,  # signée : + entrée
                unit_id=line.unit_id,
                movement_type="receipt",
                source_type="receipt_line",
                source_id=str(line.id),
                # Valorisation figée : le coût d'un produit bouge, la valeur
                # d'un mouvement passé, non.
                unit_cost=line.unit_price,
                moved_at=datetime.now(),
            )
        )

    result = control(db, tenant_id, receipt)

    # L'état de la commande suit ce qui a été reçu, sans jamais reculer.
    if receipt.order_id and result["suggested_status"]:
        order = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.id == receipt.order_id,
            )
            .first()
        )
        if order is not None and order_service.can_transition(
            order.status, result["suggested_status"]
        ):
            order.status = result["suggested_status"]

    db.commit()
    db.refresh(receipt)
    return result
