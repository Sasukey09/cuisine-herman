"""The cost engine, against a real PostgreSQL.

The cost engine *is* the product: it decides what a dish costs, which decides at
what price it is sold. Every existing test of it mocks the session — so the
prices it has been checked against were Python floats handed to it directly, not
`numeric` columns read back out of Postgres, and its unit table was a dict, not
the seeded `units` rows.

That is the same blind spot that let the RGPD export ship a 500. Here it would
not be an error page: butter is invoiced by the kilo and used by the gram, so a
broken ratio does not crash anything — it silently prices a dish at a thousandth
of its cost, and the restaurant sells at a loss until someone notices.

Skips when no DATABASE_URL is set.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.models import (
    Organization,
    Product,
    ProductPrice,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
    Supplier,
    Unit,
)
from app.services.costing import cost_engine
from app.services.rgpd import service as rgpd


@pytest.fixture
def kitchen(db):
    """A restaurant, a supplier, butter at 8.50 €/kg, and an empty recipe."""
    cost_engine.reset_unit_cache()  # the ratios are process-cached

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Cuisine Réelle"))
    db.commit()

    supplier_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    db.add(Supplier(id=supplier_id, tenant_id=tenant_id, name="Metro"))
    db.add(Product(id=product_id, tenant_id=tenant_id, name="Beurre doux"))
    db.commit()

    kg = db.query(Unit).filter(Unit.code == "kg").first()
    g = db.query(Unit).filter(Unit.code == "g").first()
    assert kg is not None and g is not None, "the units migration must have run"

    db.add(
        ProductPrice(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            product_id=product_id,
            supplier_id=supplier_id,
            price=Decimal("8.50"),   # per KILO
            unit_id=kg.id,
            currency="EUR",
            effective_date=date(2026, 1, 1),
        )
    )

    recipe_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    db.add(Recipe(id=recipe_id, tenant_id=tenant_id, name="Sauce", yield_qty=4))
    db.commit()
    db.add(RecipeVersion(id=version_id, recipe_id=recipe_id, version_number=1))
    db.commit()

    yield {
        "tenant_id": tenant_id,
        "product_id": product_id,
        "recipe_id": recipe_id,
        "version_id": version_id,
        "kg": kg.id,
        "g": g.id,
    }

    rgpd.delete_organization(db, tenant_id)
    cost_engine.reset_unit_cache()


def _use(db, k, qty, unit_id, product_id=None, loss=0, yld=100):
    db.add(
        RecipeIngredient(
            id=str(uuid.uuid4()),
            recipe_version_id=k["version_id"],
            product_id=product_id or k["product_id"],
            ingredient_name="Beurre doux",
            qty=Decimal(str(qty)),
            unit_id=unit_id,
            loss_pct=Decimal(str(loss)),
            yield_pct=Decimal(str(yld)),
        )
    )
    db.commit()


def _cost(db, k, selling_price=None):
    return cost_engine.compute_recipe_version_cost(
        db, k["tenant_id"], k["version_id"], selling_price=selling_price, persist=False
    )


# --------------------------------------------------------------------------- #
# The thousand-fold trap: priced by the kilo, used by the gram.
# --------------------------------------------------------------------------- #
def test_grams_of_a_product_priced_per_kilo(db, kitchen):
    _use(db, kitchen, qty=200, unit_id=kitchen["g"])   # 200 g of butter at 8.50 €/kg

    result = _cost(db, kitchen)

    assert result["computed_cost_total"] == pytest.approx(1.70), (
        "200 g of butter at 8.50 €/kg is 1.70 €. A wrong ratio gives 1700 € or 0.0017 € "
        "— and only one of those is loud enough to be noticed."
    )
    assert result["cost_per_portion"] == pytest.approx(0.425)  # 4 portions
    assert result["has_missing_prices"] is False


def test_the_same_quantity_in_two_units_costs_the_same(db, kitchen):
    """200 g and 0.2 kg are the same butter. The bill must not know the difference."""
    _use(db, kitchen, qty=200, unit_id=kitchen["g"])
    in_grams = _cost(db, kitchen)["computed_cost_total"]

    db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_version_id == kitchen["version_id"]
    ).delete(synchronize_session=False)
    db.commit()

    _use(db, kitchen, qty=Decimal("0.2"), unit_id=kitchen["kg"])
    in_kilos = _cost(db, kitchen)["computed_cost_total"]

    assert in_grams == in_kilos == pytest.approx(1.70)


# --------------------------------------------------------------------------- #
# Loss and yield — the difference between a costed dish and a guessed one
# --------------------------------------------------------------------------- #
def test_loss_is_paid_for(db, kitchen):
    """25 % is trimmed away, but the restaurant still bought it."""
    _use(db, kitchen, qty=200, unit_id=kitchen["g"], loss=25)
    assert _cost(db, kitchen)["computed_cost_total"] == pytest.approx(2.125)  # 1.70 × 1.25


def test_a_poor_yield_raises_the_cost(db, kitchen):
    """Half of what goes in comes out: you need twice as much."""
    _use(db, kitchen, qty=200, unit_id=kitchen["g"], yld=50)
    assert _cost(db, kitchen)["computed_cost_total"] == pytest.approx(3.40)  # 1.70 ÷ 0.5


# --------------------------------------------------------------------------- #
# A missing price must be announced, never guessed
# --------------------------------------------------------------------------- #
def test_an_unpriced_ingredient_is_flagged_not_counted_as_free(db, kitchen):
    """A dish that looks cheap because an ingredient has no price is how you sell
    at a loss with a straight face."""
    unpriced = str(uuid.uuid4())
    db.add(Product(id=unpriced, tenant_id=kitchen["tenant_id"], name="Truffe (sans prix)"))
    db.commit()

    _use(db, kitchen, qty=200, unit_id=kitchen["g"])
    _use(db, kitchen, qty=10, unit_id=kitchen["g"], product_id=unpriced)

    result = _cost(db, kitchen)

    assert result["has_missing_prices"] is True, "silence here is the expensive kind"
    assert result["computed_cost_total"] == pytest.approx(1.70), "the priced part still counts"
    missing = [line for line in result["breakdown"] if line["missing_price"]]
    assert len(missing) == 1
    assert missing[0]["line_cost"] is None, "an unknown cost is None, not 0"


# --------------------------------------------------------------------------- #
# Margin
# --------------------------------------------------------------------------- #
def test_food_cost_and_margin_on_a_real_selling_price(db, kitchen):
    _use(db, kitchen, qty=200, unit_id=kitchen["g"])

    result = _cost(db, kitchen, selling_price=5.00)

    assert result["cost_per_portion"] == pytest.approx(0.425)
    assert result["food_cost_pct"] == pytest.approx(8.5)
    assert result["margin_estimated"] == pytest.approx(4.575)


# --------------------------------------------------------------------------- #
# Isolation, on the money path
# --------------------------------------------------------------------------- #
def test_a_price_change_never_recosts_another_restaurants_recipes(db, kitchen):
    """`recompute_for_product` walks recipes. If it walked them across tenants, a
    supplier's price rise at one restaurant would silently re-cost another's menu."""
    _use(db, kitchen, qty=200, unit_id=kitchen["g"])

    intruder = str(uuid.uuid4())
    db.add(Organization(id=intruder, name="Le Restaurant d'en face"))
    db.commit()
    try:
        touched = cost_engine.recompute_for_product(db, kitchen["product_id"], intruder)
        assert touched == [], (
            "the neighbour asked to recost OUR product and must have been given nothing"
        )

        mine = cost_engine.recompute_for_product(db, kitchen["product_id"], kitchen["tenant_id"])
        assert kitchen["version_id"] in mine, "our own recipe must still be recosted"
    finally:
        rgpd.delete_organization(db, intruder)


# --------------------------------------------------------------------------- #
# The numeric column must hand back what was put in it
# --------------------------------------------------------------------------- #
def test_a_price_survives_the_round_trip_through_postgres(db, kitchen):
    """8.51 € must come back as 8.51 €, not 8.509999999. Costs are computed in
    `Decimal` precisely so that cents do not evaporate; a float slipping in
    anywhere along the way undoes that quietly."""
    row = (
        db.query(ProductPrice)
        .filter(ProductPrice.product_id == kitchen["product_id"])
        .first()
    )
    assert isinstance(row.price, Decimal), "the driver must not hand us a float"
    assert row.price == Decimal("8.50")
