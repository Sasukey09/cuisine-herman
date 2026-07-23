"""Commandes fournisseur.

Le module qui rend le comparateur exécutable : jusqu'ici il désignait le moins
cher produit par produit — donc potentiellement chez plusieurs fournisseurs — et
il n'existait aucun moyen d'agir sur ce verdict.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_writer
from app.crud import crud_order
from app.db.session import get_db
from app.schemas.schemas import (
    OrderFromQuoteLinesRequest,
    OrderPlan,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
)
from app.services.purchasing import order_service

router = APIRouter()


# NB: déclarée AVANT les routes dynamiques "/{order_id}", sinon "statuses" est
# avalé comme un identifiant de commande — le piège qui avait valu un 500 à
# GET /quotes/matrix.
@router.get("/statuses")
def api_order_statuses(_tenant_id: str = Depends(get_current_tenant_id)):
    """Les états d'une commande et leurs libellés, dans l'ordre du cycle de vie.

    Servis par l'API pour que le web et le mobile n'entretiennent pas chacun
    leur table de traduction — elles finiraient par diverger."""
    return [
        {"value": s, "label": order_service.STATUS_LABELS[s]}
        for s in order_service.STATUSES
    ]


@router.post("/plan", response_model=List[OrderPlan])
def api_plan_orders(
    payload: OrderFromQuoteLinesRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Ce qui SERA commandé, sans rien créer.

    Engager trois commandes pour découvrir ensuite qu'on s'est trompé de lignes
    coûte trois annulations : l'aperçu se regarde d'abord."""
    offers = order_service.offers_from_quote_lines(db, tenant_id, payload.quote_line_ids)
    if not offers:
        raise HTTPException(status_code=404, detail="Aucune ligne de devis trouvée")
    return order_service.plan_orders(offers)


@router.post("/from-quote-lines", status_code=201)
def api_orders_from_quote_lines(
    payload: OrderFromQuoteLinesRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Transforme les offres retenues en commandes — **une par fournisseur**.

    Le corps porte des identifiants de LIGNES de devis, pas un devis : le panier
    retenu traverse plusieurs devis dès lors que le moins cher n'est pas le même
    partout. Les prix offerts sont repris tels quels ; rien n'est rechiffré
    depuis l'historique d'achat.
    """
    if payload.status not in (order_service.DRAFT, order_service.SENT):
        raise HTTPException(
            status_code=400,
            detail="Une commande naît en brouillon ou envoyée, pas dans un autre état",
        )
    offers = order_service.offers_from_quote_lines(db, tenant_id, payload.quote_line_ids)
    if not offers:
        raise HTTPException(status_code=404, detail="Aucune ligne de devis trouvée")

    plans = order_service.plan_orders(offers)
    orders = order_service.create_orders(
        db, tenant_id, plans, expected_date=payload.expected_date, status=payload.status
    )
    return {
        "orders": [crud_order.detail(db, tenant_id, o) for o in orders],
        "order_count": len(orders),
        "supplier_count": len({str(o.supplier_id) for o in orders if o.supplier_id}),
        "total_amount": round(sum(float(o.total_amount or 0) for o in orders), 2),
    }


@router.get("/", response_model=List[PurchaseOrderRead])
def api_list_orders(
    status: Optional[str] = Query(default=None),
    supplier_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return crud_order.list_orders(db, tenant_id, status=status, supplier_id=supplier_id)


@router.get("/{order_id}")
def api_get_order(
    order_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    order = crud_order.get_order(db, tenant_id, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return crud_order.detail(db, tenant_id, order)


@router.get("/{order_id}/progress")
def api_order_progress(
    order_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Commandé face à réellement reçu, ligne par ligne, plus la valeur de ce
    qui manque — c'est le montant qu'on oppose au fournisseur, pas la
    quantité."""
    if crud_order.get_order(db, tenant_id, order_id) is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return order_service.progress_for_order(db, tenant_id, order_id)


@router.patch("/{order_id}")
def api_update_order(
    order_id: str,
    payload: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    order = crud_order.get_order(db, tenant_id, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if payload.status is not None and payload.status != order.status:
        if not order_service.can_transition(order.status, payload.status):
            current = order_service.STATUS_LABELS.get(order.status or "", order.status)
            target = order_service.STATUS_LABELS.get(payload.status, payload.status)
            raise HTTPException(
                status_code=409,
                detail=f"Une commande « {current} » ne peut pas passer à « {target} »",
            )
        order.status = payload.status
        now = datetime.now()
        # Horodater le passage plutôt qu'un `updated_at` fourre-tout : « envoyée
        # quand ? » et « confirmée quand ? » sont deux questions distinctes, et
        # ce sont celles qu'on pose à un fournisseur en retard.
        if payload.status == order_service.SENT and order.sent_at is None:
            order.sent_at = now
            order.ordered_at = order.ordered_at or now
        elif payload.status == order_service.CONFIRMED and order.confirmed_at is None:
            order.confirmed_at = now
        elif payload.status in (order_service.CLOSED, order_service.CANCELLED):
            order.closed_at = now

    if payload.expected_date is not None:
        order.expected_date = payload.expected_date
    if payload.notes is not None:
        order.notes = payload.notes
    if payload.conditions is not None:
        order.conditions = payload.conditions

    db.commit()
    db.refresh(order)
    # Le détail complet, pas seulement l'en-tête : le client vient de modifier
    # la commande, il la réaffiche dans la foulée.
    return crud_order.detail(db, tenant_id, order)


@router.delete("/{order_id}", status_code=204)
def api_delete_order(
    order_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    order = crud_order.get_order(db, tenant_id, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    # Une commande partie chez le fournisseur ne se supprime pas : elle
    # s'annule. Effacer la trace d'un engagement pris est une réécriture de
    # l'histoire, et c'est précisément ce qu'un ERP doit empêcher.
    if order.status not in (order_service.DRAFT, order_service.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail="Une commande déjà engagée s'annule, elle ne se supprime pas",
        )
    crud_order.delete_order(db, order)
    return None
