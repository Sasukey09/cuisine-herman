# Moteur d'économies (Achats — morceau B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chiffrer honnêtement l'économie d'achat (réalisée / manquée / possible) sur les commandes issues d'une mise en concurrence, et l'afficher sur la fiche fournisseur 360° (web + mobile).

**Architecture:** Un nouveau service pur `savings_service.py` (cœur `compute_savings` sans base + enveloppes BDD), branché en un seul point : `supplier_analytics.overview` fusionne un bloc `savings` dans la réponse déjà servie par `GET /suppliers/{id}/overview`. Aucune migration, aucune colonne — l'économie est recalculée depuis les devis immuables (doctrine « ce qui se déduit ne se stocke pas »). `réalisée + manquée = possible`, cohérent avec la `potential_savings` du comparateur.

**Tech Stack:** FastAPI + SQLAlchemy (Python 3, `backend/.venv`), Next.js 15 / React 19 / TS (frontend), Flutter + Riverpod + Dio (mobile), pytest, flutter_test.

## Global Constraints

- **Jamais de push direct sur `main`** — branche → CI verte → merge (Render + Vercel déploient depuis `main`).
- **Jamais de mock de la session BDD** — les tests `*_real_db` tournent contre un vrai Postgres (skippés en local, exécutés en CI).
- **Aucune colonne / migration** — rien n'est stocké ; l'AST guard `backend/tests/test_model_attribute_contract.py` doit rester vert **sans modification**.
- **Une seule définition d'économie** : `worst = max(offres)`, `best = min(offres)` sur `{choisie} ∪ {concurrentes}` ; `réalisée = (worst − chosen)×qty`, `manquée = (chosen − best)×qty`, `possible = réalisée + manquée`.
- **Concurrence obligatoire** : une ligne sans ≥1 offre concurrente n'entre ni au numérateur ni au dénominateur.
- **Arithmétique en centimes** : prix arrondis à 2 décimales ; `is_best_choice = chosen ≤ best` sur prix arrondis.
- **Labels servis par l'API** (`SAVINGS_LABELS`), jamais redupliqués dans les clients.
- **Fenêtre fiche fournisseur = 12 mois glissants** (`since = today − 365 j`), cohérente avec `annual_amount`.
- Trailer de commit : `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Commande pytest (pure, en local) :
  `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest <chemin> -q -p no:cacheprovider --no-cov`

---

## File Structure

| Fichier | Rôle | Action |
|---|---|---|
| `backend/app/services/purchasing/savings_service.py` | Cœur pur `compute_savings` + `SAVINGS_LABELS` + enveloppes BDD `_savings_for_order_lines` / `for_supplier` | **Créer** |
| `backend/tests/test_savings_service.py` | Tests purs du cœur | **Créer** |
| `backend/tests/test_savings_real_db.py` | Round-trip Postgres réel (via `GET /suppliers/{id}/overview`) | **Créer** |
| `backend/app/services/purchasing/supplier_analytics.py` | `overview` fusionne `card["savings"]` | **Modifier** |
| `backend/tests/test_supplier_analytics.py` | Docstring du garde-fou précisée (scorecard pur n'invente rien) | **Modifier** |
| `frontend/src/services/suppliers-service.ts` | Type `SupplierOverview` + champ `savings` | **Modifier** |
| `frontend/src/features/suppliers/supplier-scorecard.tsx` | Carte « Économies (12 mois) » conditionnelle | **Modifier** |
| `mobile/lib/features/suppliers/supplier_detail_screen.dart` | Bloc économies dans `_Scorecard` | **Modifier** |
| `mobile/test/supplier_savings_test.dart` | Widget test du bloc économies | **Créer** |

---

## Task 1 : Cœur pur `compute_savings` + labels

**Files:**
- Create: `backend/app/services/purchasing/savings_service.py`
- Test: `backend/tests/test_savings_service.py`

**Interfaces:**
- Produces: `compute_savings(lines: list[dict]) -> dict`. Chaque `line` = `{product_id, supplier_id, qty, chosen_unit_price, competing_prices: list[float]}`. Retour = `{realized, missed, possible, best_choice_rate, compared_lines, lines}` où `lines` est le détail par ligne comparée `{product_id, supplier_id, qty, realized, missed, possible, is_best_choice}`.
- Produces: `SAVINGS_LABELS: dict[str, str]` = `{"realized","missed","possible","best_choice_rate"}` → libellés FR.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_savings_service.py` :

