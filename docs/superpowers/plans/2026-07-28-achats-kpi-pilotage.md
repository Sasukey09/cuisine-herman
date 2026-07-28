# Pilotage Achats (KPI, morceau C) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un tableau de bord **Pilotage Achats** tenant-wide (économies, cycle commandé/reçu/facturé + écarts, prix réutilisé, fournisseurs), en **assemblage des moteurs existants — aucune duplication, aucune migration.**

**Architecture:** Un cœur pur `assemble(parts)` qui structure/dérive ; une enveloppe BDD `purchasing_kpi` qui rassemble `parts` en appelant les moteurs déjà là (`savings_service`, `quote_matrix.build_for_tenant`, `purchase_service.price_dashboard`, `dashboard_service.top_products`, sommes SQL, boucle réception, agrégat fournisseur) ; un endpoint read-only `GET /purchasing/kpi` ; écran `/pilotage` web + module « Pilotage » mobile.

**Tech Stack:** FastAPI + SQLAlchemy, Anthropic non concerné ; Next.js 15 / React 19 / TS / TanStack Query (web), Flutter + Riverpod + Dio (mobile), pytest, flutter_test.

## Global Constraints

- **Assemblage, pas duplication** : réutiliser tel quel `savings_service`, `quote_matrix.build_for_tenant`, `purchase_service.price_dashboard`, `dashboard_service.top_products`. Le détail prix reste sur `/prix` (on lie, on n'absorbe pas).
- **Aucune table / migration** : lecture pure (agrégation). Garde-fou AST `test_model_attribute_contract.py` vert sans modification.
- **Fenêtre = 12 mois glissants** (`since = today − 365 j`) ; pas de sélecteur de période.
- **Routes littérales avant `/{id}`** : un routeur `purchasing` neuf (monté à `/purchasing`) évite le piège ; endpoint `GET /purchasing/kpi`, read-only (`get_current_tenant_id` + `get_db`, PAS `require_writer`).
- **Bloc prix = résumé compact** : `{n_hausse, n_baisse, top_inflation_pct, n_critiques, switch_savings_total}` extrait de `price_dashboard`, pas les listes complètes.
- **Jamais mocker la session BDD** : l'enveloppe se teste `*_real_db` (skip local, CI). Le cœur pur `assemble` se teste sans base.
- **Forme normalisée `parts`** (contrat inter-tâches) :
  ```python
  {"savings": {realized, missed, possible, best_choice_rate, compared_lines},
   "possible_open": float,
   "ordered_total": float, "ordered_by_status": {status: float},
   "received_value": float, "missing_value": float, "billed_total": float,
   "price": {n_hausse, n_baisse, top_inflation_pct, n_critiques, switch_savings_total},
   "top_products": [{product_id, name, total_spend, total_qty, line_count}],
   "suppliers": [{supplier_id, name, spend, realized, on_time_rate, late_count, conformity_rate}]}
  ```
- Commit trailer : `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Commande pytest (pure, locale) : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest <chemin> -q -p no:cacheprovider --no-cov`

---

## File Structure

| Fichier | Rôle | Action |
|---|---|---|
| `backend/app/services/purchasing/kpi_service.py` | cœur pur `assemble` + `KPI_LABELS` + enveloppe `purchasing_kpi` | **Créer** |
| `backend/app/services/purchasing/savings_service.py` | + `for_tenant(db, tenant, today)` (miroir `for_supplier`, sans filtre, AVEC `lines`) | **Modifier** |
| `backend/app/api/api_v1/endpoints/purchasing.py` | routeur `GET /kpi` | **Créer** |
| `backend/app/api/api_v1/api.py` | enregistrer le routeur `purchasing` | **Modifier** (l.1-40) |
| `backend/tests/test_kpi_service.py` | tests purs de `assemble` | **Créer** |
| `backend/tests/test_kpi_real_db.py` | round-trip `GET /purchasing/kpi` sur Postgres | **Créer** |
| `frontend/src/services/purchasing-kpi-service.ts` + `types.ts` | type `PurchasingKpi` + fetch | **Créer / Modifier** |
| `frontend/src/hooks/use-purchasing-kpi.ts` | hook TanStack | **Créer** |
| `frontend/src/features/pilotage/pilotage-view.tsx` | écran Pilotage (StatCards + blocs) | **Créer** |
| `frontend/src/app/(dashboard)/pilotage/page.tsx` + nav | route + item de nav | **Créer / Modifier** |
| `mobile/lib/features/common/kpi_widgets.dart` | `KpiStat`/`KpiMiniStat`/`KpiSectionCard` (extraits du dashboard) | **Créer** |
| `mobile/lib/features/dashboard/dashboard_screen.dart` | consommer les widgets partagés | **Modifier** |
| `mobile/lib/features/pilotage/pilotage_screen.dart` + `home_shell.dart` | écran + module « Pilotage » | **Créer / Modifier** |
| `mobile/test/pilotage_test.dart` | widget test | **Créer** |

---

## Task 1 : Cœur pur `assemble(parts)` + `KPI_LABELS`

**Files:**
- Create: `backend/app/services/purchasing/kpi_service.py` (partie pure uniquement)
- Test: `backend/tests/test_kpi_service.py`

**Interfaces:**
- Produces: `assemble(parts: dict) -> dict` (forme d'entrée = Global Constraints ; sortie ci-dessous) ; `KPI_LABELS: dict`.

- [ ] **Step 1 : Écrire les tests qui échouent**

`backend/tests/test_kpi_service.py` :

```python
from app.services.purchasing.kpi_service import assemble, KPI_LABELS


def _parts(**over):
    base = {
        "savings": {"realized": 20.0, "missed": 5.0, "possible": 25.0,
                    "best_choice_rate": 0.8, "compared_lines": 3},
        "possible_open": 40.0,
        "ordered_total": 1000.0, "ordered_by_status": {"received": 600.0, "sent": 400.0},
        "received_value": 700.0, "missing_value": 120.0, "billed_total": 650.0,
        "price": {"n_hausse": 2, "n_baisse": 1, "top_inflation_pct": 12.5,
                  "n_critiques": 4, "switch_savings_total": 33.0},
        "top_products": [{"product_id": "p1", "name": "Beurre", "total_spend": 300.0,
                          "total_qty": 30.0, "line_count": 5}],
        "suppliers": [
            {"supplier_id": "a", "name": "A", "spend": 500.0, "realized": 20.0,
             "on_time_rate": 0.5, "late_count": 3, "conformity_rate": 0.9},
            {"supplier_id": "b", "name": "B", "spend": 300.0, "realized": 0.0,
             "on_time_rate": 1.0, "late_count": 0, "conformity_rate": 1.0},
        ],
    }
    base.update(over)
    return base


def test_cycle_gaps_are_derived():
    k = assemble(_parts())
    c = k["cycle"]
    assert c["ordered_total"] == 1000.0 and c["received_value"] == 700.0 and c["billed_total"] == 650.0
    assert c["gap_ordered_received"] == 300.0   # 1000 - 700 (commandé non encore livré/valorisé)
    assert c["gap_billed_received"] == -50.0    # 650 - 700 (facturé < reçu)
    assert c["missing_value"] == 120.0
    assert c["ordered_by_status"] == {"received": 600.0, "sent": 400.0}


def test_savings_block_gets_labels_and_possible_open():
    k = assemble(_parts())
    assert k["savings"]["realized"] == 20.0
    assert k["savings"]["labels"] == {"realized": "Économisé", "missed": "Laissé sur la table",
                                      "possible": "Économie possible", "best_choice_rate": "Taux de meilleur choix"}
    assert k["possible_open"] == 40.0


def test_price_and_top_products_are_passthrough_not_recomputed():
    parts = _parts()
    k = assemble(parts)
    assert k["price"] == parts["price"]          # aucun recalcul
    assert k["top_products"] == parts["top_products"]


def test_supplier_rankings():
    k = assemble(_parts())
    s = k["suppliers"]
    assert [x["supplier_id"] for x in s["most_competitive"]] == ["a"]   # realized>0, trié desc
    assert [x["supplier_id"] for x in s["most_late"]] == ["a"]          # late_count>0
    assert s["best_conformity"][0]["supplier_id"] == "b"               # conformity 1.0 avant 0.9


def test_empty_tenant_is_honest_zeros():
    k = assemble(_parts(savings={"realized": 0.0, "missed": 0.0, "possible": 0.0,
                                 "best_choice_rate": None, "compared_lines": 0},
                        ordered_total=0.0, received_value=0.0, billed_total=0.0,
                        missing_value=0.0, possible_open=0.0, suppliers=[],
                        ordered_by_status={}, top_products=[]))
    assert k["cycle"]["gap_ordered_received"] == 0.0
    assert k["savings"]["best_choice_rate"] is None
    assert k["suppliers"]["most_competitive"] == []


def test_labels_exposed():
    assert "ordered_total" in KPI_LABELS and "gap_ordered_received" in KPI_LABELS
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_kpi_service.py -q -p no:cacheprovider --no-cov`
Expected : FAIL (`ModuleNotFoundError: kpi_service`).

- [ ] **Step 3 : Implémenter le cœur pur**

Créer `backend/app/services/purchasing/kpi_service.py` (partie pure) :

```python
"""Pilotage Achats : assemblage tenant-wide des moteurs Achats.

Ce module N'A PAS de logique métier neuve : le cœur pur ``assemble`` structure
et dérive (écarts, classements) des données déjà calculées par les moteurs
existants ; l'enveloppe ``purchasing_kpi`` (plus bas) rassemble ces données en
appelant ces moteurs. Doctrine : on assemble, on ne duplique pas.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.services.purchasing.savings_service import SAVINGS_LABELS

#: Libellés servis par l'API — source unique web + mobile.
KPI_LABELS = {
    "ordered_total": "Commandé",
    "received_value": "Reçu",
    "billed_total": "Facturé",
    "gap_ordered_received": "Écart commandé → reçu",
    "gap_billed_received": "Écart facturé → reçu",
    "missing_value": "En attente de livraison",
    "possible_open": "Économies possibles (devis ouverts)",
    "most_competitive": "Plus compétitifs",
    "most_late": "En retard",
    "best_conformity": "Meilleure conformité",
}

_TOP_N = 5


def _r(v: Any) -> float:
    return round(float(v or 0.0), 2)


def assemble(parts: Dict[str, Any]) -> Dict[str, Any]:
    """Structure et dérive les KPI depuis des données déjà collectées (pur)."""
    ordered = _r(parts.get("ordered_total"))
    received = _r(parts.get("received_value"))
    billed = _r(parts.get("billed_total"))
    sav = dict(parts.get("savings") or {})

    suppliers: List[Dict[str, Any]] = list(parts.get("suppliers") or [])
    most_competitive = sorted(
        [s for s in suppliers if (s.get("realized") or 0) > 0],
        key=lambda s: -(s.get("realized") or 0),
    )[:_TOP_N]
    most_late = sorted(
        [s for s in suppliers if (s.get("late_count") or 0) > 0],
        key=lambda s: -(s.get("late_count") or 0),
    )[:_TOP_N]
    best_conformity = sorted(
        [s for s in suppliers if s.get("conformity_rate") is not None],
        key=lambda s: -(s.get("conformity_rate") or 0),
    )[:_TOP_N]

    return {
        "window_months": 12,
        "savings": {**sav, "labels": SAVINGS_LABELS},
        "possible_open": _r(parts.get("possible_open")),
        "cycle": {
            "ordered_total": ordered,
            "received_value": received,
            "billed_total": billed,
            "gap_ordered_received": _r(ordered - received),
            "gap_billed_received": _r(billed - received),
            "missing_value": _r(parts.get("missing_value")),
            "ordered_by_status": parts.get("ordered_by_status") or {},
        },
        "price": parts.get("price") or {},          # passe-plat, jamais recalculé
        "top_products": parts.get("top_products") or [],
        "suppliers": {
            "most_competitive": most_competitive,
            "most_late": most_late,
            "best_conformity": best_conformity,
        },
        "labels": KPI_LABELS,
    }
```

- [ ] **Step 4 : Vérifier le succès**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_kpi_service.py -q -p no:cacheprovider --no-cov`
Expected : PASS (6 tests).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/purchasing/kpi_service.py backend/tests/test_kpi_service.py
git commit -m "feat(achats): pilotage — cœur pur assemble() des KPI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2 : `savings_service.for_tenant` + enveloppe `purchasing_kpi` + endpoint

**Files:**
- Modify: `backend/app/services/purchasing/savings_service.py` (ajouter `for_tenant`, après `for_supplier`)
- Modify: `backend/app/services/purchasing/kpi_service.py` (ajouter l'enveloppe + imports)
- Create: `backend/app/api/api_v1/endpoints/purchasing.py`
- Modify: `backend/app/api/api_v1/api.py` (enregistrer le routeur)
- Test: `backend/tests/test_kpi_real_db.py`

**Interfaces:**
- Consumes: `assemble` (Task 1) ; `savings_service._savings_for_order_lines` / `SAVINGS_LABELS` ; `quote_matrix.build_for_tenant` ; `purchase_service.price_dashboard` ; `dashboard_service.top_products` ; modèles `PurchaseOrder`, `Invoice`, `Receipt`, `PurchaseHistory`, `ReceiptLine`, `ReceiptLineIssue` ; `reception_service.order_progress` ; `order_service.CANCELLED`.
- Produces: `savings_service.for_tenant(db, tenant_id, today) -> dict` (5 clés + `labels` + `lines`) ; `kpi_service.purchasing_kpi(db, tenant_id, today) -> dict`.

- [ ] **Step 1 : Ajouter `for_tenant` (miroir de `for_supplier`, avec `lines`)**

Dans `savings_service.py`, juste après `for_supplier` :

```python
def for_tenant(db: Session, tenant_id: str, today: date) -> Dict[str, Any]:
    """Économies réalisées sur TOUT le tenant, 12 mois glissants. Renvoie en plus
    le détail par ligne (``lines``) — nécessaire pour agréger par fournisseur dans
    le pilotage — là où ``for_supplier`` le laisse tomber."""
    since = today - timedelta(days=365)
    res = _savings_for_order_lines(db, tenant_id, since=since, today=today)
    return {
        "realized": res["realized"], "missed": res["missed"], "possible": res["possible"],
        "best_choice_rate": res["best_choice_rate"], "compared_lines": res["compared_lines"],
        "labels": SAVINGS_LABELS, "lines": res["lines"],
    }
```

- [ ] **Step 2 : Écrire le test real_db (échoue à la collecte tant que l'endpoint manque)**

`backend/tests/test_kpi_real_db.py` — même style que `test_savings_real_db.py` (fixture `db`, `Organization`, reset du cache d'unités car le KPI touche le coût indirectement via les moteurs) :

```python
"""Pilotage Achats contre un vrai Postgres, via GET /purchasing/kpi.
Skip en local sans DATABASE_URL, tourne en CI."""
import uuid
from datetime import date, datetime, timedelta

import pytest

from app.models.models import (
    Organization, Product, Supplier, PurchaseOrder, PurchaseOrderLine,
    Invoice, Quote, QuoteLine,
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
    db.add(Organization(id=tid, name="Pilotage"))
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


def test_kpi_assembles_cycle_and_savings(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    # Une facture (facturé) et une commande (commandé).
    db.add(Invoice(tenant_id=tid, supplier_id=metro, invoice_number="F1",
                   total_amount=650, date=today))
    db.add(PurchaseOrder(tenant_id=tid, reference="CMD-K", supplier_id=metro,
                         status="received", total_amount=1000, ordered_at=datetime.now()))
    db.commit()

    r = client.get("/api/v1/purchasing/kpi")
    assert r.status_code == 200, r.text
    k = r.json()
    assert k["window_months"] == 12
    assert k["cycle"]["ordered_total"] == 1000.0
    assert k["cycle"]["billed_total"] == 650.0
    # écart dérivé (reçu = 0 ici, pas de réception validée)
    assert k["cycle"]["gap_ordered_received"] == 1000.0
    # blocs présents (passe-plat)
    assert set(k["price"].keys()) >= {"n_hausse", "n_baisse", "n_critiques", "switch_savings_total"}
    assert "labels" in k and "most_competitive" in k["suppliers"]
    assert k["savings"]["labels"]["realized"] == "Économisé"
```

- [ ] **Step 3 : Implémenter l'enveloppe `purchasing_kpi`**

Ajouter à `kpi_service.py` (imports en tête + fonction en bas) :

```python
from datetime import date, datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    PurchaseOrder, PurchaseOrderLine, Invoice, Receipt, ReceiptLine,
    ReceiptLineIssue, PurchaseHistory,
)
from app.services.purchasing import order_service, reception_service, savings_service
from app.services.quotes import quote_matrix
from app.services.purchasing import purchase_service
from app.services.dashboard import dashboard_service


def _price_summary(pd: Dict[str, Any]) -> Dict[str, Any]:
    inc = pd.get("most_increased") or []
    return {
        "n_hausse": len(inc),
        "n_baisse": len(pd.get("most_decreased") or []),
        "top_inflation_pct": inc[0]["change_pct"] if inc else None,
        "n_critiques": len(pd.get("savings_opportunities") or []),
        "switch_savings_total": pd.get("potential_savings_total") or 0.0,
    }


def purchasing_kpi(db: Session, tenant_id: str, today: date) -> Dict[str, Any]:
    since = today - timedelta(days=365)
    since_dt = datetime.combine(since, datetime.min.time())

    # --- économies (+ détail par ligne pour l'agrégat fournisseur) ------------
    sav = savings_service.for_tenant(db, tenant_id, today)
    realized_by_supplier: Dict[str, float] = {}
    for ln in sav.get("lines", []):
        sid = ln.get("supplier_id")
        if sid:
            realized_by_supplier[sid] = round(realized_by_supplier.get(sid, 0.0) + (ln.get("realized") or 0.0), 2)

    # --- économies possibles (ex-ante) ---------------------------------------
    possible_open = (quote_matrix.build_for_tenant(db, tenant_id) or {}).get("potential_savings") or 0.0

    # --- montants (sommes SQL légères) ----------------------------------------
    order_rows = (
        db.query(PurchaseOrder.status, func.coalesce(func.sum(PurchaseOrder.total_amount), 0))
        .filter(PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.status != order_service.CANCELLED,
                PurchaseOrder.created_at >= since_dt)
        .group_by(PurchaseOrder.status)
        .all()
    )
    ordered_by_status = {s: float(t or 0) for s, t in order_rows}
    ordered_total = sum(ordered_by_status.values())
    billed_total = float(
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0))
        .filter(Invoice.tenant_id == tenant_id, Invoice.date >= since).scalar() or 0
    )

    # --- reçu (valeur acceptée) + en attente, via le moteur réception ---------
    received_value = 0.0
    missing_value = 0.0
    active_orders = (
        db.query(PurchaseOrder.id)
        .filter(PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.status != order_service.CANCELLED,
                PurchaseOrder.created_at >= since_dt).all()
    )
    for (oid,) in active_orders:
        prog = reception_service.order_progress(db, tenant_id, str(oid))
        for l in prog.get("lines", []):
            received_value += (l.get("qty_received_total") or 0.0) * (l.get("unit_price") or 0.0)
        missing_value += prog.get("missing_value") or 0.0

    # --- fournisseurs : agrégat léger (dépense + retards/conformité SQL, éco depuis les lignes) ---
    suppliers = _supplier_rows(db, tenant_id, since, today, realized_by_supplier)

    parts = {
        "savings": {k: sav[k] for k in ("realized", "missed", "possible", "best_choice_rate", "compared_lines")},
        "possible_open": possible_open,
        "ordered_total": ordered_total, "ordered_by_status": ordered_by_status,
        "received_value": round(received_value, 2), "missing_value": round(missing_value, 2),
        "billed_total": billed_total,
        "price": _price_summary(purchase_service.price_dashboard(db, tenant_id, limit=1000)),
        "top_products": dashboard_service.top_products(db, tenant_id, limit=5, date_from=since, date_to=today),
        "suppliers": suppliers,
    }
    return assemble(parts)


def _supplier_rows(db, tenant_id, since, today, realized_by_supplier):
    """Agrégat léger par fournisseur : dépense (payé), retards & conformité
    (mêmes définitions que supplier_analytics : issue-free = conforme ; reçu après
    la date promise = retard), et économies réalisées (depuis les lignes)."""
    from app.models.models import Supplier
    names = dict(db.query(Supplier.id, Supplier.name).filter(Supplier.tenant_id == tenant_id).all())

    spend = dict(
        db.query(PurchaseHistory.supplier_id, func.coalesce(func.sum(PurchaseHistory.total_price), 0))
        .filter(PurchaseHistory.tenant_id == tenant_id, PurchaseHistory.purchase_date >= since)
        .group_by(PurchaseHistory.supplier_id).all()
    )

    # réceptions validées : conformité (0 anomalie) et ponctualité (reçu <= date promise)
    issue_counts = dict(
        db.query(ReceiptLine.receipt_id, func.count(ReceiptLineIssue.id))
        .join(ReceiptLineIssue, ReceiptLineIssue.receipt_line_id == ReceiptLine.id)
        .filter(ReceiptLine.tenant_id == tenant_id).group_by(ReceiptLine.receipt_id).all()
    )
    expected = dict(
        db.query(Receipt.id, PurchaseOrder.expected_date)
        .join(PurchaseOrder, PurchaseOrder.id == Receipt.order_id)
        .filter(Receipt.tenant_id == tenant_id).all()
    )
    agg: Dict[str, Dict[str, float]] = {}
    for r in db.query(Receipt).filter(Receipt.tenant_id == tenant_id, Receipt.status == "checked"):
        sid = str(r.supplier_id) if r.supplier_id else None
        if not sid:
            continue
        a = agg.setdefault(sid, {"n": 0, "conform": 0, "datable": 0, "late": 0})
        a["n"] += 1
        if int(issue_counts.get(r.id, 0)) == 0:
            a["conform"] += 1
        exp = expected.get(r.id)
        if r.received_at and exp:
            a["datable"] += 1
            if r.received_at > exp:
                a["late"] += 1

    rows = []
    for sid, name in names.items():
        sid = str(sid)
        a = agg.get(sid)
        rows.append({
            "supplier_id": sid, "name": name,
            "spend": round(float(spend.get(sid, 0) or 0), 2),
            "realized": realized_by_supplier.get(sid, 0.0),
            "conformity_rate": round(a["conform"] / a["n"], 3) if a and a["n"] else None,
            "on_time_rate": round((a["datable"] - a["late"]) / a["datable"], 3) if a and a["datable"] else None,
            "late_count": a["late"] if a else 0,
        })
    return rows
```

- [ ] **Step 4 : Endpoint + routeur**

Créer `backend/app/api/api_v1/endpoints/purchasing.py` :

```python
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id
from app.services.purchasing import kpi_service

router = APIRouter()


@router.get("/kpi")
def api_purchasing_kpi(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Pilotage Achats : KPI tenant-wide (12 mois), assemblés depuis les moteurs
    Achats existants. Lecture seule."""
    return kpi_service.purchasing_kpi(db, tenant_id, date.today())
```

Dans `api.py` : ajouter `purchasing` à l'import (l.3-20) et
`api_router.include_router(purchasing.router, prefix="/purchasing", tags=["purchasing"])` (après `receipts`, l.39).

- [ ] **Step 5 : Lancer les tests**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_kpi_service.py tests/test_kpi_real_db.py tests/test_savings_real_db.py tests/test_model_attribute_contract.py -q -p no:cacheprovider --no-cov`
Expected : purs verts ; real_db collectés-et-skippés en local ; AST guard vert sans modif ; `app.main` importe (routeur enregistré).

- [ ] **Step 6 : Commit**

```bash
git add backend/app/services/purchasing/savings_service.py backend/app/services/purchasing/kpi_service.py backend/app/api/api_v1/endpoints/purchasing.py backend/app/api/api_v1/api.py backend/tests/test_kpi_real_db.py
git commit -m "feat(achats): pilotage — enveloppe purchasing_kpi + GET /purchasing/kpi

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3 : Web — écran `/pilotage`

**Files:**
- Modify: `frontend/src/services/types.ts` (type `PurchasingKpi`)
- Create: `frontend/src/services/purchasing-kpi-service.ts`, `frontend/src/hooks/use-purchasing-kpi.ts`, `frontend/src/features/pilotage/pilotage-view.tsx`, `frontend/src/app/(dashboard)/pilotage/page.tsx`
- Modify: la nav (là où les items de nav sont définis, à côté de « Prix »)

**Interfaces:**
- Consumes: `GET /purchasing/kpi` → `PurchasingKpi`.

- [ ] **Step 1 : Type + service + hook**

Dans `types.ts` :
```ts
export interface PurchasingKpi {
  window_months: number;
  savings: { realized: number; missed: number; possible: number;
             best_choice_rate: number | null; compared_lines: number;
             labels: { realized: string; missed: string; possible: string; best_choice_rate: string } };
  possible_open: number;
  cycle: { ordered_total: number; received_value: number; billed_total: number;
           gap_ordered_received: number; gap_billed_received: number;
           missing_value: number; ordered_by_status: Record<string, number> };
  price: { n_hausse: number; n_baisse: number; top_inflation_pct: number | null;
           n_critiques: number; switch_savings_total: number };
  top_products: Array<{ product_id: string; name: string; total_spend: number }>;
  suppliers: {
    most_competitive: Array<{ supplier_id: string; name: string; realized: number }>;
    most_late: Array<{ supplier_id: string; name: string; late_count: number }>;
    best_conformity: Array<{ supplier_id: string; name: string; conformity_rate: number | null }>;
  };
  labels: Record<string, string>;
}
```
`purchasing-kpi-service.ts` :
```ts
import { api } from "@/lib/api";
import type { PurchasingKpi } from "./types";
export async function getPurchasingKpi() {
  const { data } = await api.get<PurchasingKpi>("/purchasing/kpi");
  return data;
}
```
`use-purchasing-kpi.ts` : `useQuery({ queryKey: ["purchasing","kpi"], queryFn: getPurchasingKpi })`.

- [ ] **Step 2 : L'écran `pilotage-view.tsx`**

Composant client qui rend (réutilise `StatCard` de `@/features/dashboard/stat-card` — props `{title, value, icon, hint?, accentClassName?}` ; `formatCurrency`/`formatNumber` null-safe de `@/lib/utils`) :
- En-tête « Pilotage Achats · 12 mois ».
- **Économies** : 4 `StatCard` — `savings.labels.realized`→`formatCurrency(savings.realized)`, `labels.missed`→`missed`, `labels.best_choice_rate`→`best_choice_rate==null?"—":Math.round(rate*100)+" %"`, `labels.possible_open`(du bloc labels)→`formatCurrency(possible_open)`.
- **Cycle** : `StatCard` Commandé/Reçu/Facturé + un petit bloc écarts (`gap_ordered_received`, `gap_billed_received`, `missing_value`) en `formatCurrency`.
- **Prix (réutilisé)** : bloc compact `n_hausse` en hausse · `n_baisse` en baisse · `top_inflation_pct` · `n_critiques` critiques · `switch_savings_total` €, + `<Link href="/prix">Voir le détail →</Link>`.
- **Fournisseurs** : trois petites listes (`most_competitive` avec `formatCurrency(realized)`, `most_late` avec `late_count`, `best_conformity` avec `%`).
Envelopper les cartes annexes dans `SafeBoundary` (`@/components/safe-boundary`) comme les autres cartes du domaine.

`app/(dashboard)/pilotage/page.tsx` : `export default function Page(){ return <PilotageView/> }`.
Ajouter l'item de nav « Pilotage » (icône `LayoutDashboard` ou `Gauge` de lucide) là où « Prix » est déclaré, visible pour les rôles qui voient déjà les achats (mêmes gardes que `/prix`).

- [ ] **Step 3 : Vérifier types/lint/build**

Run : `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected : PASS. (Build bloqué disque/RAM → `TMP=D:/Dev/Temp/claude/next-build TEMP=D:/Dev/Temp/claude/next-build npm run build` ; sinon corriger le vrai souci de type.)

- [ ] **Step 4 : Commit**

```bash
git add frontend/src/services/types.ts frontend/src/services/purchasing-kpi-service.ts frontend/src/hooks/use-purchasing-kpi.ts frontend/src/features/pilotage/ "frontend/src/app/(dashboard)/pilotage/" frontend/src/components/*nav*
git commit -m "feat(achats): écran Pilotage Achats (web)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4 : Mobile — widgets partagés + écran « Pilotage »

**Files:**
- Create: `mobile/lib/features/common/kpi_widgets.dart`
- Modify: `mobile/lib/features/dashboard/dashboard_screen.dart` (consommer les widgets partagés)
- Create: `mobile/lib/features/pilotage/pilotage_screen.dart`
- Modify: `mobile/lib/app/home_shell.dart` (module « Pilotage »)
- Create: `mobile/test/pilotage_test.dart`

**Interfaces:**
- Consumes: `GET /purchasing/kpi` (via `apiClientProvider`).

- [ ] **Step 1 : Extraire les widgets partagés (amélioration ciblée, DRY)**

Créer `mobile/lib/features/common/kpi_widgets.dart` en **déplaçant** `_Stat`, `_MiniStat`, `_SectionCard` depuis `dashboard_screen.dart`, renommés **publics** : `KpiStat` (props `{required label, required value, required sub, subColor, gradient}`), `KpiMiniStat`, `KpiSectionCard` (props `{required icon, required iconColor, required title, required child}`). Importer les tokens nécessaires (`kMuted`, `kSerif`, etc.) depuis `main.dart`. Dans `dashboard_screen.dart` : supprimer les définitions privées, importer `kpi_widgets.dart`, remplacer `_Stat(`→`KpiStat(`, `_MiniStat(`→`KpiMiniStat(`, `_SectionCard(`→`KpiSectionCard(`.

- [ ] **Step 2 : Non-régression dashboard**

Run : `cd mobile && D:/flutter/bin/flutter analyze lib/features/dashboard/dashboard_screen.dart lib/features/common/kpi_widgets.dart && D:/flutter/bin/flutter test` (ou `flutter.bat`)
Expected : `No issues found` ; suite mobile verte (le dashboard rend toujours).

- [ ] **Step 3 : Widget test qui échoue**

`mobile/test/pilotage_test.dart` — sur le modèle de `video_import_test.dart` : faux `HttpClientAdapter` répondant à `/purchasing/kpi` avec une charge minimale (`{window_months:12, savings:{realized:20, labels:{...}}, cycle:{ordered_total:1000, received_value:700, billed_total:650, gap_ordered_received:300, ...}, price:{n_hausse:2,...}, top_products:[], suppliers:{most_competitive:[],most_late:[],best_conformity:[]}, labels:{...}}`), pomper `PilotageScreen`, attendre :
```dart
expect(find.textContaining('Pilotage'), findsWidgets);
expect(find.textContaining('Économisé'), findsOneWidget);
expect(find.textContaining('Commandé'), findsOneWidget);
```
(RED : l'écran n'existe pas.)

- [ ] **Step 4 : Écran `pilotage_screen.dart` + module**

`PilotageScreen` (ConsumerWidget) : provider `FutureProvider` GET `/purchasing/kpi` ; rend avec `KpiStat`/`KpiMiniStat`/`KpiSectionCard` les mêmes groupes qu'en web (Économies, Cycle commandé/reçu/facturé + écarts, Prix compact avec renvoi vers l'écran `/prix` mobile, Fournisseurs). Utiliser `eur()`/`plainNumber()` de `common/format.dart`. Enregistrer un module « Pilotage » dans `home_shell.dart` (même patron que les modules existants ; distinct du module no-code « Indicateurs »).

- [ ] **Step 5 : Test + analyze**

Run : `cd mobile && D:/flutter/bin/flutter test test/pilotage_test.dart && D:/flutter/bin/flutter analyze lib/features/pilotage/pilotage_screen.dart`
Expected : test PASS ; analyze `No issues found`.

- [ ] **Step 6 : Commit**

```bash
git add mobile/lib/features/common/kpi_widgets.dart mobile/lib/features/dashboard/dashboard_screen.dart mobile/lib/features/pilotage/ mobile/lib/app/home_shell.dart mobile/test/pilotage_test.dart
git commit -m "feat(achats): écran Pilotage Achats (mobile) + widgets KPI partagés

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5 : PR, CI verte, validation live

**Files:** aucun (intégration).

- [ ] **Step 1 : Pousser + PR**

```bash
git push -u origin HEAD
gh pr create --base main --title "feat(achats): Pilotage Achats (KPI, morceau C)" --body "$(cat <<'EOF'
Tableau de bord Pilotage Achats tenant-wide (12 mois) en ASSEMBLAGE des moteurs existants — aucune duplication, aucune migration.

- Cœur pur `assemble` (écarts dérivés, classements fournisseurs, passe-plat prix).
- Enveloppe `purchasing_kpi` : économies (`savings_service.for_tenant`), possibles (`quote_matrix`), montants (sommes SQL), reçu (moteur réception), prix (`price_dashboard` surfacé en résumé), top produits, agrégat fournisseur.
- Endpoint read-only `GET /purchasing/kpi` (routeur neuf → pas de piège d'ordre de routes).
- Écran `/pilotage` web + module « Pilotage » mobile (widgets KPI extraits en partagé).

Spec : docs/superpowers/specs/2026-07-28-achats-kpi-pilotage-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2 : CI verte** — `Backend — tests` (real_db KPI), Web, Mobile, AST guard vert. Si la branche est en retard sur `main`, `gh pr update-branch <n>` puis re-CI.

- [ ] **Step 3 : Validation live (RÈGLE ABSOLUE)** — après merge (déploiement) :
- **Backend E2E prod** : login ; créer le scénario d'économies (2 fournisseurs même produit → commande du moins cher) ; `GET /purchasing/kpi` → vérifier `savings.realized>0`, le cycle (commandé/facturé), les écarts dérivés, et le bloc `price` présent ; **nettoyer** (annuler+supprimer la commande, supprimer les devis).
- **Émulateur `foodgad`** : module « Pilotage » → écran rendu (Économies/Cycle/Prix/Fournisseurs), 0 exception logcat.
- **Web** : build vert + contrat validé en direct (pas de harnais Playwright).

- [ ] **Step 4 : Mémoire** — consigner dans [[erp-epic-progress]] : morceau C livré (PR #), reste **A (produit 360°) → D (vérif stock)**.

---

## Self-Review

**1. Spec coverage :**
- Assembleur pur + enveloppe + endpoint `/purchasing/kpi` (routeur neuf) → Tasks 1, 2. ✓
- Économies réalisées (`for_tenant`) + possibles (`quote_matrix`) → Tasks 1 (bloc), 2 (gather). ✓
- Cycle commandé/reçu/facturé + écarts dérivés + en attente → Task 1 (dérive), Task 2 (sommes SQL + boucle réception). ✓
- Prix réutilisé en résumé compact + lien `/prix` → Task 2 (`_price_summary`), Task 3/4 (bloc + lien). ✓
- Fournisseurs (compétitifs/retard/conformité) agrégat léger → Task 1 (classements), Task 2 (`_supplier_rows`). ✓
- UI web `/pilotage` + mobile module « Pilotage » + widgets partagés → Tasks 3, 4. ✓
- Fenêtre 12 mois, aucune table/migration, AST guard vert, non-régression `/prix`/dashboard/`for_supplier` → Tasks 2, 4, 5. ✓
- Réutilisation stricte (price_dashboard/top_products/quote_matrix/savings) → Task 2. ✓

**2. Placeholder scan :** aucun « TBD » ; le code d'assemblage et de gather est concret ; les tâches UI portent types, service, structure d'écran et réutilisation explicites (StatCard / KpiStat), avec « transcrire les contrôles existants » seulement pour l'extraction mobile (pas de logique inventée). ✓

**3. Type consistency :** la forme `parts` (Global Constraints) est identique dans `assemble` (T1), l'enveloppe (T2) et implicitement le type TS/Dart (T3/T4) ; `for_tenant` renvoie `{...5 clés, labels, lines}` consommé par l'enveloppe (T2) ; la sortie de `assemble` (`savings`/`cycle`/`price`/`top_products`/`suppliers`/`labels`) correspond au type `PurchasingKpi` (T3) et à la lecture Dart (T4). ✓

**Note de rigueur inter-tâches :** `_supplier_rows` recalcule conformité/retard en SQL avec **les mêmes définitions** que `supplier_analytics` (issue-free = conforme ; reçu après date promise = retard) — choix assumé du spec (« agrégat léger, pas la boucle overview »). Si le review final préfère mutualiser la définition, ce sera un petit refactor pur ; sinon la définition partagée est documentée ici. Les tests de save/KPI touchant la BDD sont real_db (skip local, CI), conforme à [[never-mock-the-db-session]].
