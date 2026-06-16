"""Video-import recipe save: the full recipe (ingredients + procedure) must be
persisted, not just name/portions.

No DB/network: the shared builder is monkeypatched to capture what video save
forwards, and crud_recipe.replace_instructions is tested against a fake session.
"""
import uuid
from types import SimpleNamespace as N

from app.services.video import service as video_service
from app.crud import crud_recipe


def test_save_draft_forwards_ingredients_and_steps(monkeypatch):
    captured = {}

    def fake_save_import(db, tenant_id, *, name, servings, instructions, ingredients,
                         selling_price=None, job_id=None):
        captured.update(
            name=name, servings=servings, instructions=instructions, ingredients=ingredients
        )
        return {"recipe_id": "r1", "version_id": "v1", "name": name,
                "yield_qty": servings or 1, "unmatched_ingredients": [], "unknown_units": [],
                "cost": {"computed_cost_total": 0, "cost_per_portion": 0,
                         "food_cost_pct": None, "margin_estimated": None, "has_missing_prices": True}}

    import app.services.recipe_import.service as ri
    monkeypatch.setattr(ri, "save_import", fake_save_import)

    out = video_service.save_draft(
        db=object(),
        tenant_id="t1",
        name="Tarte aux pommes",
        yield_qty=6,
        ingredients=[
            {"name": "Pomme", "qty": 800, "unit": "g"},
            {"name": "Sucre", "qty": 100, "unit": "g"},
        ],
        instructions=["Éplucher les pommes", "Étaler la pâte", "Cuire 40 min"],
    )

    # ingredients are mapped qty->quantity and the procedure is forwarded intact
    assert captured["name"] == "Tarte aux pommes"
    assert captured["servings"] == 6
    assert captured["ingredients"][0] == {"name": "Pomme", "quantity": 800, "unit": "g", "product_id": None}
    assert captured["instructions"] == ["Éplucher les pommes", "Étaler la pâte", "Cuire 40 min"]
    assert out["recipe_id"] == "r1"


# --- crud_recipe.replace_instructions ------------------------------------- #
class FakeDeleteQuery:
    def filter(self, *a, **k):
        return self

    def delete(self, *a, **k):
        return 0


class FakeDB:
    def __init__(self):
        self.added = []

    def query(self, *a, **k):
        return FakeDeleteQuery()

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass


def test_replace_instructions_numbers_steps_and_drops_blanks(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(uuid, "uuid4", lambda: "uid")
    n = crud_recipe.replace_instructions(db, "r1", ["  Étape 1 ", "", "Étape 2", "   "])
    assert n == 2
    rows = sorted(db.added, key=lambda r: r.step_number)
    assert [(r.step_number, r.content) for r in rows] == [(1, "Étape 1"), (2, "Étape 2")]
    assert all(r.recipe_id == "r1" for r in rows)