```python
"""Cœur pur du moteur d'économies : aucune base.

Le round-trip contre un vrai Postgres est dans ``test_savings_real_db.py``.
"""
from app.services.purchasing.savings_service import compute_savings, SAVINGS_LABELS


def line(chosen, competing, qty=1.0, pid="p1", sid="s1"):
    return {
        "product_id": pid,
        "supplier_id": sid,
        "qty": qty,
        "chosen_unit_price": chosen,
        "competing_prices": list(competing),
    }


def test_realized_plus_missed_equals_possible():
    # offres {8, 10, 12}, choisie 10, qté 2 → réalisée 4, manquée 4, possible 8
    r = compute_savings([line(10.0, [8.0, 12.0], qty=2)])
    assert r["realized"] == 4.0
    assert r["missed"] == 4.0
    assert r["possible"] == 8.0
    assert r["realized"] + r["missed"] == r["possible"]
    assert r["compared_lines"] == 1


def test_best_choice_when_cheapest_taken():
    # choisie = la moins chère → manquée 0, is_best vrai
    r = compute_savings([line(10.0, [12.0], qty=5)])
    assert r["realized"] == 10.0   # (12-10)*5
    assert r["missed"] == 0.0
    assert r["best_choice_rate"] == 1.0
    assert r["lines"][0]["is_best_choice"] is True


def test_negotiated_below_all_offers_is_never_penalised():
    # choisie 11 sous toutes les offres {12,13} → manquée 0, réalisée (13-11)*1
    r = compute_savings([line(11.0, [12.0, 13.0], qty=1)])
    assert r["missed"] == 0.0
    assert r["realized"] == 2.0
    assert r["lines"][0]["is_best_choice"] is True


def test_a_line_without_competition_is_excluded():
    r = compute_savings([line(10.0, [], qty=3)])
    assert r["compared_lines"] == 0
    assert r["realized"] == 0.0
    assert r["missed"] == 0.0
    assert r["best_choice_rate"] is None


def test_all_offers_equal_yield_zero_but_count_as_best():
    r = compute_savings([line(10.0, [10.0], qty=4)])
    assert r["realized"] == 0.0
    assert r["missed"] == 0.0
    assert r["possible"] == 0.0
    assert r["compared_lines"] == 1
    assert r["best_choice_rate"] == 1.0


def test_best_choice_rate_over_several_lines():
    r = compute_savings([
        line(10.0, [12.0]),        # meilleur choix
        line(12.0, [10.0]),        # pas le meilleur (manquée > 0)
    ])
    assert r["compared_lines"] == 2
    assert r["best_choice_rate"] == 0.5


def test_labels_are_the_single_source():
    assert set(SAVINGS_LABELS) == {"realized", "missed", "possible", "best_choice_rate"}
    assert SAVINGS_LABELS["realized"] == "Économisé"
```

- [ ] **Step 2 : Lancer les tests et vérifier l'échec**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_savings_service.py -q -p no:cacheprovider --no-cov`
Expected : FAIL (`ModuleNotFoundError: app.services.purchasing.savings_service`).

- [ ] **Step 3 : Écrire le cœur pur**

