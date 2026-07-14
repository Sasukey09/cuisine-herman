"""Dishes sold at a loss — against a real PostgreSQL.

The number was always there. `margin_estimated` is computed for every recipe and
stored, and nothing ever compared it to zero. A restaurant could sell a dish
below cost on every plate, and the platform that exists to tell it so said
nothing.
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
from app.services.dashboard import loss_service
from app.services.rgpd import service as rgpd


@pytest.fixture
def restaurant(db):
    """Truffle at 800 €/kg. Everything that follows is priced off that."""
    cost_engine.reset_unit_cache()

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Chez Perte"))
    db.commit()

    supplier_id, product_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Supplier(id=supplier_id, tenant_id=tenant_id, name="Rungis"))
    db.add(Product(id=product_id, tenant_id=tenant_id, name="Truffe noire"))
    db.commit()

    kg = db.query(Unit).filter(Unit.code == "kg").first()
    g = db.query(Unit).filter(Unit.code == "g").first()
    db.add(
        ProductPrice(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            product_id=product_id,
            supplier_id=supplier_id,
            price=Decimal("800.00"),  # per kilo
            unit_id=kg.id,
            currency="EUR",
            effective_date=date(2026, 1, 1),
        )
    )
    db.commit()

    yield {"tenant_id": tenant_id, "product_id": product_id, "g": g.id}

    rgpd.delete_organization(db, tenant_id)
    cost_engine.reset_unit_cache()


def _dish(db, r, name, grams_of_truffle, selling_price, priced=True):
    """One dish, one portion, `grams_of_truffle` of truffle in it."""
    recipe_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(
        Recipe(
            id=recipe_id,
            tenant_id=r["tenant_id"],
            name=name,
            yield_qty=1,
            selling_price=Decimal(str(selling_price)) if selling_price is not None else None,
        )
    )
    db.commit()
    db.add(RecipeVersion(id=version_id, recipe_id=recipe_id, version_number=1))
    db.commit()
    db.add(
        RecipeIngredient(
            id=str(uuid.uuid4()),
            recipe_version_id=version_id,
            product_id=r["product_id"] if priced else None,
            ingredient_name="Truffe noire",
            qty=Decimal(str(grams_of_truffle)),
            unit_id=r["g"],
        )
    )
    db.query(Recipe).filter(Recipe.id == recipe_id).update({"current_version_id": version_id})
    db.commit()
    return recipe_id


def test_a_dish_sold_below_its_cost_is_named_and_the_loss_is_quantified(db, restaurant):
    # 30 g of truffle at 800 €/kg = 24 € of truffle, sold at 19 €.
    _dish(db, restaurant, "Risotto à la truffe", grams_of_truffle=30, selling_price=19)

    report = loss_service.loss_report(db, restaurant["tenant_id"])

    assert len(report["losing_money"]) == 1
    dish = report["losing_money"][0]
    assert dish["name"] == "Risotto à la truffe"
    assert dish["cost_per_portion"] == pytest.approx(24.0)
    assert dish["loss_per_portion"] == pytest.approx(5.0), (
        "5 € lost on every plate — that is the number, and it was never once computed"
    )
    assert dish["food_cost_pct"] == pytest.approx(126.3, abs=0.1)


def test_a_profitable_dish_is_not_reported(db, restaurant):
    # 10 g of truffle = 8 €, sold at 26 €.
    _dish(db, restaurant, "Œuf à la truffe", grams_of_truffle=10, selling_price=26)

    report = loss_service.loss_report(db, restaurant["tenant_id"])

    assert report["losing_money"] == [], "crying wolf on a healthy dish is how a tool gets ignored"
    assert report["loss_per_portion_total"] == 0


def test_the_losses_are_totalled_and_the_worst_dish_comes_first(db, restaurant):
    _dish(db, restaurant, "Petite perte", grams_of_truffle=15, selling_price=10)   # 12 € → −2 €
    _dish(db, restaurant, "Grosse perte", grams_of_truffle=50, selling_price=20)   # 40 € → −20 €
    _dish(db, restaurant, "Rentable", grams_of_truffle=5, selling_price=30)        # 4 € → +26 €

    report = loss_service.loss_report(db, restaurant["tenant_id"])

    names = [d["name"] for d in report["losing_money"]]
    assert names == ["Grosse perte", "Petite perte"], "the worst bleeding gets looked at first"
    assert report["loss_per_portion_total"] == pytest.approx(22.0)


def test_a_dish_with_no_selling_price_is_unknown_not_fine(db, restaurant):
    """A dish you cannot evaluate is exactly where the loss hides. Silence would
    file it under 'profitable'."""
    _dish(db, restaurant, "Plat du jour", grams_of_truffle=30, selling_price=None)

    report = loss_service.loss_report(db, restaurant["tenant_id"])

    assert report["losing_money"] == []
    assert [d["name"] for d in report["no_selling_price"]] == ["Plat du jour"]
    assert report["no_selling_price"][0]["cost_per_portion"] == pytest.approx(24.0), (
        "we know what it costs — only what it sells for is missing"
    )


def test_a_dish_whose_cost_is_incomplete_is_never_called_profitable(db, restaurant):
    """An unpriced ingredient understates the cost by construction: it can only
    make the dish look better than it is. Calling it healthy would be dangerous;
    calling it a loss would be a lie. It is called what it is."""
    _dish(db, restaurant, "Recette incomplète", grams_of_truffle=30, selling_price=19, priced=False)

    report = loss_service.loss_report(db, restaurant["tenant_id"])

    assert report["losing_money"] == []
    assert [d["name"] for d in report["not_costable"]] == ["Recette incomplète"]


def test_the_report_never_shows_another_restaurants_dishes(db, restaurant):
    intruder = str(uuid.uuid4())
    db.add(Organization(id=intruder, name="Le voisin"))
    db.commit()
    try:
        _dish(db, restaurant, "Notre plat", grams_of_truffle=30, selling_price=19)

        report = loss_service.loss_report(db, intruder)
        assert report["losing_money"] == []
        assert report["no_selling_price"] == []
        assert report["not_costable"] == []
    finally:
        rgpd.delete_organization(db, intruder)
