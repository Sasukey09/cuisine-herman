# Fiche produit 360° (morceau A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une fiche produit 360° (le miroir produit-centré de la fiche fournisseur), en **assemblage des read models existants — aucune duplication, aucune migration.**

**Architecture:** Un cœur pur `product_analytics.scorecard` (agrège le ledger d'achat en série mensuelle / dépense / top fournisseurs / inflation, structure les blocs) + une enveloppe `overview` qui rassemble depuis les read models déjà là ; `savings_service.for_product` (one-liner) ; endpoint `GET /products/{id}/overview` ; l'onglet « Statistiques » de la fiche produit (aujourd'hui client-side) devient un `ProductScorecard` serveur (web + mobile).

**Tech Stack:** FastAPI + SQLAlchemy ; Next.js 15 / React 19 / TS / TanStack Query (web), Flutter + Riverpod + Dio (mobile), pytest, flutter_test.

## Global Constraints

- **Assemblage, pas duplication** : réutiliser tel quel `crud_purchase.product_purchases`, `purchase_service.product_suppliers`, `quote_history.product_quote_history`, `crud_product.product_recipes`/`get_product_detail`, `supplier_analytics._price_trend`, `savings_service`.
- **Produit-centré** : PAS de `conformity_rate`/`on_time_rate`/`score`/`late_count` (vertus fournisseur). AJOUTE `top_suppliers`, `cheapest_supplier`, bloc `offers`.
- **Aucune table / migration** : lecture pure. AST guard `test_model_attribute_contract.py` vert sans modification.
- **Fenêtre = 12 mois glissants** (`since = today − 365 j`).
- **Routes littérales avant `/{id}`** : `GET /{product_id}/overview` déclaré avec les autres sous-routes `/{product_id}/…`, AVANT `GET /{product_id}`. Read-only (`get_current_tenant_id` + `get_db`, garde `get_product` → 404).
- **Jamais mocker la session BDD** : l'enveloppe se teste `*_real_db` (skip local, CI, `cost_engine.reset_unit_cache()` dans la fixture car l'overview touche les prix/coûts). Le cœur pur `scorecard` se teste sans base.
- **Forme de retour `overview`** (contrat inter-tâches) :
  ```python
  {"product_id","product_name","category","unit_code",
   "annual_amount","monthly":[{month,amount}],
   "purchase_count","supplier_count","recipe_count","offer_count",
   "cheapest_supplier":{supplier_id,supplier_name,cost}|None,
   "last_cost","avg_cost","best_cost","price_trend_pct",
   "offers":{best_price,best_supplier_name,latest_price,avg_price,supplier_count}|None,
   "savings":{realized,missed,possible,best_choice_rate,compared_lines,labels},
   "top_suppliers":[{supplier_id,supplier_name,amount,count,is_cheapest}]}
  ```
- Commit trailer : `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Commande pytest (pure, locale) : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest <chemin> -q -p no:cacheprovider --no-cov`

---

## File Structure

| Fichier | Rôle | Action |
|---|---|---|
| `backend/app/services/purchasing/product_analytics.py` | cœur pur `scorecard` + enveloppe `overview` | **Créer** |
| `backend/app/services/purchasing/savings_service.py` | + `for_product` (miroir `for_supplier`) | **Modifier** |
| `backend/app/api/api_v1/endpoints/products.py` | `GET /{product_id}/overview` | **Modifier** |
| `backend/tests/test_product_analytics.py` | tests purs de `scorecard` | **Créer** |
| `backend/tests/test_product_overview_real_db.py` | round-trip `GET /products/{id}/overview` | **Créer** |
| `frontend/src/services/products-service.ts` + `use-products.ts` | `ProductOverview` + `getProductOverview` + `useProductOverview` | **Modifier** |
| `frontend/src/features/products/product-scorecard.tsx` | scorecard produit (miroir `SupplierScorecard`) | **Créer** |
| `frontend/src/features/products/product-detail.tsx` | onglet « Statistiques » → « Vue d'ensemble » = `<ProductScorecard>` | **Modifier** |
| `mobile/lib/features/products/product_detail_screen.dart` | onglet « Stats » → `_Scorecard` produit + provider | **Modifier** |
| `mobile/test/product_overview_test.dart` | widget test | **Créer** |

---

## Task 1 : Cœur pur `product_analytics.scorecard`

**Files:**
- Create: `backend/app/services/purchasing/product_analytics.py` (partie pure)
- Test: `backend/tests/test_product_analytics.py`

**Interfaces:**
- Consumes: `supplier_analytics._price_trend(purchases, today)` (réutilisé).
- Produces: `scorecard(purchases, quote_history, savings, cheapest, recipe_count, today) -> dict` (forme = Global Constraints, sans l'en-tête produit que l'enveloppe ajoute).

- [ ] **Step 1 : Écrire les tests qui échouent**

`backend/tests/test_product_analytics.py` :

```python
from datetime import date
from app.services.purchasing.product_analytics import scorecard

TODAY = date(2026, 7, 28)


def _p(when, sid, name, total, cost):
    return {"purchase_date": when, "supplier_id": sid, "supplier_name": name,
            "total_price": total, "unit_cost_standard": cost}


def _sav():
    return {"realized": 20.0, "missed": 0.0, "possible": 20.0, "best_choice_rate": 1.0,
            "compared_lines": 1, "labels": {"realized": "Économisé"}}


def test_monthly_and_annual_from_purchases():
    card = scorecard(
        [_p(date(2026, 6, 5), "a", "A", 100, 10.0), _p(date(2026, 6, 20), "a", "A", 50, 10.0),
         _p(date(2026, 7, 2), "b", "B", 200, 12.0)],
        {"count": 0}, _sav(), None, 0, TODAY)
    assert card["annual_amount"] == 350.0
    assert card["monthly"] == [{"month": "2026-06", "amount": 150.0}, {"month": "2026-07", "amount": 200.0}]
    assert card["purchase_count"] == 3 and card["supplier_count"] == 2


def test_top_suppliers_ranked_with_cheapest_flag():
    card = scorecard(
        [_p(date(2026, 7, 1), "a", "A", 100, 10.0), _p(date(2026, 7, 2), "b", "B", 400, 12.0),
         _p(date(2026, 7, 3), "a", "A", 50, 10.0)],
        {"count": 0}, _sav(), {"supplier_id": "a", "supplier_name": "A", "cost": 10.0}, 0, TODAY)
    assert card["top_suppliers"][0]["supplier_id"] == "b"           # B: 400
    assert card["top_suppliers"][1]["amount"] == 150.0              # A cumulé
    assert card["top_suppliers"][1]["is_cheapest"] is True and card["top_suppliers"][0]["is_cheapest"] is False
    assert card["cheapest_supplier"] == {"supplier_id": "a", "supplier_name": "A", "cost": 10.0}


def test_costs_and_price_trend():
    # 6 vieux mois à 10, 6 récents à 12 → +20 %
    card = scorecard(
        [_p(date(2025, 9, 1), "a", "A", 100, 10.0), _p(date(2026, 7, 1), "a", "A", 100, 12.0)],
        {"count": 0}, _sav(), None, 0, TODAY)
    assert card["last_cost"] == 12.0 and card["best_cost"] == 10.0 and card["avg_cost"] == 11.0
    assert card["price_trend_pct"] == 20.0


def test_offers_block_and_counts():
    qh = {"count": 3, "supplier_count": 2, "best_price": 9.5, "best_supplier_name": "A",
          "latest_price": 10.0, "avg_price": 10.5}
    card = scorecard([], qh, _sav(), None, 4, TODAY)
    assert card["offer_count"] == 3 and card["recipe_count"] == 4
    assert card["offers"] == {"best_price": 9.5, "best_supplier_name": "A",
                              "latest_price": 10.0, "avg_price": 10.5, "supplier_count": 2}
    assert card["savings"]["realized"] == 20.0


def test_empty_product_is_honest_and_product_centric():
    card = scorecard([], {"count": 0}, _sav(), None, 0, TODAY)
    assert card["annual_amount"] == 0.0 and card["top_suppliers"] == [] and card["monthly"] == []
    assert card["offers"] is None and card["price_trend_pct"] is None
    # produit-centré : PAS de champs fournisseur-only
    for k in ("conformity_rate", "on_time_rate", "score", "late_count"):
        assert k not in card
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_product_analytics.py -q -p no:cacheprovider --no-cov`
Expected : FAIL (`ModuleNotFoundError: product_analytics`).

- [ ] **Step 3 : Implémenter le cœur pur**

Créer `backend/app/services/purchasing/product_analytics.py` (partie pure) :

```python
"""Fiche produit 360° : tout ce que le domaine Achats sait d'un produit.

Le miroir produit-centré de ``supplier_analytics`` : au lieu de juger un
fournisseur (conformité, ponctualité), on éclaire un produit — combien il coûte,
chez qui, comment son prix dérive, ce que la concurrence fait gagner. Aucune
logique métier neuve : le cœur ``scorecard`` agrège des données déjà lues et
l'enveloppe ``overview`` (plus bas) les rassemble depuis les read models existants.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.services.purchasing.supplier_analytics import _price_trend


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def scorecard(
    purchases: List[Dict[str, Any]],
    quote_history: Dict[str, Any],
    savings: Dict[str, Any],
    cheapest: Optional[Dict[str, Any]],
    recipe_count: int,
    today: date,
) -> Dict[str, Any]:
    """Agrège l'activité d'achat d'un produit (pur).

    - ``purchases`` : ``{purchase_date, supplier_id, supplier_name, total_price,
      unit_cost_standard}``, du plus ANCIEN au plus RÉCENT (comme
      ``crud_purchase.product_purchases``).
    - ``quote_history`` : sortie de ``quote_history.product_quote_history``.
    - ``savings`` : sortie de ``savings_service.for_product``.
    - ``cheapest`` : ``{supplier_id, supplier_name, cost}`` ou None.
    """
    year_ago = today - timedelta(days=365)
    in_window = [p for p in purchases if p.get("purchase_date") and p["purchase_date"] >= year_ago]
    annual_amount = round(sum(_f(p.get("total_price")) or 0.0 for p in in_window), 2)

    monthly: Dict[str, float] = {}
    for p in in_window:
        d = p["purchase_date"]
        key = f"{d.year:04d}-{d.month:02d}"
        monthly[key] = round(monthly.get(key, 0.0) + (_f(p.get("total_price")) or 0.0), 2)
    monthly_series = [{"month": k, "amount": v} for k, v in sorted(monthly.items())]

    cheapest_sid = cheapest.get("supplier_id") if cheapest else None
    by_sup: Dict[str, Dict[str, Any]] = {}
    for p in purchases:
        sid = p.get("supplier_id")
        if not sid:
            continue
        row = by_sup.setdefault(
            str(sid), {"supplier_id": str(sid), "supplier_name": p.get("supplier_name"),
                       "amount": 0.0, "count": 0}
        )
        row["amount"] = round(row["amount"] + (_f(p.get("total_price")) or 0.0), 2)
        row["count"] += 1
    for r in by_sup.values():
        r["is_cheapest"] = r["supplier_id"] == str(cheapest_sid) if cheapest_sid else False
    top_suppliers = sorted(by_sup.values(), key=lambda r: -r["amount"])

    costs = [c for c in (_f(p.get("unit_cost_standard")) for p in purchases) if c is not None]
    last_cost = None
    for p in purchases:  # ancien→récent : le dernier coût vu est le plus récent
        c = _f(p.get("unit_cost_standard"))
        if c is not None:
            last_cost = c
    avg_cost = round(sum(costs) / len(costs), 4) if costs else None
    best_cost = min(costs) if costs else None

    qh = quote_history or {}
    offers = (
        {"best_price": qh.get("best_price"), "best_supplier_name": qh.get("best_supplier_name"),
         "latest_price": qh.get("latest_price"), "avg_price": qh.get("avg_price"),
         "supplier_count": qh.get("supplier_count")}
        if qh.get("count") else None
    )

    return {
        "annual_amount": annual_amount,
        "monthly": monthly_series,
        "purchase_count": len(purchases),
        "supplier_count": len(by_sup),
        "recipe_count": recipe_count,
        "offer_count": qh.get("count", 0),
        "cheapest_supplier": cheapest,
        "last_cost": last_cost,
        "avg_cost": avg_cost,
        "best_cost": best_cost,
        "price_trend_pct": _price_trend(purchases, today),
        "offers": offers,
        "savings": savings,
        "top_suppliers": top_suppliers,
    }
```

- [ ] **Step 4 : Vérifier le succès**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_product_analytics.py -q -p no:cacheprovider --no-cov`
Expected : PASS (5 tests).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/purchasing/product_analytics.py backend/tests/test_product_analytics.py
git commit -m "feat(achats): fiche produit 360° — cœur pur scorecard

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2 : `for_product` + enveloppe `overview` + endpoint

**Files:**
- Modify: `backend/app/services/purchasing/savings_service.py` (ajouter `for_product`, après `for_tenant`)
- Modify: `backend/app/services/purchasing/product_analytics.py` (ajouter l'enveloppe `overview`)
- Modify: `backend/app/api/api_v1/endpoints/products.py` (endpoint)
- Test: `backend/tests/test_product_overview_real_db.py`

**Interfaces:**
- Consumes: `scorecard` (Task 1) ; `savings_service._savings_for_order_lines` / `SAVINGS_LABELS` ; `crud_product.get_product_detail`/`product_recipes`/`get_product` ; `crud_purchase.product_purchases` ; `purchase_service.product_suppliers` ; `quote_history.product_quote_history` ; modèle `Supplier`.
- Produces: `savings_service.for_product(db, tenant_id, product_id, today) -> dict` ; `product_analytics.overview(db, tenant_id, product, today) -> dict`.

- [ ] **Step 1 : Ajouter `for_product` (miroir de `for_supplier`)**

Dans `savings_service.py`, après `for_tenant` :

```python
def for_product(db: Session, tenant_id: str, product_id: str, today: date) -> Dict[str, Any]:
    """Économies réalisées sur CE produit, 12 mois glissants (miroir de for_supplier)."""
    since = today - timedelta(days=365)
    res = _savings_for_order_lines(db, tenant_id, product_id=str(product_id), since=since, today=today)
    return {
        "realized": res["realized"], "missed": res["missed"], "possible": res["possible"],
        "best_choice_rate": res["best_choice_rate"], "compared_lines": res["compared_lines"],
        "labels": SAVINGS_LABELS,
    }
```

- [ ] **Step 2 : Écrire le test real_db (échoue à la collecte tant que l'endpoint manque)**

`backend/tests/test_product_overview_real_db.py` — style `test_supplier_overview_real_db.py` :

```python
"""Fiche produit 360° contre un vrai Postgres, via GET /products/{id}/overview.
Skip en local sans DATABASE_URL, tourne en CI."""
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.models import (
    Organization, Product, Supplier, PurchaseHistory, PurchaseOrder,
    PurchaseOrderLine, Quote, QuoteLine, Recipe, RecipeVersion, RecipeIngredient,
)


@pytest.fixture()
def client_ctx(db):
    from fastapi.testclient import TestClient
    from app.api.deps import get_current_tenant_id
    from app.db.session import get_db
    from app.main import app
    from app.services.costing import cost_engine

    cost_engine.reset_unit_cache()
    tid, metro, transg, pid = (str(uuid.uuid4()) for _ in range(4))
    db.add(Organization(id=tid, name="Produit 360"))
    db.commit()
    db.add(Supplier(id=metro, tenant_id=tid, name="METRO"))
    db.add(Supplier(id=transg, tenant_id=tid, name="TRANSGOURMET"))
    db.add(Product(id=pid, tenant_id=tid, name="Beurre"))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_tenant_id] = lambda: tid
    client = TestClient(app)
    yield client, {"tenant_id": tid, "metro": metro, "transg": transg, "product": pid}
    app.dependency_overrides.clear()
    cost_engine.reset_unit_cache()


