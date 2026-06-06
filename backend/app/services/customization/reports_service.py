"""No-code report builder.

Security model: there is **no dynamic SQL**. Each data source has a fixed,
whitelisted set of columns and a builder that returns plain row dicts; filters /
sorting / column projection are applied in memory. A report definition can only
reference whitelisted sources, columns and operators.

A definition looks like:
    {
      "source": "products" | "recipes" | "invoices",
      "columns": ["name", "latest_price", ...],
      "filters": [{"field": "latest_price", "op": "gte", "value": 5}],
      "sort": {"field": "name", "dir": "asc"},
      "limit": 200
    }
"""
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import (
    Product,
    Recipe,
    RecipeCost,
    RecipeVersion,
    Invoice,
    Supplier,
)
from app.crud import crud_price

_SOURCE_FETCH_CAP = 2000
_OPS = {"eq", "ne", "contains", "gt", "gte", "lt", "lte"}


class ReportError(ValueError):
    pass


def _iso(value) -> Optional[str]:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _f(value) -> Optional[float]:
    return float(value) if value is not None else None


# --------------------------------------------------------------------------- #
# row builders (each returns a list of dicts keyed by the source's column keys)
# --------------------------------------------------------------------------- #
def _build_products(db: Session, tenant_id: str) -> List[Dict[str, Any]]:
    products = (
        db.query(Product)
        .filter(Product.tenant_id == tenant_id)
        .order_by(Product.created_at.desc())
        .limit(_SOURCE_FETCH_CAP)
        .all()
    )
    rows = []
    for p in products:
        price = crud_price.get_latest_price(db, tenant_id, str(p.id))
        rows.append(
            {
                "name": p.name,
                "sku": p.sku,
                "category_id": p.category_id,
                "latest_price": _f(price.price) if price else None,
                "created_at": _iso(p.created_at),
            }
        )
    return rows


def _build_recipes(db: Session, tenant_id: str) -> List[Dict[str, Any]]:
    recipes = (
        db.query(Recipe)
        .filter(Recipe.tenant_id == tenant_id)
        .order_by(Recipe.created_at.desc())
        .limit(_SOURCE_FETCH_CAP)
        .all()
    )
    rows = []
    for r in recipes:
        version_id = r.current_version_id
        if version_id is None:
            v = (
                db.query(RecipeVersion.id)
                .filter(RecipeVersion.recipe_id == r.id)
                .order_by(RecipeVersion.version_number.desc())
                .first()
            )
            version_id = v[0] if v else None
        snapshot = None
        if version_id is not None:
            snapshot = (
                db.query(RecipeCost)
                .filter(RecipeCost.recipe_version_id == version_id)
                .order_by(RecipeCost.computed_at.desc())
                .first()
            )
        rows.append(
            {
                "name": r.name,
                "yield_qty": _f(r.yield_qty),
                "cost_per_portion": _f(snapshot.cost_per_portion) if snapshot else None,
                "food_cost_pct": _f(snapshot.food_cost_pct) if snapshot else None,
                "created_at": _iso(r.created_at),
            }
        )
    return rows


def _build_invoices(db: Session, tenant_id: str) -> List[Dict[str, Any]]:
    rows_q = (
        db.query(Invoice, Supplier.name.label("supplier_name"))
        .outerjoin(Supplier, Supplier.id == Invoice.supplier_id)
        .filter(Invoice.tenant_id == tenant_id)
        .order_by(Invoice.created_at.desc())
        .limit(_SOURCE_FETCH_CAP)
        .all()
    )
    rows = []
    for inv, supplier_name in rows_q:
        rows.append(
            {
                "invoice_number": inv.invoice_number,
                "date": _iso(inv.date),
                "supplier_name": supplier_name,
                "total_amount": _f(inv.total_amount),
                "currency": inv.currency,
                "parsed": bool(inv.parsed),
            }
        )
    return rows


