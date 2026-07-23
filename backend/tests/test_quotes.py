"""Quote comparator — CRUD + comparison + order against a real Postgres.

Skips when DATABASE_URL is absent (like the other *_real_db checks); runs in CI.
The pure basket maths is covered in ``test_quote_comparator.py``."""

import uuid
from datetime import date

from app.schemas.schemas import (
    QuoteCreate,
    QuoteLineCreate,
    QuoteUpdate,
    QuoteConfirmLine,
    QuoteConfirmRequest,
)
from app.crud import crud_quote
from app.services.quotes import quote_service, quote_import


def _seed(db):
    from app.models.models import (
        Organization,
        Product,
        PurchaseHistory,
        Supplier,
        Unit,
    )

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Devis Test"))
    db.commit()

    sup_a, sup_b = str(uuid.uuid4()), str(uuid.uuid4())
    p1, p2 = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Supplier(id=sup_a, tenant_id=tenant_id, name="Metro"))
    db.add(Supplier(id=sup_b, tenant_id=tenant_id, name="Transgourmet"))
    db.add(Product(id=p1, tenant_id=tenant_id, name="Farine T55"))
    db.add(Product(id=p2, tenant_id=tenant_id, name="Beurre doux"))
    db.commit()

    kg = db.query(Unit).filter(Unit.code == "kg").first()

    def buy(sid, pid, cost, d):
        db.add(
            PurchaseHistory(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                product_id=pid,
                supplier_id=sid,
                purchase_date=d,
                unit_id=kg.id if kg else None,
                unit_code="kg",
                unit_cost_standard=cost,
                currency="EUR",
            )
        )

    # A: p1=1.0, p2=8.0 (basket 26) ; B: p1=1.2, p2=6.5 (basket 25 -> cheapest)
    buy(sup_a, p1, 1.0, date(2026, 1, 1))
    buy(sup_a, p2, 8.0, date(2026, 1, 1))
    buy(sup_b, p1, 1.2, date(2026, 1, 2))
    buy(sup_b, p2, 6.5, date(2026, 1, 2))
    db.commit()
    return tenant_id, sup_a, sup_b, p1, p2


def test_quote_create_compare_and_order(db):
    tenant_id, sup_a, sup_b, p1, p2 = _seed(db)

    quote = crud_quote.create_quote(
        db,
        tenant_id,
        QuoteCreate(
            title="Réappro janvier",
            lines=[
                QuoteLineCreate(product_id=p1, qty=10),
                QuoteLineCreate(product_id=p2, qty=2),
            ],
        ),
    )
    assert quote.reference.startswith("DEV-")
    assert quote.status == "draft"

    lines = crud_quote.get_lines(db, tenant_id, str(quote.id))
    assert len(lines) == 2

    # --- comparison ---
    comp = quote_service.comparison(db, tenant_id, quote, lines)
    by = {s["supplier_id"]: s for s in comp["suppliers"]}
    assert by[sup_a]["total"] == 26.0
    assert by[sup_b]["total"] == 25.0
    assert by[sup_a]["is_full_coverage"] and by[sup_b]["is_full_coverage"]
    assert comp["cheapest_supplier_id"] == sup_b
    assert comp["suppliers"][0]["supplier_id"] == sup_b  # cheapest sorts first

    # --- order from the cheaper supplier: snapshot prices + total ---
    totals = quote_service.supplier_totals(db, tenant_id, lines, sup_b)
    cost_by_product = {l["product_id"]: l["unit_cost"] for l in totals["lines"]}
    crud_quote.mark_ordered(db, quote, sup_b, totals["total"], cost_by_product)

    ordered = crud_quote.get_quote(db, tenant_id, str(quote.id))
    assert ordered.status == "ordered"
    assert str(ordered.supplier_id) == sup_b
    assert float(ordered.total_amount) == 25.0
    assert ordered.ordered_at is not None

    ol = {str(l.product_id): l for l in crud_quote.get_lines(db, tenant_id, str(quote.id))}
    assert float(ol[p1].unit_price) == 1.2
    assert float(ol[p2].unit_price) == 6.5
    assert str(ol[p1].supplier_id) == sup_b
    assert str(ol[p2].supplier_id) == sup_b


