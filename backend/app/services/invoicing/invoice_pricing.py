"""Invoice -> price history -> recipe recompute pipeline (Sprint 4).

Turns extracted/persisted invoice lines into ``product_prices`` rows and triggers
recomputation of the recipe costs that depend on the affected products.
"""
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.models.models import Invoice, InvoiceLine
from app.crud import crud_invoice_line, crud_price, crud_match
from app.services.matching.product_matcher import match_product
from app.services.costing import cost_engine
from app.core import metrics
from app.core.tenancy import assert_product_in_tenant


def persist_extraction(db: Session, tenant_id: str, invoice_id: str, extraction) -> List[InvoiceLine]:
    """Persist extracted header fields + lines onto an existing invoice."""
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .first()
    )
    if invoice is None:
        raise ValueError("invoice_not_found")

    if extraction.invoice_number:
        invoice.invoice_number = extraction.invoice_number
    if extraction.date:
        invoice.date = extraction.date
    if getattr(extraction, "total_amount", None) is not None:
        invoice.total_amount = extraction.total_amount
    invoice.ocr_status = "parsed"
    invoice.parsed = True

    units_by_code = crud_price.get_units_by_code(db)
    created: List[InvoiceLine] = []
    for raw in extraction.lines:
        unit_id = units_by_code.get((raw.unit or "").strip().lower()) if raw.unit else None
        line = crud_invoice_line.create_invoice_line(
            db,
            invoice_id,
            description=raw.description,
            qty=raw.qty,
            unit_id=unit_id,
            unit_price=raw.unit_price,
            line_total=raw.line_total,
        )
        created.append(line)
    db.commit()
    return created


def _price_and_recompute(
    db: Session, tenant_id: str, line: InvoiceLine, invoice: Invoice
) -> Optional[str]:
    """Create a price row from a matched line and recompute affected recipes.

    Returns the created price id (or None when no price could be derived).
    """
    if not line.product_id or line.unit_price is None:
        return None
    price = crud_price.create_price(
        db,
        tenant_id=tenant_id,
        product_id=str(line.product_id),
        price=float(line.unit_price),
        unit_id=line.unit_id,
        supplier_id=str(invoice.supplier_id) if invoice.supplier_id else None,
        currency=invoice.currency,
        effective_date=invoice.date,
        source_invoice_line_id=str(line.id),
    )
    metrics.PRICE_CHANGES_DETECTED.inc()
    cost_engine.recompute_for_product(db, str(line.product_id), tenant_id)
    # Purchase ledger + price/margin alerts (best-effort; never breaks pricing).
    from app.services.purchasing import purchase_service
    purchase_service.record_purchase(db, tenant_id, line, invoice)
    purchase_service.detect_margin_alerts(db, tenant_id, str(line.product_id))
    return str(price.id)


def process_invoice(
    db: Session, tenant_id: str, invoice_id: str, auto_match: bool = True
) -> Dict[str, Any]:
    """Match every line of an invoice, create prices, and recompute recipes."""
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .first()
    )
    if invoice is None:
        raise ValueError("invoice_not_found")

    lines = crud_invoice_line.list_lines(db, invoice_id)
    matched = 0
    prices_created = 0
    needs_review: List[str] = []

    for line in lines:
        if auto_match and not line.product_id and line.description:
            res = match_product(db, tenant_id, line.description)
            if res["product_id"]:
                line.product_id = res["product_id"]
                line.match_confidence = res["confidence_score"]
                db.add(line)
                db.commit()
                matched += 1
            if res["manual_review"]:
                needs_review.append(str(line.id))

        if _price_and_recompute(db, tenant_id, line, invoice):
            prices_created += 1

    metrics.INVOICES_PROCESSED.inc()
    metrics.INVOICE_LINES_PROCESSED.inc(len(lines))
    metrics.PRODUCTS_MATCHED.inc(matched)
    metrics.PRODUCTS_MANUAL_REVIEW.inc(len(needs_review))

    return {
        "invoice_id": invoice_id,
        "lines": len(lines),
        "matched": matched,
        "prices_created": prices_created,
        "needs_review": needs_review,
    }


def delete_line(db: Session, tenant_id: str, line: InvoiceLine) -> None:
    """Delete a line, drop its derived price(s) and recompute affected recipes."""
    product_id = str(line.product_id) if line.product_id else None
    crud_price.delete_prices_for_line(db, tenant_id, str(line.id))
    db.delete(line)
    db.commit()
    if product_id:
        cost_engine.recompute_for_product(db, product_id, tenant_id)


def delete_invoice(db: Session, tenant_id: str, invoice_id: str) -> bool:
    """Delete an invoice (lines cascade), clean derived prices, recompute recipes."""
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .first()
    )
    if invoice is None:
        return False
    lines = crud_invoice_line.list_lines(db, invoice_id)
    product_ids = {str(l.product_id) for l in lines if l.product_id}
    for line in lines:
        crud_price.delete_prices_for_line(db, tenant_id, str(line.id))
    db.delete(invoice)
    db.commit()
    for pid in product_ids:
        cost_engine.recompute_for_product(db, pid, tenant_id)
    return True


def reprice_line(db: Session, tenant_id: str, line: InvoiceLine) -> Optional[str]:
    """Re-derive the price for an (edited) line: drop the line's previous price
    row(s) then recreate from current values + recompute affected recipes."""
    invoice = db.query(Invoice).filter(Invoice.id == line.invoice_id).first()
    if invoice is None:
        return None
    crud_price.delete_prices_for_line(db, tenant_id, str(line.id))
    return _price_and_recompute(db, tenant_id, line, invoice)


def map_line_product(
    db: Session, tenant_id: str, line: InvoiceLine, product_id: str
) -> Dict[str, Any]:
    """Manually map a line to a product, then create its price + recompute."""
    # The product id comes straight from the request body: refuse one that
    # belongs to another organization.
    assert_product_in_tenant(db, tenant_id, product_id)
    invoice = db.query(Invoice).filter(Invoice.id == line.invoice_id).first()
    line.product_id = product_id
    line.match_confidence = 100.0  # manual mapping is authoritative
    db.add(line)
    db.commit()
    price_id = _price_and_recompute(db, tenant_id, line, invoice)
    return {"line_id": str(line.id), "product_id": product_id, "price_id": price_id}