SOURCES: Dict[str, Dict[str, Any]] = {
    "products": {
        "label": "Produits",
        "builder": _build_products,
        "columns": [
            {"key": "name", "label": "Nom", "type": "string"},
            {"key": "sku", "label": "SKU", "type": "string"},
            {"key": "category_id", "label": "Catégorie", "type": "number"},
            {"key": "latest_price", "label": "Dernier prix", "type": "number"},
            {"key": "created_at", "label": "Créé le", "type": "date"},
        ],
    },
    "recipes": {
        "label": "Recettes",
        "builder": _build_recipes,
        "columns": [
            {"key": "name", "label": "Nom", "type": "string"},
            {"key": "yield_qty", "label": "Portions", "type": "number"},
            {"key": "cost_per_portion", "label": "Coût/portion", "type": "number"},
            {"key": "food_cost_pct", "label": "Food cost %", "type": "number"},
            {"key": "created_at", "label": "Créé le", "type": "date"},
        ],
    },
    "invoices": {
        "label": "Factures",
        "builder": _build_invoices,
        "columns": [
            {"key": "invoice_number", "label": "N° facture", "type": "string"},
            {"key": "date", "label": "Date", "type": "date"},
            {"key": "supplier_name", "label": "Fournisseur", "type": "string"},
            {"key": "total_amount", "label": "Montant total", "type": "number"},
            {"key": "currency", "label": "Devise", "type": "string"},
            {"key": "parsed", "label": "Analysée", "type": "boolean"},
        ],
    },
}


def available_sources() -> List[Dict[str, Any]]:
    return [
        {"key": k, "label": s["label"], "columns": s["columns"]}
        for k, s in SOURCES.items()
    ]


def _column_types(source: str) -> Dict[str, str]:
    return {c["key"]: c["type"] for c in SOURCES[source]["columns"]}


def validate_definition(definition: Dict[str, Any]) -> None:
    source = definition.get("source")
    if source not in SOURCES:
        raise ReportError("Source invalide")
    valid_cols = set(_column_types(source))
    for col in definition.get("columns") or []:
        if col not in valid_cols:
            raise ReportError(f"Colonne inconnue : {col}")
    for flt in definition.get("filters") or []:
        if flt.get("field") not in valid_cols:
            raise ReportError(f"Filtre sur colonne inconnue : {flt.get('field')}")
        if flt.get("op") not in _OPS:
            raise ReportError(f"Opérateur de filtre invalide : {flt.get('op')}")
    sort = definition.get("sort")
    if sort and sort.get("field") and sort["field"] not in valid_cols:
        raise ReportError(f"Tri sur colonne inconnue : {sort.get('field')}")


def _coerce_for_type(value: Any, col_type: str) -> Any:
    if value is None or value == "":
        return None
    if col_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if col_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "oui", "on")
    return str(value)


def _match(row_value: Any, op: str, target: Any, col_type: str) -> bool:
    if op == "contains":
        return str(target).lower() in str(row_value or "").lower()
    rv = _coerce_for_type(row_value, col_type)
    tv = _coerce_for_type(target, col_type)
    if op == "eq":
        return rv == tv
    if op == "ne":
        return rv != tv
    # ordered comparisons: None never matches
    if rv is None or tv is None:
        return False
    if op == "gt":
        return rv > tv
    if op == "gte":
        return rv >= tv
    if op == "lt":
        return rv < tv
    if op == "lte":
        return rv <= tv
    return False


def run_report(db: Session, tenant_id: str, definition: Dict[str, Any]) -> Dict[str, Any]:
    validate_definition(definition)
    source = definition["source"]
    col_types = _column_types(source)
    rows = SOURCES[source]["builder"](db, tenant_id)

    # filters
    for flt in definition.get("filters") or []:
        field, op, value = flt["field"], flt["op"], flt.get("value")
        rows = [r for r in rows if _match(r.get(field), op, value, col_types[field])]

    # sort
    sort = definition.get("sort") or {}
    if sort.get("field"):
        field = sort["field"]
        reverse = sort.get("dir") == "desc"
        rows.sort(key=lambda r: (r.get(field) is None, r.get(field)), reverse=reverse)

    # limit
    limit = definition.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    # column projection (default: all source columns)
    columns = definition.get("columns") or list(col_types.keys())
    projected = [{c: r.get(c) for c in columns} for r in rows]
    col_meta = [c for c in SOURCES[source]["columns"] if c["key"] in columns]
    return {"source": source, "columns": col_meta, "rows": projected, "count": len(projected)}
