# Import vidéo multi-recettes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire évoluer l'import vidéo YouTube de « 1 vidéo → 1 recette » à « 1 vidéo → **toutes** ses recettes », chacune éditable/fusionnable/enregistrable indépendamment, sans dupliquer le pipeline.

**Architecture:** Le cœur d'extraction renvoie désormais une **liste** de recettes (`_normalize_one` + `_normalize_many`, un seul appel LLM) ; le service renvoie `candidates: List` + une `source` (provenance oEmbed) ; le save itère et délègue **par recette** au `save_import` existant (matching + coût), en persistant provenance et champs riches dans les `meta` JSONB existants. Les deux UIs passent d'un formulaire unique à une liste de cartes. Aucune migration.

**Tech Stack:** FastAPI + SQLAlchemy + Anthropic Claude (backend), Next.js 15 / React 19 / TS / TanStack Query (web), Flutter + Riverpod + Dio (mobile), pytest, flutter_test.

## Global Constraints

- **Ne jamais dupliquer le pipeline** — faire évoluer l'existant ; réutiliser `recipe_import.save_import` (matching produit + coût) et `_parse_json`.
- **Import PDF intact** : `recipe_import/extractor.py` importe `_normalize` depuis `video/extractor.py` (ligne 13, appelé ligne 79). Après renommage `_normalize`→`_normalize_one`, le PDF reste **strictement mono-recette** ; ses tests restent verts.
- **Aucune table / migration** : provenance + champs riches vont dans les `meta` JSONB existants (`VideoSource.meta`, `Recipe.meta`, `RecipeVersion.meta`).
- **Détection = LLM + métadonnées** (chapitres/timestamps/titre passés en `hints`), **sans OCR ni analyse d'image**.
- **Non-régression 1 recette** : une vidéo mono-recette produit une liste à 1 élément et se sauve à l'identique.
- **Détection exhaustive** : le prompt exige TOUTES les recettes, jamais s'arrêter à la première, retour en liste.
- **Provenance conservée** à la sauvegarde : `Recipe.meta["source"]` = `{platform, url, video_id, thumbnail, creator, start_sec, end_sec, deeplink}` (deeplink = `https://youtu.be/<id>?t=<start_sec>`).
- **oEmbed best-effort** : `https://www.youtube.com/oembed?url=<url>&format=json`, sans clé, via `assert_safe_fetch_url`, échoue silencieusement (jamais bloquant).
- **Jamais mocker la session BDD** : tests touchant la BDD = `*_real_db` contre un vrai Postgres (skippent en local, tournent en CI).
- **Forme normalisée d'une recette** (contrat inter-tâches) :
  ```python
  {"name": str, "description": str|None, "summary": str|None,
   "yield_qty": float|None,
   "ingredients": [{"name": str, "qty": float|None, "unit": str|None}],
   "steps": [str],
   "prep_time_min": float|None, "cook_time_min": float|None,
   "tips": [str], "variants": [str], "allergens": [str],
   "start_sec": float|None, "end_sec": float|None}
  ```
- Commit trailer : `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Commande pytest (pure, locale) : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest <chemin> -q -p no:cacheprovider --no-cov`

---

## File Structure

| Fichier | Rôle | Action |
|---|---|---|
| `backend/app/services/video/extractor.py` | `SYSTEM_PROMPT` multi ; `_normalize`→`_normalize_one` (enrichi) ; `_normalize_many` ; `extract(text, hints)→List` ; `_build_user_message` | **Modifier** |
| `backend/app/services/recipe_import/extractor.py` | importer/appeler `_normalize_one` (au lieu de `_normalize`) | **Modifier** (l.13, l.79) |
| `backend/tests/test_video_extractor.py` | tests du contrat liste | **Modifier** |
| `backend/app/services/video/provenance.py` | oEmbed + parsing hints (chapitres/description) | **Créer** |
| `backend/tests/test_video_provenance.py` | tests purs du parsing + fetch best-effort | **Créer** |
| `backend/app/services/recipe_import/service.py` | `save_import` gagne `imported_from` + meta optionnels | **Modifier** (l.162-190) |
| `backend/app/services/video/service.py` | `extract_*`→`candidates`+`source` ; `save_candidates` | **Modifier** |
| `backend/app/schemas/schemas.py` | `VideoRecipeCandidate`, `VideoSource`, `VideoExtractResult.candidates`, `VideoSaveRequest` liste | **Modifier** (l.500-527) |
| `backend/app/api/api_v1/endpoints/video.py` | `/video/save` accepte une liste | **Modifier** (l.128-142) |
| `backend/tests/test_video_service.py`, `test_video_recipe_save.py` | liste + save par recette + provenance | **Modifier** |
| `frontend/src/services/types.ts` | types candidat/source/liste | **Modifier** (l.455-491) |
| `frontend/src/services/video-service.ts` | `saveVideoRecipes(list)` | **Modifier** |
| `frontend/src/hooks/use-video.ts` | hook save liste | **Modifier** |
| `frontend/src/features/video/candidate-card.tsx` | carte candidat réutilisable (extraite) | **Créer** |
| `frontend/src/features/video/video-import-view.tsx` | liste de cartes + sélection/fusion/save | **Modifier** |
| `mobile/lib/features/video/video_import_screen.dart` | liste de cartes candidat | **Modifier** |
| `mobile/test/video_import_test.dart` | widget test N cartes | **Créer** |

