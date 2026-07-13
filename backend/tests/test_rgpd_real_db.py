"""The RGPD export, against a real PostgreSQL.

This is the test that should have existed before the endpoint shipped. It did
not, the suite was green, and production answered 500 on the very first call:
the rows come straight from the ORM (`Decimal` prices, `datetime` stamps, a
column literally named `metadata` but mapped to `meta`), and none of that had
ever been fed through the code because every test mocked the session.

Skips when no DATABASE_URL is set, so a laptop without Postgres stays usable.
"""
import json
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.encoders import jsonable_encoder

from app.models.models import Invoice, Organization, Product, ProductPrice, Recipe, Supplier, User
from app.services.rgpd import service as rgpd


@pytest.fixture
def seeded_tenant(db):
    """A restaurant with exactly the types that broke in production."""
    tenant_id = str(uuid.uuid4())

    # Committed first: no relationship is declared between these models, so
    # SQLAlchemy has no idea invoices depend on organizations and happily inserts
    # them in the wrong order.
    db.add(Organization(id=tenant_id, name="Restaurant de Test"))
    db.commit()

    db.add(
        User(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            email="chef@test.fr",
            password_hash="$2b$12$fakehashfakehashfakehashfakehashfakehashfake",
            name="Chef Test",
        )
    )
    supplier_id = str(uuid.uuid4())
    db.add(Supplier(id=supplier_id, tenant_id=tenant_id, name="Metro"))

    product_id = str(uuid.uuid4())
    db.add(Product(id=product_id, tenant_id=tenant_id, name="Beurre doux AOP"))
    db.commit()  # same reason: prices and invoices point at these

    db.add(
        ProductPrice(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            product_id=product_id,
            supplier_id=supplier_id,
            price=Decimal("8.51"),           # Decimal
            currency="EUR",
            effective_date=date(2026, 7, 13),  # date
        )
    )
    db.add(
        Invoice(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            invoice_number="FAC-2026-001",
            total_amount=Decimal("1284.50"),
            date=date(2026, 7, 12),
        )
    )
    db.add(Recipe(id=str(uuid.uuid4()), tenant_id=tenant_id, name="Risotto", yield_qty=4))
    db.commit()

    yield tenant_id

    # Tearing down through the erasure path: the cleanup and the feature are the
    # same operation, so a broken cascade cannot hide behind a tidy test.
    rgpd.delete_organization(db, tenant_id)


def test_the_export_is_actually_serialisable(db, seeded_tenant):
    """The exact failure that reached production: HTTP 500 on the first call."""
    payload = rgpd.export_organization(db, seeded_tenant)

    encoded = jsonable_encoder(payload)   # this is what FastAPI does
    text = json.dumps(encoded)            # and this is what must not explode

    assert "Beurre doux AOP" in text
    assert "FAC-2026-001" in text
    assert "8.51" in text, "the Decimal price must survive the trip"


def test_the_export_holds_the_restaurants_real_data(db, seeded_tenant):
    payload = rgpd.export_organization(db, seeded_tenant)

    assert payload["organization"]["name"] == "Restaurant de Test"
    assert len(payload["users"]) == 1
    assert len(payload["products"]) == 1
    assert len(payload["suppliers"]) == 1
    assert len(payload["invoices"]) == 1
    assert len(payload["recipes"]) == 1
    assert len(payload["product_prices"]) == 1


def test_the_export_never_carries_a_password_hash(db, seeded_tenant):
    """Portability is the customer's data, not our credential store."""
    payload = rgpd.export_organization(db, seeded_tenant)
    dumped = json.dumps(jsonable_encoder(payload)).lower()

    assert "chef@test.fr" in dumped
    assert "password" not in dumped
    assert "$2b$12$" not in dumped


def test_erasure_really_erases(db):
    """Art. 17 — and the cascade must be real, not a hope."""
    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="À Supprimer"))
    db.commit()
    db.add(Product(id=str(uuid.uuid4()), tenant_id=tenant_id, name="Produit condamné"))
    # The audit rows are what used to BLOCK the deletion: log in, and you can
    # never be forgotten.
    rgpd.record(db, tenant_id, None, rgpd.ACTION_LOGIN, {"ip": "1.2.3.4"})
    db.commit()

    assert db.query(Product).filter(Product.tenant_id == tenant_id).count() == 1

    assert rgpd.delete_organization(db, tenant_id) is True

    assert db.query(Organization).filter(Organization.id == tenant_id).first() is None
    assert db.query(Product).filter(Product.tenant_id == tenant_id).count() == 0, (
        "the products of a deleted restaurant must not survive it"
    )


def test_the_audit_register_is_written_and_readable(db):
    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Audit"))
    db.commit()
    try:
        rgpd.record(db, tenant_id, None, rgpd.ACTION_LOGIN, {"ip": "1.2.3.4"})
        rgpd.record(db, tenant_id, None, rgpd.ACTION_DATA_EXPORTED, {"tables": 15})

        entries = rgpd.list_audit(db, tenant_id)
        actions = [e.action for e in entries]

        assert rgpd.ACTION_LOGIN in actions
        assert rgpd.ACTION_DATA_EXPORTED in actions
        # Most recent first: an operator reading the register wants today, not 2024.
        assert entries[0].action == rgpd.ACTION_DATA_EXPORTED
    finally:
        rgpd.delete_organization(db, tenant_id)
