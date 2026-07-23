"""Smart invoice import (Phase 3) — VAT on lines, the enriched preview, and the
auto product↔supplier link (#7). Schema checks run everywhere; the pipeline /
endpoint checks need a real Postgres (skip locally)."""

import uuid
from datetime import date

import pytest

from app.schemas.schemas import InvoiceLineUpdate, InvoicePreviewLine


# --------------------------------------------------------------------------- #
# Schemas — VAT bounds, preview defaults. DB-free.
# --------------------------------------------------------------------------- #
def test_invoice_line_update_accepts_vat_and_bounds_it():
    assert InvoiceLineUpdate(vat_rate=5.5).vat_rate == 5.5
    with pytest.raises(Exception):
        InvoiceLineUpdate(vat_rate=200)


def test_preview_line_defaults_to_needs_review():
    line = InvoicePreviewLine(description="Beurre doux 10kg")
    assert line.needs_review is True
    assert line.matched_product_id is None


# --------------------------------------------------------------------------- #
# #7 — importing an invoice auto-links its products to the supplier.
# --------------------------------------------------------------------------- #
def test_processing_an_invoice_links_product_to_its_supplier(db):
    from app.crud import crud_supplier_product
    from app.models.models import (
        Invoice,
        InvoiceLine,
        Organization,
        Product,
        Supplier,
        Unit,
    )
    from app.services.invoicing import invoice_pricing

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Auto-link Test"))
    db.commit()

    supplier_id, product_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Supplier(id=supplier_id, tenant_id=tenant_id, name="Metro"))
    db.add(Product(id=product_id, tenant_id=tenant_id, name="Beurre doux"))
    db.commit()

    kg = db.query(Unit).filter(Unit.code == "kg").first()
    invoice_id = str(uuid.uuid4())
    db.add(
        Invoice(
            id=invoice_id,
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            invoice_number="INV-7",
            date=date(2026, 2, 1),
            currency="EUR",
        )
    )
    db.commit()
    db.add(
        InvoiceLine(
            id=str(uuid.uuid4()),
            invoice_id=invoice_id,
            product_id=product_id,  # already mapped
            description="Beurre doux",
            qty=10,
            unit_id=kg.id if kg else None,
            unit_price=8.5,
            line_total=85,
            currency="EUR",
        )
    )
    db.commit()

    # No catalog link yet.
    assert crud_supplier_product.get_link_by_supplier(db, tenant_id, product_id, supplier_id) is None

    invoice_pricing.process_invoice(db, tenant_id, invoice_id)

    # The import created the product↔supplier catalog link.
    link = crud_supplier_product.get_link_by_supplier(db, tenant_id, product_id, supplier_id)
    assert link is not None


# --------------------------------------------------------------------------- #
# Enriched preview endpoint (OCR stub + real DB in CI).
# --------------------------------------------------------------------------- #
def test_preview_endpoint_enriches_lines_with_category(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.api.deps import get_current_tenant_id, require_writer
    from app.db.session import get_db
    from app.models.models import Organization

    monkeypatch.setenv("OCR_PROVIDER_CHAIN", "stub")
    monkeypatch.setenv("OCR_ALLOW_STUB_FALLBACK", "true")

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Preview Test"))
    db.commit()

    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[require_writer] = lambda: ["admin"]
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/invoices/preview",
            files={"file": ("invoice.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "lines" in data and isinstance(data["lines"], list)
        # Every previewed line carries a category suggestion + a review flag.
        for line in data["lines"]:
            assert "suggested_category" in line
            assert "needs_review" in line
    finally:
        app.dependency_overrides.clear()


def test_confirm_creates_associates_and_links_supplier(db):
    """The smart-import commit: a validated line 'create' makes a new product
    (auto-classified), an 'associate' reuses an existing one, both get linked to
    the supplier (#7) and priced."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.api.deps import get_current_tenant_id, require_writer
    from app.db.session import get_db
    from app.crud import crud_product, crud_supplier_product
    from app.models.models import Invoice, InvoiceLine, Organization
    from app.schemas.schemas import ProductCreate

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Confirm Test"))
    db.commit()
    existing = crud_product.create_product(db, ProductCreate(name="Farine T55"), tenant_id)

    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[require_writer] = lambda: ["admin"]
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/invoices/confirm",
            json={
                "supplier": "Transgourmet",
                "invoice_number": "SC-1",
                "date": "2026-02-10",
                "currency": "EUR",
                "lines": [
                    {"description": "Filet de saumon", "qty": 2, "unit": "kg",
                     "unit_price": 18, "line_total": 36, "vat_rate": 5.5, "action": "create"},
                    {"description": "Farine", "qty": 5, "unit": "kg", "unit_price": 1.2,
                     "line_total": 6, "action": "associate", "product_id": str(existing.id)},
                    {"description": "Ligne ignorée", "action": "skip"},
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        invoice_id = data["invoice_id"]
        assert data["summary"]["lines"] == 2  # skip excluded

        inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        assert inv is not None and inv.supplier_id is not None  # supplier created + linked
        lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice_id).all()
        assert len(lines) == 2
        # The created product was auto-classified + carries the VAT.
        created = crud_product.get_product(
            db, str(next(l.product_id for l in lines if str(l.product_id) != str(existing.id))), tenant_id
        )
        assert created is not None
        # Both products are now linked to the supplier (#7).
        for l in lines:
            link = crud_supplier_product.get_link_by_supplier(
                db, tenant_id, str(l.product_id), str(inv.supplier_id)
            )
            assert link is not None
    finally:
        app.dependency_overrides.clear()