def test_reference_increments_per_tenant(db):
    tenant_id, *_ = _seed(db)
    q1 = crud_quote.create_quote(db, tenant_id, QuoteCreate(title="A", lines=[]))
    q2 = crud_quote.create_quote(db, tenant_id, QuoteCreate(title="B", lines=[]))
    assert q1.reference != q2.reference
    assert q1.reference[:8] == q2.reference[:8]  # DEV-YYYY prefix shared


def test_list_read_and_line_crud(db):
    tenant_id, sup_a, sup_b, p1, p2 = _seed(db)
    quote = crud_quote.create_quote(
        db, tenant_id, QuoteCreate(title="X", lines=[QuoteLineCreate(product_id=p1, qty=5)])
    )

    reads = crud_quote.list_read(db, tenant_id)
    assert len(reads) == 1
    assert reads[0]["line_count"] == 1
    assert reads[0]["title"] == "X"

    # add a second line, then the read count follows
    crud_quote.add_line(db, tenant_id, str(quote.id), QuoteLineCreate(product_id=p2, qty=3))
    assert crud_quote.list_read(db, tenant_id)[0]["line_count"] == 2

    lines_read = crud_quote.lines_read(db, tenant_id, str(quote.id))
    names = {l["product_id"]: l["product_name"] for l in lines_read}
    assert names[p1] == "Farine T55"
    assert names[p2] == "Beurre doux"

    # update the quote title/status
    crud_quote.update_quote(db, quote, QuoteUpdate(title="X2", status="archived"))
    refreshed = crud_quote.get_quote(db, tenant_id, str(quote.id))
    assert refreshed.title == "X2"
    assert refreshed.status == "archived"

    # delete a line
    first = crud_quote.get_lines(db, tenant_id, str(quote.id))[0]
    crud_quote.delete_line(db, first)
    assert len(crud_quote.get_lines(db, tenant_id, str(quote.id))) == 1


def test_delete_quote_removes_its_lines_even_when_ordered(db):
    """Regression: deleting a quote must cascade to its lines. quote_lines.quote_id
    is NOT NULL, so the ORM's default nullify-on-parent-delete 500'd; the relation
    now relies on the DB ON DELETE CASCADE (found live: DELETE /quotes/{id} -> 500)."""
    from app.models.models import QuoteLine

    tenant_id, sup_a, sup_b, p1, p2 = _seed(db)

    # a draft quote with lines
    draft = crud_quote.create_quote(
        db, tenant_id, QuoteCreate(title="Draft", lines=[QuoteLineCreate(product_id=p1, qty=2)])
    )
    draft_id = str(draft.id)
    crud_quote.delete_quote(db, draft)
    assert crud_quote.get_quote(db, tenant_id, draft_id) is None
    assert db.query(QuoteLine).filter(QuoteLine.quote_id == draft_id).count() == 0

    # an ORDERED quote (the exact case that failed live) with snapshotted lines
    ordered = crud_quote.create_quote(
        db,
        tenant_id,
        QuoteCreate(
            title="Ordered",
            lines=[QuoteLineCreate(product_id=p1, qty=10), QuoteLineCreate(product_id=p2, qty=2)],
        ),
    )
    ordered_id = str(ordered.id)
    lines = crud_quote.get_lines(db, tenant_id, ordered_id)
    totals = quote_service.supplier_totals(db, tenant_id, lines, sup_b)
    crud_quote.mark_ordered(
        db,
        ordered,
        sup_b,
        totals["total"],
        {l["product_id"]: l["unit_cost"] for l in totals["lines"]},
    )
    assert crud_quote.get_quote(db, tenant_id, ordered_id).status == "ordered"

    crud_quote.delete_quote(db, ordered)
    assert crud_quote.get_quote(db, tenant_id, ordered_id) is None
    assert db.query(QuoteLine).filter(QuoteLine.quote_id == ordered_id).count() == 0


