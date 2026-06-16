"""Recipe-from-PDF import tests.

No DB / no network: the Anthropic client is faked, and OCR / matching / costing
are monkeypatched, so we exercise the pipeline logic for every documented case:
PDF texte, PDF scanné (OCR text), unités mixtes, sans quantités, ingrédients
inconnus.
"""
import json
from types import SimpleNamespace as N

import pytest

from app.services.recipe_import import service as svc
from app.services.recipe_import.extractor import RecipeDocumentExtractor
from app.services.recipe_import.errors import RecipeExtractionError


# --------------------------------------------------------------------------- #
# fake Anthropic client
# --------------------------------------------------------------------------- #
class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


class _Messages:
    def __init__(self, text):
        self._text = text

    def create(self, **_):
        return _Resp(self._text)


class FakeClient:
    def __init__(self, payload):
        self.messages = _Messages(payload if isinstance(payload, str) else json.dumps(payload))


# --------------------------------------------------------------------------- #
# extractor (PDF texte / unités mixtes / sans quantités)
# --------------------------------------------------------------------------- #
def test_extractor_text_recipe():
    payload = {
        "name": "Pizza Margherita",
        "yield_qty": 2,
        "ingredients": [
            {"name": "Tomate", "qty": 400, "unit": "g"},
            {"name": "Mozzarella", "qty": 1, "unit": "piece"},
        ],
        "steps": ["Étaler la pâte", "Garnir", "Cuire"],
        "summary": "Pizza classique",
    }
    draft = RecipeDocumentExtractor(client=FakeClient(payload)).extract("texte du pdf")
    assert draft["name"] == "Pizza Margherita"
    assert draft["yield_qty"] == 2
    assert len(draft["ingredients"]) == 2
    assert draft["steps"][0] == "Étaler la pâte"


def test_extractor_mixed_units_are_lowercased():
    payload = {
        "name": "Test",
        "yield_qty": 4,
        "ingredients": [
            {"name": "Farine", "qty": 1, "unit": "KG"},
            {"name": "Lait", "qty": 500, "unit": "ML"},
            {"name": "Oeuf", "qty": 3, "unit": "Piece"},
        ],
        "steps": [],
    }
    draft = RecipeDocumentExtractor(client=FakeClient(payload)).extract("x")
    units = [i["unit"] for i in draft["ingredients"]]
    assert units == ["kg", "ml", "piece"]


def test_extractor_missing_quantities_become_null():
    payload = {
        "name": "Vinaigrette",
        "yield_qty": None,
        "ingredients": [
            {"name": "Huile", "qty": None, "unit": None},
            {"name": "Sel", "qty": None, "unit": "pincée"},
        ],
        "steps": ["Mélanger"],
    }
    draft = RecipeDocumentExtractor(client=FakeClient(payload)).extract("x")
    assert draft["ingredients"][0]["qty"] is None
    assert draft["yield_qty"] is None


def test_extractor_json_in_code_fence_is_parsed():
    payload = '```json\n{"name": "X", "ingredients": [{"name": "Sel", "qty": 5, "unit": "g"}]}\n```'
    draft = RecipeDocumentExtractor(client=FakeClient(payload)).extract("x")
    assert draft["name"] == "X"
    assert draft["ingredients"][0]["name"] == "Sel"


def test_extractor_non_recipe_raises():
    payload = {"name": "", "ingredients": []}
    with pytest.raises(RecipeExtractionError):
        RecipeDocumentExtractor(client=FakeClient(payload)).extract("facture edf")


# --------------------------------------------------------------------------- #
# preview building (matching + unknown ingredients + unknown units)
# --------------------------------------------------------------------------- #
def _patch_preview_deps(monkeypatch):
    # "Mozzarella …" matches product p1; everything else is unknown.
    def fake_match(db, tenant_id, name):
        if "mozzarella" in name.lower():
            return {"product_id": "p1", "confidence_score": 88.0, "manual_review": False}
        return {"product_id": None, "confidence_score": 0.0, "manual_review": True}

    monkeypatch.setattr(svc, "match_product", fake_match)
    monkeypatch.setattr(svc, "_product_names", lambda db, t: {"p1": "Mozzarella"})
    monkeypatch.setattr(svc.crud_price, "get_units_by_code", lambda db: {"g": 1, "kg": 2, "ml": 3, "piece": 4})
    monkeypatch.setattr(
        svc, "_estimate_cost",
        lambda db, t, ings, serv: {
            "computed_cost_total": 3.2, "cost_per_portion": 1.6,
            "food_cost_pct": None, "margin_estimated": None, "has_missing_prices": True,
        },
    )


def test_build_preview_matches_and_flags_unknowns(monkeypatch):
    _patch_preview_deps(monkeypatch)
    draft = {
        "name": "Pizza",
        "yield_qty": 2,
        "ingredients": [
            {"name": "Mozzarella râpée", "qty": 200, "unit": "g"},
            {"name": "Truc exotique", "qty": 1, "unit": "botte"},  # unknown product + unit
        ],
        "steps": ["Cuire"],
    }
    preview = svc._build_preview(None, "t1", draft)

    assert preview["recipe_name"] == "Pizza"
    assert preview["servings"] == 2
    moz, exo = preview["ingredients"]
    assert moz["matched_product_id"] == "p1"
    assert moz["matched_product_name"] == "Mozzarella"
    assert moz["unit_recognized"] is True
    assert exo["matched_product_id"] is None
    assert "Truc exotique" in preview["unmatched_ingredients"]
    assert "botte" in preview["unknown_units"]
    assert exo["unit_recognized"] is False
    assert preview["cost"]["has_missing_prices"] is True
    assert preview["instructions"] == ["Cuire"]


