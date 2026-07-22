"""Quote comparator (#1) — REST surface.

A quote is a named basket of products; ``GET /quotes/{id}/comparison`` prices it
across suppliers and ``POST /quotes/{id}/order`` converts the retained supplier's
offer into an order. See ``app.services.quotes.quote_service``.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.schemas.schemas import (
    QuoteCreate,
    QuoteUpdate,
    QuoteRead,
    QuoteLineCreate,
    QuoteLineUpdate,
    QuoteOrderRequest,
)
from app.crud import crud_quote
from app.services.quotes import quote_service

router = APIRouter()


def _detail(db: Session, tenant_id: str, quote) -> dict:
    supplier_names = crud_quote._supplier_names(db, tenant_id)
    line_counts = crud_quote._line_counts(db, tenant_id)
    data = crud_quote.to_read(quote, supplier_names, line_counts)
    data["lines"] = crud_quote.lines_read(db, tenant_id, str(quote.id))
    return data


@router.get("/", response_model=List[QuoteRead])
def api_list_quotes(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return crud_quote.list_read(db, tenant_id, status)


@router.post("/", status_code=201)
def api_create_quote(
    payload: QuoteCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    quote = crud_quote.create_quote(db, tenant_id, payload)
    return _detail(db, tenant_id, quote)


@router.get("/{quote_id}")
def api_get_quote(
    quote_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return _detail(db, tenant_id, quote)


@router.patch("/{quote_id}")
def api_update_quote(
    quote_id: str,
    payload: QuoteUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    crud_quote.update_quote(db, quote, payload)
    return _detail(db, tenant_id, quote)


@router.delete("/{quote_id}", status_code=204)
def api_delete_quote(
    quote_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    crud_quote.delete_quote(db, quote)
    return None


@router.get("/{quote_id}/comparison")
def api_quote_comparison(
    quote_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Price the basket across suppliers: per-supplier total, coverage, lead time,
    cheapest + best-coverage flags."""
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    lines = crud_quote.get_lines(db, tenant_id, quote_id)
    return quote_service.comparison(db, tenant_id, quote, lines)


@router.post("/{quote_id}/order")
def api_order_quote(
    quote_id: str,
    payload: QuoteOrderRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Convert the quote into an order for the chosen supplier, snapshotting its
    prices onto the lines and the total onto the quote."""
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    lines = crud_quote.get_lines(db, tenant_id, quote_id)
    totals = quote_service.supplier_totals(db, tenant_id, lines, payload.supplier_id)
    cost_by_product = {
        l["product_id"]: l["unit_cost"]
        for l in totals["lines"]
        if l.get("product_id")
    }
    crud_quote.mark_ordered(
        db, quote, payload.supplier_id, totals["total"], cost_by_product
    )
    return _detail(db, tenant_id, quote)


# --- lines ---------------------------------------------------------------- #


@router.post("/{quote_id}/lines", status_code=201)
def api_add_line(
    quote_id: str,
    payload: QuoteLineCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    crud_quote.add_line(db, tenant_id, quote_id, payload)
    return _detail(db, tenant_id, quote)


@router.patch("/{quote_id}/lines/{line_id}")
def api_update_line(
    quote_id: str,
    line_id: str,
    payload: QuoteLineUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    line = crud_quote.get_line(db, tenant_id, quote_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    crud_quote.update_line(db, line, payload)
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    return _detail(db, tenant_id, quote)


@router.delete("/{quote_id}/lines/{line_id}")
def api_delete_line(
    quote_id: str,
    line_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    line = crud_quote.get_line(db, tenant_id, quote_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    crud_quote.delete_line(db, line)
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    return _detail(db, tenant_id, quote)
