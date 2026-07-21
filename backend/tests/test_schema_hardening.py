"""Pre-launch input hardening — non-regression.

Two real defects found in the pre-launch adversarial pass, both reproduced by
execution before the fix:

1. A non-finite number (``NaN`` / ``Infinity``) sailed through Pydantic (which
   accepts them by default) into a Postgres ``numeric`` column, then the cost
   engine did ``Decimal('NaN') > 0`` / ``Decimal('Infinity').quantize(...)`` —
   both raise ``InvalidOperation`` — uncaught → HTTP 500. Worse, the loss-making
   dashboard (``loss_service``) has no try/except, so one poisoned recipe 500s
   the whole tenant's dashboard on every load. ``Field(gt=0)`` did NOT stop
   ``Infinity`` (``float('inf') > 0`` is ``True``).

2. No ``max_length`` on any free-text field: a 200_000-char name was accepted
   and stored verbatim.

The fix rejects both at the schema boundary (before the DB is ever touched), so
they surface as a clean 422 instead of a 500 or silent storage abuse.
"""
import math

import pytest
from pydantic import ValidationError

from app.schemas import schemas as S


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected_on_the_cost_path(bad):
    # Every numeric field that feeds the cost engine must refuse NaN/Inf.
    with pytest.raises(ValidationError):
        S.ProductPriceCreate(price=bad, unit_id=1)
    with pytest.raises(ValidationError):
        S.RecipeBase(name="x", yield_qty=bad)
    with pytest.raises(ValidationError):
        S.RecipeBase(name="x", selling_price=bad)
    with pytest.raises(ValidationError):
        S.RecipeIngredientCreate(qty=bad)
    with pytest.raises(ValidationError):
        S.RecipeIngredientCreate(loss_pct=bad)


def test_finite_numbers_still_pass():
    # The fix must not reject legitimate finite values.
    assert S.ProductPriceCreate(price=8.5, unit_id=1).price == 8.5
    r = S.RecipeBase(name="Tarte", yield_qty=8, selling_price=24.9)
    assert r.yield_qty == 8 and r.selling_price == 24.9
    ing = S.RecipeIngredientCreate(qty=2.5, loss_pct=10, yield_pct=95)
    assert ing.qty == 2.5 and ing.loss_pct == 10


def test_oversized_free_text_is_rejected():
    huge = "A" * 200_000
    for ctor in (
        lambda: S.ProductBase(name=huge),
        lambda: S.SupplierBase(name=huge),
        lambda: S.RecipeBase(name=huge),
    ):
        with pytest.raises(ValidationError):
            ctor()


def test_normal_length_names_still_pass():
    assert S.ProductBase(name="Beurre doux 82% AOP Charentes-Poitou").name.startswith("Beurre")
    assert S.SupplierBase(name="METRO Cash & Carry France").name.startswith("METRO")
