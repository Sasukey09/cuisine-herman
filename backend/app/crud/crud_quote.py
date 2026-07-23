"""CRUD for quotes (comparateur de devis) and their lines.

A quote is a named basket; converting it to an order (``mark_ordered``) stamps
the retained supplier + total and snapshots each line's unit price so the order
stays stable as future prices move. The comparison itself lives in
``app.services.quotes.quote_service``.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Quote, QuoteLine, Supplier, Product
from app.schemas.schemas import (
    QuoteCreate,
    QuoteUpdate,
    QuoteLineCreate,
    QuoteLineUpdate,
)


def _next_reference(db: Session, tenant_id: str) -> str:
    """Per-tenant, per-year sequential reference, e.g. ``DEV-2026-0007``."""
    prefix = f"DEV-{datetime.now().year}-"
    count = (
        db.query(func.count(Quote.id))
        .filter(Quote.tenant_id == tenant_id, Quote.reference.like(prefix + "%"))
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:04d}"


def _next_order_reference(db: Session, tenant_id: str) -> str:
    """Référence de COMMANDE, ex. ``CMD-2026-0003``. Une commande a sa propre
    numérotation : le devis est une offre, la commande un engagement."""
    prefix = f"CMD-{datetime.now().year}-"
    count = (
        db.query(func.count(Quote.id))
        .filter(Quote.tenant_id == tenant_id, Quote.order_reference.like(prefix + "%"))
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:04d}"


def list_quotes(db: Session, tenant_id: str, status: Optional[str] = None) -> List[Quote]:
    q = db.query(Quote).filter(Quote.tenant_id == tenant_id)
    if status:
        q = q.filter(Quote.status == status)
    return q.order_by(Quote.created_at.desc()).all()


def get_quote(db: Session, tenant_id: str, quote_id: str) -> Optional[Quote]:
    return (
        db.query(Quote)
        .filter(Quote.id == quote_id, Quote.tenant_id == tenant_id)
        .first()
    )


def get_lines(db: Session, tenant_id: str, quote_id: str) -> List[QuoteLine]:
    return (
        db.query(QuoteLine)
        .filter(QuoteLine.tenant_id == tenant_id, QuoteLine.quote_id == quote_id)
        .order_by(QuoteLine.created_at.asc())
        .all()
    )


def create_quote(db: Session, tenant_id: str, payload: QuoteCreate) -> Quote:
    quote = Quote(
        tenant_id=tenant_id,
        reference=_next_reference(db, tenant_id),
        title=payload.title,
        notes=payload.notes,
        status="draft",
    )
    db.add(quote)
    db.flush()
    for l in payload.lines:
        db.add(
            QuoteLine(
                tenant_id=tenant_id,
                quote_id=quote.id,
                product_id=l.product_id,
                description=l.description,
                qty=l.qty,
                unit_id=l.unit_id,
            )
        )
    db.commit()
    db.refresh(quote)
    return quote


def create_imported_quote(
    db: Session, tenant_id: str, payload, supplier_id: Optional[str]
) -> Quote:
    """Crée le devis issu d'un import OCR validé (en-tête seulement ; les lignes
    sont ajoutées ensuite par :func:`add_import_line`). Notre `reference` reste
    générée par nous ; `quote_number` porte le numéro du fournisseur."""
    quote = Quote(
        tenant_id=tenant_id,
        reference=_next_reference(db, tenant_id),
        title=payload.title or (f"Devis {payload.quote_number}" if payload.quote_number else None),
        status="draft",
        supplier_id=supplier_id,
        quote_number=payload.quote_number,
        date=payload.date,
        valid_until=payload.valid_until,
        currency=payload.currency or "EUR",
        total_amount=payload.total_amount,
        discount_total=payload.discount_total,
        delivery_fee=getattr(payload, "delivery_fee", None),
        conditions=payload.conditions,
        parsed=True,
        ocr_status="confirmed",
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def add_import_line(
    db: Session,
    tenant_id: str,
    quote_id: str,
    line,
    unit_id: Optional[int],
    product_id: Optional[str],
    supplier_id: Optional[str],
) -> QuoteLine:
    """Une ligne de devis importée. Flush (pas commit) : l'appelant confirme
    l'ensemble en une transaction."""
    obj = QuoteLine(
        tenant_id=tenant_id,
        quote_id=quote_id,
        product_id=product_id,
        description=line.description,
        qty=line.qty,
        unit_id=unit_id,
        unit_price=line.unit_price,
        line_total=line.line_total,
        vat_rate=line.vat_rate,
        discount_pct=line.discount_pct,
        pack_size=line.pack_size,
        brand=getattr(line, "brand", None),
        min_qty=getattr(line, "min_qty", None),
        supplier_id=supplier_id,
    )
    db.add(obj)
    db.flush()
    return obj


def update_quote(db: Session, quote: Quote, payload: QuoteUpdate) -> Quote:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(quote, field, value)
    db.commit()
    db.refresh(quote)
    return quote


def delete_quote(db: Session, quote: Quote) -> None:
    db.delete(quote)
    db.commit()


