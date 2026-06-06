from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.schemas.schemas import (
    CustomFieldCreate,
    CustomFieldRead,
    CustomFieldValues,
    CustomFieldValuesUpdate,
)
from app.crud import crud_custom_field
from app.services.customization import fields_service

router = APIRouter()

_VALID_TARGETS = {"product", "recipe"}
_VALID_TYPES = {"text", "number", "boolean", "select"}


def _to_read(d) -> dict:
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


@router.get("/", response_model=List[CustomFieldRead])
def api_list_fields(
    target: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return [_to_read(d) for d in crud_custom_field.list_fields(db, tenant_id, target)]


@router.post("/", response_model=CustomFieldRead, status_code=201)
def api_create_field(
    payload: CustomFieldCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    if payload.target not in _VALID_TARGETS:
        raise HTTPException(status_code=400, detail="Cible invalide (product|recipe)")
    if payload.type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail="Type invalide (text|number|boolean|select)")
    if not payload.label.strip():
        raise HTTPException(status_code=400, detail="Libellé requis")
    d = crud_custom_field.create_field(
        db, tenant_id, payload.label.strip(), payload.target, payload.type,
        key=payload.key, options=payload.options, required=payload.required,
        description=payload.description,
    )
    return _to_read(d)


@router.delete("/{field_id}", status_code=204)
def api_delete_field(
    field_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    if not crud_custom_field.delete_field(db, tenant_id, field_id):
        raise HTTPException(status_code=404, detail="Champ introuvable")


@router.get("/values/{target}/{entity_id}", response_model=CustomFieldValues)
def api_get_values(
    target: str,
    entity_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    try:
        return fields_service.get_values(db, tenant_id, target, entity_id)
    except fields_service.FieldValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/values/{target}/{entity_id}")
def api_set_values(
    target: str,
    entity_id: str,
    payload: CustomFieldValuesUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    try:
        return fields_service.set_values(db, tenant_id, target, entity_id, payload.values)
    except fields_service.FieldValueError as exc:
        detail = str(exc)
        code = 404 if detail == "entity_not_found" else 400
        raise HTTPException(status_code=code, detail=detail)
