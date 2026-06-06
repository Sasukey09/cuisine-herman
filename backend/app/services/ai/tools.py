"""Tools the AI assistant can call to read the tenant's own data.

Every executor is **tenant-scoped**: it receives the caller's ``tenant_id`` and
only ever returns rows belonging to that organization. The LLM never touches the
database directly — it emits a ``tool_use`` request, the assistant loop dispatches
it here, and only the structured result is fed back to the model.

Each tool is declared as ``(schema, executor)`` where:
  - ``schema``   is an Anthropic tool definition (name / description / input_schema)
  - ``executor`` is ``(db, tenant_id, input: dict) -> dict`` (JSON-serialisable)

The tool surface deliberately reuses the existing cost engine, dashboard and
pricing services so the assistant sees exactly the same numbers as the UI.
"""
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.models import (
    Product,
    Recipe,
    RecipeCost,
    RecipeIngredient,
    RecipeVersion,
    Supplier,
)
from app.crud import crud_price
from app.services.costing import cost_engine
from app.services.dashboard import dashboard_service
from app.services.units.unit_conversion import UnitConversionService

Executor = Callable[[Session, str, Dict[str, Any]], Dict[str, Any]]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _effective_version_id(db: Session, recipe: Recipe) -> Optional[str]:
    """The recipe's current version, falling back to the highest version_number."""
    if recipe.current_version_id:
        return str(recipe.current_version_id)
    row = (
        db.query(RecipeVersion.id)
        .filter(RecipeVersion.recipe_id == recipe.id)
        .order_by(RecipeVersion.version_number.desc())
        .first()
    )
    return str(row[0]) if row else None


