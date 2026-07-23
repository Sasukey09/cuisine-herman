"""Contrôle facture : commandé → livré → facturé, en une seule vue.

C'est le dernier maillon du cycle. Une facture n'arrive jamais seule : elle
prétend facturer une commande passée et une marchandise reçue. Le contrôle
confronte les trois — ce qu'on avait engagé, ce qu'on a réellement accepté, ce
qu'on nous facture — et met en évidence tout ce qui ne colle pas.

Ce module **remplace** l'ancien rapprochement devis↔facture (§9). Celui-ci
cherchait un devis « commandé », un statut qui n'existe plus depuis que la
commande est un objet de plein droit : il était devenu silencieusement mort.
Rattacher la facture à la COMMANDE, et non au devis, c'est aussi la seule façon
d'avoir la colonne « livré » — un devis ne sait rien des réceptions.

Le cœur (``compare_control``) est **pur** : trois listes de dictionnaires en
entrée, un rapport en sortie. Les enveloppes qui parlent à Postgres sont en bas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import (
    Invoice,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.services.purchasing import order_service, reception_service

_PRICE_EPSILON = 0.005
_QTY_EPSILON = 0.001
_VAT_EPSILON = 0.01

# --- drapeaux d'une ligne, du plus grave au moins grave ---------------------
BILLED_NOT_RECEIVED = "billed_not_received"  # on paie une marchandise jamais reçue
EXTRA = "extra"                              # facturé hors commande
NOT_RECEIVED = "not_received"                # commandé, pas (encore) reçu
MISSING = "missing"                          # commandé et reçu, mais pas facturé
PRICE_UP = "price_up"
PRICE_DOWN = "price_down"
VAT_DIFF = "vat_diff"
QTY_DIFF = "qty_diff"                        # facturé ≠ reçu (quantité)
OVER_BILLED = "over_billed"                  # facturé plus que reçu

FLAG_LABELS = {
    BILLED_NOT_RECEIVED: "Facturé mais non reçu",
    EXTRA: "Facturé hors commande",
    NOT_RECEIVED: "Commandé, pas encore reçu",
    MISSING: "Reçu mais pas encore facturé",
    PRICE_UP: "Prix facturé en hausse",
    PRICE_DOWN: "Prix facturé en baisse",
    VAT_DIFF: "TVA différente",
    QTY_DIFF: "Quantité facturée différente de la reçue",
    OVER_BILLED: "Facturé plus que reçu",
}

#: L'ordre dans lequel un drapeau devient le statut principal de la ligne.
#: « On me facture ce que je n'ai pas reçu » prime sur une simple hausse de prix.
_SEVERITY = [
    BILLED_NOT_RECEIVED,
    EXTRA,
    OVER_BILLED,
    NOT_RECEIVED,
    PRICE_UP,
    VAT_DIFF,
    QTY_DIFF,
    PRICE_DOWN,
    MISSING,
]


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").lower().split())


def _line_total(qty, price, given) -> Optional[float]:
    if given is not None:
        return given
    if qty is not None and price is not None:
        return round(qty * price, 2)
    return None


def compare_control(
    order_lines: List[Dict[str, Any]],
    received_by_product: Dict[str, float],
    invoice_lines: List[Dict[str, Any]],
    product_names: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Confronte commandé, livré et facturé, produit par produit.

    - ``order_lines`` : ``{product_id, description, qty_ordered, unit_price,
      vat_rate, discount_pct}``
    - ``received_by_product`` : quantité **acceptée** par produit, toutes
      réceptions de la commande confondues (le refusé et le détruit sont exclus
      en amont — on ne les a pas).
    - ``invoice_lines`` : ``{product_id, description, qty, unit_price, vat_rate,
      line_total}``

    Le rapprochement se fait par ``product_id`` quand il existe (fiable), sinon
    par description normalisée — un fournisseur qui réécrit son libellé ne doit
    pas produire un faux « facturé en trop ».
    """
    product_names = product_names or {}

    def key_of(l: Dict[str, Any]):
        pid = l.get("product_id")
        return ("p", str(pid)) if pid else ("d", _norm(l.get("description")))

    ordered: Dict[Any, Dict[str, Any]] = {}
    for l in order_lines:
        ordered.setdefault(key_of(l), l)
    billed: Dict[Any, Dict[str, Any]] = {}
    for l in invoice_lines:
        billed.setdefault(key_of(l), l)

    keys = list(ordered.keys()) + [k for k in billed if k not in ordered]
    lines: List[Dict[str, Any]] = []
    ordered_total = billed_total = 0.0

    for key in keys:
        o = ordered.get(key)
        b = billed.get(key)
        pid = (o or b or {}).get("product_id")
        name = (product_names.get(str(pid)) if pid else None) or (o or b or {}).get(
            "description"
        )
        received = float(received_by_product.get(str(pid), 0.0)) if pid else 0.0

        o_qty = _f(o.get("qty_ordered")) if o else None
        o_price = _f(o.get("unit_price")) if o else None
        o_vat = _f(o.get("vat_rate")) if o else None
        o_total = _line_total(o_qty, o_price, _f(o.get("line_total")) if o else None)

        b_qty = _f(b.get("qty")) if b else None
        b_price = _f(b.get("unit_price")) if b else None
        b_vat = _f(b.get("vat_rate")) if b else None
        b_total = _line_total(b_qty, b_price, _f(b.get("line_total")) if b else None)

        if o_total:
            ordered_total += o_total
        if b_total:
            billed_total += b_total

        flags: List[str] = []

        if o is None:
            # Facturé sans figurer à la commande. Le plus suspect : ou bien c'est
            # une erreur, ou bien un produit glissé sans accord.
            flags.append(EXTRA)
        elif b is None:
            # Commandé mais pas facturé. Deux cas très différents : pas encore
            # reçu (normal, la facture suit la livraison), ou reçu et non
            # facturé (à réclamer, ou avoir à venir).
            flags.append(NOT_RECEIVED if received <= _QTY_EPSILON else MISSING)
        else:
            # La ligne existe des deux côtés : on compare.
            if b_qty is not None and received + _QTY_EPSILON < b_qty:
                # On nous facture plus que ce qui est entré. Si rien n'est reçu,
                # c'est carrément une facturation à vide.
                flags.append(
                    BILLED_NOT_RECEIVED if received <= _QTY_EPSILON else OVER_BILLED
                )
            if (
                o_price is not None
                and b_price is not None
                and abs(b_price - o_price) > _PRICE_EPSILON
            ):
                flags.append(PRICE_UP if b_price > o_price else PRICE_DOWN)
            if o_vat is not None and b_vat is not None and abs(b_vat - o_vat) > _VAT_EPSILON:
                flags.append(VAT_DIFF)
            if (
                b_qty is not None
                and received > _QTY_EPSILON
                and abs(b_qty - received) > _QTY_EPSILON
                and OVER_BILLED not in flags
            ):
                # Facturé différent du reçu, sans être un sur-facturation franche.
                flags.append(QTY_DIFF)

        status = next((f for f in _SEVERITY if f in flags), "ok")
        price_delta = (
            round(b_price - o_price, 4)
            if (o_price is not None and b_price is not None)
            else None
        )
        total_delta = (
            round((b_total or 0.0) - (o_total or 0.0), 2)
            if (o_total is not None or b_total is not None)
            else None
        )

        lines.append(
            {
                "product_id": str(pid) if pid else None,
                "description": name,
                "ordered": {"qty": o_qty, "unit_price": o_price, "vat_rate": o_vat}
                if o
                else None,
                "received": {"qty": round(received, 4)} if o or received else None,
                "billed": {
                    "qty": b_qty,
                    "unit_price": b_price,
                    "vat_rate": b_vat,
                    "total": b_total,
                }
                if b
                else None,
                "price_delta": price_delta,
                "total_delta": total_delta,
                "flags": flags,
                "status": status,
            }
        )

    # Le tri met les lignes à problème en tête : c'est ce qu'on regarde.
    lines.sort(key=lambda r: (r["status"] == "ok", r["description"] or ""))

    issues = [l for l in lines if l["status"] != "ok"]
    return {
        "lines": lines,
        "ordered_total": round(ordered_total, 2),
        "billed_total": round(billed_total, 2),
        "total_delta": round(billed_total - ordered_total, 2),
        "issue_count": len(issues),
        "billed_not_received_count": sum(
            1 for l in lines if l["status"] in (BILLED_NOT_RECEIVED, OVER_BILLED)
        ),
        "is_conform": not issues,
    }