def _ov(client, pid):
    r = client.get(f"/api/v1/products/{pid}/overview")
    assert r.status_code == 200, r.text
    return r.json()


def test_a_fresh_product_is_zeros(client_ctx):
    client, c = client_ctx
    o = _ov(client, c["product"])
    assert o["product_name"] == "Beurre"
    assert o["annual_amount"] == 0 and o["top_suppliers"] == [] and o["offers"] is None
    assert "score" not in o and "conformity_rate" not in o   # produit-centré


def test_overview_assembles_spend_offers_and_recipes(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()
    # achats des deux fournisseurs
    for sid, tot, cost in [(metro, Decimal("185"), Decimal("18.5")), (transg, Decimal("200"), Decimal("20"))]:
        db.add(PurchaseHistory(id=str(uuid.uuid4()), tenant_id=tid, supplier_id=sid, product_id=pid,
                               purchase_date=today, total_price=tot, unit_cost_standard=cost))
    # une offre (devis)
    qid = str(uuid.uuid4())
    db.add(Quote(id=qid, tenant_id=tid, reference="DEV-1", status="draft", date=today))
    db.add(QuoteLine(tenant_id=tid, quote_id=qid, product_id=pid, supplier_id=metro, qty=5, unit_price=Decimal("18")))
    # une recette qui l'utilise
    rid, vid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Recipe(id=rid, tenant_id=tid, name="Sauce", current_version_id=vid))
    db.add(RecipeVersion(id=vid, recipe_id=rid, version_number=1))
    db.add(RecipeIngredient(id=str(uuid.uuid4()), recipe_version_id=vid, product_id=pid, ingredient_name="Beurre", qty=2))
    db.commit()

    o = _ov(client, pid)
    assert o["annual_amount"] == 385.0
    assert {s["supplier_name"] for s in o["top_suppliers"]} == {"METRO", "TRANSGOURMET"}
    assert o["offers"]["supplier_count"] == 1 and o["offers"]["best_price"] == 18.0
    assert o["recipe_count"] == 1
    assert "savings" in o and o["savings"]["labels"]["realized"] == "Économisé"


