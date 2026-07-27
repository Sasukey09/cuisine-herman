# Import vidéo multi-recettes

**Date :** 2026-07-27
**Statut :** design validé, prêt pour le plan d'implémentation
**Périmètre :** faire évoluer le module d'import vidéo YouTube de « 1 vidéo → 1 recette » à « 1 vidéo → **toutes** ses recettes », chacune enregistrable indépendamment. **Sans dupliquer le pipeline existant.**

## Contexte

Le pipeline vidéo actuel (`backend/app/services/video/`) est **synchrone** et extrait **une seule** recette. Le verrou « une recette » vit à 5 endroits, mais le plus coûteux est déjà mutualisé :

- **Racine du verrou** : `video/extractor.py` — `SYSTEM_PROMPT` demande « un objet JSON » et `_normalize` renvoie **un** dict. En découlent : le schéma `VideoExtractResult.draft` (objet unique), les `extract_*` du service (un `draft`), et les deux UIs (formulaire unique).
- **Déjà réutilisable par recette** : la sauvegarde + matching produit + calcul de coût passe par `recipe_import.service.save_import` (mutualisé avec l'import PDF) — **il sauve déjà une recette par appel**.
- **Patron 1→N déjà présent** ailleurs (import PDF `RecipeImportJob → RecipeImportResult`) — mais **on ne l'utilise pas** ici : décision produit validée = pipeline **synchrone, candidats en mémoire** (voir §2).

**Objectif** : détecter, séparer et retranscrire **toutes** les recettes d'une vidéo — une recette ne doit jamais en masquer une autre. Détection = **LLM + métadonnées** (chapitres YouTube, timestamps de description), **sans OCR ni traitement d'image**.

## Décisions de cadrage (validées)

1. **Détection = LLM + métadonnées.** Un seul appel LLM voit toute la transcription et renvoie une **liste** de recettes avec bornes temporelles, en s'appuyant sur les chapitres YouTube et les timestamps de la description comme indices. Pas d'extraction de frames, pas d'OCR.
2. **Pipeline synchrone, candidats en mémoire.** La requête renvoie directement la liste de candidats (au lieu d'un seul `draft`). L'UI tient la liste, l'édite/fusionne localement, puis POST les recettes sélectionnées. **Aucune nouvelle table, aucune migration** ; risque de timeout STT sur très longue vidéo = pré-existant, non aggravé (l'appel LLM reste unique).

## Section 1 — Le contrat d'extraction (`video/extractor.py`)

**Nouveau `SYSTEM_PROMPT`** exigeant explicitement **toutes** les recettes, en **liste**, sans jamais s'arrêter à la première. Extrait de l'esprit du prompt (à rédiger en FR) :

> « Détecte **toutes** les recettes présentes dans cette vidéo. Ne t'arrête **jamais** à la première. Retourne une **liste complète**. Utilise les indices : changement de titre, "ensuite"/"maintenant"/"deuxième recette", changement d'ingrédients/étapes, chapitres et timestamps fournis. »

**Sortie JSON attendue** — un objet enveloppe avec un tableau :

```json
{"recipes": [
  {"name": str, "description": str, "yield_qty": number|null,
   "ingredients": [{"name": str, "qty": number|null, "unit": str|null}],
   "steps": [str], "prep_time_min": number|null, "cook_time_min": number|null,
   "tips": [str], "variants": [str], "allergens": [str],
   "start_sec": number|null, "end_sec": number|null, "summary": str}
]}
```

**Refactor sans casse :**
- L'actuel `_normalize(obj)` devient **`_normalize_one(obj)`** : une recette, enrichie des nouveaux champs (défauts tolérants : listes vides, `None` pour les temps).
- Nouveau **`_normalize_many(parsed) -> List[dict]`** : accepte `{"recipes": [...]}` **ou** un objet unique (robustesse / rétro-compat si le LLM renvoie un seul objet), applique `_normalize_one` à chaque, et **filtre les recettes vides** (`name` et `ingredients` tous deux vides).
- `RecipeExtractor.extract(text, hints=None) -> List[dict]` (au lieu d'un dict). `hints` = `{chapters: [...], description_timestamps: [...], title: str|None}` injectés dans le message utilisateur. Lève `RecipeExtractionError` **seulement si la liste finale est vide**.
- `_parse_json` est **inchangé** et réutilisé.

**Dérivation des bornes temporelles (`start_sec`/`end_sec`).** Elles viennent des **indices de métadonnées** : le LLM rattache chaque recette à un chapitre / timestamp de description. **Sans chapitre ni timestamp dans la vidéo, les bornes sont `null`** (best-effort) — les recettes restent **séparées par le contenu** (titres, ingrédients, marqueurs « ensuite »…), simplement sans découpage horaire précis. C'est cohérent avec le cadrage « LLM + métadonnées » : on ne fabrique pas un timing qu'on n'a pas. Le deeplink n'est ajouté que si `start_sec` est connu.

**Non-régression PDF :** `recipe_import/extractor.py` importe aujourd'hui `_parse_json` **et** `_normalize` depuis `video/extractor.py`. On le fait importer `_normalize_one` (renommage 1:1) → l'import PDF reste strictement mono-recette, mutualisation préservée.

## Section 2 — Service, endpoint, provenance (`video/service.py`, `endpoints/video.py`)

- Les `extract_*` (`extract_recipe_from_url`, `extract_recipe_from_transcript`, `extract_recipe_from_file`) renvoient `candidates: List[dict]` au lieu de `draft`. **Un seul appel LLM.**
- **Provenance** : à l'acquisition (URL YouTube), récupérer via **YouTube oEmbed** (`https://www.youtube.com/oembed?url=...&format=json`, **sans clé API**) : `title`, `author_name` (créateur), `thumbnail_url`. Parser chapitres / timestamps de description quand disponibles. Stocker le tout dans `VideoSource.meta` (colonne JSONB déjà présente, aujourd'hui inutilisée). L'appel oEmbed passe par le garde-fou SSRF `assert_safe_fetch_url` et échoue **silencieusement** (provenance best-effort — jamais bloquante pour l'extraction).
- **Save** : `POST /video/save` accepte désormais une **liste** de recettes sélectionnées (+ la provenance). Le service itère et délègue **par recette** au `save_import` **existant** (matching produit + coût — que la vidéo n'utilisait même pas jusqu'ici). Pour chaque recette créée on persiste :
  - la **provenance** dans `Recipe.meta["source"]` = `{platform, url, video_id, thumbnail, creator, start_sec, end_sec, deeplink}` où `deeplink` = `https://youtu.be/<id>?t=<start_sec>` ;
  - les **champs riches** (`prep_time_min`, `cook_time_min`, `tips`, `variants`, `allergens`, `description`) dans `RecipeVersion.meta` ;
  - `imported_from = "video"` (aujourd'hui codé en dur `"pdf"` dans `save_import` — on le paramètre : `save_import(..., imported_from="pdf")` avec la vidéo passant `"video"`).
- **Schémas** (`schemas.py`) : nouveau `VideoRecipeCandidate` (tous les champs ci-dessus) ; `VideoExtractResult.draft` → `candidates: List[VideoRecipeCandidate]` ; `VideoExtractResult` gagne `source: {video_id, url, platform, title, creator, thumbnail}`. `VideoSaveRequest` → liste de recettes + `source`. Types miroir web `frontend/src/services/types.ts`.
- **Aucune nouvelle table, aucune migration** : tout tient dans les `meta` JSONB existants (`VideoSource.meta`, `Recipe.meta`, `RecipeVersion.meta`).

## Section 3 — L'écran multi-recettes (web + mobile, stricte parité)

Les deux clients passent d'un **formulaire unique** à une **liste de candidats**. L'éditeur mono-recette actuel est **refactorisé en composant réutilisable par carte** (amélioration ciblée : `video-import-view.tsx` fait déjà 349 lignes ; on en extrait un `<CandidateCard>`/éditeur).

- **En-tête** : « **Nous avons détecté N recette(s)** ».
- **Une carte par candidat** :
  - **repliée = aperçu** : emoji, nom, puces (portions · prépa/cuisson · N ingrédients · plage horaire cliquable → deeplink YouTube `&t=Ns`) ;
  - **dépliée = édition** : le formulaire actuel (nom / portions / lignes d'ingrédients / étapes) réutilisé, + les champs riches.
- **Actions par carte** : éditer (déplier), **supprimer** (retire de la liste en mémoire), **fusionner** (choisir une autre carte → ingrédients + étapes concaténés ; bornes = `min(start)`/`max(end)` ; allergènes/conseils/variantes = union ; la carte absorbée disparaît), **case « à enregistrer »**.
- **Pied** : bascule tout sélectionner / désélectionner + bouton « **Enregistrer les N sélectionnées** » → un POST `/video/save`. Retour : « N recettes enregistrées » avec liens vers les fiches.
- **Emoji** : petite heuristique par mots-clés du nom (gâteau/tarte→🍰, salade→🥗, soupe→🍲, pâtes→🍝, …) avec repli 🍽️ — purement cosmétique.
- **Mobile** (`video_import_screen.dart`) : identique. Le fetch des captions on-device via `youtube_explode_dart` (IP résidentielle) → `POST /video/extract-transcript` reste inchangé ; seule la partie « draft unique » devient « liste de cartes ».

## Section 4 — Compatibilité, tests, validation live

- **Non-régression 1 recette (test clé)** : une vidéo mono-recette produit une liste à **1 élément** et se sauve à l'identique.
- **Tests purs backend** (`test_video_extractor.py`, `FakeClient` renvoyant du JSON déterministe) : `_normalize_one` ; `_normalize_many` (entrée `{"recipes":[...]}`, objet unique en repli, recettes vides filtrées) ; `extract` renvoie une liste. Fixtures de transcription couvrant la matrice : **1, 2, 5 recettes, menu complet, compilation, Short multi-préparations, avec/sans chapitres, recettes partageant des ingrédients** (chaque candidat reste indépendant — mêmes ingrédients ne fusionnent pas les recettes).
- **Service / save** (`test_video_service.py`, `test_video_recipe_save.py`) : `extract_*` renvoient la liste ; le save itère et délègue **par recette** à `save_import` ; provenance persistée dans `meta` ; `imported_from="video"`. Le test existant `test_save_draft_delegates_to_the_recipe_import_service` est adapté à la nouvelle signature liste.
- **PDF intact** : `test_recipe_import*` restent verts (`recipe_import/extractor.py` importe `_normalize_one`).
- **Web** : `tsc` / lint / build + test de composant (rendu de N cartes, sélection, suppression, fusion, save). **Mobile** : `flutter analyze` + widget test sur le modèle de `recipe_pdf_import_test.dart` (faux backend renvoyant N candidats → N cartes rendues).
- **Validation live (RÈGLE ABSOLUE)** : avec de **vraies URLs YouTube** couvrant la matrice ci-dessus (Playwright web + émulateur `foodgad`), vérifier que **toutes** les recettes sortent, qu'**aucune n'est oubliée**, et que le cas 1-recette fonctionne toujours. Surveiller `logcat` (aucune exception Flutter). Nettoyer les fiches de test créées après validation.
  *(L'extraction réelle passe par le LLM/réseau — impossible en CI ; les tests automatisés utilisent donc des transcriptions-fixtures + `FakeClient`, et le réel se valide en live, comme les autres modules.)*

## Mapping des champs riches → modèle canonique (rappel)

| Champ candidat | Persistance à la sauvegarde |
|---|---|
| name | `Recipe.name` |
| yield_qty (portions) | `Recipe.yield_qty` |
| ingredients (name/qty/unit) | `save_import` → matching produit + `RecipeIngredient` |
| steps | `save_import` → `RecipeInstruction` |
| description, summary | `RecipeVersion.notes` / `RecipeVersion.meta` |
| prep_time_min, cook_time_min, tips, variants, allergens | `RecipeVersion.meta` (JSONB) |
| start_sec, end_sec, url, video_id, thumbnail, creator, deeplink | `Recipe.meta["source"]` (JSONB) |

Aucune colonne ajoutée : tout va dans les `meta` JSONB existants.

## Hors périmètre (YAGNI)

- OCR / analyse de frames (indice « texte à l'écran ») — écarté au cadrage.
- Pipeline asynchrone / persistance des candidats (job → résultats) — écarté au cadrage (synchrone en mémoire).
- Aperçu de coût par candidat au moment de l'extraction (le `_build_preview` du PDF) — non requis ; le coût est calculé à la sauvegarde via `save_import`. Réutilisable plus tard si besoin.

## Contraintes de livraison (rappel)

Branche → CI verte → merge (jamais de push direct sur `main`) ; jamais de mock de la session BDD (tests contre un vrai Postgres pour tout ce qui touche la BDD) ; ids de révision Alembic ≤ 32 car. (ici **aucune migration**) ; RÈGLE ABSOLUE : « terminé » seulement après validation live Android + Web + Playwright + PostgreSQL réel ; nettoyage des données de test après validation ; ne jamais déclencher de build Codemagic sans accord explicite.