Créer `backend/app/services/purchasing/savings_service.py` (partie pure uniquement pour l'instant) :

```python
"""Moteur d'économies : ce que la mise en concurrence a rapporté.

Une seule définition d'économie dans tout le domaine Achats, cohérente avec la
``potential_savings`` du comparateur (``quote_matrix``). Pour une ligne commandée
qui avait des offres concurrentes, sur l'ensemble ``{choisie} ∪ {concurrentes}`` :

- ``worst = max(offres)``, ``best = min(offres)``
- **réalisée** ``(worst − chosen) × qty`` — ce qu'on a évité de payer par rapport
  à la pire offre
- **manquée** ``(chosen − best) × qty`` — l'argent laissé sur la table
- **possible** = réalisée + manquée = ``(worst − best) × qty``

Rigueur : pas de concurrence, pas d'économie (la ligne est exclue, pas comptée
zéro) ; le mérite de la négociation sous toutes les offres n'est jamais pénalisé
(``manquée = 0``). Le cœur ``compute_savings`` est **pur** ; les enveloppes qui
lisent les devis et les commandes sont plus bas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

#: Libellés servis par l'API — source unique, web et mobile ne les redupliquent pas.
SAVINGS_LABELS = {
    "realized": "Économisé",
    "missed": "Laissé sur la table",
    "possible": "Économie possible",
    "best_choice_rate": "Taux de meilleur choix",
}


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def compute_savings(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrège les économies sur des lignes déjà mises en concurrence (pur).

    ``lines`` : ``{product_id, supplier_id, qty, chosen_unit_price,
    competing_prices: [float]}`` — ``competing_prices`` ne contient QUE les offres
    éligibles des AUTRES fournisseurs (filtrage validité/dispo fait en amont).
    """
    detail: List[Dict[str, Any]] = []
    tot_real = tot_missed = 0.0
    compared = 0
    best_choices = 0

    for l in lines:
        chosen = _f(l.get("chosen_unit_price"))
        qty = _f(l.get("qty"))
        competing = [round(p, 2) for p in (l.get("competing_prices") or []) if p is not None]
        if chosen is None or qty is None or not competing:
            continue  # pas de concurrence → hors calcul

        chosen_r = round(chosen, 2)
        offers = competing + [chosen_r]
        worst, best = max(offers), min(offers)
        realized = round((worst - chosen_r) * qty, 2)
        missed = round((chosen_r - best) * qty, 2)
        possible = round(realized + missed, 2)
        is_best = chosen_r <= best

        compared += 1
        best_choices += 1 if is_best else 0
        tot_real += realized
        tot_missed += missed
        detail.append(
            {
                "product_id": l.get("product_id"),
                "supplier_id": l.get("supplier_id"),
                "qty": qty,
                "realized": realized,
                "missed": missed,
                "possible": possible,
                "is_best_choice": is_best,
            }
        )

    tot_real = round(tot_real, 2)
    tot_missed = round(tot_missed, 2)
    return {
        "realized": tot_real,
        "missed": tot_missed,
        "possible": round(tot_real + tot_missed, 2),
        "best_choice_rate": round(best_choices / compared, 3) if compared else None,
        "compared_lines": compared,
        "lines": detail,
    }
```

- [ ] **Step 4 : Lancer les tests et vérifier le succès**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_savings_service.py -q -p no:cacheprovider --no-cov`
Expected : PASS (7 tests).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/purchasing/savings_service.py backend/tests/test_savings_service.py
git commit -m "feat(achats): moteur d'économies — cœur pur compute_savings

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2 : Enveloppes BDD `_savings_for_order_lines` + `for_supplier`

**Files:**
- Modify: `backend/app/services/purchasing/savings_service.py`
- Test: `backend/tests/test_savings_real_db.py`

**Interfaces:**
- Consumes: `compute_savings` (Task 1) ; modèles `PurchaseOrder`, `PurchaseOrderLine`, `Quote`, `QuoteLine` ; `order_service.CANCELLED` ; `crud_supplier_product.list_links(db, tenant_id, product_id)` (liens avec `.supplier_id`, `.available`).
- Produces: `_savings_for_order_lines(db, tenant_id, *, supplier_id=None, product_id=None, since=None, today=None) -> dict` (même forme que `compute_savings`).
- Produces: `for_supplier(db, tenant_id, supplier_id, today) -> dict` = `{realized, missed, possible, best_choice_rate, compared_lines, labels}` (fenêtre 12 mois, sans le détail par ligne).

- [ ] **Step 1 : Écrire le test real_db qui échoue**

Créer `backend/tests/test_savings_real_db.py` :

```python
"""Moteur d'économies contre un vrai Postgres, via GET /suppliers/{id}/overview.

Ce qui se vérifie ici et nulle part ailleurs : la résolution réelle des offres
concurrentes depuis les devis, la borne de validité (une offre postérieure à la
commande ne compte pas), et l'exclusion des commandes saisies à la main.
"""
import uuid
from datetime import date, datetime, timedelta

import pytest

from app.models.models import (
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    QuoteLine,
    Supplier,
)


@pytest.fixture()
def client_ctx(db):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_tenant_id
    from app.db.session import get_db
    from app.main import app

    tid = str(uuid.uuid4())
    metro, transg, pid = (str(uuid.uuid4()) for _ in range(3))
    db.add(Organization(id=tid, name="Éco"))
    db.commit()
    db.add(Supplier(id=metro, tenant_id=tid, name="METRO"))
    db.add(Supplier(id=transg, tenant_id=tid, name="TRANSGOURMET"))
    db.add(Product(id=pid, tenant_id=tid, name="Farine T55"))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_tenant_id] = lambda: tid
    client = TestClient(app)
    yield client, {"tenant_id": tid, "metro": metro, "transg": transg, "product": pid}
    app.dependency_overrides.clear()


def _overview(client, sid):
    r = client.get(f"/api/v1/suppliers/{sid}/overview")
    assert r.status_code == 200, r.text
    return r.json()


def _quote_line(db, tid, sid, pid, price, when, valid_until=None):
    """Une offre : un devis (daté) + sa ligne. Renvoie l'id de la ligne."""
    qid, lid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Quote(id=qid, tenant_id=tid, reference=f"DEV-{price}", status="draft",
                 date=when, valid_until=valid_until))
    db.add(QuoteLine(id=lid, tenant_id=tid, quote_id=qid, product_id=pid,
                     supplier_id=sid, qty=5, unit_price=price))
    db.commit()
    return lid


