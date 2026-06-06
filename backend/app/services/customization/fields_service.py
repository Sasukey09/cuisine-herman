"""Custom field values: read/write user-defined fields on products & recipes.

Field *definitions* live in the ``custom_fields`` table (per tenant + target).
Field *values* are stored in the target row's ``meta`` JSONB under a ``custom``
sub-dict, so no schema change is needed to add fields.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import Product, Recipe, CustomField
from app.crud import crud_custom_field

_MODELS = {"product": Product, "recipe": Recipe}


class FieldValueError(ValueError):
    pass


def _model(target: str):
    model = _MODELS.get(target)
    if model is None:
        raise FieldValueError(f"Cible inconnue : {target}")
    return model


def _coerce(value: Any, field_type: str, options: List[str], key: str) -> Any:
    if value is None or value == "":
        return None
    if field_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            raise FieldValueError(f"'{key}' doit être un nombre")
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "oui", "on")
    if field_type == "select":
        sval = str(value)
        if options and sval not in options:
            raise FieldValueError(f"'{key}' doit être l'une des valeurs : {', '.join(options)}")
        return sval
    return str(value)  # text


def get_entity(db: Session, tenant_id: str, target: str, entity_id: str):
    model = _model(target)
    return (
        db.query(model)
        .filter(model.id == entity_id, model.tenant_id == tenant_id)
        .first()
    )


def get_values(db: Session, tenant_id: str, target: str, entity_id: str) -> Dict[str, Any]:
    """Return {definitions, values} for an entity's custom fields."""
    entity = get_entity(db, tenant_id, target, entity_id)
    if entity is None:
        raise FieldValueError("entity_not_found")
    defs = crud_custom_field.list_fields(db, tenant_id, target)
    stored = (entity.meta or {}).get("custom", {}) if entity.meta else {}
    return {
        "target": target,
        "entity_id": entity_id,
        "definitions": [_def_dict(d) for d in defs],
        "values": {d.schema.get("key"): stored.get(d.schema.get("key")) for d in defs},
    }


def set_values(
    db: Session, tenant_id: str, target: str, entity_id: str, values: Dict[str, Any]
) -> Dict[str, Any]:
    entity = get_entity(db, tenant_id, target, entity_id)
    if entity is None:
        raise FieldValueError("entity_not_found")
    defs = {d.schema.get("key"): d for d in crud_custom_field.list_fields(db, tenant_id, target)}

    coerced: Dict[str, Any] = {}
    for key, definition in defs.items():
        schema = definition.schema or {}
        raw = values.get(key)
        value = _coerce(raw, schema.get("type", "text"), schema.get("options", []), key)
        if value is None and schema.get("required"):
            raise FieldValueError(f"Le champ '{definition.name}' est requis")
        coerced[key] = value

    meta = dict(entity.meta or {})
    meta["custom"] = coerced
    entity.meta = meta  # reassign so SQLAlchemy tracks the JSONB change
    db.commit()
    return {"target": target, "entity_id": entity_id, "values": coerced}


def _def_dict(d: CustomField) -> Dict[str, Any]:
    schema = d.schema or {}
    return {
        "id": str(d.id),
        "label": d.name,
        "target": d.target_entity,
        "key": schema.get("key"),
        "type": schema.get("type", "text"),
        "options": schema.get("options", []),
        "required": bool(schema.get("required")),
        "description": schema.get("description"),
    }
