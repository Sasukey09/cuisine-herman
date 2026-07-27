import pytest

from app.services.video import transcript as transcript_mod
from app.services.video import audio as audio_mod
from app.services.video import service as video_service
from app.services.recipe_import import service as recipe_import_service
from app.services.video.errors import STTNotConfiguredError, TranscriptUnavailableError


class FakeSTT:
    def __init__(self, configured=True, text="texte transcrit"):
        self._configured = configured
        self._text = text
        self.calls = []

    def is_configured(self):
        return self._configured

    def transcribe(self, audio_path, language=None):
        self.calls.append(audio_path)
        return self._text


def test_youtube_captions_path(monkeypatch):
    monkeypatch.setattr(transcript_mod, "_youtube_captions", lambda vid: "sous-titres youtube")
    text, source = transcript_mod.get_transcript("https://youtu.be/dQw4w9WgXcQ")
    assert source == "youtube_captions"
    assert text == "sous-titres youtube"


def test_stt_fallback_for_non_youtube(monkeypatch):
    # no captions involved; audio download is stubbed, STT provider injected
    monkeypatch.setattr(audio_mod, "download_audio", lambda url: "/tmp/does-not-exist.mp3")
    stt = FakeSTT(configured=True, text="recette tiktok transcrite")
    text, source = transcript_mod.get_transcript(
        "https://www.tiktok.com/@chef/video/123", stt_provider=stt
    )
    assert source == "stt"
    assert text == "recette tiktok transcrite"
    assert stt.calls == ["/tmp/does-not-exist.mp3"]


def test_stt_not_configured_raises(monkeypatch):
    monkeypatch.setattr(audio_mod, "download_audio", lambda url: "/tmp/x.mp3")
    stt = FakeSTT(configured=False)
    with pytest.raises(STTNotConfiguredError):
        transcript_mod.get_transcript("https://www.tiktok.com/@x/video/1", stt_provider=stt)


def test_audio_disabled_raises(monkeypatch):
    monkeypatch.setenv("VIDEO_ALLOW_AUDIO_STT", "false")
    # youtube url but no captions -> falls through to disabled STT
    monkeypatch.setattr(transcript_mod, "_youtube_captions", lambda vid: None)
    with pytest.raises(TranscriptUnavailableError):
        transcript_mod.get_transcript("https://youtu.be/dQw4w9WgXcQ")


def test_save_candidates_delegates_per_recipe(monkeypatch):
    """save_candidates calls recipe_import.save_import once per selected recipe.

    It used to call the AI tool ``create_recipe_draft``, which dropped the
    ingredients and the steps; it was rewritten to reuse the PDF-import path.
    This test pins the current, list-shaped contract.
    """
    calls = []

    def fake_save_import(db, tenant_id, name, servings, instructions, ingredients, **kwargs):
        calls.append(dict(
            db=db, tenant_id=tenant_id, name=name, servings=servings,
            instructions=instructions, ingredients=ingredients, kwargs=kwargs,
        ))
        return {"recipe_id": f"r{len(calls)}", "cost": {"cost_per_portion": 1.0}}

    monkeypatch.setattr(recipe_import_service, "save_import", fake_save_import)
    source = {"platform": "youtube_client", "url": "https://youtu.be/abc", "video_id": "abc",
              "title": "Ma vidéo", "creator": "Chef", "thumbnail": None}
    out = video_service.save_candidates(
        db="DB", tenant_id="t1",
        recipes=[
            {
                "name": "Gâteau", "yield_qty": 8,
                "ingredients": [{"name": "fraises", "qty": 500, "unit": "g"}],
                "steps": ["Laver les fraises", "Cuire 20 min"],
            },
            {
                "name": "Sauce", "yield_qty": 4,
                "ingredients": [{"name": "tomates", "qty": 300, "unit": "g"}],
                "steps": ["Mijoter 30 min"],
            },
        ],
        source=source,
    )

    assert len(out) == 2
    assert out[0]["recipe_id"] == "r1" and out[1]["recipe_id"] == "r2"
    assert len(calls) == 2

    first = calls[0]
    assert first["tenant_id"] == "t1"
    assert first["name"] == "Gâteau"
    assert first["servings"] == 8
    assert first["ingredients"][0]["name"] == "fraises"
    # The regression this path was written for: steps must survive.
    assert first["instructions"] == ["Laver les fraises", "Cuire 20 min"]
    assert first["kwargs"]["imported_from"] == "video"

    second = calls[1]
    assert second["name"] == "Sauce"
    assert second["instructions"] == ["Mijoter 30 min"]