def _price_per_base(price_row, ratios: Dict[int, Any]) -> Optional[float]:
    """Normalise a price to its base unit so products are comparable."""
    if price_row is None:
        return None
    ratio = ratios.get(price_row.unit_id) or 1
    try:
        return float(price_row.price) / float(ratio or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --------------------------------------------------------------------------- #
# executors
# --------------------------------------------------------------------------- #
def _list_recipes(db: Session, tenant_id: str, _: Dict[str, Any]) -> Dict[str, Any]:
    recipes = (
        db.query(Recipe)
        .filter(Recipe.tenant_id == tenant_id)
        .order_by(Recipe.created_at.desc())
        .limit(200)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in recipes:
        version_id = _effective_version_id(db, r)
        food_cost = None
        if version_id:
            snapshot = (
                db.query(RecipeCost)
                .filter(RecipeCost.recipe_version_id == version_id)
                .order_by(RecipeCost.computed_at.desc())
                .first()
            )
            if snapshot is not None and snapshot.food_cost_pct is not None:
                food_cost = float(snapshot.food_cost_pct)
        out.append(
            {
                "recipe_id": str(r.id),
                "name": r.name,
                "version_id": version_id,
                "latest_food_cost_pct": food_cost,
            }
        )
    return {"recipes": out, "count": len(out)}


def _get_recipe_details(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    recipe_id = inp.get("recipe_id")
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id, Recipe.tenant_id == tenant_id)
        .first()
    )
    if recipe is None:
        return {"error": "recipe_not_found", "recipe_id": recipe_id}
    version_id = _effective_version_id(db, recipe)
    if version_id is None:
        return {"error": "no_version", "recipe_id": recipe_id, "name": recipe.name}

    selling_price = inp.get("selling_price")
    # persist=False: the assistant must never mutate cost history as a side effect.
    breakdown = cost_engine.compute_recipe_version_cost(
        db,
        tenant_id,
        version_id,
        selling_price=selling_price,
        persist=False,
    )
    # enrich the per-line breakdown with product names for readability
    names = {
        str(p.id): p.name
        for p in db.query(Product).filter(Product.tenant_id == tenant_id).all()
    }
    for line in breakdown.get("breakdown", []):
        line["product_name"] = names.get(line.get("product_id"))
    return {
        "recipe_id": str(recipe.id),
        "name": recipe.name,
        "version_id": version_id,
        "yield_qty": float(recipe.yield_qty) if recipe.yield_qty is not None else None,
        **breakdown,
    }


def _search_products(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    query = (inp.get("query") or "").strip()
    q = db.query(Product).filter(Product.tenant_id == tenant_id)
    if query:
        q = q.filter(Product.name.ilike(f"%{query}%"))
    products = q.order_by(Product.name.asc()).limit(50).all()
    ratios = UnitConversionService.from_db(db).ratio_map()
    out = []
    for p in products:
        price_row = crud_price.get_latest_price(db, tenant_id, str(p.id))
        out.append(
            {
                "product_id": str(p.id),
                "name": p.name,
                "category_id": p.category_id,
                "latest_price": float(price_row.price) if price_row else None,
                "price_per_base_unit": _price_per_base(price_row, ratios),
                "currency": price_row.currency if price_row else None,
            }
        )
    return {"products": out, "count": len(out)}


def _get_price_history(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    product_id = inp.get("product_id")
    history = dashboard_service.price_trends(db, tenant_id, product_id)
    return {
        "product_id": product_id,
        "history": [
            {
                "effective_date": h["effective_date"].isoformat()
                if h.get("effective_date")
                else None,
                "price": h["price"],
                "currency": h["currency"],
            }
            for h in history
        ],
    }


def _get_margin_alerts(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    threshold = inp.get("max_food_cost_pct", 35.0)
    alerts = dashboard_service.margin_alerts(db, tenant_id, max_food_cost_pct=threshold)
    return {
        "threshold_pct": threshold,
        "alerts": [
            {
                "recipe_id": a["recipe_id"],
                "recipe_name": a["recipe_name"],
                "food_cost_pct": a["food_cost_pct"],
            }
            for a in alerts
        ],
    }


def _get_price_increase_alerts(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    threshold = inp.get("min_increase_pct", 10.0)
    alerts = dashboard_service.price_alerts(db, tenant_id, min_increase_pct=threshold)
    return {
        "min_increase_pct": threshold,
        "alerts": [
            {
                "product_id": a["product_id"],
                "product_name": a["product_name"],
                "previous_price": a["previous_price"],
                "latest_price": a["latest_price"],
                "change_pct": a["change_pct"],
            }
            for a in alerts
        ],
    }


def _find_cheaper_alternatives(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    product_id = inp.get("product_id")
    target = (
        db.query(Product)
        .filter(Product.id == product_id, Product.tenant_id == tenant_id)
        .first()
    )
    if target is None:
        return {"error": "product_not_found", "product_id": product_id}

    ratios = UnitConversionService.from_db(db).ratio_map()
    target_price = _price_per_base(
        crud_price.get_latest_price(db, tenant_id, str(target.id)), ratios
    )

    # candidates: same category (when known), excluding the target itself
    q = db.query(Product).filter(
        Product.tenant_id == tenant_id, Product.id != target.id
    )
    if target.category_id is not None:
        q = q.filter(Product.category_id == target.category_id)

    alternatives = []
    for p in q.limit(200).all():
        unit_price = _price_per_base(
            crud_price.get_latest_price(db, tenant_id, str(p.id)), ratios
        )
        if unit_price is None:
            continue
        if target_price is not None and unit_price >= target_price:
            continue
        savings_pct = (
            round((target_price - unit_price) / target_price * 100, 1)
            if target_price
            else None
        )
        alternatives.append(
            {
                "product_id": str(p.id),
                "name": p.name,
                "price_per_base_unit": round(unit_price, 4),
                "savings_pct": savings_pct,
            }
        )
    alternatives.sort(key=lambda a: a["price_per_base_unit"])
    return {
        "product_id": str(target.id),
        "product_name": target.name,
        "target_price_per_base_unit": round(target_price, 4) if target_price else None,
        "alternatives": alternatives[:10],
    }


def _match_product(db: Session, tenant_id: str, name: str) -> Optional[Product]:
    """Resolve an ingredient name to an existing product (exact, then partial)."""
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    exact = (
        db.query(Product)
        .filter(Product.tenant_id == tenant_id, Product.name.ilike(cleaned))
        .first()
    )
    if exact is not None:
        return exact
    return (
        db.query(Product)
        .filter(Product.tenant_id == tenant_id, Product.name.ilike(f"%{cleaned}%"))
        .order_by(Product.name.asc())
        .first()
    )


def _create_recipe_draft(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    """Create a draft recipe (recipe + version 1 + ingredients) and cost it.

    Ingredients are matched to existing products by name; unmatched ones are
    reported so the user can create the product/price. **Write operation** —
    only invoked when the user explicitly asks to save a recipe.
    """
    name = (inp.get("name") or "").strip()
    if not name:
        return {"error": "missing_name"}
    yield_qty = inp.get("yield_qty") or 1
    ingredients = inp.get("ingredients") or []
    if not ingredients:
        return {"error": "no_ingredients"}

    units_by_code = crud_price.get_units_by_code(db)

    recipe = Recipe(
        id=str(uuid.uuid4()), tenant_id=tenant_id, name=name, yield_qty=yield_qty
    )
    db.add(recipe)
    db.flush()

    version = RecipeVersion(
        id=str(uuid.uuid4()), recipe_id=recipe.id, version_number=1, is_published=False
    )
    db.add(version)
    db.flush()

    resolved: List[Dict[str, Any]] = []
    unmatched: List[str] = []
    unknown_units: List[str] = []

    for ing in ingredients:
        ing_name = (ing.get("name") or "").strip()
        if not ing_name:
            continue
        unit_code = (ing.get("unit") or "").strip().lower()
        unit_id = units_by_code.get(unit_code) if unit_code else None
        if unit_code and unit_id is None and unit_code not in unknown_units:
            unknown_units.append(unit_code)

        product = _match_product(db, tenant_id, ing_name)
        if product is None:
            unmatched.append(ing_name)

        db.add(
            RecipeIngredient(
                id=str(uuid.uuid4()),
                recipe_version_id=version.id,
                product_id=str(product.id) if product else None,
                ingredient_name=ing_name,
                qty=ing.get("qty"),
                unit_id=unit_id,
                loss_pct=ing.get("loss_pct") or 0,
                yield_pct=ing.get("yield_pct") if ing.get("yield_pct") is not None else 100,
                prep_notes=ing.get("prep_notes"),
            )
        )
        resolved.append(
            {
                "name": ing_name,
                "matched_product_id": str(product.id) if product else None,
                "matched_product_name": product.name if product else None,
                "unit_recognized": unit_id is not None or not unit_code,
            }
        )

    recipe.current_version_id = version.id
    db.commit()

    # cost the freshly-created version (persists a snapshot, like the UI does)
    cost = cost_engine.compute_recipe_version_cost(
        db, tenant_id, str(version.id), persist=True
    )
    return {
        "recipe_id": str(recipe.id),
        "version_id": str(version.id),
        "name": name,
        "yield_qty": float(yield_qty),
        "ingredients": resolved,
        "unmatched_ingredients": unmatched,
        "unknown_units": unknown_units,
        "cost": {
            "computed_cost_total": cost.get("computed_cost_total"),
            "cost_per_portion": cost.get("cost_per_portion"),
            "food_cost_pct": cost.get("food_cost_pct"),
            "has_missing_prices": cost.get("has_missing_prices"),
        },
        "note": (
            "Fiche créée en brouillon. Les quantités sont estimées par l'IA et "
            "doivent être validées. Les ingrédients non reconnus / sans prix "
            "rendent le coût incomplet — créez les produits et prix manquants."
        ),
    }


def _link_recipe_products(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    """Re-match a recipe's unmapped ingredients to catalog products by name.

    Useful after products are created later: walks the recipe's current version,
    links each ingredient that has no product but a stored name to a matching
    product, then recomputes the cost. **Write operation.**
    """
    recipe_id = inp.get("recipe_id")
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id, Recipe.tenant_id == tenant_id)
        .first()
    )
    if recipe is None:
        return {"error": "recipe_not_found", "recipe_id": recipe_id}
    version_id = _effective_version_id(db, recipe)
    if version_id is None:
        return {"error": "no_version", "recipe_id": recipe_id}

    ingredients = (
        db.query(RecipeIngredient)
        .filter(
            RecipeIngredient.recipe_version_id == version_id,
            RecipeIngredient.product_id.is_(None),
        )
        .all()
    )
    linked: List[Dict[str, Any]] = []
    still_unmatched: List[str] = []
    for ing in ingredients:
        name = (ing.ingredient_name or "").strip()
        if not name:
            still_unmatched.append(ing.ingredient_name or "(sans nom)")
            continue
        product = _match_product(db, tenant_id, name)
        if product is None:
            still_unmatched.append(name)
            continue
        ing.product_id = str(product.id)
        linked.append({"ingredient_name": name, "product_name": product.name})

    if linked:
        db.commit()

    cost = cost_engine.compute_recipe_version_cost(
        db, tenant_id, str(version_id), persist=True
    )
    return {
        "recipe_id": str(recipe.id),
        "version_id": str(version_id),
        "linked": linked,
        "linked_count": len(linked),
        "still_unmatched": still_unmatched,
        "cost": {
            "computed_cost_total": cost.get("computed_cost_total"),
            "cost_per_portion": cost.get("cost_per_portion"),
            "food_cost_pct": cost.get("food_cost_pct"),
            "has_missing_prices": cost.get("has_missing_prices"),
        },
    }


def _create_product(db: Session, tenant_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    """Create a product (optionally with a base unit + an initial price).

    **Write operation** — only when the user explicitly asks to create a product
    / add a price. Reuses an existing product with the same name instead of
    duplicating; a price is still added if one is provided.
    """
    name = (inp.get("name") or "").strip()
    if not name:
        return {"error": "missing_name"}

    units_by_code = crud_price.get_units_by_code(db)

    base_unit_code = (inp.get("base_unit") or "").strip().lower()
    base_unit_id = units_by_code.get(base_unit_code) if base_unit_code else None
    unknown_units = []
    if base_unit_code and base_unit_id is None:
        unknown_units.append(base_unit_code)

    existing = _match_product(db, tenant_id, name)
    # only reuse on an exact (case-insensitive) name match, not a partial one
    reused = existing is not None and existing.name.strip().lower() == name.lower()
    if reused:
        product = existing
    else:
        product = Product(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
            base_unit_id=base_unit_id,
        )
        db.add(product)
        db.commit()
        db.refresh(product)

    price_created = False
    price_value = inp.get("price")
    if price_value is not None:
        price_unit_code = (inp.get("price_unit") or base_unit_code or "").strip().lower()
        price_unit_id = units_by_code.get(price_unit_code) if price_unit_code else base_unit_id
        if price_unit_code and price_unit_id is None and price_unit_code not in unknown_units:
            unknown_units.append(price_unit_code)

        supplier_id = None
        supplier_name = (inp.get("supplier_name") or "").strip()
        if supplier_name:
            supplier = (
                db.query(Supplier)
                .filter(Supplier.tenant_id == tenant_id, Supplier.name.ilike(supplier_name))
                .first()
            )
            supplier_id = str(supplier.id) if supplier else None

        crud_price.create_price(
            db,
            tenant_id=tenant_id,
            product_id=str(product.id),
            price=price_value,
            unit_id=price_unit_id,
            supplier_id=supplier_id,
            currency=inp.get("currency"),
        )
        price_created = True

    return {
        "product_id": str(product.id),
        "name": product.name,
        "reused_existing": reused,
        "base_unit": base_unit_code or None,
        "price_created": price_created,
        "unknown_units": unknown_units,
        "note": (
            "Produit prêt. Pour qu'une recette utilise ce produit dans son coût, "
            "l'ingrédient correspondant doit y être rattaché — créez la fiche "
            "(create_recipe_draft) APRÈS avoir créé les produits pour que le "
            "rapprochement par nom fonctionne."
        ),
    }


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #
_TOOLS: Dict[str, Tuple[Dict[str, Any], Executor]] = {
    "list_recipes": (
        {
            "name": "list_recipes",
            "description": (
                "Lister toutes les recettes du restaurant avec leur dernier food cost "
                "connu (en %). À utiliser pour avoir une vue d'ensemble ou retrouver "
                "l'identifiant d'une recette."
            ),
            "input_schema": {"type": "object", "properties": {}},
        },
        _list_recipes,
    ),
    "get_recipe_details": (
        {
            "name": "get_recipe_details",
            "description": (
                "Détail complet du coût d'une recette : coût matière total, coût par "
                "portion, food cost %, marge, et le détail ligne par ligne des "
                "ingrédients (avec prix manquants signalés). Fournir 'selling_price' "
                "pour obtenir food cost % et marge."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipe_id": {"type": "string", "description": "Identifiant de la recette"},
                    "selling_price": {
                        "type": "number",
                        "description": "Prix de vente TTC par portion (optionnel)",
                    },
                },
                "required": ["recipe_id"],
            },
        },
        _get_recipe_details,
    ),
    "search_products": (
        {
            "name": "search_products",
            "description": (
                "Rechercher des produits/ingrédients par nom et obtenir leur dernier "
                "prix et prix ramené à l'unité de base. Laisser 'query' vide pour "
                "lister les produits."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texte de recherche (nom du produit)"}
                },
            },
        },
        _search_products,
    ),
    "get_price_history": (
        {
            "name": "get_price_history",
            "description": "Historique des prix d'un produit (par date).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Identifiant du produit"}
                },
                "required": ["product_id"],
            },
        },
        _get_price_history,
    ),
    "get_margin_alerts": (
        {
            "name": "get_margin_alerts",
            "description": (
                "Recettes dont le food cost dépasse un seuil (défaut 35%). À utiliser "
                "pour repérer les recettes peu rentables."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "max_food_cost_pct": {
                        "type": "number",
                        "description": "Seuil de food cost % (défaut 35)",
                    }
                },
            },
        },
        _get_margin_alerts,
    ),
    "get_price_increase_alerts": (
        {
            "name": "get_price_increase_alerts",
            "description": (
                "Produits dont le dernier prix a augmenté d'au moins X% par rapport au "
                "prix précédent (défaut 10%)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "min_increase_pct": {
                        "type": "number",
                        "description": "Hausse minimale en % (défaut 10)",
                    }
                },
            },
        },
        _get_price_increase_alerts,
    ),
    "find_cheaper_alternatives": (
        {
            "name": "find_cheaper_alternatives",
            "description": (
                "Pour un produit donné, proposer des alternatives moins chères de la "
                "même catégorie, comparées au prix ramené à l'unité de base."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Identifiant du produit"}
                },
                "required": ["product_id"],
            },
        },
        _find_cheaper_alternatives,
    ),
    "create_recipe_draft": (
        {
            "name": "create_recipe_draft",
            "description": (
                "Créer et ENREGISTRER une fiche technique brouillon dans la base "
                "(recette + version 1 + ingrédients), puis calculer son coût. "
                "À n'utiliser QUE si l'utilisateur demande explicitement de créer / "
                "enregistrer une fiche. Les ingrédients sont rapprochés des produits "
                "existants par nom ; ceux non trouvés sont signalés. Avertis toujours "
                "que les quantités sont estimées et à valider, et demande le nombre "
                "de portions si l'utilisateur ne l'a pas précisé. Unités attendues : "
                "codes comme g, kg, l, ml, piece."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom de la recette"},
                    "yield_qty": {
                        "type": "number",
                        "description": "Nombre de portions (défaut 1)",
                    },
                    "ingredients": {
                        "type": "array",
                        "description": "Liste des ingrédients de la recette",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Nom de l'ingrédient"},
                                "qty": {"type": "number", "description": "Quantité"},
                                "unit": {
                                    "type": "string",
                                    "description": "Code unité (g, kg, l, ml, piece)",
                                },
                                "loss_pct": {
                                    "type": "number",
                                    "description": "Perte en % (optionnel)",
                                },
                                "yield_pct": {
                                    "type": "number",
                                    "description": "Rendement en % (optionnel, défaut 100)",
                                },
                            },
                            "required": ["name", "qty", "unit"],
                        },
                    },
                },
                "required": ["name", "ingredients"],
            },
        },
        _create_recipe_draft,
    ),
    "create_product": (
        {
            "name": "create_product",
            "description": (
                "Créer et ENREGISTRER un produit/ingrédient dans le catalogue, avec "
                "en option son unité de base et un prix initial (et un fournisseur "
                "existant). À n'utiliser QUE si l'utilisateur demande explicitement "
                "de créer un produit / saisir un prix. Réutilise un produit existant "
                "de même nom au lieu d'en créer un doublon. Unités : codes comme g, "
                "kg, l, ml, piece. Astuce : pour chiffrer une nouvelle recette, créer "
                "les produits AVANT la fiche pour que le rapprochement par nom marche."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom du produit"},
                    "base_unit": {
                        "type": "string",
                        "description": "Unité de base (g, kg, l, ml, piece)",
                    },
                    "price": {
                        "type": "number",
                        "description": "Prix unitaire actuel (optionnel)",
                    },
                    "price_unit": {
                        "type": "string",
                        "description": "Unité à laquelle se réfère le prix (défaut: base_unit)",
                    },
                    "supplier_name": {
                        "type": "string",
                        "description": "Nom d'un fournisseur existant (optionnel)",
                    },
                    "currency": {"type": "string", "description": "Devise (optionnel)"},
                },
                "required": ["name"],
            },
        },
        _create_product,
    ),
    "link_recipe_products": (
        {
            "name": "link_recipe_products",
            "description": (
                "Rattacher les ingrédients non mappés d'une recette aux produits du "
                "catalogue (par nom) puis recalculer le coût. À utiliser quand une "
                "fiche a été créée avant que les produits existent : crée d'abord les "
                "produits manquants (create_product), puis appelle cet outil pour "
                "relier la fiche et obtenir un coût réel. Action d'écriture."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipe_id": {"type": "string", "description": "Identifiant de la recette"}
                },
                "required": ["recipe_id"],
            },
        },
        _link_recipe_products,
    ),
}


def tool_schemas() -> List[Dict[str, Any]]:
    """Anthropic tool definitions, for the ``tools`` request parameter."""
    return [schema for schema, _ in _TOOLS.values()]


def execute_tool(db: Session, tenant_id: str, name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a tool call to its tenant-scoped executor."""
    entry = _TOOLS.get(name)
    if entry is None:
        return {"error": "unknown_tool", "tool": name}
    _, executor = entry
    try:
        return executor(db, tenant_id, tool_input or {})
    except Exception as exc:  # surface the error to the model, don't crash the loop
        return {"error": "tool_execution_failed", "tool": name, "detail": str(exc)}