def test_savings_from_a_real_competition(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    # Deux offres, même produit : METRO 10, TRANSGOURMET 14, valides.
    metro_line = _quote_line(db, tid, metro, pid, 10.0, today - timedelta(days=10),
                             valid_until=today + timedelta(days=30))
    _quote_line(db, tid, transg, pid, 14.0, today - timedelta(days=10),
                valid_until=today + timedelta(days=30))

    # On a commandé chez METRO (le moins cher), 5 unités à 10, depuis SON offre.
    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-1", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0,
                             source_quote_line_id=metro_line))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["compared_lines"] == 1
    assert s["realized"] == 20.0   # (14 - 10) * 5
    assert s["missed"] == 0.0
    assert s["possible"] == 20.0
    assert s["best_choice_rate"] == 1.0
    assert s["labels"]["realized"] == "Économisé"


def test_a_later_quote_does_not_rewrite_the_past(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    metro_line = _quote_line(db, tid, metro, pid, 10.0, today - timedelta(days=10))
    _quote_line(db, tid, transg, pid, 14.0, today - timedelta(days=10))
    # Une offre FUTURE, arrivée après la commande : ne doit pas gonfler l'économie.
    _quote_line(db, tid, transg, pid, 30.0, today + timedelta(days=5))

    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-2", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0,
                             source_quote_line_id=metro_line))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["realized"] == 20.0, "l'offre postérieure (30) est ignorée : worst = 14"


def test_a_hand_typed_order_contributes_nothing(db, client_ctx):
    client, c = client_ctx
    tid, metro, pid = c["tenant_id"], c["metro"], c["product"]
    # Commande sans source_quote_line_id : pas de comparatif, donc pas d'économie.
    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-3", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["compared_lines"] == 0
    assert s["realized"] == 0.0
    assert s["best_choice_rate"] is None
```

- [ ] **Step 2 : Vérifier l'échec (localement : collecte OK, tests skippés faute de Postgres)**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_savings_real_db.py -q -p no:cacheprovider --no-cov`
Expected : les tests se collectent sans erreur d'import ; ils **skippent** en local (pas de `real_db`). L'échec réel (`KeyError: 'savings'`) sera prouvé en CI à l'étape suivante — c'est attendu et documenté par [[never-mock-the-db-session]].

- [ ] **Step 3 : Écrire les enveloppes BDD**

Ajouter à `backend/app/services/purchasing/savings_service.py` (imports en tête + fonctions en bas) :

```python
# --- en tête du fichier, après les imports existants ---
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.crud import crud_supplier_product
from app.models.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    QuoteLine,
)
from app.services.purchasing import order_service


# --------------------------------------------------------------------------- #
# Enveloppes base de données
# --------------------------------------------------------------------------- #
def _order_date(o: PurchaseOrder) -> Optional[date]:
    """La date qui fait foi pour juger quelles offres étaient sur la table :
    la date de commande si elle existe, sinon la création."""
    dt = o.ordered_at or o.created_at
    if dt is None:
        return None
    return dt.date() if isinstance(dt, datetime) else dt


def _savings_for_order_lines(
    db: Session,
    tenant_id: str,
    *,
    supplier_id: Optional[str] = None,
    product_id: Optional[str] = None,
    since: Optional[date] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Assemble les lignes commandées mises en concurrence et délègue au cœur pur.

    Les concurrents d'une ligne = les lignes de devis du même produit, d'un AUTRE
    fournisseur, valides à la date de la commande (l'offre existait et n'était pas
    périmée) et disponibles. Rien n'est stocké : tout est recalculé ici.
    """
    today = today or date.today()

    q = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == tenant_id,
        PurchaseOrder.status != order_service.CANCELLED,
    )
    if supplier_id:
        q = q.filter(PurchaseOrder.supplier_id == str(supplier_id))
    orders = q.all()
    if not orders:
        return compute_savings([])

    odate = {o.id: _order_date(o) for o in orders}
    osupplier = {o.id: (str(o.supplier_id) if o.supplier_id else None) for o in orders}

    line_q = db.query(PurchaseOrderLine).filter(
        PurchaseOrderLine.tenant_id == tenant_id,
        PurchaseOrderLine.order_id.in_([o.id for o in orders]),
        PurchaseOrderLine.source_quote_line_id.isnot(None),
        PurchaseOrderLine.product_id.isnot(None),
    )
    kept = []
    for l in line_q.all():
        if product_id and str(l.product_id) != str(product_id):
            continue
        d = odate.get(l.order_id)
        if d is None or (since and d < since):
            continue
        kept.append(l)
    if not kept:
        return compute_savings([])

    pids = {str(l.product_id) for l in kept}

    # Toutes les offres (lignes de devis) de ces produits, avec la date/validité du devis.
    offers_by_product: Dict[str, List[Dict[str, Any]]] = {}
    for ql, quote in (
        db.query(QuoteLine, Quote)
        .join(Quote, Quote.id == QuoteLine.quote_id)
        .filter(
            QuoteLine.tenant_id == tenant_id,
            QuoteLine.product_id.in_(list(pids)),
            QuoteLine.unit_price.isnot(None),
        )
        .all()
    ):
        sid = ql.supplier_id or quote.supplier_id
        qdate = quote.date or (quote.created_at.date() if quote.created_at else None)
        offers_by_product.setdefault(str(ql.product_id), []).append(
            {
                "supplier_id": str(sid) if sid else None,
                "unit_price": _f(ql.unit_price),
                "quote_date": qdate,
                "valid_until": quote.valid_until,
            }
        )

    # Disponibilité par (produit, fournisseur) — défaut : disponible.
    avail: Dict[str, Dict[str, bool]] = {}
    for pid in pids:
        avail[pid] = {
            str(link.supplier_id): (bool(link.available) if link.available is not None else True)
            for link in crud_supplier_product.list_links(db, tenant_id, pid)
        }

    def competing(pid: str, chosen_sid: Optional[str], order_d: date) -> List[float]:
        out: List[float] = []
        for off in offers_by_product.get(pid, []):
            if off["unit_price"] is None or off["supplier_id"] == chosen_sid:
                continue
            if off["quote_date"] is None or off["quote_date"] > order_d:
                continue  # l'offre n'existait pas encore à la commande
            vu = off["valid_until"]
            if vu is not None and vu < order_d:
                continue  # offre périmée
            if avail.get(pid, {}).get(off["supplier_id"], True) is False:
                continue  # indisponible
            out.append(off["unit_price"])
        return out

    inputs = [
        {
            "product_id": str(l.product_id),
            "supplier_id": osupplier.get(l.order_id),
            "qty": _f(l.qty_ordered),
            "chosen_unit_price": _f(l.unit_price),
            "competing_prices": competing(
                str(l.product_id), osupplier.get(l.order_id), odate[l.order_id]
            ),
        }
        for l in kept
    ]
    return compute_savings(inputs)


def for_supplier(
    db: Session, tenant_id: str, supplier_id: str, today: date
) -> Dict[str, Any]:
    """Le bloc économies d'un fournisseur, sur 12 mois glissants. Sans détail par
    ligne (la fiche n'a besoin que des totaux) et avec les libellés."""
    since = today - timedelta(days=365)
    res = _savings_for_order_lines(
        db, tenant_id, supplier_id=str(supplier_id), since=since, today=today
    )
    return {
        "realized": res["realized"],
        "missed": res["missed"],
        "possible": res["possible"],
        "best_choice_rate": res["best_choice_rate"],
        "compared_lines": res["compared_lines"],
        "labels": SAVINGS_LABELS,
    }
```