---

## Task 1 : Contrat d'extraction → liste de recettes (racine du verrou)

**Files:**
- Modify: `backend/app/services/video/extractor.py`
- Modify: `backend/app/services/recipe_import/extractor.py` (ligne 13 import, ligne 79 appel)
- Test: `backend/tests/test_video_extractor.py`

**Interfaces:**
- Produces: `_normalize_one(raw: dict) -> dict` (forme normalisée du Global Constraints) ; `_normalize_many(parsed) -> List[dict]` ; `RecipeExtractor.extract(transcript: str, hints: dict|None=None) -> List[dict]`.
- Consumes (inchangé) : `_parse_json`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Dans `backend/tests/test_video_extractor.py`, remplacer les tests qui référencent `_normalize` / un `extract` renvoyant un dict, et ajouter :

```python
from app.services.video.extractor import (
    _normalize_one, _normalize_many, RecipeExtractor,
)
from app.services.video.errors import RecipeExtractionError
import json, pytest


class _FakeBlock:
    type = "text"
    def __init__(self, text): self.text = text


class _FakeResp:
    def __init__(self, text): self.content = [_FakeBlock(text)]


class _FakeClient:
    """Renvoie un JSON fixe, quel que soit l'appel."""
    def __init__(self, payload): self._payload = payload
    class messages:  # placeholder, replaced in __init__
        pass
    def __init__(self, payload):
        self._payload = payload
        outer = self
        class _Msgs:
            def create(self, **kw): return _FakeResp(outer._payload)
        self.messages = _Msgs()


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
    recipes = RecipeExtractor(client=_FakeClient(payload)).extract("transcription…")
    assert [r["name"] for r in recipes] == ["R1", "R2", "R3"]


def test_extract_raises_only_when_no_recipe_at_all():
    payload = json.dumps({"recipes": [{"name": "", "ingredients": []}]})
    with pytest.raises(RecipeExtractionError):
        RecipeExtractor(client=_FakeClient(payload)).extract("bla")


def test_extract_single_recipe_still_yields_a_one_element_list():
    payload = json.dumps({"recipes": [{"name": "Unique", "ingredients": [{"name": "x"}]}]})
    recipes = RecipeExtractor(client=_FakeClient(payload)).extract("bla")
    assert len(recipes) == 1 and recipes[0]["name"] == "Unique"
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_video_extractor.py -q -p no:cacheprovider --no-cov`
Expected : FAIL (`ImportError: cannot import name '_normalize_one'`).

- [ ] **Step 3 : Implémenter le contrat liste dans `video/extractor.py`**

Remplacer `SYSTEM_PROMPT` (l.18-30) par un prompt multi, renommer `_normalize`→`_normalize_one` en l'enrichissant, ajouter `_normalize_many` + `_build_user_message`, et faire renvoyer une liste par `extract` :

```python
SYSTEM_PROMPT = (
    "Tu analyses la transcription d'une vidéo de cuisine qui peut contenir "
    "PLUSIEURS recettes. Détecte TOUTES les recettes présentes. Ne t'arrête "
    "JAMAIS à la première. Utilise tous les indices de changement de recette : "
    "titre annoncé, 'ensuite'/'maintenant'/'deuxième recette'/'pour la prochaine', "
    "changement d'ingrédients ou d'étapes, chapitres et timestamps fournis.\n\n"
    "Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, au format :\n"
    '{"recipes": [{"name": str, "description": str, "yield_qty": number|null, '
    '"ingredients": [{"name": str, "qty": number|null, "unit": str|null}], '
    '"steps": [str], "prep_time_min": number|null, "cook_time_min": number|null, '
    '"tips": [str], "variants": [str], "allergens": [str], '
    '"start_sec": number|null, "end_sec": number|null, "summary": str}]}\n\n'
    "Règles : noms d'ingrédients en français, courts et génériques. Unités via les "
    "codes g, kg, l, ml, piece. Estime les quantités manquantes de façon "
    "raisonnable (qty=null si impossible). yield_qty = nombre de portions. "
    "start_sec/end_sec = bornes de la recette en secondes si des chapitres ou "
    "timestamps le permettent, sinon null. allergens seulement si détectés. "
    'Chaque recette est INDÉPENDANTE, même si elles partagent des ingrédients. '
    'Si la transcription ne contient aucune recette, renvoie {"recipes": []}.'
)


def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None


def _str_list(v):
    return [s.strip() for s in (v or []) if isinstance(s, str) and s.strip()]


def _normalize_one(raw: Dict[str, Any]) -> Dict[str, Any]:
    ingredients: List[Dict[str, Any]] = []
    for ing in raw.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        name = (ing.get("name") or "").strip()
        if not name:
            continue
        ingredients.append({
            "name": name,
            "qty": ing.get("qty"),
            "unit": (ing.get("unit") or "").strip().lower() or None,
        })
    return {
        "name": (raw.get("name") or "").strip(),
        "description": (raw.get("description") or "").strip() or None,
        "summary": (raw.get("summary") or "").strip() or None,
        "yield_qty": _num(raw.get("yield_qty")),
        "ingredients": ingredients,
        "steps": _str_list(raw.get("steps")),
        "prep_time_min": _num(raw.get("prep_time_min")),
        "cook_time_min": _num(raw.get("cook_time_min")),
        "tips": _str_list(raw.get("tips")),
        "variants": _str_list(raw.get("variants")),
        "allergens": _str_list(raw.get("allergens")),
        "start_sec": _num(raw.get("start_sec")),
        "end_sec": _num(raw.get("end_sec")),
    }


def _normalize_many(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, dict) and isinstance(parsed.get("recipes"), list):
        items = parsed["recipes"]
    elif isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = [parsed]  # robustesse : le modèle a renvoyé un objet unique
    else:
        items = []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        r = _normalize_one(it)
        if r["name"] or r["ingredients"]:  # on filtre les recettes vides
            out.append(r)
    return out


def _build_user_message(content: str, hints: Optional[Dict[str, Any]]) -> str:
    hints = hints or {}
    parts = []
    if hints.get("title"):
        parts.append(f"Titre de la vidéo : {hints['title']}")
    if hints.get("chapters"):
        chap = "\n".join(
            f"- {c.get('start_sec')}s : {c.get('title')}" for c in hints["chapters"]
        )
        parts.append("Chapitres :\n" + chap)
    if hints.get("description_timestamps"):
        ts = "\n".join(
            f"- {t.get('sec')}s : {t.get('label')}" for t in hints["description_timestamps"]
        )
        parts.append("Timestamps de la description :\n" + ts)
    parts.append("Transcription :\n" + content)
    return "\n\n".join(parts)
```

