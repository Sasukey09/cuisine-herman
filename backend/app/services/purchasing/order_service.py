"""Commandes fournisseur : création depuis les devis, cycle de vie, avancement.

Le cœur du module — ``plan_orders`` et ``line_progress`` — est **pur** : il
prend des dictionnaires et rend des dictionnaires, sans base ni réseau. Les
enveloppes qui parlent à Postgres sont en bas du fichier.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    QuoteLine,
    ReceiptLine,
    Supplier,
)
from app.services.purchasing import numbering

# --------------------------------------------------------------------------- #
# Cycle de vie
# --------------------------------------------------------------------------- #
DRAFT = "draft"
SENT = "sent"
CONFIRMED = "confirmed"
PREPARING = "preparing"
SHIPPED = "shipped"
PARTIALLY_RECEIVED = "partially_received"
RECEIVED = "received"
INVOICED = "invoiced"
CLOSED = "closed"
CANCELLED = "cancelled"

STATUSES = (
    DRAFT, SENT, CONFIRMED, PREPARING, SHIPPED,
    PARTIALLY_RECEIVED, RECEIVED, INVOICED, CLOSED, CANCELLED,
)

#: Transitions autorisées. Une commande clôturée ou annulée est un point final :
#: rouvrir un document d'engagement passé réécrirait l'histoire.
_TRANSITIONS: Dict[str, tuple] = {
    DRAFT: (SENT, CONFIRMED, CANCELLED),
    SENT: (CONFIRMED, PREPARING, SHIPPED, CANCELLED),
    CONFIRMED: (PREPARING, SHIPPED, PARTIALLY_RECEIVED, RECEIVED, CANCELLED),
    PREPARING: (SHIPPED, PARTIALLY_RECEIVED, RECEIVED, CANCELLED),
    SHIPPED: (PARTIALLY_RECEIVED, RECEIVED, CANCELLED),
    PARTIALLY_RECEIVED: (RECEIVED, INVOICED, CLOSED, CANCELLED),
    RECEIVED: (INVOICED, CLOSED),
    INVOICED: (CLOSED,),
    CLOSED: (),
    CANCELLED: (),
}

#: Ce qu'on montre à l'utilisateur. Le stockage reste en anglais comme le reste
#: du schéma ; la traduction vit ici, pas éparpillée dans les deux clients.
STATUS_LABELS = {
    DRAFT: "Brouillon",
    SENT: "Envoyée",
    CONFIRMED: "Confirmée",
    PREPARING: "En préparation",
    SHIPPED: "Expédiée",
    PARTIALLY_RECEIVED: "Partiellement livrée",
    RECEIVED: "Livrée",
    INVOICED: "Facturée",
    CLOSED: "Terminée",
    CANCELLED: "Annulée",
}


def can_transition(current: Optional[str], target: str) -> bool:
    if target not in STATUSES:
        return False
    return target in _TRANSITIONS.get(current or DRAFT, ())


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


# --------------------------------------------------------------------------- #
# Pur : planifier les commandes à partir d'offres retenues
# --------------------------------------------------------------------------- #
def plan_orders(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Regroupe des offres retenues en commandes, **une par fournisseur**.

    C'est la fonction qui rend le comparateur exécutable. Il désigne le moins
    cher produit par produit, donc potentiellement chez trois fournisseurs
    différents ; jusqu'ici on ne pouvait pas agir dessus, parce que commander
    marquait un devis entier comme commandé chez un seul fournisseur.

    Chaque offre porte : ``supplier_id``, ``quote_line_id``, ``product_id``,
    ``description``, ``qty``, ``unit_price``, et éventuellement ``vat_rate``,
    ``discount_pct``, ``pack_size``, ``brand``, ``unit_id``, ainsi que les
    conditions du devis d'origine (``delivery_fee``, ``discount_total``,
    ``conditions``, ``currency``).

    Le prix offert est repris **tel quel**. Rien n'est rechiffré depuis
    l'historique d'achat : c'est précisément ce qui rendait le contrôle
    devis/facture circulaire.
    """
    by_supplier: Dict[Any, Dict[str, Any]] = {}

    for o in offers:
        sup = o.get("supplier_id")
        qty = _f(o.get("qty")) or 0.0
        price = _f(o.get("unit_price"))
        discount = _f(o.get("discount_pct")) or 0.0
        # Le total de ligne fourni prime : il vient du document et peut inclure
        # des arrondis que le produit qté × PU ne reproduirait pas.
        total = _f(o.get("line_total"))
        if total is None and price is not None:
            total = round(qty * price * (1 - discount / 100.0), 2)

        order = by_supplier.setdefault(
            sup,
            {
                "supplier_id": sup,
                "supplier_name": o.get("supplier_name"),
                "currency": o.get("currency") or "EUR",
                "delivery_fee": None,
                "discount_total": None,
                "conditions": o.get("conditions"),
                "lines": [],
                "lines_total": 0.0,
            },
        )
        # Les frais de port portent sur la commande : si les lignes viennent de
        # plusieurs devis du même fournisseur, on retient les plus élevés plutôt
        # que de les additionner — on ne paie le port qu'une fois.
        fee = _f(o.get("delivery_fee"))
        if fee is not None:
            order["delivery_fee"] = max(order["delivery_fee"] or 0.0, fee)
        disc = _f(o.get("discount_total"))
        if disc is not None:
            order["discount_total"] = max(order["discount_total"] or 0.0, disc)
        if order["conditions"] is None and o.get("conditions"):
            order["conditions"] = o.get("conditions")

        order["lines"].append(
            {
                "source_quote_line_id": o.get("quote_line_id"),
                "product_id": o.get("product_id"),
                "description": o.get("description"),
                "qty_ordered": qty or None,
                "unit_id": o.get("unit_id"),
                "unit_price": price,
                "vat_rate": _f(o.get("vat_rate")),
                "discount_pct": _f(o.get("discount_pct")),
                "line_total": total,
                "pack_size": o.get("pack_size"),
                "brand": o.get("brand"),
            }
        )
        order["lines_total"] += total or 0.0

    plans = []
    for order in by_supplier.values():
        lines_total = round(order.pop("lines_total"), 2)
        order["lines_total"] = lines_total
        # Ce qu'on paiera vraiment : panier − remise globale + port.
        order["total_amount"] = round(
            lines_total - (order["discount_total"] or 0.0) + (order["delivery_fee"] or 0.0), 2
        )
        plans.append(order)

    # Le plus gros panier d'abord : c'est la commande qui engage le plus.
    plans.sort(key=lambda p: -p["total_amount"])
    return plans