def test_confirm_import_creates_quote_products_and_catalog_links(db):
    """Import validé : crée le devis (en-tête OCR), les lignes enrichies, les
    produits manquants, et le lien catalogue produit↔fournisseur."""
    from app.models.models import Product, SupplierProduct

    tenant_id, sup_a, sup_b, p1, p2 = _seed(db)

    payload = QuoteConfirmRequest(
        title="Import devis METRO",
        supplier_id=sup_a,
        date=date(2026, 7, 20),
        valid_until=date(2026, 8, 20),
        quote_number="D-2026-88",
        total_amount=143.75,
        currency="EUR",
        discount_total=12.5,
        conditions="virement à 30 jours",
        lines=[
            # associe un produit existant
            QuoteConfirmLine(
                description="Farine T55", action="associate", product_id=p1,
                qty=10, unit_price=1.05, line_total=10.5, vat_rate=5.5,
                discount_pct=2, pack_size="sac 25 kg",
            ),
            # crée un produit inexistant
            QuoteConfirmLine(
                description="Huile d'olive vierge", action="create",
                qty=6, unit_price=8.90, line_total=53.4, vat_rate=5.5,
            ),
            # ignorée
            QuoteConfirmLine(description="Frais de port", action="skip"),
        ],
    )

    out = quote_import.confirm_import(db, tenant_id, payload)

    assert out["lines"] == 2
    assert out["created_products"] == 1
    assert out["associated"] == 1
    assert out["skipped"] == 1
    assert out["reference"].startswith("DEV-")

    # --- en-tête OCR persisté ---
    quote = crud_quote.get_quote(db, tenant_id, out["quote_id"])
    assert quote.quote_number == "D-2026-88"
    assert quote.date == date(2026, 7, 20)
    assert quote.valid_until == date(2026, 8, 20)
    assert quote.conditions == "virement à 30 jours"
    assert float(quote.discount_total) == 12.5
    assert quote.parsed is True
    assert str(quote.supplier_id) == sup_a

    # --- lignes enrichies ---
    lines = {l.description: l for l in crud_quote.get_lines(db, tenant_id, out["quote_id"])}
    assert "Frais de port" not in lines  # ignorée
    farine = lines["Farine T55"]
    assert str(farine.product_id) == p1
    assert float(farine.vat_rate) == 5.5
    assert float(farine.discount_pct) == 2
    assert farine.pack_size == "sac 25 kg"
    assert float(farine.line_total) == 10.5

    # --- produit créé, rattaché au tenant ---
    huile = (
        db.query(Product)
        .filter(Product.tenant_id == tenant_id, Product.name == "Huile d'olive vierge")
        .first()
    )
    assert huile is not None

    # --- lien catalogue produit↔fournisseur (dispo/délai du comparateur) ---
    links = (
        db.query(SupplierProduct)
        .filter(
            SupplierProduct.tenant_id == tenant_id,
            SupplierProduct.supplier_id == sup_a,
            SupplierProduct.product_id.in_([p1, str(huile.id)]),
        )
        .count()
    )
    assert links == 2


def test_confirm_import_never_writes_purchase_history_or_prices(db):
    """Garantie centrale : un devis est une OFFRE, pas un achat.

    Ses prix ne doivent JAMAIS alimenter product_prices / purchase_history,
    sinon le coût matière des recettes serait calculé sur des prix jamais payés.
    """
    from app.models.models import ProductPrice, PurchaseHistory

    tenant_id, sup_a, sup_b, p1, p2 = _seed(db)

    before_prices = (
        db.query(ProductPrice).filter(ProductPrice.tenant_id == tenant_id).count()
    )
    before_history = (
        db.query(PurchaseHistory).filter(PurchaseHistory.tenant_id == tenant_id).count()
    )

    quote_import.confirm_import(
        db,
        tenant_id,
        QuoteConfirmRequest(
            supplier_id=sup_a,
            quote_number="D-NO-PRICE",
            lines=[
                QuoteConfirmLine(
                    description="Farine T55", action="associate", product_id=p1,
                    qty=100, unit_price=0.01,  # prix absurde : s'il fuitait, ça se verrait
                ),
                QuoteConfirmLine(
                    description="Produit tout neuf", action="create",
                    qty=5, unit_price=999.0,
                ),
            ],
        ),
    )

    assert (
        db.query(ProductPrice).filter(ProductPrice.tenant_id == tenant_id).count()
        == before_prices
    ), "un devis ne doit pas créer de prix produit"
    assert (
        db.query(PurchaseHistory).filter(PurchaseHistory.tenant_id == tenant_id).count()
        == before_history
    ), "un devis ne doit pas créer d'historique d'achat"
