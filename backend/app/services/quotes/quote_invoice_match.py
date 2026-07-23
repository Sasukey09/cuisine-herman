"""Rapprochement devis ↔ facture : ce qui était accepté vs ce qui est facturé.

C'est le contrôle de gestion du module Achats (§9). Une fois la commande passée
sur la base d'un devis, la facture du fournisseur doit être confrontée à ce
devis : prix, quantités, TVA. Un fournisseur qui facture 3 % au-dessus du devis
accepté ne se voit pas à l'œil nu sur une facture de 40 lignes.

:func:`compare_quote_invoice` est **pure** (deux listes -> un rapport d'écarts),
donc testée sans BDD. :func:`find_matching_quote` fait le rapprochement en base.

Convention de signe : un écart **positif** est défavorable (on paie plus que
prévu), un écart négatif est favorable.
"""
from typing import Any, Dict, List, Optional

# En dessous, un écart de prix vient d'un arrondi, pas d'une hausse.
_PRICE_EPSILON = 0.005
_QTY_EPSILON = 0.001


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").lower().split())


def _line_total(qty: Optional[float], unit_price: Optional[float],
                explicit_total: Optional[float] = None) -> Optional[float]:
    if explicit_total is not None:
        return explicit_total
    if qty is not None and unit_price is not None:
        return round(qty * unit_price, 4)
    return None


