"""Entering a price by hand — against a real PostgreSQL.

Until now, a price could only enter the platform through an OCR'd invoice. A chef
who knew perfectly well that butter is 8.50 €/kg at Metro had no way to say so:
every recipe using it stayed uncostable until an invoice happened to arrive and
happened to be read correctly. For a tool whose entire question is "what does
this dish cost me", that is a strange thing to require.

`crud_price.create_price` had existed all along. It was simply never exposed.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.core.tenancy import CrossTenantReferenceError, assert_product_in_tenant
from app.crud import crud_price
from app.models.models import (
    Organization,
    Product,
    ProductPrice,
    Purchase,
    PurchaseHistory,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
    Supplier,
    Unit,
)
from app.services.costing import cost_engine
from app.services.rgpd import service as rgpd


@pytest.fixture
def restaurant(db):
    """A butter with no price, and a recipe that needs one."""
    cost_engine.reset_unit_cache()

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Sans Prix"))
    db.commit()

    supplier_id, product_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Supplier(id=supplier_id, tenant_id=tenant_id, name="Metro"))
    db.add(Product(id=product_id, tenant_id=tenant_id, name="Beurre doux"))
    db.commit()

    kg = db.query(Unit).filter(Unit.code == "kg").first()
    g = db.query(Unit).filter(Unit.code == "g").first()

    recipe_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(
        Recipe(
            id=recipe_id,
            tenant_id=tenant_id,
            name="Sauce beurre blanc",
            yield_qty=4,
            selling_price=Decimal("12.00"),
        )
    )
    db.commit()
    db.add(RecipeVersion(id=version_id, recipe_id=recipe_id, version_number=1))
    db.commit()
    db.add(
        RecipeIngredient(
            id=str(uuid.uuid4()),
            recipe_version_id=version_id,
            product_id=product_id,
            ingredient_name="Beurre doux",
            qty=Decimal("200"),
            unit_id=g.id,
        )
    )
    db.query(Recipe).filter(Recipe.id == recipe_id).update({"current_version_id": version_id})
    db.commit()

    yield {
        "tenant_id": tenant_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "version_id": version_id,
        "kg": kg.id,
    }

    rgpd.delete_organization(db, tenant_id)
    cost_engine.reset_unit_cache()


def test_a_recipe_is_uncostable_until_someone_can_say_what_the_butter_costs(db, restaurant):
    before = cost_engine.compute_recipe_version_cost(
        db, restaurant["tenant_id"], restaurant["version_id"], persist=False
    )
    assert before["has_missing_prices"] is True
    assert before["computed_cost_total"] == 0, "nothing is known, so nothing is counted"


def test_a_hand_typed_price_makes_the_recipe_costable_immediately(db, restaurant):
    crud_price.create_price(
        db,
        tenant_id=restaurant["tenant_id"],
        product_id=restaurant["product_id"],
        price=8.50,                       # per KILO
        unit_id=restaurant["kg"],
        supplier_id=restaurant["supplier_id"],
        currency="EUR",
        effective_date=date(2026, 7, 13),
    )
    recosted = cost_engine.recompute_for_product(
        db, restaurant["product_id"], restaurant["tenant_id"]
    )

    assert restaurant["version_id"] in recosted, (
        "a price nobody acts on is just a number in a table"
    )

    after = cost_engine.compute_recipe_version_cost(
        db, restaurant["tenant_id"], restaurant["version_id"], persist=False
    )
    assert after["has_missing_prices"] is False
    assert after["computed_cost_total"] == pytest.approx(1.70)  # 200 g at 8.50 €/kg


def test_typing_a_price_never_invents_a_purchase(db, restaurant):
    """Nothing was bought. Fabricating a purchase to carry the price would corrupt
    the very history the price alerts are computed from."""
    crud_price.create_price(
        db,
        tenant_id=restaurant["tenant_id"],
        product_id=restaurant["product_id"],
        price=8.50,
        unit_id=restaurant["kg"],
        supplier_id=restaurant["supplier_id"],
    )

    tid = restaurant["tenant_id"]
    assert db.query(ProductPrice).filter(ProductPrice.tenant_id == tid).count() == 1
    assert db.query(Purchase).filter(Purchase.tenant_id == tid).count() == 0
    assert db.query(PurchaseHistory).filter(PurchaseHistory.tenant_id == tid).count() == 0


def test_the_latest_hand_typed_price_wins(db, restaurant):
    for price, when in ((8.50, date(2026, 1, 1)), (9.20, date(2026, 7, 1))):
        crud_price.create_price(
            db,
            tenant_id=restaurant["tenant_id"],
            product_id=restaurant["product_id"],
            price=price,
            unit_id=restaurant["kg"],
            supplier_id=restaurant["supplier_id"],
            effective_date=when,
        )

    latest = crud_price.get_latest_price(db, restaurant["tenant_id"], restaurant["product_id"])
    assert float(latest.price) == pytest.approx(9.20), "butter went up; the cost must follow"

    cost = cost_engine.compute_recipe_version_cost(
        db, restaurant["tenant_id"], restaurant["version_id"], persist=False
    )
    assert cost["computed_cost_total"] == pytest.approx(1.84)  # 0.2 kg × 9.20


def test_you_cannot_price_another_restaurants_product(db, restaurant):
    """The product id comes from the client. Without this check, one restaurant
    could price a competitor's butter — and silently recost their whole menu.

    Both halves are asserted, and the first one is the point. An earlier version
    of this test only checked that the intruder was refused — and it passed while
    the endpoint had its arguments swapped, refusing *everyone*, owner included.
    A guard that says no to everything is not a guard; it is an outage. Testing
    only the unhappy path agrees with that bug instead of catching it.
    """
    # The owner can price their own product.
    assert_product_in_tenant(db, restaurant["tenant_id"], restaurant["product_id"])

    intruder = str(uuid.uuid4())
    db.add(Organization(id=intruder, name="Le voisin"))
    db.commit()
    try:
        with pytest.raises(CrossTenantReferenceError):
            assert_product_in_tenant(db, intruder, restaurant["product_id"])
    finally:
        rgpd.delete_organization(db, intruder)
