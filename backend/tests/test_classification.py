"""Rule-based product classifier — the piece that makes classification actually
do something (category_id used to be permanently NULL). Pure, DB-free."""

import pytest

from app.services.classification.classifier import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    classify,
    coerce_category,
)


@pytest.mark.parametrize(
    "name,expected",
    [
        # Meat vs fish disambiguation (the tie-break that motivates the order).
        ("Filet de saumon frais", "Poisson"),
        ("Filet de bœuf", "Viande"),
        ("Escalope de poulet", "Viande"),
        ("Crevettes roses", "Poisson"),
        # Dairy vs the look-alike "laitue" (lettuce) must NOT collide.
        ("Lait entier 1L", "Produits laitiers"),
        ("Laitue iceberg", "Légumes"),
        ("Œufs frais x6", "Produits laitiers"),
        # Plurals resolve like the singular.
        ("Tomates cerises", "Légumes"),
        ("Pommes Golden", "Fruits"),
        # Multi-word keyword outranks a single-word match elsewhere.
        ("Pommes de terre Charlotte", "Légumes"),
        # Other buckets.
        ("Baguette tradition", "Boulangerie"),
        ("Coca-Cola 33cl", "Boissons"),
        ("Sac poubelle 50L", "Emballages"),
        ("Liquide vaisselle citron", "Hygiène"),
        ("Moutarde de Dijon", "Condiments"),
        ("Farine de blé T55", "Épicerie"),
        ("Tablette de chocolat noir", "Desserts"),
        ("Petits pois surgelés", "Surgelés"),
    ],
)
def test_classify_common_products(name, expected):
    assert classify(name) == expected


def test_unknown_falls_back_to_autres():
    assert classify("Widget XYZ 42") == DEFAULT_CATEGORY
    assert classify("") == DEFAULT_CATEGORY
    assert classify("   ") == DEFAULT_CATEGORY


def test_extra_text_helps_disambiguate():
    # A bare "filet" is ambiguous; the supplier hint tips it.
    assert classify("Filet", extra="Poissonnerie de la mer") == "Poisson"


def test_every_result_is_a_known_category():
    for name in ["Saumon", "Pain", "Eau", "Chose inconnue"]:
        assert classify(name) in CATEGORIES


def test_coerce_category_maps_onto_taxonomy():
    assert coerce_category("legumes") == "Légumes"
    assert coerce_category("PRODUITS LAITIERS") == "Produits laitiers"
    assert coerce_category(None) is None
    # Unknown custom values are preserved, not dropped.
    assert coerce_category("Ma catégorie perso") == "Ma catégorie perso"


def test_categories_endpoint_returns_the_taxonomy():
    """GET /products/categories feeds the UI's category picker — no DB needed."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.api.deps import get_current_tenant_id

    app.dependency_overrides[get_current_tenant_id] = lambda: "test-tenant"
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/products/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data == CATEGORIES
        assert len(data) == 14
        assert "Viande" in data and "Autres" in data
    finally:
        app.dependency_overrides.clear()
