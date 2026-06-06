from types import SimpleNamespace

import pytest

from app.services.video.extractor import RecipeExtractor, _parse_json, _normalize
from app.services.video.errors import RecipeExtractionError


def text_block(t):
    return SimpleNamespace(type="text", text=t)


class FakeMessages:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[text_block(self._text)])


class FakeClient:
    def __init__(self, text):
        self.messages = FakeMessages(text)


def test_parse_json_plain_and_fenced():
    assert _parse_json('{"a": 1}') == {"a": 1}
    assert _parse_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert _parse_json('blabla {"a": 3} trailing') == {"a": 3}


def test_parse_json_invalid_raises():
    with pytest.raises(RecipeExtractionError):
        _parse_json("not json at all")


def test_normalize_filters_and_lowercases_units():
    raw = {
        "name": " Tarte ",
        "yield_qty": "6",
        "ingredients": [
            {"name": "Farine", "qty": 250, "unit": "G"},
            {"name": "", "qty": 1, "unit": "kg"},  # dropped (no name)
            "garbage",  # dropped (not a dict)
        ],
        "steps": ["Mélanger", "  ", 5],
    }
    out = _normalize(raw)
    assert out["name"] == "Tarte"
    assert out["yield_qty"] == 6.0
    assert out["ingredients"] == [{"name": "Farine", "qty": 250, "unit": "g"}]
    assert out["steps"] == ["Mélanger"]


def test_extractor_returns_draft_from_model_json():
    payload = (
        '{"name":"Gâteau à la fraise","yield_qty":8,'
        '"ingredients":[{"name":"fraises","qty":500,"unit":"g"},'
        '{"name":"sucre","qty":100,"unit":"g"}],"steps":["Mélanger"],"summary":"x"}'
    )
    extractor = RecipeExtractor(client=FakeClient(payload))
    draft = extractor.extract("transcription d'une video de gateau...")
    assert draft["name"] == "Gâteau à la fraise"
    assert draft["yield_qty"] == 8.0
    assert len(draft["ingredients"]) == 2
    assert draft["ingredients"][0]["unit"] == "g"


def test_extractor_rejects_non_recipe():
    extractor = RecipeExtractor(client=FakeClient('{"name":"","ingredients":[]}'))
    with pytest.raises(RecipeExtractionError):
        extractor.extract("ceci n'est pas une recette")
