"""Le food cost d'un instantané — contre un vrai PostgreSQL.

La recette connaît son prix de vente. `compute_recipe_version_cost` n'utilisait
pourtant QUE celui qu'on lui passait. Or le panneau de coût propose une case vide
marquée « (optionnel) » : un chef qui clique simplement sur « Calculer » — la chose
évidente à faire — enregistrait un instantané avec `food_cost_pct = NULL`.

Le tableau de bord lit ces instantanés et garde ceux au-dessus de 35 %. `NULL` n'est
pas au-dessus de 35 %. Donc **aucune alerte de marge ne pouvait jamais se
déclencher** — et personne ne s'en apercevait, parce qu'une alerte qui ne part jamais
ressemble exactement à un restaurant aux marges saines.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.models import (
    Organization,
    Product,
    ProductPrice,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
    Supplier,
    Unit,
)
from app.services.costing import cost_engine
from app.services.dashboard import dashboard_service
from app.services.rgpd import service as rgpd


@pytest.fixture
def plat(db):
    """Un plat à 24 € de matière, vendu 30 € : food cost 80 %, bien au-dessus de 35 %."""
    cost_engine.reset_unit_cache()

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Marges"))
    db.commit()

    supplier_id, product_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Supplier(id=supplier_id, tenant_id=tenant_id, name="Rungis"))
    db.add(Product(id=product_id, tenant_id=tenant_id, name="Truffe"))
    db.commit()

    kg = db.query(Unit).filter(Unit.code == "kg").first()
    g = db.query(Unit).filter(Unit.code == "g").first()
    db.add(
        ProductPrice(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            product_id=product_id,
            supplier_id=supplier_id,
            price=Decimal("800.00"),
            unit_id=kg.id,
            currency="EUR",
            effective_date=date(2026, 1, 1),
        )
    )

    recipe_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(
        Recipe(
            id=recipe_id,
            tenant_id=tenant_id,
            name="Risotto truffé",
            yield_qty=1,
            selling_price=Decimal("30.00"),   # la recette SAIT ce qu'elle vaut
        )
    )
    db.commit()
    db.add(RecipeVersion(id=version_id, recipe_id=recipe_id, version_number=1))
    db.commit()
    db.add(
        RecipeIngredient(
            id=str(uuid.uuid4()),
            recipe_version_id=version_id,
            product_id=product_id,
            ingredient_name="Truffe",
            qty=Decimal("30"),               # 30 g × 800 €/kg = 24 €
            unit_id=g.id,
        )
    )
    db.query(Recipe).filter(Recipe.id == recipe_id).update({"current_version_id": version_id})
    db.commit()

    yield {"tenant_id": tenant_id, "version_id": version_id}

    rgpd.delete_organization(db, tenant_id)
    cost_engine.reset_unit_cache()


def test_le_food_cost_est_calcule_sans_qu_on_redonne_le_prix_de_vente(db, plat):
    """Le chef clique sur « Calculer ». Il ne retape rien. Ça doit suffire."""
    result = cost_engine.compute_recipe_version_cost(
        db, plat["tenant_id"], plat["version_id"], persist=False
    )

    assert result["cost_per_portion"] == pytest.approx(24.0)
    assert result["food_cost_pct"] == pytest.approx(80.0), (
        "la recette connaît son prix de vente ; lui redemander est ce qui produisait un NULL"
    )
    assert result["margin_estimated"] == pytest.approx(6.0)


def test_l_instantane_enregistre_porte_le_food_cost(db, plat):
    """C'est l'instantané que les alertes lisent. S'il est vide, elles sont aveugles."""
    result = cost_engine.compute_recipe_version_cost(
        db, plat["tenant_id"], plat["version_id"], persist=True
    )
    assert result["snapshot_id"]
    assert result["food_cost_pct"] == pytest.approx(80.0)


def test_l_alerte_de_marge_peut_enfin_se_declencher(db, plat):
    """La conséquence réelle du bug : `NULL` n'est pas supérieur à 35 %, donc aucune
    alerte ne partait jamais — et un restaurant sans alertes ressemble à un
    restaurant en bonne santé."""
    cost_engine.compute_recipe_version_cost(
        db, plat["tenant_id"], plat["version_id"], persist=True
    )

    alertes = dashboard_service.margin_alerts(db, plat["tenant_id"], max_food_cost_pct=35.0)

    assert len(alertes) == 1
    assert alertes[0]["food_cost_pct"] == pytest.approx(80.0)


def test_un_prix_explicite_l_emporte_toujours(db, plat):
    """C'est tout l'intérêt de la case : simuler « et si je le vendais 60 € ? » sans
    toucher à la recette."""
    result = cost_engine.compute_recipe_version_cost(
        db, plat["tenant_id"], plat["version_id"], selling_price=60.0, persist=False
    )

    assert result["food_cost_pct"] == pytest.approx(40.0)   # 24 / 60
    assert result["margin_estimated"] == pytest.approx(36.0)

    inchange = db.query(Recipe).filter(Recipe.id.isnot(None)).filter(
        Recipe.tenant_id == plat["tenant_id"]
    ).first()
    assert float(inchange.selling_price) == 30.0, "la simulation ne doit pas modifier la carte"