# --------------------------------------------------------------------------- #
# Pur : avancement d'une commande (commandé vs reçu)
# --------------------------------------------------------------------------- #
_QTY_EPSILON = 0.001


def line_progress(ordered: List[Dict[str, Any]], received: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Confronte les lignes commandées aux lignes réellement reçues.

    ``ordered`` : ``{id, product_id, description, qty_ordered, unit_price}``.
    ``received`` : ``{order_line_id, product_id, description, qty_received,
    condition}`` — ``order_line_id`` peut être nul, c'est justement le cas d'un
    produit livré **hors commande**.

    Rend, par ligne, ce qui manque ou ce qui est en trop, et l'état global de la
    commande. Aucune quantité reçue n'est stockée sur la commande : elle se
    calcule ici, donc il n'existe qu'une seule vérité.
    """
    got: Dict[Any, float] = {}
    conditions: Dict[Any, List[str]] = {}
    extras: List[Dict[str, Any]] = []

    for r in received:
        key = r.get("order_line_id")
        qty = _f(r.get("qty_received")) or 0.0
        if key is None:
            extras.append(
                {
                    "product_id": r.get("product_id"),
                    "description": r.get("description"),
                    "qty_received": qty,
                    "condition": r.get("condition") or "extra",
                    "status": "extra",
                }
            )
            continue
        got[key] = got.get(key, 0.0) + qty
        if r.get("condition") and r["condition"] != "ok":
            conditions.setdefault(key, []).append(r["condition"])

    lines: List[Dict[str, Any]] = []
    for o in ordered:
        key = o.get("id")
        want = _f(o.get("qty_ordered")) or 0.0
        have = got.get(key, 0.0)
        delta = round(have - want, 4)
        if have <= _QTY_EPSILON:
            status = "pending" if want > 0 else "ok"
        elif abs(delta) <= _QTY_EPSILON:
            status = "ok"
        elif delta < 0:
            status = "partial"
        else:
            status = "over"
        lines.append(
            {
                "order_line_id": key,
                "product_id": o.get("product_id"),
                "description": o.get("description"),
                "qty_ordered": want or None,
                "qty_received": have,
                "qty_missing": round(want - have, 4) if have < want else 0.0,
                "unit_price": _f(o.get("unit_price")),
                # Valeur de ce qui manque : c'est le chiffre qu'on oppose au
                # fournisseur, pas la quantité.
                "missing_value": (
                    round((want - have) * (_f(o.get("unit_price")) or 0.0), 2)
                    if have < want else 0.0
                ),
                "conditions": conditions.get(key, []),
                "status": status,
            }
        )

    lines.extend(extras)
    ordered_lines = [l for l in lines if l.get("status") != "extra"]
    fully = ordered_lines and all(l["status"] == "ok" for l in ordered_lines)
    nothing = all(
        (l.get("qty_received") or 0.0) <= _QTY_EPSILON for l in ordered_lines
    ) if ordered_lines else True

    return {
        "lines": lines,
        "issue_count": sum(
            1 for l in lines if l.get("status") not in ("ok",)
        ),
        "missing_value": round(sum(l.get("missing_value") or 0.0 for l in lines), 2),
        "extra_count": len(extras),
        "is_complete": bool(fully),
        "nothing_received": bool(nothing),
        # L'état que la commande devrait porter au vu de ses réceptions.
        "suggested_status": (
            RECEIVED if fully else (None if nothing else PARTIALLY_RECEIVED)
        ),
    }


# --------------------------------------------------------------------------- #
# Enveloppes base de données
# --------------------------------------------------------------------------- #
def offers_from_quote_lines(
    db: Session, tenant_id: str, quote_line_ids: Iterable[str]
) -> List[Dict[str, Any]]:
    """Charge les lignes de devis retenues sous la forme attendue par
    ``plan_orders``, en refusant celles d'une autre organisation."""
    ids = [i for i in quote_line_ids if i]
    if not ids:
        return []
    rows = (
        db.query(QuoteLine, Quote, Supplier)
        .join(Quote, Quote.id == QuoteLine.quote_id)
        .outerjoin(
            Supplier,
            Supplier.id == func.coalesce(QuoteLine.supplier_id, Quote.supplier_id),
        )
        .filter(QuoteLine.tenant_id == tenant_id, QuoteLine.id.in_(ids))
        .all()
    )
    return [
        {
            "quote_line_id": str(line.id),
            "supplier_id": str(line.supplier_id or quote.supplier_id)
            if (line.supplier_id or quote.supplier_id)
            else None,
            "supplier_name": supplier.name if supplier else None,
            "product_id": str(line.product_id) if line.product_id else None,
            "description": line.description,
            "qty": line.qty,
            "unit_id": line.unit_id,
            "unit_price": line.unit_price,
            "vat_rate": line.vat_rate,
            "discount_pct": line.discount_pct,
            "line_total": line.line_total,
            "pack_size": line.pack_size,
            "brand": line.brand,
            "currency": quote.currency,
            "delivery_fee": quote.delivery_fee,
            "discount_total": quote.discount_total,
            "conditions": quote.conditions,
        }
        for line, quote, supplier in rows
    ]


def create_orders(
    db: Session,
    tenant_id: str,
    plans: List[Dict[str, Any]],
    expected_date=None,
    status: str = DRAFT,
) -> List[PurchaseOrder]:
    """Persiste les commandes planifiées. Une transaction pour l'ensemble :
    commander chez trois fournisseurs réussit en entier ou pas du tout."""
    created: List[PurchaseOrder] = []
    for plan in plans:
        order = PurchaseOrder(
            tenant_id=tenant_id,
            reference=numbering.next_reference(
                db, tenant_id, numbering.ORDER, PurchaseOrder
            ),
            supplier_id=plan.get("supplier_id"),
            status=status,
            expected_date=expected_date,
            ordered_at=datetime.now() if status != DRAFT else None,
            total_amount=plan.get("total_amount"),
            currency=plan.get("currency") or "EUR",
            delivery_fee=plan.get("delivery_fee"),
            discount_total=plan.get("discount_total"),
            conditions=plan.get("conditions"),
        )
        db.add(order)
        db.flush()  # besoin de l'id pour les lignes
        for l in plan.get("lines", []):
            db.add(PurchaseOrderLine(tenant_id=tenant_id, order_id=order.id, **l))
        created.append(order)
    db.commit()
    for o in created:
        db.refresh(o)
    return created


def progress_for_order(db: Session, tenant_id: str, order_id: str) -> Dict[str, Any]:
    """Avancement d'une commande : commandé vs réellement reçu."""
    ordered = [
        {
            "id": str(l.id),
            "product_id": str(l.product_id) if l.product_id else None,
            "description": l.description,
            "qty_ordered": l.qty_ordered,
            "unit_price": l.unit_price,
        }
        for l in db.query(PurchaseOrderLine)
        .filter(
            PurchaseOrderLine.tenant_id == tenant_id,
            PurchaseOrderLine.order_id == order_id,
        )
        .all()
    ]
    line_ids = [l["id"] for l in ordered]
    received_rows = (
        db.query(ReceiptLine)
        .filter(
            ReceiptLine.tenant_id == tenant_id,
            ReceiptLine.order_line_id.in_(line_ids) if line_ids else False,
        )
        .all()
        if line_ids
        else []
    )
    received = [
        {
            "order_line_id": str(r.order_line_id) if r.order_line_id else None,
            "product_id": str(r.product_id) if r.product_id else None,
            "description": r.description,
            "qty_received": r.qty_received,
            "condition": r.condition,
        }
        for r in received_rows
    ]
    return line_progress(ordered, received)
