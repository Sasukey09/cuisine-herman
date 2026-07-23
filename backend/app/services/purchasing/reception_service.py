"""Réception de marchandise : contrôle qualité, écarts, validation.

Trois principes gouvernent ce module, et ils expliquent la plupart des choix
qu'on y trouve.

**Une réception est un événement.** Tant qu'elle est en brouillon elle se
corrige librement ; une fois validée elle est figée. Une correction ultérieure
prend la forme d'une nouvelle réception corrective, jamais d'une réécriture.
C'est ce qui permet, trois semaines plus tard, de dire ce qui avait été
constaté le jour de la livraison.

**Ce qui se déduit ne se stocke pas.** Une seule quantité est saisie par ligne :
``qty_delivered``, ce qui est descendu du camion. Accepté, refusé, détruit et
l'état de la ligne se calculent depuis les anomalies. Aucune réconciliation à
tenir, donc aucune dérive possible entre deux vérités — ce projet a déjà payé
deux fois ce type de bug.

**Une anomalie porte sur une PARTIE de la ligne.** Sur 10 unités on peut en
refuser une pour DLC trop courte et en détruire une pour casse, sans rien dire
des huit autres. Étiqueter la ligne entière aurait obligé à choisir un motif.

Le cœur (``line_quality``, ``compare_reception``) est **pur** : il prend des
dictionnaires et rend des dictionnaires.
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

# --- issue d'une anomalie ---------------------------------------------------
ACCEPTED = "accepted"    # gardée sous réserve : on l'a, on la paie
REJECTED = "rejected"    # repartie avec le livreur
DESTROYED = "destroyed"  # détruite sur place

OUTCOMES = (ACCEPTED, REJECTED, DESTROYED)
OUTCOME_LABELS = {
    ACCEPTED: "Acceptée sous réserve",
    REJECTED: "Refusée",
    DESTROYED: "Détruite",
}

# --- motifs de contrôle qualité ---------------------------------------------
PACKAGING_DAMAGED = "packaging_damaged"
PRODUCT_DAMAGED = "product_damaged"
SHORT_SHELF_LIFE = "short_shelf_life"
WRONG_GRADE = "wrong_grade"
WRONG_TEMPERATURE = "wrong_temperature"
WRONG_PACKAGING = "wrong_packaging"
SUBSTITUTED = "substituted"
BREAKAGE = "breakage"
MISSING = "missing"
OTHER = "other"

REASONS = (
    PACKAGING_DAMAGED,
    PRODUCT_DAMAGED,
    SHORT_SHELF_LIFE,
    WRONG_GRADE,
    WRONG_TEMPERATURE,
    WRONG_PACKAGING,
    SUBSTITUTED,
    BREAKAGE,
    MISSING,
    OTHER,
)

REASON_LABELS = {
    PACKAGING_DAMAGED: "Emballage endommagé",
    PRODUCT_DAMAGED: "Produit abîmé",
    SHORT_SHELF_LIFE: "DLC/DLUO trop courte",
    WRONG_GRADE: "Mauvais calibre",
    WRONG_TEMPERATURE: "Mauvaise température",
    WRONG_PACKAGING: "Mauvais conditionnement",
    SUBSTITUTED: "Produit remplacé",
    BREAKAGE: "Casse",
    MISSING: "Produit absent",
    OTHER: "Autre",
}

# --- état calculé d'une ligne ----------------------------------------------
CONFORME = "conforme"
PARTIELLEMENT_CONFORME = "partiellement_conforme"
REFUSEE = "refusee"
REMPLACEE = "remplacee"
EN_ATTENTE = "en_attente"
HORS_COMMANDE = "hors_commande"

LINE_STATE_LABELS = {
    CONFORME: "Conforme",
    PARTIELLEMENT_CONFORME: "Partiellement conforme",
    REFUSEE: "Refusée",
    REMPLACEE: "Remplacée",
    EN_ATTENTE: "En attente",
    HORS_COMMANDE: "Hors commande",
}

# --- état d'une réception ---------------------------------------------------
DRAFT = "draft"
CHECKED = "checked"

_QTY_EPSILON = 0.001
_PRICE_EPSILON = 0.005


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


# --------------------------------------------------------------------------- #
# Pur : la qualité d'une ligne reçue
# --------------------------------------------------------------------------- #
def line_quality(line: Dict[str, Any]) -> Dict[str, Any]:
    """Répartit ce qui est arrivé entre accepté, refusé et détruit.

    ``line`` porte ``qty_delivered``, éventuellement ``substituted_product_id``,
    et ``issues`` : une liste de ``{qty, reason, outcome}``.

    Une anomalie sans quantité porte sur la ligne entière — c'est le cas usuel
    d'un « tout refusé », qu'on ne veut pas obliger à chiffrer.

    Refusée ou détruite, la marchandise n'est pas là : ni pour la commande, qui
    reste due, ni pour le stock. La distinction entre les deux se garde pour le
    dossier et pour la discussion avec le fournisseur.
    """
    delivered = _f(line.get("qty_delivered")) or 0.0
    issues = line.get("issues") or []

    rejected = 0.0
    destroyed = 0.0
    flagged = 0.0  # unités touchées par une anomalie, quelle qu'en soit l'issue
    for i in issues:
        qty = _f(i.get("qty"))
        # Pas de quantité : l'anomalie vaut pour toute la ligne.
        qty = delivered if qty is None else qty
        flagged += qty
        outcome = i.get("outcome") or REJECTED
        if outcome == REJECTED:
            rejected += qty
        elif outcome == DESTROYED:
            destroyed += qty

    lost = min(rejected + destroyed, delivered)
    accepted = max(delivered - lost, 0.0)

    if line.get("substituted_product_id") or any(
        i.get("reason") == SUBSTITUTED for i in issues
    ):
        state = REMPLACEE
    elif delivered <= _QTY_EPSILON:
        state = EN_ATTENTE
    elif accepted <= _QTY_EPSILON:
        state = REFUSEE
    elif flagged > _QTY_EPSILON:
        state = PARTIELLEMENT_CONFORME
    else:
        state = CONFORME

    return {
        "qty_delivered": round(delivered, 4),
        "qty_accepted": round(accepted, 4),
        "qty_rejected": round(min(rejected, delivered), 4),
        "qty_destroyed": round(min(destroyed, max(delivered - rejected, 0.0)), 4),
        "state": state,
        "state_label": LINE_STATE_LABELS[state],
        "reasons": sorted({i.get("reason") for i in issues if i.get("reason")}),
    }


def accepted_qty(line: Dict[str, Any]) -> float:
    """Ce qui compte face à la commande et pour le stock."""
    return line_quality(line)["qty_accepted"]


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

        qualities = [line_quality(r) for r in rows]
        delivered_now = sum(q["qty_delivered"] for q in qualities)
        accepted_now = sum(q["qty_accepted"] for q in qualities)
        total = already + accepted_now
        remaining = round(ordered - total, 4)

        anomalies: List[str] = []
        ordered_price = _f(o.get("unit_price"))

        # Écart de PRIX : le bon de livraison n'annonce pas ce que la commande
        # avait retenu. Ce n'est pas encore une facture, mais c'est le premier
        # endroit où ça se voit.
        for r in rows:
            got = _f(r.get("unit_price"))
            if (
                ordered_price is not None
                and got is not None
                and abs(got - ordered_price) > _PRICE_EPSILON
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

        if any(q["state"] == REMPLACEE for q in qualities):
            anomalies.append("product")
        if any(q["qty_rejected"] or q["qty_destroyed"] for q in qualities):
            anomalies.append("quality")

        # Le statut se lit sur ce qui a été ACCEPTÉ, pas sur la présence d'une
        # ligne de réception : une livraison entièrement refusée a bien eu lieu,
        # mais elle n'a rien apporté.
        if ordered <= _QTY_EPSILON:
            # Rien n'était dû : la ligne ne doit pas retenir la commande
            # ouverte pour toujours.
            status = "ok"
        elif total <= _QTY_EPSILON:
            status = "pending"
        elif abs(remaining) <= _QTY_EPSILON:
            status = "ok"
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
                "qty_delivered_now": round(delivered_now, 4),
                "qty_accepted_now": round(accepted_now, 4),
                "qty_rejected_now": round(sum(q["qty_rejected"] for q in qualities), 4),
                "qty_destroyed_now": round(sum(q["qty_destroyed"] for q in qualities), 4),
                "qty_received_total": round(total, 4),
                "qty_remaining": max(remaining, 0.0),
                "unit_price": ordered_price,
                # Ce qu'on oppose au fournisseur est un montant, pas un compte.
                "missing_value": (
                    round(remaining * (ordered_price or 0.0), 2) if remaining > 0 else 0.0
                ),
                "reasons": sorted({r for q in qualities for r in q["reasons"]}),
                "line_states": [q["state"] for q in qualities],
                "anomalies": sorted(set(anomalies)),
                "status": status,
            }
        )

    for r in extras:
        q = line_quality(r)
        lines.append(
            {
                "order_line_id": None,
                "product_id": r.get("product_id"),
                "description": r.get("description"),
                "qty_ordered": None,
                "qty_received_before": 0.0,
                "qty_delivered_now": q["qty_delivered"],
                "qty_accepted_now": q["qty_accepted"],
                "qty_rejected_now": q["qty_rejected"],
                "qty_destroyed_now": q["qty_destroyed"],
                "qty_received_total": q["qty_accepted"],
                "qty_remaining": 0.0,
                "unit_price": _f(r.get("unit_price")),
                "missing_value": 0.0,
                "reasons": q["reasons"],
                "line_states": [HORS_COMMANDE],
                "anomalies": ["unordered"],
                "status": "extra",
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

    ordered_only = [l for l in lines if l["status"] != "extra"]
    complete = bool(ordered_only) and all(l["status"] == "ok" for l in ordered_only)
    nothing = (
        all(l["qty_received_total"] <= _QTY_EPSILON for l in ordered_only)
        if ordered_only
        else True
    )

    return {
        "lines": lines,
        "document_anomalies": document_anomalies,
        "issue_count": sum(
            1 for l in lines if l["status"] != "ok" or l["reasons"] or l["anomalies"]
        )
        + len(document_anomalies),
        "missing_value": round(sum(l["missing_value"] for l in lines), 2),
        "rejected_count": sum(1 for l in lines if l["qty_rejected_now"] > 0),
        "destroyed_count": sum(1 for l in lines if l["qty_destroyed_now"] > 0),
        "extra_count": sum(1 for l in lines if l["status"] == "extra"),
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


def line_to_dict(line: ReceiptLine) -> Dict[str, Any]:
    """Forme attendue par le cœur pur, depuis une ligne de la base."""
    return {
        "id": str(line.id),
        "order_line_id": str(line.order_line_id) if line.order_line_id else None,
        "product_id": str(line.product_id) if line.product_id else None,
        "description": line.description,
        "qty_delivered": line.qty_delivered,
        "unit_id": line.unit_id,
        "unit_price": line.unit_price,
        "pack_size": line.pack_size,
        "substituted_product_id": str(line.substituted_product_id)
        if line.substituted_product_id
        else None,
        "notes": line.notes,
        "issues": [
            {
                "id": str(i.id),
                "qty": _f(i.qty),
                "reason": i.reason,
                "outcome": i.outcome,
                "notes": i.notes,
            }
            for i in (line.issues or [])
        ],
    }


def _receipt_lines(db: Session, tenant_id: str, receipt_id: str) -> List[Dict[str, Any]]:
    return [
        line_to_dict(l)
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
    """Ce que les réceptions de cette commande ont déjà **accepté**, par ligne.

    ``exclude_receipt_id`` écarte la réception en cours de contrôle, pour ne pas
    compter deux fois ce qu'elle apporte. Nul quand on veut le total — c'est le
    cas du pré-remplissage d'un nouveau brouillon.

    Refusé et détruit sont exclus : on ne les a pas, la commande reste due.
    """
    q = (
        db.query(ReceiptLine)
        .join(Receipt, Receipt.id == ReceiptLine.receipt_id)
        .filter(ReceiptLine.tenant_id == tenant_id, Receipt.order_id == order_id)
    )
    if exclude_receipt_id:
        # Comparer un UUID à une chaîne vide ferait échouer Postgres à
        # l'exécution : le filtre ne se pose que s'il y a quelque chose à exclure.
        q = q.filter(Receipt.id != exclude_receipt_id)

    out: Dict[str, float] = {}
    for line in q.all():
        if line.order_line_id is None:
            continue
        key = str(line.order_line_id)
        out[key] = out.get(key, 0.0) + accepted_qty(line_to_dict(line))
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

    **Seul l'ACCEPTÉ entre en stock.** Ce qui est reparti ou a été détruit n'a
    jamais été à nous : l'entrer puis le sortir laisserait deux mouvements pour
    un fait qui n'a pas eu lieu.
    """
    receipt.status = CHECKED
    receipt.checked_at = datetime.now()
    receipt.checked_by = user_id

    for line in (
        db.query(ReceiptLine)
        .filter(ReceiptLine.tenant_id == tenant_id, ReceiptLine.receipt_id == receipt.id)
        .all()
    ):
        if line.product_id is None:
            continue
        accepted = accepted_qty(line_to_dict(line))
        if accepted <= _QTY_EPSILON:
            continue
        db.add(
            StockMovement(
                tenant_id=tenant_id,
                product_id=line.product_id,
                qty=accepted,  # signée : + entrée
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


def order_progress(db: Session, tenant_id: str, order_id: str) -> Dict[str, Any]:
    """Avancement d'une commande, toutes ses réceptions confondues.

    Le pendant de ``control``, qui ne regarde qu'une réception. C'est ce que la
    fiche commande affiche : où en est-on, et que reste-t-il dû.
    """
    order = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.id == order_id)
        .first()
    )
    lines: List[Dict[str, Any]] = []
    for receipt in (
        db.query(Receipt)
        .filter(Receipt.tenant_id == tenant_id, Receipt.order_id == order_id)
        .all()
    ):
        lines.extend(_receipt_lines(db, tenant_id, str(receipt.id)))

    return compare_reception(
        _order_lines(db, tenant_id, order_id),
        lines,
        order_supplier_id=str(order.supplier_id) if order and order.supplier_id else None,
        receipt_supplier_id=None,  # plusieurs réceptions : l'écart se lit par réception
    )
