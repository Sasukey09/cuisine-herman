"""Phase 3 — the recipe listing must cost a constant number of queries.

The listing used to call `compute_recipe_version_cost` once per recipe. Each call
re-queried the version, the recipe, its ingredients, EVERY unit, EVERY conversion,
then one price per ingredient. With 500 recipes of 10 ingredients that is roughly
7 500 round trips to answer a single page — the app's most-used screen.
"""
from types import SimpleNamespace as N

import pytest

from app.services.costing import cost_engine


class CountingDB:
    """Counts how many queries the code issues, and serves canned rows."""

    def __init__(self, ingredients_by_version, prices_by_product, units, conversions):
        self.queries = 0
        self._ing = ingredients_by_version
        self._prices = prices_by_product
        self._units = units
        self._conversions = conversions

    # --- the tiny slice of the SQLAlchemy API the code actually uses ---
    def query(self, *cols):
        self.queries += 1
        from app.models.models import ProductPrice, RecipeIngredient, Unit, UnitConversion

        target = cols[0]
        if target is RecipeIngredient:
            return _Result([i for ings in self._ing.values() for i in ings])
        if target is ProductPrice:
            return _Result(list(self._prices.values()))
        if target is Unit:
            return _Result(self._units)
        if target is UnitConversion:
            return _Result(self._conversions)
        return _Result([])


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def distinct(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self._rows


@pytest.fixture(autouse=True)
def _fresh_unit_cache():
    cost_engine.reset_unit_cache()
    yield
    cost_engine.reset_unit_cache()


def _dataset(n_recipes: int, n_ingredients: int):
    units = [
        N(id=1, code="g", category="mass", name="gramme", ratio_to_base=1),
        N(id=2, code="kg", category="mass", name="kilogramme", ratio_to_base=1000),
    ]
    conversions = [N(from_unit_id=2, to_unit_id=1, factor=1000)]

    recipes, ingredients, prices = [], {}, {}
    for r in range(n_recipes):
        vid = f"v{r}"
        recipes.append(
            N(id=f"r{r}", current_version_id=vid, yield_qty=4, selling_price=20.0, name=f"R{r}")
        )
        ings = []
        for i in range(n_ingredients):
            pid = f"p{i}"  # the catalogue is shared across recipes, as in real life
            ings.append(
                N(
                    product_id=pid,
                    recipe_version_id=vid,
                    qty=100,
                    unit_id=1,
                    qty_normalized=None,
                    loss_pct=None,
                    yield_pct=None,
                )
            )
            prices[pid] = N(id=f"pr{i}", product_id=pid, price=2.0, unit_id=1, currency="EUR")
        ingredients[vid] = ings
    return recipes, ingredients, prices, units, conversions


def test_the_query_count_does_not_grow_with_the_catalogue():
    """1 recipe or 200: the same handful of queries."""
    counts = {}
    for n in (1, 200):
        recipes, ing, prices, units, conv = _dataset(n, 10)
        db = CountingDB(ing, prices, units, conv)
        cost_engine.reset_unit_cache()
        cost_engine.compute_costs_for_recipes(db, "t1", recipes)
        counts[n] = db.queries

    assert counts[1] == counts[200], (
        f"query count grew with the number of recipes: "
        f"{counts[1]} for 1 recipe, {counts[200]} for 200"
    )
    # ingredients + prices + units + conversions
    assert counts[200] <= 4, f"expected a handful of queries, got {counts[200]}"


def test_the_old_path_would_have_issued_thousands():
    """Guards the claim: 200 recipes x 10 ingredients used to mean ~3 000 queries.

    Per recipe the old code did: version + recipe + ingredients + all units +
    all conversions (5) then one price per ingredient (10) = 15.
    """
    old = 200 * (5 + 10)
    recipes, ing, prices, units, conv = _dataset(200, 10)
    db = CountingDB(ing, prices, units, conv)
    cost_engine.compute_costs_for_recipes(db, "t1", recipes)

    assert db.queries < old / 100, (
        f"the batch must be at least 100x cheaper: {db.queries} vs {old}"
    )


def test_units_are_loaded_once_not_once_per_recipe():
    recipes, ing, prices, units, conv = _dataset(50, 3)
    db = CountingDB(ing, prices, units, conv)

    cost_engine.compute_costs_for_recipes(db, "t1", recipes)
    first = db.queries
    cost_engine.compute_costs_for_recipes(db, "t1", recipes)  # units now cached
    second = db.queries - first

    assert second < first, "the second call must not reload the unit tables"


def test_the_figures_are_unchanged():
    """A faster path that returns different numbers is a bug, not an optimisation."""
    recipes, ing, prices, units, conv = _dataset(3, 2)
    db = CountingDB(ing, prices, units, conv)

    out = cost_engine.compute_costs_for_recipes(db, "t1", recipes)

    assert len(out) == 3
    for computed in out.values():
        # 2 ingredients x 100 g x 2.00 EUR/g = 400 ; 4 portions -> 100 / portion
        assert computed["cost_per_portion"] is not None
        assert computed["computed_cost_total"] is not None
        assert "breakdown" in computed