def test_unknown_product_404(client_ctx):
    client, _ = client_ctx
    assert client.get(f"/api/v1/products/{uuid.uuid4()}/overview").status_code == 404
```

- [ ] **Step 3 : Implémenter l'enveloppe `overview`**

Ajouter à `product_analytics.py` :

```python
from sqlalchemy.orm import Session


def overview(db: Session, tenant_id: str, product, today: date) -> Dict[str, Any]:
    """Le 360° d'un produit, assemblé depuis les read models du domaine Achats."""
    from app.crud import crud_product, crud_purchase
    from app.models.models import Supplier
    from app.services.purchasing import purchase_service, savings_service
    from app.services.quotes import quote_history as qh

    pid = str(product.id)
    header = crud_product.get_product_detail(db, pid, tenant_id) or {}
    names = dict(db.query(Supplier.id, Supplier.name).filter(Supplier.tenant_id == tenant_id).all())

    purchases = [
        {"purchase_date": p.purchase_date,
         "supplier_id": str(p.supplier_id) if p.supplier_id else None,
         "supplier_name": names.get(p.supplier_id),
         "total_price": _f(p.total_price), "unit_cost_standard": _f(p.unit_cost_standard)}
        for p in crud_purchase.product_purchases(db, tenant_id, pid)
    ]
    quote_h = qh.product_quote_history(db, tenant_id, pid)
    savings = savings_service.for_product(db, tenant_id, pid, today)

    ps = purchase_service.product_suppliers(db, tenant_id, pid)
    cheapest = None
    csid = ps.get("cheapest_supplier_id")
    if csid:
        row = next((s for s in ps.get("suppliers", []) if str(s.get("supplier_id")) == str(csid)), None)
        if row:
            cheapest = {"supplier_id": str(csid), "supplier_name": row.get("supplier_name"),
                        "cost": row.get("best_cost") if row.get("best_cost") is not None else row.get("last_cost")}

    recipe_count = len(crud_product.product_recipes(db, tenant_id, pid))

    card = scorecard(purchases, quote_h, savings, cheapest, recipe_count, today)
    card.update({
        "product_id": pid,
        "product_name": header.get("name") or product.name,
        "category": header.get("category"),
        "unit_code": header.get("unit"),
    })
    return card
