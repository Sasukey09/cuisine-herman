"""Tenant-ownership guards for client-supplied row ids.

Several write paths take a raw ``product_id`` straight from the request body:
mapping an invoice line to a product, adding a recipe ingredient, validating an
imported recipe. Nothing used to check that the id belongs to the caller's
organization, so a tenant could plant a reference to another tenant's product —
and cost recomputation would then walk into that organization's recipes.

The guard lives at the service layer so every caller is covered (HTTP endpoints,
Celery tasks, AI tools). It raises a plain domain exception rather than an
``HTTPException``: ``app.main`` translates it into a 404 at the web boundary,
which keeps this module usable outside a request (and free of FastAPI).
"""
from typing import Iterable, List, Set

from sqlalchemy.orm import Session

from app.models.models import Product


class CrossTenantReferenceError(Exception):
    """A caller referenced a row owned by another organization."""

    def __init__(self, kind: str = "product", ids: Iterable[str] = ()) -> None:
        self.kind = kind
        self.ids: List[str] = [str(i) for i in ids]
        super().__init__(f"Unknown {kind} for this organization")


def owned_product_ids(db: Session, tenant_id: str, product_ids: Iterable[str]) -> Set[str]:
    """Subset of ``product_ids`` that really belongs to ``tenant_id``."""
    wanted = {str(pid) for pid in product_ids if pid}
    if not wanted:
        return set()
    rows = (
        db.query(Product.id)
        .filter(Product.tenant_id == tenant_id, Product.id.in_(wanted))
        .all()
    )
    return {str(row[0]) for row in rows}


def assert_products_in_tenant(db: Session, tenant_id: str, product_ids: Iterable[str]) -> None:
    """Reject any product id the caller does not own.

    Raises :class:`CrossTenantReferenceError`, surfaced as a 404 (not a 403: a
    403 would confirm the id exists in *someone else's* organization).
    """
    wanted = {str(pid) for pid in product_ids if pid}
    if not wanted:
        return
    missing = wanted - owned_product_ids(db, tenant_id, wanted)
    if missing:
        raise CrossTenantReferenceError("product", sorted(missing))


def assert_product_in_tenant(db: Session, tenant_id: str, product_id) -> None:
    if product_id:
        assert_products_in_tenant(db, tenant_id, [product_id])