- [ ] **Step 4 : Vérifier localement que rien n'est cassé (tests purs + collecte)**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_savings_service.py tests/test_savings_real_db.py -q -p no:cacheprovider --no-cov`
Expected : `test_savings_service.py` PASS ; `test_savings_real_db.py` SKIP en local. (Le PASS réel sur Postgres arrive après le branchement de la Task 3, en CI.)

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/purchasing/savings_service.py backend/tests/test_savings_real_db.py
git commit -m "feat(achats): moteur d'économies — enveloppes BDD (offres concurrentes valides à la commande)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3 : Brancher `savings` dans la fiche fournisseur + préciser le garde-fou

**Files:**
- Modify: `backend/app/services/purchasing/supplier_analytics.py:263-271` (le bloc `card.update(...)` de `overview`) et ses imports (ligne 39).
- Modify: `backend/tests/test_supplier_analytics.py:200-206` (docstring du garde-fou).

**Interfaces:**
- Consumes: `savings_service.for_supplier` (Task 2).
- Produces: la réponse de `GET /suppliers/{id}/overview` contient désormais `card["savings"]` (contrat consommé par les Tasks 4 et 5).

- [ ] **Step 1 : Écrire l'assertion real_db qui échoue**

Le test de présence vit déjà dans `test_savings_real_db.py` (Task 2, `test_savings_from_a_real_competition` lit `["savings"]`). Avant branchement il lèverait `KeyError`. Aucune nouvelle assertion à écrire ici — cette task fait passer ces tests en CI.

- [ ] **Step 2 : Vérifier l'état actuel (le champ manque)**

Confirmer par lecture que `supplier_analytics.overview` ne renvoie pas encore `savings` (bloc `card.update(...)`, lignes ~263-271). Aucune commande à lancer.

- [ ] **Step 3 : Brancher le moteur**

Dans `backend/app/services/purchasing/supplier_analytics.py`, ligne 39, étendre l'import :

```python
from app.services.purchasing import order_service, savings_service
```

Puis dans `overview`, compléter le `card.update({...})` pour ajouter la clé `savings` :