```

- [ ] **Step 4 : Endpoint (mirroir de `/suppliers/{id}/overview`)**

Dans `products.py`, ajouter parmi les sous-routes `/{product_id}/…` (ex. après `supplier-comparison`, l.87), donc AVANT `GET /{product_id}` :

```python
@router.get("/{product_id}/overview")
def api_product_overview(
    product_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Fiche produit 360° : dépense, prix, inflation, offres, économies, top
    fournisseurs, recettes — assemblé depuis les read models Achats."""
    from datetime import date
    from app.services.purchasing import product_analytics

    product = get_product(db, product_id, tenant_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_analytics.overview(db, tenant_id, product, date.today())
```

- [ ] **Step 5 : Lancer les tests**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_product_analytics.py tests/test_product_overview_real_db.py tests/test_supplier_overview_real_db.py tests/test_model_attribute_contract.py -q -p no:cacheprovider --no-cov`
Expected : purs verts ; real_db collectés-et-skippés ; fiche fournisseur intacte ; AST guard vert ; `app.main` importe.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/services/purchasing/savings_service.py backend/app/services/purchasing/product_analytics.py backend/app/api/api_v1/endpoints/products.py backend/tests/test_product_overview_real_db.py
git commit -m "feat(achats): fiche produit 360° — for_product + overview + GET /products/{id}/overview

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3 : Web — l'onglet Statistiques devient le `ProductScorecard`

**Files:**
- Modify: `frontend/src/services/products-service.ts` (type `ProductOverview` + `getProductOverview`)
- Modify: `frontend/src/hooks/use-products.ts` (`useProductOverview`)
- Create: `frontend/src/features/products/product-scorecard.tsx`
- Modify: `frontend/src/features/products/product-detail.tsx` (onglet `stats`)

**Interfaces:**
- Consumes: `GET /products/{id}/overview` → `ProductOverview`.

- [ ] **Step 1 : Type + service + hook** (miroir de `SupplierOverview`/`getSupplierOverview`/`useSupplierOverview`)

Dans `products-service.ts` :
```ts
export interface ProductOverview {
  product_id: string; product_name: string; category: string | null; unit_code: string | null;
  annual_amount: number; monthly: Array<{ month: string; amount: number }>;
  purchase_count: number; supplier_count: number; recipe_count: number; offer_count: number;
  cheapest_supplier: { supplier_id: string; supplier_name: string | null; cost: number | null } | null;
  last_cost: number | null; avg_cost: number | null; best_cost: number | null;
  price_trend_pct: number | null;
  offers: { best_price: number | null; best_supplier_name: string | null; latest_price: number | null; avg_price: number | null; supplier_count: number } | null;
  savings: { realized: number; missed: number; possible: number; best_choice_rate: number | null; compared_lines: number; labels: { realized: string; missed: string; possible: string; best_choice_rate: string } };
  top_suppliers: Array<{ supplier_id: string; supplier_name: string | null; amount: number; count: number; is_cheapest: boolean }>;
}
export async function getProductOverview(id: string) {
  const { data } = await api.get<ProductOverview>(`/products/${id}/overview`);
  return data;
}
```
Dans `use-products.ts` : `useProductOverview(id?) => useQuery({ queryKey: ["products", id, "overview"], queryFn: () => getProductOverview(id!), enabled: Boolean(id) })`.

- [ ] **Step 2 : Composant `product-scorecard.tsx`** (miroir de `supplier-scorecard.tsx`)

`ProductScorecard({ productId })` : `const { data } = useProductOverview(productId); if (!data) return null;`
- Tuiles KPI : « Payé sur 12 mois » (`formatCurrency(annual_amount)`) ; « Inflation produit » (`price_trend_pct==null?"—":(+/-)formatNumber(price_trend_pct,1)+" %"`, rouge si >0 vert si <0) ; « Économisé » (`formatCurrency(savings.realized)`, sous-légende taux de meilleur choix `savings.best_choice_rate`).
- Ligne volumes : `purchase_count` achats · `supplier_count` fournisseurs · `recipe_count` recettes · `offer_count` offres.
- Barres mensuelles : réutiliser le motif `MonthlyBars` de `supplier-scorecard.tsx` (copier le sous-composant ou l'extraire ; pas de librairie).
- Bloc « moins cher » : `cheapest_supplier` (nom + `formatCurrency(cost)`), et bloc « Offres » : `offers` (best/latest/avg).
- Top fournisseurs : liste `top_suppliers` liée `href={/fournisseurs/${s.supplier_id}}`, `formatCurrency(amount)`, badge « moins cher » si `is_cheapest`. Cartes annexes en `SafeBoundary`.

- [ ] **Step 3 : Brancher dans l'onglet Statistiques**

Dans `product-detail.tsx` : renommer le trigger `<TabsTrigger value="stats">Statistiques</TabsTrigger>` → `<TabsTrigger value="stats">Vue d'ensemble</TabsTrigger>` (l.198) ; remplacer le **contenu** de `<TabsContent value="stats">…</TabsContent>` (les stats client-side) par `<TabsContent value="stats"><ProductScorecard productId={productId} /></TabsContent>`. Supprimer le code de calcul des stats client-side devenu inutilisé (imports, `useMemo`, etc.).

- [ ] **Step 4 : Vérifier types/lint/build**

Run : `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected : PASS. (Build bloqué disque/RAM → `TMP=D:/Dev/Temp/claude/next-build TEMP=D:/Dev/Temp/claude/next-build npm run build`.)

- [ ] **Step 5 : Commit**

```bash
git add frontend/src/services/products-service.ts frontend/src/hooks/use-products.ts frontend/src/features/products/product-scorecard.tsx frontend/src/features/products/product-detail.tsx
git commit -m "feat(achats): fiche produit 360° — onglet Vue d'ensemble (web)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4 : Mobile — l'onglet Stats devient le `_Scorecard` produit

**Files:**
- Modify: `mobile/lib/features/products/product_detail_screen.dart`
- Create: `mobile/test/product_overview_test.dart`

**Interfaces:**
- Consumes: `GET /products/{id}/overview` (via `apiClientProvider`).

- [ ] **Step 1 : Widget test qui échoue**

`mobile/test/product_overview_test.dart` — sur le modèle de `mobile/test/supplier_savings_test.dart` : faux `HttpClientAdapter` répondant à `/products/p1/overview` avec une charge (`{product_id:"p1", product_name:"Beurre", annual_amount:385.0, monthly:[], purchase_count:2, supplier_count:2, recipe_count:1, offer_count:1, cheapest_supplier:{supplier_id:"m", supplier_name:"METRO", cost:18.0}, last_cost:20.0, avg_cost:19.25, best_cost:18.5, price_trend_pct:8.0, offers:{best_price:18.0, best_supplier_name:"METRO", latest_price:18.0, avg_price:18.0, supplier_count:1}, savings:{realized:20.0, missed:0.0, possible:20.0, best_choice_rate:1.0, compared_lines:1, labels:{realized:"Économisé", missed:"Laissé sur la table", possible:"Économie possible", best_choice_rate:"Taux de meilleur choix"}}, top_suppliers:[{supplier_id:"m", supplier_name:"METRO", amount:185.0, count:1, is_cheapest:true}]}`) + les endpoints que la fiche appelle déjà (`/products/p1`, etc. — renvoyer `{}`/`[]`). Pomper `ProductDetailScreen`, aller sur l'onglet « Vue d'ensemble », attendre :
```dart
expect(find.textContaining('Payé sur 12 mois'), findsOneWidget);
expect(find.text('Économisé'), findsOneWidget);
```
(RED : l'onglet montre encore les stats client-side.)

- [ ] **Step 2 : Vérifier l'échec**

Run : `cd mobile && D:/flutter/bin/flutter test test/product_overview_test.dart` (ou `flutter.bat`).
Expected : FAIL.

- [ ] **Step 3 : Provider + `_Scorecard` produit + brancher l'onglet**

Dans `product_detail_screen.dart` : ajouter `_productOverviewProvider` (`FutureProvider.autoDispose.family` → `GET /products/$id/overview`, miroir de `_supplierOverviewProvider` dans `supplier_detail_screen.dart`). Renommer le `Tab('Stats')` → `Tab('Vue d\'ensemble')`. Remplacer le contenu du `TabBarView` correspondant (les stats client-side) par `overview.maybeWhen(orElse: () => const SizedBox.shrink(), data: (o) => _Scorecard(o))`, avec un `_Scorecard(Map o)` produit miroir de celui de `supplier_detail_screen.dart` (tuiles payé/inflation/économisé, volumes, barres mensuelles, top fournisseurs liés, moins cher, offres). Réutiliser `eur()`/`plainNumber()`.

- [ ] **Step 4 : Test + analyze**

Run : `cd mobile && D:/flutter/bin/flutter test test/product_overview_test.dart && D:/flutter/bin/flutter analyze lib/features/products/product_detail_screen.dart`
Expected : test PASS ; analyze `No issues found`.

- [ ] **Step 5 : Commit**

```bash
git add mobile/lib/features/products/product_detail_screen.dart mobile/test/product_overview_test.dart
git commit -m "feat(achats): fiche produit 360° — onglet Vue d'ensemble (mobile)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5 : PR, CI verte, validation live

**Files:** aucun (intégration).

- [ ] **Step 1 : Pousser + PR**

```bash
git push -u origin HEAD
gh pr create --base main --title "feat(achats): fiche produit 360° (morceau A)" --body "$(cat <<'EOF'
Fiche produit 360° — miroir produit-centré de la fiche fournisseur, en ASSEMBLAGE des read models existants. Aucune duplication, aucune migration.

- Cœur pur `product_analytics.scorecard` (dépense/mensuel/top fournisseurs/inflation) réutilisant `_price_trend`.
- Enveloppe `overview` : `product_purchases`, `product_suppliers`, `product_quote_history`, `product_recipes`, `for_product` (nouveau one-liner).
- `GET /products/{id}/overview` (miroir de `/suppliers/{id}/overview`).
- L'onglet « Statistiques » client-side devient un `ProductScorecard` serveur (web + mobile), renommé « Vue d'ensemble ».

Spec : docs/superpowers/specs/2026-07-28-achats-produit-360-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2 : CI verte** — `Backend — tests` (real_db produit), Web, Mobile, AST guard. Si la branche est en retard sur `main`, `gh pr update-branch <n>` puis re-CI.

- [ ] **Step 3 : Validation live (RÈGLE ABSOLUE)** — après merge (déploiement) :
- **Backend E2E prod** : login ; créer pour un produit : achats de 2 fournisseurs, un devis (offre), une commande issue du devis (économies), une recette ; `GET /products/{id}/overview` → vérifier `annual_amount`, `top_suppliers`, `cheapest_supplier`, `savings.realized>0`, `offers`, `recipe_count` ; **nettoyer** tout.
- **Émulateur `foodgad`** : fiche produit → onglet « Vue d'ensemble » rendu (tuiles + top fournisseurs), 0 exception logcat.
- **Web** : build vert + contrat validé en direct.

- [ ] **Step 4 : Mémoire** — consigner dans [[erp-epic-progress]] : morceau A livré (PR #), reste **D (vérif prépa stock)**.

---

## Self-Review

**1. Spec coverage :**
- Assembleur pur `scorecard` + enveloppe `overview` + endpoint `/products/{id}/overview` → Tasks 1, 2. ✓
- `savings_service.for_product` (one-liner) → Task 2. ✓
- Dépense/mensuel/inflation/top-fournisseurs/prix/offres/économies/recettes, produit-centré (pas de conformité/score) → Task 1 (dérive) + Task 2 (gather). ✓
- Onglet « Statistiques » → `ProductScorecard` serveur « Vue d'ensemble », web + mobile, suppression du client-side → Tasks 3, 4. ✓
- Réutilisation stricte (product_suppliers/product_quote_history/product_purchases/product_recipes/_price_trend/savings) → Task 2. ✓
- Fenêtre 12 mois ; aucune table/migration ; AST guard vert ; non-régression fiche fournisseur + 5 autres onglets produit → Tasks 2, 3, 4, 5. ✓

**2. Placeholder scan :** code d'assemblage et de gather concret ; tâches UI portent types/service/structure + « miroir de supplier-scorecard/_Scorecard » (composant existant, pas de logique inventée), « supprimer le client-side » explicite. Aucun « TBD ». ✓

**3. Type consistency :** la forme `overview` (Global Constraints) est identique dans `scorecard` (T1, sans en-tête) + l'enveloppe qui ajoute `product_id/product_name/category/unit_code` (T2), le type TS `ProductOverview` (T3) et la lecture Dart (T4) ; `for_product` renvoie les 6 clés `{realized,missed,possible,best_choice_rate,compared_lines,labels}` (T2) consommées comme `savings` par `scorecard`/l'UI. ✓

**Note de rigueur :** `scorecard` suppose `purchases` ancien→récent (comme `crud_purchase.product_purchases`) pour `last_cost` — documenté dans la docstring et respecté par l'enveloppe. Les tests touchant la BDD sont real_db (skip local, CI), conforme à [[never-mock-the-db-session]].
