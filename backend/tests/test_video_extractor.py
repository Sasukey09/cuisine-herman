import json
from types import SimpleNamespace

import pytest

from app.services.video.extractor import (
    RecipeExtractor, _parse_json, _normalize_one, _normalize_many,
)
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


def test_normalize_one_enriches_with_rich_fields():
    r = _normalize_one({
        "name": "  Tarte  ", "yield_qty": "6",
        "ingredients": [{"name": "Farine", "qty": 250, "unit": "G"}, {"name": ""}],
        "steps": [" Mélanger ", ""], "prep_time_min": "20", "cook_time_min": 30,
        "tips": ["Repos 1h", 3], "variants": ["Sans gluten"], "allergens": ["gluten"],
        "start_sec": "12", "end_sec": 340, "description": " une tarte ", "summary": "s",
    })
    assert r["name"] == "Tarte"
    assert r["yield_qty"] == 6.0
    assert r["ingredients"] == [{"name": "Farine", "qty": 250, "unit": "g"}]
    assert r["steps"] == ["Mélanger"]
    assert r["prep_time_min"] == 20.0 and r["cook_time_min"] == 30.0
    assert r["tips"] == ["Repos 1h"] and r["allergens"] == ["gluten"]
    assert r["start_sec"] == 12.0 and r["end_sec"] == 340.0
    assert r["description"] == "une tarte"


def test_normalize_many_reads_the_recipes_list():
    parsed = {"recipes": [
        {"name": "Pâtes", "ingredients": [{"name": "pâtes"}]},
        {"name": "Salade", "ingredients": [{"name": "laitue"}]},
    ]}
    out = _normalize_many(parsed)
    assert [r["name"] for r in out] == ["Pâtes", "Salade"]


def test_normalize_many_falls_back_to_a_single_object():
    out = _normalize_many({"name": "Soupe", "ingredients": [{"name": "poireau"}]})
    assert len(out) == 1 and out[0]["name"] == "Soupe"


def test_normalize_many_filters_empty_recipes():
    out = _normalize_many({"recipes": [
        {"name": "", "ingredients": []},
        {"name": "Cake", "ingredients": [{"name": "farine"}]},
    ]})
    assert [r["name"] for r in out] == ["Cake"]


def test_extract_returns_a_list_of_all_recipes():
    payload = json.dumps({"recipes": [
        {"name": "R1", "ingredients": [{"name": "a"}], "steps": ["s1"]},
        {"name": "R2", "ingredients": [{"name": "b"}], "steps": ["s2"]},
        {"name": "R3", "ingredients": [{"name": "c"}], "steps": ["s3"]},
    ]})
    recipes = RecipeExtractor(client=FakeClient(payload)).extract("transcription…")
    assert [r["name"] for r in recipes] == ["R1", "R2", "R3"]


def test_extract_raises_only_when_no_recipe_at_all():
    payload = json.dumps({"recipes": [{"name": "", "ingredients": []}]})
    with pytest.raises(RecipeExtractionError):
        RecipeExtractor(client=FakeClient(payload)).extract("bla")


def test_extract_single_recipe_still_yields_a_one_element_list():
    payload = json.dumps({"recipes": [{"name": "Unique", "ingredients": [{"name": "x"}]}]})
    recipes = RecipeExtractor(client=FakeClient(payload)).extract("bla")
    assert len(recipes) == 1 and recipes[0]["name"] == "Unique"
