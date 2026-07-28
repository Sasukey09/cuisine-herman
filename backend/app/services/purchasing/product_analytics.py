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

from sqlalchemy.orm import Session

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


# --------------------------------------------------------------------------- #
# Enveloppe base de données
# --------------------------------------------------------------------------- #
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
