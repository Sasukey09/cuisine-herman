"""Video-import recipe save: the full recipe (ingredients + procedure) must be
persisted, not just name/portions.

No DB/network for the top tests: the shared builder is monkeypatched to
capture what video save forwards, and crud_recipe.replace_instructions is
tested against a fake session. The bottom (real_db) tests persist for real
and skip locally when there is no DATABASE_URL (see conftest.py).
"""
import uuid
from types import SimpleNamespace as N

import pytest

from app.services.video import service as video_service
from app.crud import crud_recipe


def test_save_candidates_forwards_ingredients_and_steps(monkeypatch):
    captured = {}

    def fake_save_import(db, tenant_id, *, name, servings, instructions, ingredients,
                         selling_price=None, job_id=None, **kwargs):
        captured.update(
            name=name, servings=servings, instructions=instructions, ingredients=ingredients
        )
        return {"recipe_id": "r1", "version_id": "v1", "name": name,
                "yield_qty": servings or 1, "unmatched_ingredients": [], "unknown_units": [],
                "cost": {"computed_cost_total": 0, "cost_per_portion": 0,
                         "food_cost_pct": None, "margin_estimated": None, "has_missing_prices": True}}

    import app.services.recipe_import.service as ri
    monkeypatch.setattr(ri, "save_import", fake_save_import)

    out = video_service.save_candidates(
        db=object(),
        tenant_id="t1",
        recipes=[{
            "name": "Tarte aux pommes",
            "yield_qty": 6,
            "ingredients": [
                {"name": "Pomme", "qty": 800, "unit": "g"},
                {"name": "Sucre", "qty": 100, "unit": "g"},
            ],
            "steps": ["Éplucher les pommes", "Étaler la pâte", "Cuire 40 min"],
        }],
        source={},
    )

    # ingredients are mapped qty->quantity and the procedure is forwarded intact
    assert captured["name"] == "Tarte aux pommes"
    assert captured["servings"] == 6
    assert captured["ingredients"][0] == {"name": "Pomme", "quantity": 800, "unit": "g"}
    assert captured["instructions"] == ["Éplucher les pommes", "Étaler la pâte", "Cuire 40 min"]
    # Partial-success shape: {count, recipes, errors}, each saved result carrying
    # its input index.
    assert out["count"] == 1
    assert out["recipes"][0]["recipe_id"] == "r1"
    assert out["recipes"][0]["index"] == 0
    assert out["errors"] == []


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


def test_extract_recipe_from_file(monkeypatch):
    import app.services.video.service as vs

    class FakeSTT:
        def is_configured(self):
            return True

        def transcribe(self, path, language=None):
            return "Tiramisu recipe with mascarpone, eggs and sugar. Mix, layer, chill."

    def fake_transcode(inp):
        out = inp + ".out.mp3"
        with open(out, "wb") as fh:
            fh.write(b"\x00" * 256)  # small real file so getsize() works
        return out

    monkeypatch.setattr("app.services.video.audio.transcode_to_mp3", fake_transcode)
    fake_extractor = N(
        extract=lambda text, hints=None: [
            {
                "name": "Tiramisu", "yield_qty": 6,
                "ingredients": [{"name": "Mascarpone", "qty": 250, "unit": "g"}],
                "steps": ["Mélanger", "Dresser", "Réfrigérer"], "summary": None,
            },
        ]
    )

    class DB:
        def add(self, *a):
            pass

        def commit(self):
            pass

    out = vs.extract_recipe_from_file(
        DB(), "t1", b"fake-video-bytes", "clip.mp4", "video/mp4",
        stt_provider=FakeSTT(), extractor=fake_extractor,
    )
    assert out["platform"] == "upload"
    assert out["transcript_source"] == "audio_upload"
    assert out["source"] == {
        "platform": "upload", "url": None, "video_id": None,
        "title": "clip.mp4", "creator": None, "thumbnail": None,
    }
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["name"] == "Tiramisu"
    assert out["candidates"][0]["ingredients"][0]["name"] == "Mascarpone"
    assert len(out["candidates"][0]["steps"]) == 3


def test_extract_from_file_requires_stt(monkeypatch):
    import app.services.video.service as vs
    from app.services.video.errors import STTNotConfiguredError

    class NoSTT:
        def is_configured(self):
            return False

    import pytest
    with pytest.raises(STTNotConfiguredError):
        vs.extract_recipe_from_file(object(), "t1", b"x", "c.mp4", "video/mp4", stt_provider=NoSTT())