```python
    card = scorecard(orders, receipts, invoices, purchases, int(quote_count), today)
    card.update(
        {
            "supplier_id": sid,
            "supplier_name": supplier.name,
            "rating": _f(supplier.rating),  # note manuelle 0–5, distincte du score calculé
            # L'économie réalisée par la mise en concurrence — recalculée depuis les
            # devis (Task B), jamais stockée. Absente du cœur pur `scorecard`, qui
            # n'a pas accès aux offres : elle s'assemble seulement ici.
            "savings": savings_service.for_supplier(db, tenant_id, sid, today),
        }
    )
    return card
```

- [ ] **Step 4 : Préciser le garde-fou de la Phase 5 (il reste vrai pour `scorecard`)**

Dans `backend/tests/test_supplier_analytics.py`, remplacer la docstring de `test_no_fabricated_savings_field` pour refléter que le cœur pur n'invente toujours rien — l'économie honnête vit désormais dans `overview` (prouvée par `test_savings_real_db.py`) :

```python
def test_no_fabricated_savings_field():
    """Le cœur pur ``scorecard`` n'invente pas d'économie : il n'a pas les offres.
    Le vrai « montant économisé » est désormais assemblé dans ``overview`` à partir
    des comparatifs de devis (moteur B) et vérifié dans ``test_savings_real_db.py``.
    Ici on garde la garantie que la couche pure, elle, reste sans économie inventée."""
    assert "savings" not in empty()
    assert "montant_economise" not in empty()
```

- [ ] **Step 5 : Vérifier localement (pur) et confirmer l'AST guard**