Puis dans `extract` (remplace l.98-127) — signature `extract(self, transcript, hints=None)`, `system=SYSTEM_PROMPT`, message via `_build_user_message`, et :

```python
        recipes = _normalize_many(_parse_json(text))
        if not recipes:
            raise RecipeExtractionError(
                "La vidéo ne semble pas contenir de recette exploitable."
            )
        return recipes
```

(supprime l'ancien paramètre `hint_title` ; les appelants passeront `hints={"title": ...}` — voir Task 3.)

- [ ] **Step 4 : Réparer l'import PDF (non-régression)**

Dans `backend/app/services/recipe_import/extractor.py` : ligne 13 `from app.services.video.extractor import _parse_json, _normalize_one` ; ligne 79 `draft = _normalize_one(_parse_json(raw))`. (Le PDF reste mono-recette : `_normalize_one` renvoie une recette, ses champs `name`/`ingredients` sont lus comme avant.)

- [ ] **Step 5 : Lancer les tests (vidéo + PDF)**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_video_extractor.py tests/test_recipe_import_extractor.py -q -p no:cacheprovider --no-cov`
(si `test_recipe_import_extractor.py` n'existe pas, lister le fichier de tests du PDF réellement présent, ex. `tests/test_recipe_import*.py`.)
Expected : PASS (contrat liste + PDF mono-recette intacts).

- [ ] **Step 6 : Commit**

```bash
git add backend/app/services/video/extractor.py backend/app/services/recipe_import/extractor.py backend/tests/test_video_extractor.py
git commit -m "feat(video): extraction en liste de recettes (contrat multi + PDF intact)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2 : Provenance oEmbed + indices de segmentation

**Files:**
- Create: `backend/app/services/video/provenance.py`
- Test: `backend/tests/test_video_provenance.py`

**Interfaces:**
- Produces: `parse_description_timestamps(text: str) -> List[dict]` (`{"sec": int, "label": str}`) ; `chapters_from_info(info: dict) -> List[dict]` (`{"start_sec": int, "title": str}`) ; `fetch_oembed(url, fetcher=None) -> dict` (`{"title","creator","thumbnail"}` ou `{}`) ; `build_source(url, platform, oembed) -> dict` ; `video_id_of(url) -> str|None`.

- [ ] **Step 1 : Écrire les tests qui échouent**

`backend/tests/test_video_provenance.py` :

```python
from app.services.video import provenance as P


def test_parse_description_timestamps_reads_mm_ss_and_hh_mm_ss():
    text = ("Au menu :\n"
            "0:00 Intro\n"
            "1:30 Recette 1 - Pâtes\n"
            "12:05 Recette 2 - Salade\n"
            "1:02:10 Recette 3 - Gâteau\n")
    ts = P.parse_description_timestamps(text)
    assert ts[0] == {"sec": 0, "label": "Intro"}
    assert ts[1] == {"sec": 90, "label": "Recette 1 - Pâtes"}
    assert ts[2]["sec"] == 725
    assert ts[3]["sec"] == 3730


def test_chapters_from_info_maps_youtube_chapters():
    info = {"chapters": [
        {"start_time": 0, "title": "Intro"},
        {"start_time": 90.0, "title": "Pâtes"},
    ]}
    assert P.chapters_from_info(info) == [
        {"start_sec": 0, "title": "Intro"},
        {"start_sec": 90, "title": "Pâtes"},
    ]


def test_video_id_of_extracts_the_id():
    assert P.video_id_of("https://www.youtube.com/watch?v=abc123DEF45") == "abc123DEF45"
    assert P.video_id_of("https://youtu.be/abc123DEF45?t=30") == "abc123DEF45"


def test_fetch_oembed_is_best_effort_and_never_raises():
    def boom(url):  # simulate network/SSRF failure
        raise RuntimeError("blocked")
    assert P.fetch_oembed("https://youtube.com/watch?v=x", fetcher=boom) == {}


def test_fetch_oembed_maps_fields():
    def ok(url):
        return {"title": "Ma vidéo", "author_name": "Chef Gad",
                "thumbnail_url": "https://img/x.jpg"}
    assert P.fetch_oembed("https://youtube.com/watch?v=x", fetcher=ok) == {
        "title": "Ma vidéo", "creator": "Chef Gad", "thumbnail": "https://img/x.jpg",
    }
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `cd backend && ... pytest tests/test_video_provenance.py -q -p no:cacheprovider --no-cov`
Expected : FAIL (`ModuleNotFoundError: app.services.video.provenance`).

- [ ] **Step 3 : Implémenter `provenance.py`**

```python
"""Provenance & indices de segmentation d'une vidéo (best-effort).

- oEmbed YouTube : titre, créateur, miniature — sans clé API.
- Parsing des timestamps de description et des chapitres → indices pour le LLM.
Tout est best-effort : un échec réseau ne bloque jamais l'extraction.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

from app.core.url_guard import assert_safe_fetch_url
from .platforms import youtube_video_id

_TS = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})\s+(.+?)\s*$")


def video_id_of(url: str) -> Optional[str]:
    return youtube_video_id(url)


def parse_description_timestamps(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in (text or "").splitlines():
        m = _TS.match(line)
        if not m:
            continue
        h, mm, ss, label = m.groups()
        sec = (int(h) if h else 0) * 3600 + int(mm) * 60 + int(ss)
        out.append({"sec": sec, "label": label.strip()})
    return out


def chapters_from_info(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for c in (info or {}).get("chapters") or []:
        if c.get("start_time") is None:
            continue
        out.append({"start_sec": int(c["start_time"]), "title": (c.get("title") or "").strip()})
    return out


def _default_fetcher(url: str) -> Dict[str, Any]:  # pragma: no cover - network
    import urllib.request
    assert_safe_fetch_url(url)
    with urllib.request.urlopen(url, timeout=6) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_oembed(url: str, fetcher: Optional[Callable[[str], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Titre/créateur/miniature via oEmbed. Best-effort : {} si échec."""
    fetcher = fetcher or _default_fetcher
    endpoint = "https://www.youtube.com/oembed?format=json&url=" + quote(url, safe="")
    try:
        data = fetcher(endpoint)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "title": data.get("title"),
        "creator": data.get("author_name"),
        "thumbnail": data.get("thumbnail_url"),
    }


