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

from app.models.models import (
    Invoice,
    Organization,
    Product,
    ProductPrice,
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
    ReceiptLine,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
    Supplier,
    User,
)
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
    recipe_id = str(uuid.uuid4())
    db.add(Recipe(id=recipe_id, tenant_id=tenant_id, name="Risotto", yield_qty=4))
    db.commit()

    # What makes this restaurant real — and what used to make it un-erasable.
    # Six foreign keys in the schema have no ON DELETE (they are what makes
    # "you cannot delete a product a recipe uses" true), and each one blocked the
    # organization's own cascade. A seed without recipes, ingredients or purchases
    # is exactly the seed that fails to notice.
    version_id = str(uuid.uuid4())
    db.add(RecipeVersion(id=version_id, recipe_id=recipe_id, version_number=1))
    db.commit()
    db.add(
        RecipeIngredient(
            id=str(uuid.uuid4()),
            recipe_version_id=version_id,     # → recipe_versions
            product_id=product_id,            # → products, NO cascade
            ingredient_name="Beurre doux AOP",
            qty=Decimal("0.2"),
        )
    )
    # Le domaine Achats : une commande passée, reçue. Un restaurant réel en a ;
    # une coquille vide, non — et c'est justement sur une coquille vide que
    # l'effacement réussissait avant qu'un test contre une vraie base ne le dise.
    order_id = str(uuid.uuid4())
    order_line_id = str(uuid.uuid4())
    receipt_id = str(uuid.uuid4())
    db.add(
        PurchaseOrder(
            id=order_id,
            tenant_id=tenant_id,
            reference="CMD-2026-0001",
            supplier_id=supplier_id,          # → suppliers
            status="received",
        )
    )
    db.add(
        PurchaseOrderLine(
            id=order_line_id,
            tenant_id=tenant_id,
            order_id=order_id,
            product_id=product_id,            # → products
            description="Beurre doux AOP",
            qty_ordered=Decimal("10"),
            unit_price=Decimal("8.5"),
        )
    )
    db.add(
        Receipt(
            id=receipt_id,
            tenant_id=tenant_id,
            reference="REC-2026-0001",
            order_id=order_id,
            supplier_id=supplier_id,
        )
    )
    db.add(
        ReceiptLine(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            receipt_id=receipt_id,
            order_line_id=order_line_id,
            product_id=product_id,
            qty_received=Decimal("10"),
        )
    )
    rgpd.record(db, tenant_id, None, rgpd.ACTION_LOGIN, {"ip": "1.2.3.4"})
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

    # The 500 was a RecursionError: `getattr(row, "metadata")` handed back
    # SQLAlchemy's MetaData — the whole schema — instead of the cell.
    for table in ("products", "invoices", "suppliers"):
        for row in payload[table]:
            assert "metadata" in row, "the JSONB column must be exported, under its real name"
            assert not hasattr(row["metadata"], "tables"), "the ORM schema leaked into the export"


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


def test_erasure_really_erases_a_restaurant_that_has_actually_been_used(db, seeded_tenant):
    """Art. 17, on a restaurant with recipes, ingredients, purchases and a login
    history — i.e. on a restaurant, rather than on an empty shell.

    Erasure used to succeed only for a tenant that had none of those. That is not
    a customer; it is a test fixture.
    """
    tenant_id = seeded_tenant
    assert db.query(Product).filter(Product.tenant_id == tenant_id).count() == 1
    assert db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == tenant_id).count() == 1

    assert rgpd.delete_organization(db, tenant_id) is True

    assert db.query(Organization).filter(Organization.id == tenant_id).first() is None
    for model, what in (
        (Product, "products"),
        (Supplier, "suppliers"),
        (Invoice, "invoices"),
        (Recipe, "recipes"),
        (PurchaseOrder, "purchase orders"),
        (PurchaseOrderLine, "order lines"),
        (Receipt, "goods receipts"),
        (ReceiptLine, "receipt lines"),
        (User, "staff accounts"),
    ):
        assert db.query(model).filter(model.tenant_id == tenant_id).count() == 0, (
            f"the {what} of an erased restaurant must not survive it"
        )
    assert rgpd.list_audit(db, tenant_id) == [], "nor its connection log"


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