Run : `cd backend && APP_ENV=development SECRET_KEY=test OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests/test_supplier_analytics.py tests/test_model_attribute_contract.py -q -p no:cacheprovider --no-cov`
Expected : PASS (le garde-fou reste vert ; l'AST guard reste vert sans modification — aucune colonne ajoutée).

- [ ] **Step 6 : Commit**

```bash
git add backend/app/services/purchasing/supplier_analytics.py backend/tests/test_supplier_analytics.py
git commit -m "feat(achats): la fiche fournisseur 360° expose enfin le montant économisé

Comble le trou laissé en Phase 5 : overview fusionne le bloc savings du
moteur B. Le cœur pur scorecard reste sans économie inventée.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4 : Web — carte « Économies » sur la fiche fournisseur

**Files:**
- Modify: `frontend/src/services/suppliers-service.ts:46-68` (type `SupplierOverview`)
- Modify: `frontend/src/features/suppliers/supplier-scorecard.tsx`

**Interfaces:**
- Consumes: `GET /suppliers/{id}/overview` → champ `savings` (Task 3).

- [ ] **Step 1 : Étendre le type `SupplierOverview`**

Dans `frontend/src/services/suppliers-service.ts`, ajouter le champ `savings` à l'interface (avant la fermeture `}` de `SupplierOverview`, après `orders_by_status`) :

```ts
  orders_by_status: Record<string, number>;
  savings: {
    realized: number;
    missed: number;
    possible: number;
    best_choice_rate: number | null;
    compared_lines: number;
    labels: { realized: string; missed: string; possible: string; best_choice_rate: string };
  };
}
```

- [ ] **Step 2 : Ajouter la carte dans le scorecard**

Dans `frontend/src/features/suppliers/supplier-scorecard.tsx`, insérer ce bloc juste **après** la carte des volumes (le `</Card>` qui suit `data.price_trend_pct`, avant le commentaire `{/* Évolution mensuelle ... */}`) :

```tsx
      {/* Économies : ce que la mise en concurrence a rapporté. Rien si aucune
          ligne n'a été comparée — on n'annonce pas une économie qu'on n'a pas. */}
      {data.savings.compared_lines > 0 ? (
        <Card>
          <CardContent className="py-4">
            <div className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
              Économies (12 mois) · {data.savings.compared_lines} ligne(s) comparée(s)
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <div className="text-lg font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                  {formatCurrency(data.savings.realized)}
                </div>
                <div className="text-xs text-muted-foreground">{data.savings.labels.realized}</div>
              </div>
              <div>
                <div className="text-lg font-bold tabular-nums text-amber-600 dark:text-amber-400">
                  {formatCurrency(data.savings.missed)}
                </div>
                <div className="text-xs text-muted-foreground">{data.savings.labels.missed}</div>
              </div>
              <div>
                <div className="text-lg font-bold tabular-nums">
                  {data.savings.best_choice_rate == null
                    ? "—"
                    : `${Math.round(data.savings.best_choice_rate * 100)} %`}
                </div>
                <div className="text-xs text-muted-foreground">
                  {data.savings.labels.best_choice_rate}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}
```

- [ ] **Step 3 : Vérifier types, lint et build**

Run : `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected : PASS (aucune erreur de type ; `savings` reconnu).

- [ ] **Step 4 : Commit**

```bash
git add frontend/src/services/suppliers-service.ts frontend/src/features/suppliers/supplier-scorecard.tsx
git commit -m "feat(achats): carte Économies sur la fiche fournisseur (web)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5 : Mobile — bloc « Économies » dans `_Scorecard`

**Files:**
- Modify: `mobile/lib/features/suppliers/supplier_detail_screen.dart` (`_Scorecard.build`, après le bloc « Produits les plus achetés »)
- Create: `mobile/test/supplier_savings_test.dart`

**Interfaces:**
- Consumes: `GET /suppliers/{id}/overview` → champ `savings` (Task 3). `_Scorecard` lit `o` comme `Map<String, dynamic>` brut ; réutilise le helper `_tile`.

- [ ] **Step 1 : Écrire le widget test qui échoue**

Créer `mobile/test/supplier_savings_test.dart` :

```dart
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:foodgad_mobile/core/api_client.dart';
import 'package:foodgad_mobile/core/providers.dart';
import 'package:foodgad_mobile/core/token_store.dart';
import 'package:foodgad_mobile/features/suppliers/supplier_detail_screen.dart';

/// Faux backend : sert les 4 endpoints que lit l'écran, avec un bloc `savings`
/// dans l'overview (shape de `savings_service.for_supplier`).
class _SupplierApi implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? _,
      Future<void>? __) async {
    final path = options.path;
    dynamic body;
    if (path.endsWith('/suppliers/s1/overview')) {
      body = {
        'supplier_id': 's1',
        'supplier_name': 'METRO',
        'annual_amount': 1850.0,
        'score': null,
        'conformity_rate': null,
        'on_time_rate': null,
        'late_count': 0,
        'receipt_count': 0,
        'quote_count': 1,
        'order_count': 1,
        'invoice_count': 0,
        'distinct_products': 1,
        'monthly': [],
        'top_products': [],
        'price_trend_pct': null,
        'orders_by_status': {},
        'savings': {
          'realized': 20.0,
          'missed': 0.0,
          'possible': 20.0,
          'best_choice_rate': 1.0,
          'compared_lines': 1,
          'labels': {
            'realized': 'Économisé',
            'missed': 'Laissé sur la table',
            'possible': 'Économie possible',
            'best_choice_rate': 'Taux de meilleur choix',
          },
        },
      };
    } else if (path.endsWith('/suppliers/s1/purchase-history')) {
      body = {'purchases': []};
    } else if (path.endsWith('/suppliers/s1/prices')) {
      body = [];
    } else if (path.endsWith('/suppliers/s1')) {
      body = {'id': 's1', 'name': 'METRO', 'contact': {}, 'rating': null};
    } else {
      body = {};
    }
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {Headers.contentTypeHeader: [Headers.jsonContentType]},
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });

  testWidgets('the supplier fiche shows the Économies block', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final client = ApiClient(TokenStore());
    client.dio.httpClientAdapter = _SupplierApi();

    await tester.pumpWidget(ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(client)],
      child: const MaterialApp(
        home: SupplierDetailScreen(supplierId: 's1', supplierName: 'METRO'),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('Économies (12 mois)'), findsOneWidget);
    expect(find.text('Économisé'), findsOneWidget);
    expect(find.text('Taux de meilleur choix'), findsOneWidget);
  });
}
```

- [ ] **Step 2 : Lancer le test et vérifier l'échec**

Run : `cd mobile && D:/flutter/bin/flutter test test/supplier_savings_test.dart`
Expected : FAIL (`find.textContaining('Économies (12 mois)')` → zéro widget : le bloc n'existe pas encore).

- [ ] **Step 3 : Ajouter le bloc économies dans `_Scorecard`**

Dans `mobile/lib/features/suppliers/supplier_detail_screen.dart`, méthode `_Scorecard.build`, insérer ce bloc à la fin de la liste `children` (juste avant le `]);` de fermeture du `Column`, après le `if (products.isNotEmpty) ...[ ... ]`) :

```dart
      if (((o['savings'] as Map?)?['compared_lines'] as num?)?.toInt() != null &&
          ((o['savings'] as Map)['compared_lines'] as num).toInt() > 0) ...[
        const SizedBox(height: 8),
        Builder(builder: (_) {
          final s = Map<String, dynamic>.from(o['savings'] as Map);
          final labels = Map<String, dynamic>.from(s['labels'] as Map);
          final rate = s['best_choice_rate'] as num?;
          return Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Économies (12 mois) · ${s['compared_lines']} ligne(s) comparée(s)',
                    style: const TextStyle(
                        fontSize: 11.5, fontWeight: FontWeight.w700, color: kMuted)),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: _tile(eur(s['realized'] as num?), '${labels['realized']}', kGood)),
                  const SizedBox(width: 8),
                  Expanded(child: _tile(eur(s['missed'] as num?), '${labels['missed']}', kWarn)),
                  const SizedBox(width: 8),
                  Expanded(child: _tile(
                      rate == null ? '—' : '${(rate * 100).round()} %',
                      '${labels['best_choice_rate']}', kTerracotta)),
                ]),
              ]),
            ),
          );
        }),
      ],