def build_source(url: str, platform: str, oembed: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "platform": platform,
        "url": url,
        "video_id": video_id_of(url),
        "title": oembed.get("title"),
        "creator": oembed.get("creator"),
        "thumbnail": oembed.get("thumbnail"),
    }
```

(Vérifier que `platforms.youtube_video_id` existe — il est cité dans la carte du pipeline ; sinon adapter l'import.)

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `cd backend && ... pytest tests/test_video_provenance.py -q -p no:cacheprovider --no-cov`
Expected : PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/video/provenance.py backend/tests/test_video_provenance.py
git commit -m "feat(video): provenance oEmbed + parsing des indices de segmentation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3 : Service → candidats + save par recette + provenance persistée

**Files:**
- Modify: `backend/app/services/recipe_import/service.py` (`save_import`, l.162-190)
- Modify: `backend/app/services/video/service.py`
- Modify: `backend/app/schemas/schemas.py` (l.500-527)
- Modify: `backend/app/api/api_v1/endpoints/video.py` (l.128-142)
- Test: `backend/tests/test_video_service.py`, `backend/tests/test_video_recipe_save.py`

**Interfaces:**
- Consumes: `extractor.extract(text, hints) -> List[dict]` (Task 1) ; `provenance.fetch_oembed/build_source` (Task 2) ; `save_import`.
- Produces: `video_service.save_candidates(db, tenant_id, recipes: List[dict], source: dict) -> List[dict]` ; `extract_*` renvoient `{... , "candidates": List[dict], "source": dict}` (plus de clé `draft`).

- [ ] **Step 1 : Étendre `save_import` (rétro-compatible) + tests**

Ajouter à `test_video_recipe_save.py` (ou son équivalent real_db) un test que `save_import` honore `imported_from` et `recipe_meta` :

```python
def test_save_import_stores_imported_from_and_recipe_meta(db):
    # ... créer tenant + appeler save_import(..., imported_from="video",
    #     recipe_meta={"source": {"video_id": "abc"}}, version_meta_extra={"prep_time_min": 20})
    # puis relire Recipe.meta["source"]["video_id"] == "abc",
    #     RecipeVersion.meta["imported_from"] == "video",
    #     RecipeVersion.meta["prep_time_min"] == 20
