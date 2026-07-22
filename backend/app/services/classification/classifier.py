"""Rule-based product classifier.

The `product_categories` table + `Product.category_id` existed but were never
written — every product's category was NULL, so filtering, the "cheaper
alternative" tool and the whole notion of a category silently no-op'd. This
module assigns a category from the product's name (and optional supplier /
description text) so classification actually works.

It is deliberately deterministic and dependency-free: French keyword matching,
accent- and plural-insensitive, first-listed category wins ties, `"Autres"` when
nothing matches. The user can always override the result. An AI fallback for the
genuinely ambiguous cases lives in `ai_fallback` and is opt-in (used by the smart
invoice import), so the hot create path stays fast and predictable.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Optional, Tuple

# The canonical taxonomy shown in the UI. Order is also the tie-break priority
# (a name matched by two categories goes to the one listed first here — e.g.
# "Poisson" before "Viande" so "filet de saumon" is fish, "filet de bœuf" meat).
CATEGORIES: List[str] = [
    "Viande",
    "Poisson",
    "Légumes",
    "Fruits",
    "Produits laitiers",
    "Boulangerie",
    "Épicerie",
    "Boissons",
    "Surgelés",
    "Desserts",
    "Condiments",
    "Hygiène",
    "Emballages",
    "Autres",
]

DEFAULT_CATEGORY = "Autres"


def _norm(s: Optional[str]) -> str:
    """Lowercase and strip accents so 'Légumes' and 'legumes' match alike.

    Ligatures (œ/æ) are not decomposed by NFD, so 'bœuf' would never match the
    keyword 'boeuf' — expand them first."""
    s = (s or "").replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae").replace("Æ", "ae")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


# Keyword lists are already accent-stripped (normalized form). Single-word
# keywords match whole tokens (with common French plural endings); multi-word
# keywords match as a phrase and count double (they are far more specific).
# Order MUST follow CATEGORIES for the tie-break to hold; Poisson is checked
# before Viande on purpose.
_RULES: List[Tuple[str, List[str]]] = [
    ("Poisson", [
        "poisson", "poissonnerie", "poissonnier", "saumon", "thon", "cabillaud",
        "colin", "merlu", "truite", "bar", "dorade", "sole", "lieu", "morue", "hareng",
        "sardine", "maquereau", "anchois", "crevette", "gambas", "moule", "huitre",
        "calamar", "poulpe", "seiche", "crustace", "homard", "langoustine", "surimi",
        "lotte", "raie", "eglefin",
        "fruits de mer", "noix de saint jacques", "saint jacques", "coquille saint",
    ]),
    ("Viande", [
        "boeuf", "veau", "porc", "agneau", "mouton", "poulet", "volaille", "dinde",
        "canard", "lapin", "jambon", "saucisse", "saucisson", "lardon", "lardons",
        "bacon", "steak", "escalope", "cote", "cotelette", "entrecote", "merguez",
        "chipolata", "viande", "hache", "rumsteck", "paleron", "gigot", "magret",
        "cuisse", "aiguillette", "andouille", "boudin", "rillettes", "charcuterie",
        "cordon bleu", "chair a saucisse", "roti",
    ]),
    ("Produits laitiers", [
        "lait", "beurre", "creme", "fromage", "yaourt", "yogourt", "mozzarella",
        "parmesan", "emmental", "gruyere", "comte", "cheddar", "mascarpone", "ricotta",
        "feta", "chevre", "camembert", "brie", "raclette", "reblochon", "oeuf", "oeufs",
        "creme fraiche", "fromage blanc", "petit suisse", "lait entier",
        "lait demi ecreme", "cancoillotte", "boursin",
    ]),
    ("Boulangerie", [
        "pain", "baguette", "brioche", "viennoiserie", "croissant", "chocolatine",
        "levure", "boulangerie", "fougasse", "ciabatta", "focaccia", "pita", "naan",
        "tortilla", "wrap", "pain de mie", "pain au chocolat", "pate a pain",
        "pain burger", "bun",
    ]),
    # Légumes before Fruits so an ambiguous "tomates cerises" (a vegetable whose
    # name also carries the fruit word "cerise") lands on Légumes.
    ("Légumes", [
        "tomate", "carotte", "oignon", "courgette", "salade", "laitue", "patate",
        "poireau", "epinard", "chou", "poivron", "aubergine", "champignon", "ail",
        "echalote", "legume", "brocoli", "concombre", "radis", "betterave", "navet",
        "celeri", "fenouil", "artichaut", "asperge", "courge", "potiron", "citrouille",
        "mais", "endive", "blette", "panais", "gingembre", "piment", "haricot vert",
        "pomme de terre", "pommes de terre", "petit pois", "patate douce",
    ]),
    ("Fruits", [
        "pomme", "banane", "orange", "citron", "fraise", "framboise", "raisin",
        "poire", "peche", "abricot", "ananas", "mangue", "kiwi", "melon", "pasteque",
        "cerise", "fruit", "myrtille", "prune", "clementine", "mandarine",
        "pamplemousse", "nectarine", "figue", "grenade", "litchi", "cassis",
        "groseille", "mure", "datte", "avocat", "fruit de la passion", "noix de coco",
    ]),
    ("Desserts", [
        "gateau", "tarte", "biscuit", "entremets", "mousse", "patisserie", "macaron",
        "eclair", "meringue", "flan", "tiramisu", "cheesecake", "cookie", "madeleine",
        "financier", "sorbet", "chocolat", "cacao", "confiserie", "bonbon", "nutella",
        "creme dessert", "pate a tartiner", "glace vanille",
    ]),
    ("Boissons", [
        "eau", "jus", "soda", "vin", "biere", "cidre", "cafe", "the", "boisson",
        "limonade", "sirop", "cola", "coca", "perrier", "evian", "champagne", "alcool",
        "whisky", "vodka", "rhum", "pastis", "tonic", "schweppes", "smoothie",
        "ice tea", "eau gazeuse", "eau minerale", "jus de fruit", "boisson vegetale",
    ]),
    ("Surgelés", [
        "surgele", "congele", "glacon", "frozen", "legumes surgeles", "frites surgelees",
    ]),
    ("Condiments", [
        "moutarde", "ketchup", "mayonnaise", "sauce", "epice", "herbe", "poivre", "sel",
        "curry", "paprika", "condiment", "cornichon", "capre", "harissa", "pesto",
        "vinaigre", "vinaigrette", "tabasco", "cumin", "curcuma", "cannelle", "muscade",
        "origan", "basilic", "thym", "laurier", "persil", "coriandre", "bouillon",
        "aromate", "sauce soja", "fond de veau", "concentre de tomate",
    ]),
    ("Épicerie", [
        "farine", "sucre", "riz", "pate", "pates", "huile", "conserve", "lentille",
        "pois chiche", "semoule", "couscous", "boulgour", "quinoa", "cereale", "flocon",
        "miel", "confiture", "compote", "chapelure", "maizena", "fecule", "gelatine",
        "biscotte", "tapioca", "polenta", "noix", "amande", "noisette", "olive",
        "gnocchi", "raisin sec", "fruit sec", "levure chimique", "huile d olive",
    ]),
    ("Hygiène", [
        "savon", "nettoyant", "detergent", "eponge", "essuie", "desinfectant",
        "hygiene", "javel", "lessive", "gant", "gants", "sopalin", "desodorisant",
        "degraissant", "papier toilette", "liquide vaisselle", "produit vaisselle",
        "gel hydroalcoolique", "spray nettoyant", "essuie tout",
    ]),
    ("Emballages", [
        "emballage", "sac", "sachet", "barquette", "carton", "boite", "gobelet",
        "couvercle", "serviette", "aluminium", "ramequin", "opercule", "paille",
        "film alimentaire", "film etirable", "papier alu", "papier cuisson",
        "papier sulfurise", "couvert jetable", "assiette jetable", "sac poubelle",
    ]),
]


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text))


def _token_hit(kw: str, tokens: set) -> bool:
    # Match the keyword or a common French plural (s / x / es) as a whole token,
    # so "tomates" matches "tomate" but "laitue" never matches "lait".
    return not tokens.isdisjoint({kw, kw + "s", kw + "x", kw + "es"})


def classify(name: str, extra: Optional[str] = None) -> str:
    """Return the best category for a product name, `"Autres"` if none matches.

    `extra` may carry supplier name / description to disambiguate. Multi-word
    keywords weigh double (they are specific); ties go to the earlier category.
    """
    text = _norm(f"{name or ''} {extra or ''}")
    if not text.strip():
        return DEFAULT_CATEGORY
    tokens = _tokens(text)

    best = DEFAULT_CATEGORY
    best_score = 0
    for category, keywords in _RULES:
        score = 0
        for kw in keywords:
            if " " in kw:
                if kw in text:
                    score += 2
            elif _token_hit(kw, tokens):
                score += 1
        if score > best_score:
            best_score = score
            best = category
    return best


def is_known_category(name: Optional[str]) -> bool:
    return bool(name) and name in CATEGORIES


def coerce_category(name: Optional[str]) -> Optional[str]:
    """Map a free-text category onto the canonical taxonomy when possible."""
    if not name:
        return None
    n = _norm(name)
    for c in CATEGORIES:
        if _norm(c) == n:
            return c
    return name  # keep custom values as-is