# --------------------------------------------------------------------------- #
# Enveloppes base de données
# --------------------------------------------------------------------------- #
def find_matching_order(db: Session, tenant_id: str, invoice) -> Optional[PurchaseOrder]:
    """La commande que cette facture prétend le plus vraisemblablement facturer.

    Mêmes critères que l'ancien rapprochement au devis, mais sur les commandes :
    même fournisseur (obligatoire), puis le plus grand recouvrement de produits,
    puis la plus récente. Une commande en brouillon ou annulée n'est jamais
    facturée : on ne la propose pas.
    """
    from app.crud import crud_invoice_line

    if invoice is None or not invoice.supplier_id:
        return None

    candidates = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.supplier_id == invoice.supplier_id,
            PurchaseOrder.status.notin_((order_service.DRAFT, order_service.CANCELLED)),
        )
        .order_by(PurchaseOrder.ordered_at.desc().nullslast())
        .all()
    )
    if not candidates:
        return None

    invoice_products = {
        str(l.product_id)
        for l in crud_invoice_line.list_lines(db, str(invoice.id))
        if l.product_id
    }
    if not invoice_products:
        return candidates[0]  # même fournisseur, commande la plus récente

    best, best_overlap = None, 0
    for order in candidates:
        pids = {
            str(l.product_id)
            for l in db.query(PurchaseOrderLine)
            .filter(
                PurchaseOrderLine.tenant_id == tenant_id,
                PurchaseOrderLine.order_id == order.id,
            )
            .all()
            if l.product_id
        }
        overlap = len(pids & invoice_products)
        if overlap > best_overlap:
            best, best_overlap = order, overlap
    return best if best_overlap > 0 else None