```
(écrire ce test au format real_db du fichier existant — fixture `db` + lecture ORM.)

Dans `recipe_import/service.py`, `save_import` (signature l.162-165) : ajouter `imported_from: str = "pdf"`, `recipe_meta: Optional[Dict[str, Any]] = None`, `version_meta_extra: Optional[Dict[str, Any]] = None`. Puis :

```python
    recipe = Recipe(
        id=str(uuid.uuid4()), tenant_id=tenant_id, name=name, yield_qty=servings or 1,
        meta=recipe_meta or None,
    )
    ...
    version = RecipeVersion(
        id=str(uuid.uuid4()), recipe_id=recipe.id, version_number=1, is_published=False,
        notes="\n".join(steps) or None,
        meta={"steps": steps, "imported_from": imported_from, **(version_meta_extra or {})},
    )
```
(PDF inchangé : appel sans ces params → `imported_from="pdf"`, pas de meta extra.)

- [ ] **Step 2 : Schémas — candidat riche + liste + source**

Dans `schemas.py`, remplacer `VideoRecipeDraft`/`VideoExtractResult`/`VideoSaveRequest` (l.506-527) :

```python
class VideoRecipeCandidate(BaseModel):
    name: str = ""
    description: Optional[str] = None
    summary: Optional[str] = None
    yield_qty: Optional[float] = None
    ingredients: List[VideoIngredientDraft] = []
    steps: List[str] = []
    prep_time_min: Optional[float] = None
    cook_time_min: Optional[float] = None
    tips: List[str] = []
    variants: List[str] = []
    allergens: List[str] = []
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None


class VideoSourceInfo(BaseModel):
    platform: Optional[str] = None
    url: Optional[str] = None
    video_id: Optional[str] = None
    title: Optional[str] = None
    creator: Optional[str] = None
    thumbnail: Optional[str] = None


class VideoExtractResult(BaseModel):
    source_id: str
    platform: str
    transcript_source: str
    transcript_excerpt: str
    candidates: List[VideoRecipeCandidate] = []
    source: VideoSourceInfo = VideoSourceInfo()
    note: str


class VideoSaveRequest(BaseModel):
    recipes: List[VideoRecipeCandidate] = []
    source: VideoSourceInfo = VideoSourceInfo()
```
Mettre à jour l'import dans `endpoints/video.py` (`VideoRecipeCandidate`, `VideoSourceInfo` si besoin).

- [ ] **Step 3 : Service — `extract_*` renvoient candidats + source ; `save_candidates`**

Dans `video/service.py` :
- remplacer, dans les trois `extract_*`, `draft = extractor.extract(text, hint_title=…)` par
  `candidates = extractor.extract(text, hints={"title": <title|filename>})` et la clé de retour `"draft": draft` par `"candidates": candidates, "source": <source>`.
- pour `extract_recipe_from_url` : avant l'appel LLM, `oembed = provenance.fetch_oembed(url)` ; `source = provenance.build_source(url, platform, oembed)` ; stocker `source` dans `VideoSource.meta` (`source_row.meta = source`), passer `hints={"title": source.get("title")}`.
- pour `extract_recipe_from_transcript` : `source = provenance.build_source(url or "", "youtube_client", provenance.fetch_oembed(url) if url else {})` ; hints title = `title or source.get("title")`.
- pour `extract_recipe_from_file` : `source = {"platform": "upload", "url": None, "video_id": None, "title": filename, "creator": None, "thumbnail": None}`.
- supprimer `save_draft` et ajouter :

```python
def save_candidates(db, tenant_id, recipes, source):
    """Enregistre chaque recette sélectionnée via le save_import mutualisé,
    en persistant provenance (Recipe.meta['source']) et champs riches
    (RecipeVersion.meta)."""
    from app.services.recipe_import import service as recipe_import_service

    src = source or {}
    vid = src.get("video_id")
    results = []
    for rec in recipes:
        start = rec.get("start_sec")
        deeplink = (
            f"https://youtu.be/{vid}?t={int(start)}" if vid and start is not None
            else (f"https://youtu.be/{vid}" if vid else src.get("url"))
        )
        recipe_meta = {"source": {
            "platform": src.get("platform"), "url": src.get("url"), "video_id": vid,
            "thumbnail": src.get("thumbnail"), "creator": src.get("creator"),
            "start_sec": start, "end_sec": rec.get("end_sec"), "deeplink": deeplink,
        }}
        version_meta_extra = {
            "description": rec.get("description"),
            "prep_time_min": rec.get("prep_time_min"),
            "cook_time_min": rec.get("cook_time_min"),
            "tips": rec.get("tips") or [],
            "variants": rec.get("variants") or [],
            "allergens": rec.get("allergens") or [],
        }
        mapped = [{"name": i.get("name"), "quantity": i.get("qty"),
                   "unit": i.get("unit"), "product_id": i.get("product_id")}
                  for i in (rec.get("ingredients") or [])]
        results.append(recipe_import_service.save_import(
            db, tenant_id, name=(rec.get("name") or "").strip() or "Recette",
            servings=rec.get("yield_qty"), instructions=rec.get("steps") or [],
            ingredients=mapped, imported_from="video",
            recipe_meta=recipe_meta, version_meta_extra=version_meta_extra,
        ))
    return results
