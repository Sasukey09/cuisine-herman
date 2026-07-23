"""Réceptions de marchandise.

Le maillon qui manquait entre la commande et la facture. Une règle gouverne
tout ce module : **une réception validée est figée**. Elle se corrige tant
qu'elle est en brouillon ; après, une correction prend la forme d'une nouvelle
réception corrective. C'est ce qui permet de dire, trois semaines plus tard, ce
qui avait été constaté le jour de la livraison.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user, require_writer
from app.crud import crud_receipt
from app.db.session import get_db
from app.models.models import PurchaseOrder, PurchaseOrderLine, User
from app.schemas.schemas import ReceiptCreate, ReceiptRead, ReceiptUpdate
from app.services.purchasing import reception_service
from app.services.rgpd import service as rgpd

router = APIRouter()

_FROZEN = (
    "Cette réception est validée : elle ne se modifie plus. "
    "Enregistrez une nouvelle réception pour corriger."
)


# Déclarées AVANT "/{receipt_id}" — sinon « conditions » et « from-order » sont
# avalés comme des identifiants.
@router.get("/conditions")
def api_receipt_conditions(_tenant_id: str = Depends(get_current_tenant_id)):
    """Les états possibles d'une ligne reçue et leurs libellés.

    Servis par l'API pour que web et mobile n'en tiennent aucune copie."""
    return [
        {"value": c, "label": reception_service.CONDITION_LABELS[c]}
        for c in reception_service.CONDITIONS
    ]


@router.get("/from-order/{order_id}")
def api_prefill_from_order(
    order_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Le brouillon de réception d'une commande, pré-rempli avec ce qui RESTE dû.

    Pré-remplir avec la quantité commandée serait faux dès la deuxième
    livraison : on re-proposerait des quantités déjà reçues. On propose donc le
    restant, que le réceptionnaire corrige à la baisse s'il manque quelque
    chose."""
    order = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.id == order_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    already = reception_service.received_by_order_line(db, tenant_id, order_id)
    lines = []
    for l in (
        db.query(PurchaseOrderLine)
        .filter(
            PurchaseOrderLine.tenant_id == tenant_id,
            PurchaseOrderLine.order_id == order_id,
        )
        .order_by(PurchaseOrderLine.created_at)
        .all()
    ):
        ordered = float(l.qty_ordered or 0)
        remaining = max(ordered - float(already.get(str(l.id), 0.0)), 0.0)
        lines.append(
            {
                "order_line_id": str(l.id),
                "product_id": str(l.product_id) if l.product_id else None,
                "description": l.description,
                "qty_ordered": ordered or None,
                "qty_already_received": float(already.get(str(l.id), 0.0)),
                "qty_received": remaining or None,
                "unit_id": l.unit_id,
                "unit_price": float(l.unit_price) if l.unit_price is not None else None,
                "pack_size": l.pack_size,
                "condition": reception_service.OK,
            }
        )
    return {
        "order_id": str(order.id),
        "order_reference": order.reference,
        "supplier_id": str(order.supplier_id) if order.supplier_id else None,
        "lines": lines,
    }


@router.get("/", response_model=List[ReceiptRead])
def api_list_receipts(
    order_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return crud_receipt.list_receipts(db, tenant_id, order_id=order_id, status=status)


@router.post("/", status_code=201)
def api_create_receipt(
    payload: ReceiptCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_writer),
):
    receipt = crud_receipt.create(db, tenant_id, payload, str(current_user.id))
    return crud_receipt.detail(db, tenant_id, receipt)


@router.get("/{receipt_id}")
def api_get_receipt(
    receipt_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    receipt = crud_receipt.get(db, tenant_id, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Réception introuvable")
    return crud_receipt.detail(db, tenant_id, receipt)


@router.get("/{receipt_id}/control")
def api_control_receipt(
    receipt_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Commandé face à livré, ligne par ligne, plus les écarts que le seul
    comptage ne voit pas : prix, conditionnement, produit, fournisseur."""
    receipt = crud_receipt.get(db, tenant_id, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Réception introuvable")
    return reception_service.control(db, tenant_id, receipt)


@router.patch("/{receipt_id}")
def api_update_receipt(
    receipt_id: str,
    payload: ReceiptUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    receipt = crud_receipt.get(db, tenant_id, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Réception introuvable")
    if receipt.status == reception_service.CHECKED:
        raise HTTPException(status_code=409, detail=_FROZEN)
    crud_receipt.update(db, tenant_id, receipt, payload)
    return crud_receipt.detail(db, tenant_id, receipt)


@router.post("/{receipt_id}/validate")
def api_validate_receipt(
    receipt_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_writer),
):
    """Fige la réception, écrit les mouvements de stock, avance la commande.

    Les mouvements naissent ici et pas au brouillon : une quantité mal saisie
    dans un brouillon entrerait sinon au stock, et il faudrait un mouvement
    compensatoire pour la reprendre."""
    receipt = crud_receipt.get(db, tenant_id, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Réception introuvable")
    if receipt.status == reception_service.CHECKED:
        raise HTTPException(status_code=409, detail="Réception déjà validée")

    control = reception_service.validate(db, tenant_id, receipt, str(current_user.id))
    # Qui a validé quoi, et avec quels écarts : la trace reste même si la
    # réception est un jour supprimée.
    rgpd.record(
        db,
        tenant_id,
        str(current_user.id),
        "receipt.validated",
        {
            "receipt_id": str(receipt.id),
            "reference": receipt.reference,
            "issue_count": control.get("issue_count"),
            "missing_value": control.get("missing_value"),
        },
    )
    return {"receipt": crud_receipt.detail(db, tenant_id, receipt), "control": control}


@router.delete("/{receipt_id}", status_code=204)
def api_delete_receipt(
    receipt_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    receipt = crud_receipt.get(db, tenant_id, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Réception introuvable")
    # Une réception validée est un constat daté et signé. La supprimer
    # effacerait la preuve de ce qui avait été relevé à la livraison.
    if receipt.status == reception_service.CHECKED:
        raise HTTPException(status_code=409, detail=_FROZEN)
    crud_receipt.delete(db, receipt)
    return None
