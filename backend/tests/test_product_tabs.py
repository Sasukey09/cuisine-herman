"""Product detail tabs backend (Phase 2): the product's category/unit detail, the
invoices that contain it, and the recipes whose current version use it. DB-backed
(real Postgres in CI; skips locally)."""

import uuid
from datetime import date

from app.crud import crud_product
from app.models.models import (
    Invoice,
    InvoiceLine,
    Organization,
    Product,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
    Supplier,
    Unit,
)
from app.schemas.schemas import ProductCreate


def test_product_detail_invoices_and_recipes(db):
    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Tabs Test"))
    db.commit()

    supplier_id = str(uuid.uuid4())
    db.add(Supplier(id=supplier_id, tenant_id=tenant_id, name="Metro"))
    db.commit()

    kg = db.query(Unit).filter(Unit.code == "kg").first()

    # A product created through the CRUD so it gets auto-classified.
    product = crud_product.create_product(
        db, ProductCreate(name="Filet de saumon", base_unit_id=kg.id if kg else None), tenant_id
    )
    product_id = str(product.id)

    # --- Informations tab: detail carries the category name + unit code. --------
    detail = crud_product.get_product_detail(db, product_id, tenant_id)
    assert detail is not None
    assert detail["category"] == "Poisson"  # auto-classified
    if kg:
        assert detail["unit"] == "kg"

    # --- Factures tab: an invoice with a line for this product. ------------------
    invoice_id = str(uuid.uuid4())
    db.add(
        Invoice(
            id=invoice_id,
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            invoice_number="INV-1",
            date=date(2026, 2, 1),
            total_amount=100,
            currency="EUR",
        )
    )
    db.commit()
    db.add(
        InvoiceLine(
            id=str(uuid.uuid4()),
            invoice_id=invoice_id,
            product_id=product_id,
            description="Saumon",
            qty=2,
            unit_price=15,
            line_total=30,
            currency="EUR",
        )
    )
    db.commit()

    invoices = crud_product.product_invoices(db, tenant_id, product_id)
    assert len(invoices) == 1
    assert invoices[0]["invoice_id"] == invoice_id
    assert invoices[0]["invoice_number"] == "INV-1"
    assert invoices[0]["supplier_name"] == "Metro"
    assert invoices[0]["qty"] == 2.0
    assert invoices[0]["line_total"] == 30.0

    # --- Recettes tab: a recipe whose current version uses the product. ---------
    recipe_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Recipe(id=recipe_id, tenant_id=tenant_id, name="Saumon grillé", current_version_id=version_id))
    db.commit()
    db.add(RecipeVersion(id=version_id, recipe_id=recipe_id, version_number=1))
    db.commit()
    db.add(
        RecipeIngredient(
            id=str(uuid.uuid4()),
            recipe_version_id=version_id,
            product_id=product_id,
            ingredient_name="Filet de saumon",
            qty=0.2,
            unit_id=kg.id if kg else None,
        )
    )
    db.commit()

    recipes = crud_product.product_recipes(db, tenant_id, product_id)
    assert len(recipes) == 1
    assert recipes[0]["recipe_id"] == recipe_id
    assert recipes[0]["name"] == "Saumon grillé"

    # A product not used anywhere lists nothing.
    other = crud_product.create_product(db, ProductCreate(name="Sel fin"), tenant_id)
    assert crud_product.product_invoices(db, tenant_id, str(other.id)) == []
    assert crud_product.product_recipes(db, tenant_id, str(other.id)) == []