def compare_quote_invoice(
    quote_lines: List[Dict[str, Any]],
    invoice_lines: List[Dict[str, Any]],
    product_names: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Confronte les lignes d'un devis à celles d'une facture.

    Rapprochement par ``product_id`` en priorité (fiable), sinon par description
    normalisée — un fournisseur qui réécrit son libellé ne doit pas produire un
    faux « facturé en plus ».

    Statuts par ligne :
      * ``ok``          — conforme au devis
      * ``price_up``    — facturé plus cher que devisé
      * ``price_down``  — facturé moins cher
      * ``qty_diff``    — quantité différente (prix conforme)
      * ``missing``     — devisé mais absent de la facture (non livré ?)
      * ``extra``       — facturé sans figurer au devis (le plus suspect)
    """
    product_names = product_names or {}

    def key_of(l: Dict[str, Any]):
        pid = l.get("product_id")
        return ("p", str(pid)) if pid else ("d", _norm(l.get("description")))

    quoted: Dict[Any, Dict[str, Any]] = {}
    for l in quote_lines:
        quoted.setdefault(key_of(l), l)
    billed: Dict[Any, Dict[str, Any]] = {}
    for l in invoice_lines:
        billed.setdefault(key_of(l), l)

    rows: List[Dict[str, Any]] = []
    quoted_total = 0.0
    billed_total = 0.0

    for key in list(quoted.keys()) + [k for k in billed if k not in quoted]:
        q = quoted.get(key)
        b = billed.get(key)
        pid = (q or b or {}).get("product_id")
        name = (
            product_names.get(str(pid))
            if pid
            else ((q or b or {}).get("description"))
        ) or (q or b or {}).get("description")

        q_qty = _f(q.get("qty")) if q else None
        q_price = _f(q.get("unit_price")) if q else None
        q_vat = _f(q.get("vat_rate")) if q else None
        q_total = _line_total(q_qty, q_price, _f(q.get("line_total")) if q else None)

        b_qty = _f(b.get("qty")) if b else None
        b_price = _f(b.get("unit_price")) if b else None
        b_vat = _f(b.get("vat_rate")) if b else None
        b_total = _line_total(b_qty, b_price, _f(b.get("line_total")) if b else None)

        if q_total:
            quoted_total += q_total
        if b_total:
            billed_total += b_total

        if q is None:
            status = "extra"
        elif b is None:
            status = "missing"
        else:
            price_gap = (
                (b_price - q_price)
                if (b_price is not None and q_price is not None)
                else None
            )
            qty_gap = (
                (b_qty - q_qty) if (b_qty is not None and q_qty is not None) else None
            )
            if price_gap is not None and price_gap > _PRICE_EPSILON:
                status = "price_up"
            elif price_gap is not None and price_gap < -_PRICE_EPSILON:
                status = "price_down"
            elif qty_gap is not None and abs(qty_gap) > _QTY_EPSILON:
                status = "qty_diff"
            else:
                status = "ok"

        price_delta = (
            round(b_price - q_price, 4)
            if (b_price is not None and q_price is not None)
            else None
        )
        rows.append(
            {
                "product_id": str(pid) if pid else None,
                "product_name": name,
                "quoted": {"qty": q_qty, "unit_price": q_price, "vat_rate": q_vat, "total": q_total},
                "billed": {"qty": b_qty, "unit_price": b_price, "vat_rate": b_vat, "total": b_total},
                "qty_delta": (
                    round(b_qty - q_qty, 4)
                    if (b_qty is not None and q_qty is not None)
                    else None
                ),
                "price_delta": price_delta,
                "price_delta_pct": (
                    round(price_delta / q_price * 100.0, 2)
                    if (price_delta is not None and q_price)
                    else None
                ),
                "total_delta": (
                    round(b_total - q_total, 2)
                    if (b_total is not None and q_total is not None)
                    else None
                ),
                # Une TVA différente change le montant dû : à signaler même si le
                # prix HT est conforme.
                "vat_mismatch": (
                    q_vat is not None and b_vat is not None and abs(b_vat - q_vat) > 0.01
                ),
                "status": status,
            }
        )

    rows.sort(key=lambda r: (r["status"] == "ok", (r["product_name"] or "").lower()))
    issues = [r for r in rows if r["status"] != "ok" or r["vat_mismatch"]]
    total_delta = round(billed_total - quoted_total, 2)

    return {
        "lines": rows,
        "quoted_total": round(quoted_total, 2),
        "billed_total": round(billed_total, 2),
        "total_delta": total_delta,
        "total_delta_pct": (
            round(total_delta / quoted_total * 100.0, 2) if quoted_total else None
        ),
        "issue_count": len(issues),
        "is_conform": len(issues) == 0,
    }


# --------------------------------------------------------------------------- #
# Rapprochement en base
# --------------------------------------------------------------------------- #
def find_matching_quote(db, tenant_id: str, invoice) -> Optional[Any]:
    """Le devis commandé qui correspond le mieux à cette facture.

    Critères, du plus fiable au moins fiable : même fournisseur (obligatoire),
    puis le plus grand recouvrement de produits, puis la commande la plus
    récente. On ne devine pas au-delà : sans fournisseur ni produit commun, on
    préfère ne rien lier plutôt que rapprocher deux documents étrangers.
    """
    from app.models.models import Quote, QuoteLine
    from app.crud import crud_invoice_line

    if invoice is None or not invoice.supplier_id:
        return None

    candidates = (
        db.query(Quote)
        .filter(
            Quote.tenant_id == tenant_id,
            Quote.supplier_id == invoice.supplier_id,
            Quote.status == "ordered",
        )
        .order_by(Quote.ordered_at.desc().nullslast())
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
    for q in candidates:
        pids = {
            str(l.product_id)
            for l in db.query(QuoteLine)
            .filter(QuoteLine.tenant_id == tenant_id, QuoteLine.quote_id == q.id)
            .all()
            if l.product_id
        }
        overlap = len(pids & invoice_products)
        if overlap > best_overlap:
            best, best_overlap = q, overlap
    return best if best_overlap > 0 else None


def variance_for_invoice(db, tenant_id: str, invoice, quote) -> Dict[str, Any]:
    """Rapport d'écarts entre un devis commandé et la facture reçue."""
    from app.models.models import Product, QuoteLine
    from app.crud import crud_invoice_line

    q_lines = [
        {
            "product_id": l.product_id,
            "description": l.description,
            "qty": l.qty,
            "unit_price": l.unit_price,
            "vat_rate": l.vat_rate,
            "line_total": l.line_total,
        }
        for l in db.query(QuoteLine)
        .filter(QuoteLine.tenant_id == tenant_id, QuoteLine.quote_id == quote.id)
        .all()
    ]
    i_lines = [
        {
            "product_id": l.product_id,
            "description": l.description,
            "qty": l.qty,
            "unit_price": l.unit_price,
            "vat_rate": l.vat_rate,
            "line_total": l.line_total,
        }
        for l in crud_invoice_line.list_lines(db, str(invoice.id))
    ]
    pids = [str(l["product_id"]) for l in q_lines + i_lines if l["product_id"]]
    names = {
        str(p.id): p.name
        for p in db.query(Product.id, Product.name)
        .filter(Product.tenant_id == tenant_id, Product.id.in_(pids or ["-"]))
        .all()
    } if pids else {}

    report = compare_quote_invoice(q_lines, i_lines, names)
    report["quote_id"] = str(quote.id)
    report["quote_reference"] = quote.reference
    report["invoice_id"] = str(invoice.id)
    report["invoice_number"] = invoice.invoice_number
    return report