```

- [ ] **Step 4 : Lancer le test et l'analyse**

Run : `cd mobile && D:/flutter/bin/flutter test test/supplier_savings_test.dart && D:/flutter/bin/flutter analyze lib/features/suppliers/supplier_detail_screen.dart`
Expected : test PASS ; analyze sans erreur (`No issues found`).

- [ ] **Step 5 : Commit**

```bash
git add mobile/lib/features/suppliers/supplier_detail_screen.dart mobile/test/supplier_savings_test.dart
git commit -m "feat(achats): bloc Économies sur la fiche fournisseur (mobile)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6 : PR, CI verte, validation live

**Files:** aucun (intégration).

- [ ] **Step 1 : Pousser la branche et ouvrir la PR**

```bash
git push -u origin HEAD
gh pr create --base main --title "feat(achats): moteur d'économies — fiche fournisseur (morceau B)" --body "$(cat <<'EOF'
Moteur d'économies du domaine Achats (morceau B du pilotage restant).

- Cœur pur `compute_savings` : réalisée/manquée/possible, `réalisée + manquée = possible`,
  cohérent avec la `potential_savings` du comparateur.
- Enveloppe BDD : offres concurrentes recalculées depuis les devis valides à la
  date de la commande — rien n'est stocké (aucune migration).
- Branchement unique : `GET /suppliers/{id}/overview` expose un bloc `savings` ;
  fiche fournisseur web + mobile. Comble le trou laissé en Phase 5.

Spec : docs/superpowers/specs/2026-07-27-achats-moteur-economies-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2 : Attendre la CI (Postgres réel)**

Vérifier que la CI passe, en particulier `test_savings_real_db.py` (qui skippe en local) et `test_model_attribute_contract.py` (vert sans modif). Corriger si rouge, re-pousser.

- [ ] **Step 3 : Merge après CI verte**

Merger la PR (déclenche le déploiement Render backend). Le web se déploiera au prochain reset Vercel, empilé avec les Phases 4 & 5 en attente.

- [ ] **Step 4 : Validation live (RÈGLE ABSOLUE)**

Selon [[erp-epic-progress]] et le compte de test : créer un devis multi-fournisseurs (≥2 offres même produit, ex. SMOKE-ECO), commander la ligne la moins chère via le comparateur, ouvrir la fiche du fournisseur.
- **Web (Playwright)** : la carte « Économies (12 mois) » affiche le montant réalisé attendu.
- **Mobile (émulateur `foodgad`)** : le bloc économies s'affiche sur la fiche fournisseur ; surveiller `logcat` (aucune exception Flutter).
- **Nettoyer** tous les jeux de test créés (devis/commandes SMOKE-ECO) via l'API après validation.

- [ ] **Step 5 : Mettre à jour la mémoire**

Consigner dans [[erp-epic-progress]] : morceau B livré (PR #), reste C (KPI) → A (produit 360°) → D (vérif stock).

---

## Self-Review

**1. Spec coverage :**
- Décision de métrique (vs offre la plus chère, invariant) → Task 1 (cœur + tests). ✓
- Résolution des offres concurrentes valides à la commande, rien stocké → Task 2. ✓
- Branchement unique fiche fournisseur, `SAVINGS_LABELS` servis par l'API, garde-fou inversé, AST guard inchangé → Task 3. ✓
- Fenêtre 12 mois → `for_supplier` (Task 2) + libellé carte (Tasks 4-5). ✓
- Surfaces web + mobile → Tasks 4, 5. ✓
- Tests purs + real_db + widget + validation live → Tasks 1, 2, 5, 6. ✓
- `for_product` / `for_tenant` / écran KPI → **hors périmètre** (morceaux A et C), conforme au spec. ✓

**2. Placeholder scan :** aucun « TBD »/« TODO »/« handle edge cases » ; chaque étape de code porte le code réel. ✓

**3. Type consistency :** `compute_savings` renvoie `{realized, missed, possible, best_choice_rate, compared_lines, lines}` (Task 1) ; `for_supplier` renvoie les mêmes clés moins `lines`, plus `labels` (Task 2) ; le type TS `savings` (Task 4) et le Map mobile (Task 5) lisent exactement ces clés ; `SAVINGS_LABELS` a les 4 clés `realized/missed/possible/best_choice_rate` cohérentes partout. ✓

**Note de rigueur inter-tasks :** `test_savings_real_db.py` (Task 2) est rouge (`KeyError: 'savings'`) tant que la Task 3 n'a pas branché `overview`. C'est voulu : la BDD réelle n'existe qu'en CI, et l'ordre 2→3 garde chaque commit atomique. La preuve d'échec/succès se fait en CI (Task 6), conformément à [[never-mock-the-db-session]].