# --------------------------------------------------------------------------- #
# orchestration (inline job: PDF texte/scanné -> done ; unreadable -> error)
# --------------------------------------------------------------------------- #
class FakeJob:
    def __init__(self):
        self.id = "job1"
        self.tenant_id = "t1"
        self.status = "processing"
        self.error = None


def _patch_job_crud(monkeypatch, saved):
    monkeypatch.setattr(svc.crud_recipe_import, "create_job", lambda db, t, fn, ct: FakeJob())

    def set_status(db, job, status, error=None):
        job.status = status
        job.error = error
        return job

    monkeypatch.setattr(svc.crud_recipe_import, "set_status", set_status)
    monkeypatch.setattr(
        svc.crud_recipe_import, "save_result",
        lambda db, job, text, preview: saved.update({"text": text, "preview": preview}) or N(id="r1"),
    )


def test_process_import_done(monkeypatch):
    saved = {}
    _patch_job_crud(monkeypatch, saved)
    monkeypatch.setattr(svc, "extract_text", lambda b, ct: "Recette: pizza\nTomate 400 g")
    monkeypatch.setattr(svc, "_build_preview", lambda db, t, draft: {"recipe_name": draft["name"]})
    fake_extractor = N(
        extract=lambda text, hint_title=None: {
            "name": "Pizza", "yield_qty": 2,
            "ingredients": [{"name": "Tomate", "qty": 400, "unit": "g"}], "steps": [],
        }
    )

    job = svc.process_import(None, "t1", b"%PDF-1.4 ...", "application/pdf", "pizza.pdf",
                             extractor=fake_extractor)
    assert job.status == "done"
    assert saved["preview"]["recipe_name"] == "Pizza"


def test_process_import_scanned_pdf_uses_ocr_text(monkeypatch):
    # A scanned PDF differs only in that OCR provides the text; same pipeline.
    saved = {}
    _patch_job_crud(monkeypatch, saved)
    monkeypatch.setattr(svc, "extract_text", lambda b, ct: "TEXTE OCR D'UN SCAN")
    captured = {}
    monkeypatch.setattr(svc, "_build_preview", lambda db, t, draft: {"recipe_name": draft["name"]})
    fake_extractor = N(
        extract=lambda text, hint_title=None: captured.update({"text": text})
        or {"name": "Soupe", "yield_qty": 4, "ingredients": [{"name": "Carotte", "qty": 3, "unit": "piece"}], "steps": []}
    )
    job = svc.process_import(None, "t1", b"scan", "application/pdf", "scan.pdf", extractor=fake_extractor)
    assert job.status == "done"
    assert captured["text"] == "TEXTE OCR D'UN SCAN"


def test_process_import_unreadable_pdf_errors(monkeypatch):
    saved = {}
    _patch_job_crud(monkeypatch, saved)
    monkeypatch.setattr(svc, "extract_text", lambda b, ct: "   ")  # OCR found nothing
    job = svc.process_import(None, "t1", b"img", "application/pdf", "blank.pdf",
                             extractor=N(extract=lambda *a, **k: {}))
    assert job.status == "error"
    assert "lire" in (job.error or "").lower()


def test_process_import_extraction_error(monkeypatch):
    saved = {}
    _patch_job_crud(monkeypatch, saved)
    monkeypatch.setattr(svc, "extract_text", lambda b, ct: "du texte qui n'est pas une recette")

    def boom(text, hint_title=None):
        raise RecipeExtractionError("pas une recette")

    job = svc.process_import(None, "t1", b"x", "application/pdf", "x.pdf",
                             extractor=N(extract=boom))
    assert job.status == "error"
    assert "recette" in (job.error or "").lower()


# --------------------------------------------------------------------------- #
# save (honors corrected product_id; computes cost)
# --------------------------------------------------------------------------- #
class FakeDB:
    def add(self, *a):
        pass

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, *a):
        pass


def test_save_import_persists_and_costs(monkeypatch):
    monkeypatch.setattr(svc.crud_price, "get_units_by_code", lambda db: {"g": 1, "kg": 2})
    # explicit product_id is honored; name-matching only fills the gaps
    monkeypatch.setattr(svc, "match_product", lambda db, t, name: {"product_id": "auto", "confidence_score": 70.0})
    captured = {}

    def fake_cost(db, tenant_id, version_id, selling_price=None, persist=True):
        captured["version_id"] = version_id
        captured["selling_price"] = selling_price
        return {"computed_cost_total": 5.0, "cost_per_portion": 1.25,
                "food_cost_pct": 25.0, "margin_estimated": 3.75, "has_missing_prices": False}

    monkeypatch.setattr(svc.cost_engine, "compute_recipe_version_cost", fake_cost)

    out = svc.save_import(
        FakeDB(), "t1",
        name="Pizza",
        servings=4,
        instructions=["Étaler", "Cuire"],
        ingredients=[
            {"name": "Mozzarella", "quantity": 200, "unit": "g", "product_id": "chosen"},
            {"name": "Basilic", "quantity": 10, "unit": "g"},  # no product_id -> matched
        ],
        selling_price=5.0,
    )
    assert out["name"] == "Pizza"
    assert out["cost"]["food_cost_pct"] == 25.0
    assert out["cost"]["cost_per_portion"] == 1.25
    assert captured["selling_price"] == 5.0