```

- [ ] **Step 4 : Endpoint `/video/save` accepte une liste**

Dans `endpoints/video.py` (l.128-142) :

```python
@router.post("/save")
def api_video_save(
    payload: VideoSaveRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    recipes = [r.model_dump() for r in payload.recipes if (r.name or "").strip()]
    if not recipes:
        raise HTTPException(status_code=400, detail="Aucune recette à enregistrer")
    saved = video_service.save_candidates(db, tenant_id, recipes, payload.source.model_dump())
    return {"count": len(saved), "recipes": saved}
```

- [ ] **Step 5 : Adapter les tests service/save**

Dans `test_video_service.py` : les tests d'`extract_*` lisent désormais `res["candidates"]` (liste) au lieu de `res["draft"]`, et `res["source"]`. Le test existant `test_save_draft_delegates_to_the_recipe_import_service` devient `test_save_candidates_delegates_per_recipe` (une liste de 2 recettes → 2 appels `save_import`, steps/ingrédients préservés). Ajouter (real_db, fixture `db`) un test que `save_candidates` persiste `Recipe.meta["source"]["deeplink"]` et `RecipeVersion.meta["imported_from"]=="video"`. Injecter un extracteur factice renvoyant une liste et un `fetcher` oEmbed factice pour rester hors réseau.

- [ ] **Step 6 : Lancer les tests**

Run : `cd backend && ... pytest tests/test_video_service.py tests/test_video_recipe_save.py tests/test_recipe_import*.py -q -p no:cacheprovider --no-cov`
Expected : purs verts ; les real_db (save) collectés-et-skippés en local (PASS en CI) ; PDF intact.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/services/recipe_import/service.py backend/app/services/video/service.py backend/app/schemas/schemas.py backend/app/api/api_v1/endpoints/video.py backend/tests/test_video_service.py backend/tests/test_video_recipe_save.py
git commit -m "feat(video): service renvoie des candidats + save par recette avec provenance

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4 : Web — écran multi-recettes (cartes)

**Files:**
- Modify: `frontend/src/services/types.ts` (l.455-491)
- Modify: `frontend/src/services/video-service.ts`
- Modify: `frontend/src/hooks/use-video.ts`
- Create: `frontend/src/features/video/candidate-card.tsx`
- Modify: `frontend/src/features/video/video-import-view.tsx`

**Interfaces:**
- Consumes: `GET`/`POST /video/extract*` → `{candidates: VideoRecipeCandidate[], source: VideoSourceInfo}` ; `POST /video/save` → `{count, recipes}`.

- [ ] **Step 1 : Types**

Dans `types.ts`, remplacer `VideoRecipeDraft`/`VideoExtractResult` (l.461-476) par :

```ts
export interface VideoRecipeCandidate {
  name: string;
  description: string | null;
  summary: string | null;
  yield_qty: number | null;
  ingredients: VideoIngredientDraft[];
  steps: string[];
  prep_time_min: number | null;
  cook_time_min: number | null;
  tips: string[];
  variants: string[];
  allergens: string[];
  start_sec: number | null;
  end_sec: number | null;
}

export interface VideoSourceInfo {
  platform: string | null;
  url: string | null;
  video_id: string | null;
  title: string | null;
  creator: string | null;
  thumbnail: string | null;
}

export interface VideoExtractResult {
  source_id: string;
  platform: string;
  transcript_source: string;
  transcript_excerpt: string;
  candidates: VideoRecipeCandidate[];
  source: VideoSourceInfo;
  note: string;
}
```

- [ ] **Step 2 : Service + hook (save liste)**

Dans `video-service.ts`, remplacer `saveVideoRecipe` par :

```ts
export async function saveVideoRecipes(payload: {
  recipes: VideoRecipeCandidate[];
  source: VideoSourceInfo;
}): Promise<{ count: number; recipes: VideoSaveResult[] }> {
  const { data } = await api.post("/video/save", payload);
  return data;
}
```
Adapter l'import de type (`VideoRecipeCandidate`, `VideoSourceInfo`) et le hook `use-video.ts` (`useSaveVideoRecipes`) en conséquence (renvoie la liste, invalide la liste des recettes, toast « N recettes enregistrées »).

- [ ] **Step 3 : Composant carte `candidate-card.tsx`**

Extraire l'éditeur mono-recette actuel (`video-import-view.tsx`, bloc l.211-301) en un composant contrôlé `<CandidateCard>` :

```tsx
"use client";
import { useState } from "react";

export interface CandidateState extends VideoRecipeCandidate { selected: boolean; }

export function emojiFor(name: string): string {
  const n = (name || "").toLowerCase();
  if (/(gâteau|gateau|tarte|dessert|cake|cookie)/.test(n)) return "🍰";
  if (/(salade|crudité)/.test(n)) return "🥗";
  if (/(soupe|velouté|potage)/.test(n)) return "🍲";
  if (/(pâtes|pates|pasta|spaghetti|lasagne)/.test(n)) return "🍝";
  return "🍽️";
}

export function CandidateCard({
  value, index, videoId, onChange, onDelete, onToggle, onMerge,
}: {
  value: CandidateState; index: number; videoId: string | null;
  onChange: (v: CandidateState) => void; onDelete: () => void;
  onToggle: () => void; onMerge: () => void;
}) {
  const [open, setOpen] = useState(false);
  // Repliée : emoji + nom + puces (portions · prépa/cuisson · N ingrédients ·
  //   plage horaire → lien youtu.be/<id>?t=<start_sec> si start_sec != null).
  // Dépliée : champs nom / portions / lignes d'ingrédients (name/qty/unit) /
  //   étapes (textarea), + champs riches. Toute édition => onChange({...value, ...}).
  // Actions : checkbox (onToggle), Éditer (setOpen), Supprimer (onDelete),
  //   Fusionner (onMerge).
  // Réutiliser les mêmes contrôles que l'éditeur actuel (l.211-301) — ne pas
  //   réinventer les lignes d'ingrédients.
  return (/* … */ null);
}
```
(Transcrire les contrôles d'édition existants du bloc l.211-301, en les câblant sur `value`/`onChange` au lieu de l'état plat.)

- [ ] **Step 4 : Vue liste `video-import-view.tsx`**

Remplacer l'état plat (l.47-53) et `loadDraft` (l.60-67) par :

```tsx
const [candidates, setCandidates] = useState<CandidateState[]>([]);
const [source, setSource] = useState<VideoSourceInfo | null>(null);
const [mergeFrom, setMergeFrom] = useState<number | null>(null);

function loadResult(res: VideoExtractResult) {
  setSource(res.source);
  setCandidates(res.candidates.map((c) => ({ ...c, selected: true })));
}

function mergeInto(target: number) {
  // fusionne candidates[mergeFrom] dans candidates[target] :
  // ingredients+steps concaténés, start=min, end=max, tips/variants/allergens=union,
  // puis retire la carte absorbée. Réinitialise mergeFrom.
}
```
- En-tête : `Nous avons détecté ${candidates.length} recette(s)`.
- Rendre `candidates.map((c, i) => <CandidateCard ... />)`.
- Pied : bascule tout (dé)sélectionner + bouton « Enregistrer les N sélectionnées » (`candidates.filter(c=>c.selected)`) → `useSaveVideoRecipes().mutate({ recipes: selected, source })`.
- Le résultat (l.303-345) devient « N recettes enregistrées » avec liens `/recettes/${id}`.
- `onSave` (l.102) et l'ancien state mono-recette sont supprimés.

- [ ] **Step 5 : Vérifier types/lint/build**

Run : `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected : PASS. (Si build bloqué disque/RAM : `TMP=D:/Dev/Temp/claude/next-build TEMP=D:/Dev/Temp/claude/next-build npm run build` ; sinon corriger le vrai problème de type.)

- [ ] **Step 6 : Commit**

```bash
git add frontend/src/services/types.ts frontend/src/services/video-service.ts frontend/src/hooks/use-video.ts frontend/src/features/video/candidate-card.tsx frontend/src/features/video/video-import-view.tsx
git commit -m "feat(video): écran multi-recettes (cartes sélectionnables) sur le web

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5 : Mobile — écran multi-recettes (cartes)

**Files:**
- Modify: `mobile/lib/features/video/video_import_screen.dart`
- Create: `mobile/test/video_import_test.dart`

**Interfaces:**
- Consumes: `POST /video/extract-transcript` (et `/extract`, `/extract-file`) → `{candidates: [...], source: {...}}` ; `POST /video/save` → `{count, recipes}`.

- [ ] **Step 1 : Widget test qui échoue**

`mobile/test/video_import_test.dart` — sur le modèle de `recipe_pdf_import_test.dart` : faux `HttpClientAdapter` répondant à `/video/extract-transcript` avec un `candidates` de 2 recettes + `source`, pomper `VideoImportScreen`, et attendre :

```dart
expect(find.textContaining('2 recette'), findsOneWidget); // "Nous avons détecté 2 recettes"
expect(find.text('Pâtes'), findsOneWidget);
expect(find.text('Salade'), findsOneWidget);
```
(RED d'abord : l'écran actuel n'affiche qu'un formulaire.)

- [ ] **Step 2 : Vérifier l'échec**

Run : `cd mobile && D:/flutter/bin/flutter test test/video_import_test.dart` (ou `flutter.bat`).
Expected : FAIL.

- [ ] **Step 3 : Refondre `_applyDraft` → `_applyCandidates` + liste de cartes**

Dans `video_import_screen.dart` : remplacer l'état plat (`_name/_portions/_steps/_ings/_hasDraft`, l.41-48) par `List<Map<String,dynamic>> _candidates` (+ un flag `selected` par élément) et `Map<String,dynamic>? _source`. `_applyDraft` (l.129-143) devient `_applyCandidates(data)` lisant `data['candidates']` + `data['source']`. Le bloc éditable unique (l.285-410) devient une liste de cartes extensibles (aperçu replié / édition dépliée), avec supprimer / fusionner / cocher. `_save` (l.184) poste `{"recipes": <sélection éditée>, "source": _source}` sur `/video/save`. Le fetch captions on-device (`_fetchYoutubeCaptions`, l.67) est inchangé.

- [ ] **Step 4 : Test + analyze**

Run : `cd mobile && D:/flutter/bin/flutter test test/video_import_test.dart && D:/flutter/bin/flutter analyze lib/features/video/video_import_screen.dart`
Expected : test PASS ; analyze `No issues found`.

- [ ] **Step 5 : Commit**

```bash
git add mobile/lib/features/video/video_import_screen.dart mobile/test/video_import_test.dart
git commit -m "feat(video): écran multi-recettes (cartes) sur mobile

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6 : PR, CI verte, validation live

**Files:** aucun (intégration).

- [ ] **Step 1 : Pousser + PR**

```bash
git push -u origin HEAD
gh pr create --base main --title "feat(video): import vidéo multi-recettes" --body "$(cat <<'EOF'
Une vidéo YouTube → TOUTES ses recettes, chacune éditable/fusionnable/enregistrable.

- Extraction en liste (_normalize_one + _normalize_many, PDF intact).
- Détection LLM + métadonnées (provenance oEmbed, indices chapitres/timestamps), sans OCR.
- Pipeline synchrone : candidats en mémoire ; save par recette via save_import (matching+coût).
- Provenance + champs riches persistés en meta JSONB (aucune migration).
- UI cartes multi-recettes web + mobile.

Spec : docs/superpowers/specs/2026-07-27-video-multi-recettes-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2 : CI verte**

Vérifier `Backend — tests` (real_db du save), `Web — lint/types/build`, `Mobile — analyze`. Corriger si rouge, re-pousser.

- [ ] **Step 3 : Validation live (RÈGLE ABSOLUE)** — après merge (déclenche le déploiement)

Avec de **vraies URLs YouTube** couvrant la matrice — **1 recette, 2 recettes, 5 recettes, menu complet, compilation, Short multi-préparations, avec chapitres, sans chapitres, recettes à ingrédients partagés** :
- **Web (Playwright)** : coller l'URL → « Nous avons détecté N recettes » → éditer/fusionner/désélectionner → enregistrer les sélectionnées → vérifier N fiches créées, provenance (miniature/créateur/deeplink) présente. Vérifier le cas **1 recette** (liste à 1 carte, save identique).
- **Mobile (émulateur `foodgad`)** : même parcours ; surveiller `logcat` (aucune exception Flutter).
- **Aucune recette oubliée** : le nombre de cartes = nombre de recettes réellement présentes.
- **Nettoyer** toutes les fiches de test créées via l'API après validation.

- [ ] **Step 4 : Mémoire**

Mettre à jour [[video-import-module]] : passage mono→multi-recettes (PR #), provenance en meta, contrat `_normalize_one`/`_normalize_many` partagé avec le PDF.

---

## Self-Review

**1. Spec coverage :**
- Détecter/séparer/retranscrire toutes les recettes, jamais s'arrêter à la première, retour liste → Task 1 (prompt + `_normalize_many` + `extract→List`). ✓
- Champs par recette (nom, description, ingrédients/qty/unités, étapes, prep/cook, portions, conseils, variantes, allergènes) → forme normalisée Task 1 + schéma candidat Task 3. ✓
- Détection LLM + indices (chapitres/timestamps/titre) → hints Task 1 + provenance Task 2. ✓ (OCR explicitement hors périmètre.)
- Pipeline Video→List<Candidate>→validation→List<Recipe> → service Task 3. ✓
- UI « N recettes détectées » + cartes preview/édit/suppr/fusion/select + save all/certaines → Tasks 4 (web) & 5 (mobile). ✓
- Conserver vidéo source/timestamps/lien/miniature/créateur → provenance Task 2 + `Recipe.meta["source"]` Task 3. ✓
- Cas particuliers (1/2/5/menu/compilation/Short/chapitres/sans/ingrédients partagés) → fixtures Task 1 + validation live Task 6. ✓
- Non-régression 1 recette + PDF intact → Task 1 (PDF `_normalize_one`), `test_extract_single_recipe_still_yields_a_one_element_list`, Task 6. ✓
- Aucune duplication : réutilise `save_import`, `_parse_json` ; extrait `<CandidateCard>` du bloc existant. ✓

**2. Placeholder scan :** les tâches UI (3-5) portent les nouveaux types, la forme d'état, la structure du composant et le câblage de save en code concret ; les contrôles d'édition d'ingrédients sont explicitement « transcrire l'existant l.211-301 / l.285-410 » (pas de logique inventée). Aucun « TBD/gérer les cas limites » sans code. ✓

**3. Type consistency :** la forme normalisée (Global Constraints) est identique dans `_normalize_one` (T1), le schéma `VideoRecipeCandidate` (T3), le type TS (T4) et la lecture Dart (T5) ; `extract(text, hints)→List` (T1) consommé par `extract_*` (T3) ; `save_candidates(db, tenant, recipes, source)` (T3) consommé par l'endpoint (T3) et les UIs (T4/T5) via `{recipes, source}`. ✓

**Note de rigueur inter-tâches :** les tests de save (`save_candidates`/`save_import` meta) touchent la BDD → écrits en real_db, rouges/skippés en local, prouvés en CI (Task 6), conformément à [[never-mock-the-db-session]].