def _order_lines(db: Session, tenant_id: str, order_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "product_id": str(l.product_id) if l.product_id else None,
            "description": l.description,
            "qty_ordered": _f(l.qty_ordered),
            "unit_price": _f(l.unit_price),
            "vat_rate": _f(l.vat_rate),
            "discount_pct": _f(l.discount_pct),
            "line_total": _f(l.line_total),
        }
        for l in db.query(PurchaseOrderLine)
        .filter(
            PurchaseOrderLine.tenant_id == tenant_id,
            PurchaseOrderLine.order_id == order_id,
        )
        .all()
    ]


def _received_by_product(db: Session, tenant_id: str, order_id: str) -> Dict[str, float]:
    """Quantité **acceptée** par produit, toutes réceptions de la commande.

    Passe par le service Réception, qui seul sait que « reçu » veut dire accepté :
    une somme SQL brute compterait aussi le refusé et le détruit."""
    from app.models.models import PurchaseOrderLine

    by_line = reception_service.received_by_order_line(db, tenant_id, order_id)
    if not by_line:
        return {}
    line_to_product = {
        str(l.id): str(l.product_id)
        for l in db.query(PurchaseOrderLine).filter(
            PurchaseOrderLine.tenant_id == tenant_id,
            PurchaseOrderLine.order_id == order_id,
        )
        if l.product_id
    }
    out: Dict[str, float] = {}
    for line_id, qty in by_line.items():
        pid = line_to_product.get(line_id)
        if pid:
            out[pid] = out.get(pid, 0.0) + qty
    return out


def _invoice_lines(db: Session, tenant_id: str, invoice_id: str) -> List[Dict[str, Any]]:
    from app.crud import crud_invoice_line

    return [
        {
            "product_id": str(l.product_id) if l.product_id else None,
            "description": l.description,
            "qty": _f(l.qty),
            "unit_price": _f(l.unit_price),
            "vat_rate": _f(l.vat_rate),
            "line_total": _f(l.line_total),
        }
        for l in crud_invoice_line.list_lines(db, invoice_id)
    ]


def control_for_invoice(db: Session, tenant_id: str, invoice: Invoice) -> Dict[str, Any]:
    """Le contrôle complet d'une facture, rattachée à sa commande.

    Rend ``linked: false`` plutôt que d'inventer un rapprochement douteux : mieux
    vaut ne rien affirmer que confronter deux documents étrangers.
    """
    order = None
    if getattr(invoice, "order_id", None):
        order = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.id == invoice.order_id,
            )
            .first()
        )
    if order is None:
        order = find_matching_order(db, tenant_id, invoice)
    if order is None:
        return {"linked": False, "invoice_id": str(invoice.id)}

    names = dict(
        db.query(Product.id, Product.name).filter(Product.tenant_id == tenant_id).all()
    )
    report = compare_control(
        _order_lines(db, tenant_id, str(order.id)),
        _received_by_product(db, tenant_id, str(order.id)),
        _invoice_lines(db, tenant_id, str(invoice.id)),
        {str(k): v for k, v in names.items()},
    )
    report.update(
        {
            "linked": True,
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "order_id": str(order.id),
            "order_reference": order.reference,
            "order_status": order.status,
        }
    )
    return report