def add_line(
    db: Session, tenant_id: str, quote_id: str, payload: QuoteLineCreate
) -> QuoteLine:
    line = QuoteLine(
        tenant_id=tenant_id,
        quote_id=quote_id,
        product_id=payload.product_id,
        description=payload.description,
        qty=payload.qty,
        unit_id=payload.unit_id,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def get_line(
    db: Session, tenant_id: str, quote_id: str, line_id: str
) -> Optional[QuoteLine]:
    return (
        db.query(QuoteLine)
        .filter(
            QuoteLine.id == line_id,
            QuoteLine.quote_id == quote_id,
            QuoteLine.tenant_id == tenant_id,
        )
        .first()
    )


def update_line(db: Session, line: QuoteLine, payload: QuoteLineUpdate) -> QuoteLine:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    db.commit()
    db.refresh(line)
    return line


def delete_line(db: Session, line: QuoteLine) -> None:
    db.delete(line)
    db.commit()


def mark_ordered(
    db: Session,
    quote: Quote,
    supplier_id: str,
    total: Optional[float],
    cost_by_product: Dict[str, Optional[float]],
) -> Quote:
    """Convert to an order: stamp the retained supplier + total on the quote and
    snapshot each line's unit price (from ``cost_by_product``) and supplier.

    Un prix DÉJÀ porté par la ligne est conservé. Deux origines coexistent :

    - le panier monté à la main n'a pas de prix propre, il est chiffré depuis
      l'historique d'achat — c'est ``cost_by_product`` qui fait foi ;
    - la ligne issue d'un devis IMPORTÉ porte le prix offert par le
      fournisseur, lu sur son document. L'écraser avec notre historique
      détruirait l'offre (§8 : la commande garde les prix du devis) et rendrait
      circulaire le contrôle devis/facture — on comparerait la facture à un
      prix que cette facture a elle-même alimenté.

    Le prix offert n'est gardé que si on commande bien AUPRÈS du fournisseur qui
    l'a proposé : retenir un autre fournisseur rend son offre caduque."""
    quote.status = "ordered"
    quote.supplier_id = supplier_id
    quote.total_amount = total
    quote.ordered_at = datetime.now()
    if not quote.order_reference:
        quote.order_reference = _next_order_reference(db, quote.tenant_id)
    for line in get_lines(db, quote.tenant_id, quote.id):
        if line.product_id is None:
            continue
        offered_by_retained_supplier = line.unit_price is not None and (
            line.supplier_id is None or str(line.supplier_id) == str(supplier_id)
        )
        if offered_by_retained_supplier:
            line.supplier_id = supplier_id
            continue
        price = cost_by_product.get(str(line.product_id))
        if price is not None:
            line.unit_price = price
            line.supplier_id = supplier_id
    db.commit()
    db.refresh(quote)
    return quote


# --------------------------------------------------------------------------- #
# serialization helpers (attach supplier_name + line_count for QuoteRead)
# --------------------------------------------------------------------------- #
def _supplier_names(db: Session, tenant_id: str) -> Dict[str, str]:
    return {
        str(s.id): s.name
        for s in db.query(Supplier.id, Supplier.name)
        .filter(Supplier.tenant_id == tenant_id)
        .all()
    }


def _line_counts(db: Session, tenant_id: str) -> Dict[str, int]:
    rows = (
        db.query(QuoteLine.quote_id, func.count(QuoteLine.id))
        .filter(QuoteLine.tenant_id == tenant_id)
        .group_by(QuoteLine.quote_id)
        .all()
    )
    return {str(qid): int(n) for qid, n in rows}


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def to_read(quote: Quote, supplier_names: Dict[str, str], line_counts: Dict[str, int]) -> Dict[str, Any]:
    return {
        "id": str(quote.id),
        "reference": quote.reference,
        "title": quote.title,
        "status": quote.status,
        "supplier_id": str(quote.supplier_id) if quote.supplier_id else None,
        "supplier_name": supplier_names.get(str(quote.supplier_id)) if quote.supplier_id else None,
        "total_amount": _f(quote.total_amount),
        "notes": quote.notes,
        "line_count": line_counts.get(str(quote.id), 0),
        "ordered_at": quote.ordered_at,
        "order_reference": quote.order_reference,
        "created_at": quote.created_at,
        # Import OCR
        "quote_number": quote.quote_number,
        "date": quote.date,
        "valid_until": quote.valid_until,
        "currency": quote.currency,
        "discount_total": _f(quote.discount_total),
        "delivery_fee": _f(quote.delivery_fee),
        "conditions": quote.conditions,
    }


def list_read(db: Session, tenant_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    supplier_names = _supplier_names(db, tenant_id)
    line_counts = _line_counts(db, tenant_id)
    return [to_read(q, supplier_names, line_counts) for q in list_quotes(db, tenant_id, status)]


def line_to_read(line: QuoteLine, product_names: Dict[str, str]) -> Dict[str, Any]:
    return {
        "id": str(line.id),
        "product_id": str(line.product_id) if line.product_id else None,
        "product_name": product_names.get(str(line.product_id)) if line.product_id else None,
        "description": line.description,
        "qty": _f(line.qty),
        "unit_id": line.unit_id,
        "unit_price": _f(line.unit_price),
        "supplier_id": str(line.supplier_id) if line.supplier_id else None,
        # Import OCR
        "vat_rate": _f(line.vat_rate),
        "line_total": _f(line.line_total),
        "discount_pct": _f(line.discount_pct),
        "pack_size": line.pack_size,
        "brand": line.brand,
        "min_qty": _f(line.min_qty),
    }


def lines_read(db: Session, tenant_id: str, quote_id: str) -> List[Dict[str, Any]]:
    lines = get_lines(db, tenant_id, quote_id)
    pids = [str(l.product_id) for l in lines if l.product_id]
    product_names = {
        str(p.id): p.name
        for p in db.query(Product.id, Product.name)
        .filter(Product.tenant_id == tenant_id, Product.id.in_(pids or ["-"]))
        .all()
    }
    return [line_to_read(l, product_names) for l in lines]