def test_replace_instructions_numbers_steps_and_drops_blanks(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(uuid, "uuid4", lambda: "uid")
    n = crud_recipe.replace_instructions(db, "r1", ["  Étape 1 ", "", "Étape 2", "   "])
    assert n == 2
    rows = sorted(db.added, key=lambda r: r.step_number)
    assert [(r.step_number, r.content) for r in rows] == [(1, "Étape 1"), (2, "Étape 2")]
    assert all(r.recipe_id == "r1" for r in rows)


# --------------------------------------------------------------------------- #
# real_db: provenance/rich fields must round-trip through actual JSONB columns,
# not just through a monkeypatched fake. Skips locally without DATABASE_URL,
# runs in CI (see conftest.py).
# --------------------------------------------------------------------------- #
from app.models.models import Organization, Recipe, RecipeVersion  # noqa: E402
from app.services.recipe_import import service as recipe_import_service  # noqa: E402
from app.services.rgpd import service as rgpd  # noqa: E402


@pytest.fixture
def tenant(db):
    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Cuisine Vidéo"))
    db.commit()
    yield tenant_id
    rgpd.delete_organization(db, tenant_id)


def test_save_import_stores_imported_from_and_recipe_meta(db, tenant):
    """save_import (Step 1's extension) must persist provenance on Recipe.meta
    and both the imported_from flag and any extra fields on RecipeVersion.meta —
    without disturbing the PDF path, which never passes these."""
    out = recipe_import_service.save_import(
        db, tenant,
        name="Tarte vidéo",
        servings=6,
        instructions=["Étaler", "Cuire"],
        ingredients=[{"name": "Pomme", "quantity": 800, "unit": "g"}],
        imported_from="video",
        recipe_meta={"source": {"video_id": "abc"}},
        version_meta_extra={"prep_time_min": 20},
    )

    recipe = db.query(Recipe).filter(Recipe.id == out["recipe_id"]).first()
    version = db.query(RecipeVersion).filter(RecipeVersion.id == out["version_id"]).first()

    assert recipe.meta["source"]["video_id"] == "abc"
    assert version.meta["imported_from"] == "video"
    assert version.meta["prep_time_min"] == 20


def test_save_candidates_persists_source_and_imported_from(db, tenant, monkeypatch):
    """End-to-end: extraction hands back candidates + source, save_candidates
    persists each recipe with a deeplink built from the video's provenance.

    Both the AI extractor and the oEmbed fetch are faked so this never touches
    the network — only Postgres is real here.
    """
    from app.services.video import service as video_service

    monkeypatch.setattr(
        video_service.provenance, "fetch_oembed",
        lambda url, fetcher=None: {"title": "Ma vidéo", "creator": "Chef", "thumbnail": "http://x/thumb.jpg"},
    )

    fake_extractor = N(
        extract=lambda text, hints=None: [
            {
                "name": "Tarte vidéo", "yield_qty": 6,
                "ingredients": [{"name": "Pomme", "qty": 800, "unit": "g"}],
                "steps": ["Éplucher", "Cuire"],
                "description": "Une tarte simple", "prep_time_min": 15, "cook_time_min": 30,
                "tips": ["Bien beurrer le moule"], "variants": [], "allergens": ["gluten"],
                "start_sec": 42, "end_sec": 300,
            },
        ]
    )

    # extract_recipe_from_transcript persists a VideoSource + Transcription row,
    # which is exactly what the real `db` fixture is for here.
    result = video_service.extract_recipe_from_transcript(
        db, tenant, "Prenez 800g de pommes, épluchez, cuisez 30 min.",
        url="https://youtu.be/abc123XYZ0", title="Ma vidéo", extractor=fake_extractor,
    )
    assert result["candidates"][0]["name"] == "Tarte vidéo"
    assert result["source"]["video_id"] == "abc123XYZ0"

    saved = video_service.save_candidates(db, tenant, result["candidates"], result["source"])
    assert saved["count"] == 1
    assert saved["errors"] == []

    recipe = db.query(Recipe).filter(Recipe.id == saved["recipes"][0]["recipe_id"]).first()
    version = db.query(RecipeVersion).filter(RecipeVersion.id == saved["recipes"][0]["version_id"]).first()

    assert recipe.meta["source"]["deeplink"] == "https://youtu.be/abc123XYZ0?t=42"
    assert recipe.meta["source"]["video_id"] == "abc123XYZ0"
    assert version.meta["imported_from"] == "video"
    assert version.meta["prep_time_min"] == 15
    assert version.meta["tips"] == ["Bien beurrer le moule"]


def test_save_candidates_is_resilient_to_a_per_recipe_failure(db, tenant, monkeypatch):
    """A mid-batch failure must NOT 500 nor roll back the recipes already saved:
    save_candidates catches per recipe and returns partial success so a retry
    can't duplicate the already-committed ones. Here the 2nd recipe ("BOOM")
    blows up inside save_import; the 1st ("OK") must still be persisted, and the
    failure reported (not raised)."""
    from app.services.recipe_import import service as ris

    real = ris.save_import

    def flaky(*a, **k):
        if k.get("name") == "BOOM":
            raise RuntimeError("coût indisponible")
        return real(*a, **k)

    monkeypatch.setattr(ris, "save_import", flaky)

    out = video_service.save_candidates(
        db,
        tenant,
        [
            {"name": "OK", "yield_qty": 4, "ingredients": [{"name": "farine"}], "steps": ["m"]},
            {"name": "BOOM", "yield_qty": 2, "ingredients": [{"name": "sucre"}], "steps": ["x"]},
        ],
        {"platform": "youtube", "url": "https://youtu.be/x", "video_id": "x"},
    )

    assert out["count"] == 1
    assert out["recipes"][0]["index"] == 0
    assert len(out["errors"]) == 1
    assert out["errors"][0]["index"] == 1 and out["errors"][0]["name"] == "BOOM"

    # the good recipe is really persisted, the bad one is not
    names = {r.name for r in db.query(Recipe).filter(Recipe.tenant_id == tenant)}
    assert "OK" in names and "BOOM" not in names
