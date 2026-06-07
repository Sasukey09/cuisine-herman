"""Fuzzy product matcher (canonical model).

Matches an OCR/invoice line against the tenant's products and aliases.
Ported from the former app.domain layer onto app.models.models so it works
against the real (migrated) schema.
"""
import re
from difflib import SequenceMatcher
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.crud import crud_match


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Frequent invoice words that carry no product meaning — ignored when comparing
# token sets so they can't create (or block) a match on their own.
_STOPWORDS = {
    "de", "du", "des", "le", "la", "les", "l", "au", "aux", "en", "et", "a",
    "kg", "g", "gr", "l", "ml", "cl", "pcs", "pc", "piece", "pieces", "unite",
    "x", "lot", "carton", "colis", "bte", "boite", "sachet", "pack",
}


def _tokens(s: str) -> set:
    """Significant tokens of a string, singularised (trailing 's' dropped)."""
    out = set()
    for t in _normalize(s).split():
        if t in _STOPWORDS:
            continue
        if len(t) > 3 and t.endswith("s"):
            t = t[:-1]
        out.add(t)
    return out


def _partial_ratio(a: str, b: str) -> float:
    """Best ratio of the shorter string against any same-length window of the
    longer one (catches 'tomate' inside 'tomates rondes bio')."""
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    n = len(shorter)
    if n == 0:
        return 0.0
    if n == len(longer):
        return SequenceMatcher(None, shorter, longer).ratio()
    best = 0.0
    for i in range(len(longer) - n + 1):
        best = max(best, SequenceMatcher(None, shorter, longer[i:i + n]).ratio())
        if best == 1.0:
            break
    return best


def _fuzzy_score(a: str, b: str) -> float:
    """Similarity in [0,100] combining whole-string ratio, substring ratio and
    token containment, so multi-word invoice labels still match short product
    names (and vice-versa)."""
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    partial = _partial_ratio(a, b)
    ta, tb = _tokens(a), _tokens(b)
    shared = len(ta & tb) if (ta and tb) else 0
    containment = shared / min(len(ta), len(tb)) if (ta and tb) else 0.0
    score = max(ratio, partial, containment)
    # A match resting on a single shared word between multi-word labels (e.g.
    # "Lait" vs "Tablette chocolat au lait") is only a hint: keep it just below
    # the auto-accept threshold so it surfaces for manual review instead of
    # silently binding a wrong product. Near-identical strings are exempt.
    if shared <= 1 and ta and tb and max(len(ta), len(tb)) > 1 and ratio < 0.8:
        score = min(score, 0.78)
    return score * 100.0


def match_product(
    db: Session, tenant_id: str, ocr_text: str, fuzzy_min_score: float = 60.0
) -> Dict[str, Any]:
    """Attempt to match an OCR line to a product.

    Returns a dict: product_id, confidence_score, match_type, manual_review, matched_alias.
    Persists the result when ``db`` is provided.
    """
    norm = _normalize(ocr_text)

    products = crud_match.get_products_for_tenant(db, tenant_id)
    aliases = crud_match.get_aliases_for_tenant(db, tenant_id)

    name_map = {}
    sku_map = {}
    for p in products:
        name_map[_normalize(p.name or "")] = p
        if getattr(p, "sku", None):
            sku_map[_normalize(str(p.sku))] = p

    alias_map = {_normalize(a.alias): a for a in aliases}

    def _finalize(product_id, confidence, match_type, matched_alias):
        manual = confidence < 80.0
        if db is not None:
            crud_match.save_match_result(
                db, tenant_id, ocr_text, product_id, confidence, match_type, manual
            )
        return {
            "product_id": product_id,
            "confidence_score": confidence,
            "match_type": match_type,
            "manual_review": manual,
            "matched_alias": matched_alias,
        }

    # Exact SKU
    if norm in sku_map:
        return _finalize(str(sku_map[norm].id), 100.0, "exact_sku", None)

    # Exact name
    if norm in name_map:
        return _finalize(str(name_map[norm].id), 100.0, "exact_name", None)

    # Exact alias
    if norm in alias_map:
        a = alias_map[norm]
        return _finalize(str(a.product_id), 95.0, "alias", a.alias)

    # Fuzzy over names and aliases
    best = {"product_id": None, "score": 0.0, "match_type": None, "matched_alias": None}
    for p in products:
        score = _fuzzy_score(norm, _normalize(p.name or ""))
        if score > best["score"]:
            best = {"product_id": str(p.id), "score": score, "match_type": "fuzzy_name", "matched_alias": None}
    for a in aliases:
        score = _fuzzy_score(norm, _normalize(a.alias or ""))
        if score > best["score"]:
            best = {"product_id": str(a.product_id), "score": score, "match_type": "fuzzy_alias", "matched_alias": a.alias}

    if best["score"] >= fuzzy_min_score:
        return _finalize(best["product_id"], float(best["score"]), best["match_type"], best["matched_alias"])

    # No good match -> needs manual review
    return _finalize(None, 0.0, "none", None)
