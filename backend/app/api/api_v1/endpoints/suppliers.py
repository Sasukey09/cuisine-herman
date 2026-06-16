from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.schemas.schemas import (
    SupplierCreate,
    SupplierUpdate,
    SupplierRead,
    SupplierPriceRead,
)
from app.crud.crud_supplier import (
    create_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
    delete_supplier,
    get_supplier_prices,
)
from app.services.purchasing import purchase_service

router = APIRouter()


@router.get("/{supplier_id}/purchase-history")
def api_supplier_purchase_history(
    supplier_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """All purchases recorded from this supplier (per product, with variations)."""
    if not get_supplier(db, supplier_id, tenant_id):
        raise HTTPException(status_code=404, detail="Supplier not found")
    return purchase_service.supplier_purchase_history(db, tenant_id, supplier_id)


@router.post("/", response_model=SupplierRead, status_code=201)
def api_create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    return create_supplier(db, payload, tenant_id)


@router.get("/", response_model=List[SupplierRead])
def api_list_suppliers(
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return list_suppliers(db, tenant_id, skip=skip, limit=limit, q=q)


@router.get("/{supplier_id}", response_model=SupplierRead)
def api_get_supplier(
    supplier_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    supplier = get_supplier(db, supplier_id, tenant_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.get("/{supplier_id}/prices", response_model=List[SupplierPriceRead])
def api_supplier_prices(
    supplier_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    supplier = get_supplier(db, supplier_id, tenant_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return get_supplier_prices(db, supplier_id, tenant_id)


@router.put("/{supplier_id}", response_model=SupplierRead)
def api_update_supplier(
    supplier_id: str,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    supplier = update_supplier(db, supplier_id, tenant_id, payload)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.delete("/{supplier_id}", status_code=204)
def api_delete_supplier(
    supplier_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    try:
        deleted = delete_supplier(db, supplier_id, tenant_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Fournisseur référencé (factures/prix) — suppression impossible.",
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return None
