"""Moteur de comparaison multi-devis : le tableau produit × fournisseur.

Une ligne = un produit, une colonne = un fournisseur (§7). Pour chaque offre on
rend le prix affiché, le **prix à l'unité de base** (le seul comparable), la
TVA, la remise, le conditionnement, le délai, la disponibilité et la validité —
puis un rang (meilleure / moyenne / plus chère) et l'écart en % avec la
meilleure.

Deux garde-fous qui font la différence entre un comparateur utile et un
comparateur trompeur :

1. **On ne compare que ce qui est comparable.** Si toutes les offres d'un
   produit ont un conditionnement lisible, le classement se fait au prix à
   l'unité de base. Sinon on retombe sur le prix affiché **et on le signale**
   (`basis="unit_price"`, `mixed_packaging=True`) : l'utilisateur doit savoir
   que le classement est fragile.
2. **Une offre périmée ne gagne pas.** Une offre dont la validité est dépassée
   est marquée `expired` et exclue du classement : proposer un « moins cher »
   qu'on ne peut plus commander est pire que ne rien proposer.

Pur : aucune dépendance BDD, testé isolément.
"""
from datetime import date
from typing import Any, Dict, List, Optional

from .pack_parser import price_per_base_unit


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def build_matrix(
    offers: List[Dict[str, Any]],
    history: Optional[Dict[str, Dict[str, Any]]] = None,
    catalog: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    supplier_names: Optional[Dict[str, str]] = None,
    product_names: Optional[Dict[str, str]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Construit le tableau comparatif.

    ``offers`` : lignes de devis, chacune
    ``{product_id, supplier_id, quote_id, quote_reference, description,
       unit_price, qty, unit, vat_rate, discount_pct, pack_size, valid_until}``.
    ``history`` : ``{product_id: {last_paid, avg_paid, best_paid, unit_code}}``.
    ``catalog`` : ``{product_id: {supplier_id: {available, preferred,
       lead_time_days}}}``.
    """
    history = history or {}
    catalog = catalog or {}
    supplier_names = supplier_names or {}
    product_names = product_names or {}

    by_product: Dict[str, List[Dict[str, Any]]] = {}
    for o in offers:
        pid = o.get("product_id")
        if pid:
            by_product.setdefault(str(pid), []).append(o)

    products: List[Dict[str, Any]] = []
    supplier_totals: Dict[str, Dict[str, Any]] = {}
    potential_savings = 0.0

    for pid, raws in by_product.items():
        cat_for_product = catalog.get(pid, {})
        rows: List[Dict[str, Any]] = []

        for o in raws:
            sid = str(o.get("supplier_id")) if o.get("supplier_id") else None
            unit_price = _f(o.get("unit_price"))
            discount = _f(o.get("discount_pct"))
            ppu = price_per_base_unit(
                unit_price,
                pack_size=o.get("pack_size"),
                description=o.get("description"),
                discount_pct=discount,
            )
            cat = cat_for_product.get(sid, {}) if sid else {}
            valid_until = o.get("valid_until")
            expired = bool(today and valid_until and valid_until < today)

            rows.append(
                {
                    "supplier_id": sid,
                    "supplier_name": supplier_names.get(sid) if sid else None,
                    "quote_id": o.get("quote_id"),
                    # L'identifiant de la LIGNE, pas seulement du devis : c'est
                    # lui qui permet de commander cette offre-là. Sans lui, le
                    # comparateur ne peut désigner un gagnant que par écrit.
                    "quote_line_id": o.get("quote_line_id"),
                    "quote_reference": o.get("quote_reference"),
                    "unit_price": unit_price,
                    "qty": _f(o.get("qty")),
                    "unit": o.get("unit"),
                    "vat_rate": _f(o.get("vat_rate")),
                    "discount_pct": discount,
                    "pack_size": o.get("pack_size"),
                    "brand": o.get("brand"),
                    "min_qty": _f(o.get("min_qty")),
                    "delivery_fee": _f(o.get("delivery_fee")),
                    "price_per_base_unit": ppu[0] if ppu else None,
                    "base_unit": ppu[1] if ppu else None,
                    "lead_time_days": cat.get("lead_time_days"),
                    "available": bool(cat.get("available", True)),
                    "preferred": bool(cat.get("preferred", False)),
                    "valid_until": valid_until,
                    "expired": expired,
                }
            )

        # Base de comparaison : l'unité de base si TOUTES les offres retenues la
        # donnent (et la même), sinon le prix affiché — signalé comme fragile.
        eligible = [r for r in rows if not r["expired"] and r["available"]]
        units = {r["base_unit"] for r in eligible if r["price_per_base_unit"] is not None}
        all_normalised = bool(eligible) and len(units) == 1 and all(
            r["price_per_base_unit"] is not None for r in eligible
        )
        basis = "base_unit" if all_normalised else "unit_price"
        key = "price_per_base_unit" if all_normalised else "unit_price"

        priced = [r for r in eligible if r.get(key) is not None]
        priced.sort(key=lambda r: r[key])
        best = priced[0][key] if priced else None
        worst = priced[-1][key] if priced else None

        for r in rows:
            value = r.get(key)
            if r["expired"] or not r["available"] or value is None or best is None:
                r["rank"] = None  # hors classement : ni vert, ni orange, ni rouge
                r["delta_pct_vs_best"] = None
                continue
            if value == best:
                r["rank"] = "best"
            elif worst is not None and value == worst and len(priced) > 1:
                r["rank"] = "worst"
            else:
                r["rank"] = "mid"
            r["delta_pct_vs_best"] = (
                round((value - best) / best * 100.0, 1) if best else None
            )

        hist = history.get(pid, {}) or {}
        last_paid = _f(hist.get("last_paid"))
        vs_last = None
        if last_paid and best is not None and basis == "base_unit":
            vs_last = round((best - last_paid) / last_paid * 100.0, 1)

        # Économie possible : écart entre la pire et la meilleure offre, sur la
        # quantité demandée. C'est ce que coûte le mauvais choix.
        qty = next((r["qty"] for r in priced if r["qty"]), None)
        if best is not None and worst is not None and qty and worst > best:
            span = (worst - best) * qty
            potential_savings += span

        products.append(
            {
                "product_id": pid,
                "product_name": product_names.get(pid)
                or next((o.get("description") for o in raws if o.get("description")), None),
                "basis": basis,
                "mixed_packaging": basis == "unit_price" and len(rows) > 1,
                "offers": rows,
                "best_supplier_id": priced[0]["supplier_id"] if priced else None,
                "best_price": best,
                "history": {
                    "last_paid": last_paid,
                    "avg_paid": _f(hist.get("avg_paid")),
                    "best_paid": _f(hist.get("best_paid")),
                },
                "vs_last_paid_pct": vs_last,
            }
        )

        for r in rows:
            sid = r["supplier_id"]
            if not sid:
                continue
            agg = supplier_totals.setdefault(
                sid,
                {
                    "supplier_id": sid,
                    "supplier_name": r["supplier_name"],
                    "covered": 0,
                    "best_count": 0,
                    "total": 0.0,
                    "delivery_fee": None,
                    "total_with_delivery": 0.0,
                    "max_lead_time_days": None,
                    "preferred": False,
                },
            )
            if r["expired"] or not r["available"]:
                continue
            agg["covered"] += 1
            if r["rank"] == "best":
                agg["best_count"] += 1
            if r["unit_price"] is not None and r["qty"]:
                agg["total"] += r["unit_price"] * r["qty"]
            if r["delivery_fee"] is not None:
                # Les frais de port s'appliquent à la commande entière : on
                # retient ceux du devis, pas une somme par ligne.
                agg["delivery_fee"] = max(agg["delivery_fee"] or 0.0, r["delivery_fee"])
            if r["lead_time_days"] is not None:
                agg["max_lead_time_days"] = max(
                    agg["max_lead_time_days"] or 0, r["lead_time_days"]
                )
            agg["preferred"] = agg["preferred"] or r["preferred"]

    products.sort(key=lambda p: (p["product_name"] or "").lower())
    suppliers = list(supplier_totals.values())
    for s in suppliers:
        s["total"] = round(s["total"], 2)
        # Le « moins cher » se juge sur ce qu'on paie réellement : panier + port.
        s["total_with_delivery"] = round(s["total"] + (s["delivery_fee"] or 0.0), 2)
    suppliers.sort(key=lambda s: (-s["best_count"], s["total_with_delivery"]))

    priceable = len(products)
    full = [s for s in suppliers if s["covered"] == priceable and priceable > 0]
    cheapest = min(full, key=lambda s: s["total_with_delivery"], default=None) or (
        min(suppliers, key=lambda s: s["total_with_delivery"], default=None)
    )
    with_lead = [s for s in suppliers if s["max_lead_time_days"] is not None]
    fastest = min(with_lead, key=lambda s: s["max_lead_time_days"], default=None)

    return {
        "products": products,
        "suppliers": suppliers,
        "product_count": priceable,
        "cheapest_supplier_id": cheapest["supplier_id"] if cheapest else None,
        "fastest_supplier_id": fastest["supplier_id"] if fastest else None,
        "potential_savings": round(potential_savings, 2),
    }


# --------------------------------------------------------------------------- #
# Wrapper BDD
# --------------------------------------------------------------------------- #
def _product_history(db, tenant_id: str, product_id: str) -> Dict[str, Any]:
    """Dernier / moyen / meilleur prix RÉELLEMENT payé (toutes sources), en coût
    standardisé. Vient des factures — jamais des devis (une offre n'est pas un
    achat)."""
    from app.crud import crud_purchase

    costs = []
    last = None
    for p in crud_purchase.product_purchases(db, tenant_id, product_id):  # ancien -> récent
        c = _f(p.unit_cost_standard)
        if c is not None:
            costs.append(c)
            last = c
    if not costs:
        return {}
    return {
        "last_paid": last,
        "avg_paid": round(sum(costs) / len(costs), 4),
        "best_paid": min(costs),
    }


def build_for_tenant(db, tenant_id: str, statuses=("draft",)) -> Dict[str, Any]:
    """Le tableau comparatif de tous les devis d'un statut donné.

    Rassemble les offres (lignes de devis), l'historique d'achat par produit et
    le catalogue fournisseur (dispo / délai / préféré), puis délègue au moteur
    pur :func:`build_matrix`.
    """
    from datetime import date as _date

    from app.crud import crud_supplier_product
    from app.models.models import Product, Quote, QuoteLine, Supplier

    quotes = (
        db.query(Quote)
        .filter(Quote.tenant_id == tenant_id, Quote.status.in_(list(statuses)))
        .all()
    )
    if not quotes:
        return build_matrix([])
    by_id = {str(q.id): q for q in quotes}

    lines = (
        db.query(QuoteLine)
        .filter(
            QuoteLine.tenant_id == tenant_id,
            QuoteLine.quote_id.in_(list(by_id.keys())),
            QuoteLine.product_id.isnot(None),
        )
        .all()
    )

    offers = []
    for l in lines:
        q = by_id.get(str(l.quote_id))
        # Le fournisseur de la ligne, sinon celui du devis.
        sid = l.supplier_id or (q.supplier_id if q else None)
        offers.append(
            {
                "product_id": str(l.product_id),
                "supplier_id": str(sid) if sid else None,
                "quote_id": str(l.quote_id),
                "quote_line_id": str(l.id),
                "quote_reference": q.reference if q else None,
                "description": l.description,
                "unit_price": _f(l.unit_price),
                "qty": _f(l.qty),
                "unit": None,
                "vat_rate": _f(l.vat_rate),
                "discount_pct": _f(l.discount_pct),
                "pack_size": l.pack_size,
                "brand": l.brand,
                "min_qty": _f(l.min_qty),
                "delivery_fee": _f(q.delivery_fee) if q else None,
                "valid_until": q.valid_until if q else None,
            }
        )

    pids = {o["product_id"] for o in offers}
    history = {pid: _product_history(db, tenant_id, pid) for pid in pids}
    catalog = {
        pid: {
            str(link.supplier_id): {
                "available": bool(link.available) if link.available is not None else True,
                "preferred": bool(link.preferred) if link.preferred else False,
                "lead_time_days": link.lead_time_days,
            }
            for link in crud_supplier_product.list_links(db, tenant_id, pid)
        }
        for pid in pids
    }
    product_names = {
        str(p.id): p.name
        for p in db.query(Product.id, Product.name)
        .filter(Product.tenant_id == tenant_id, Product.id.in_(list(pids) or ["-"]))
        .all()
    }
    supplier_names = {
        str(s.id): s.name
        for s in db.query(Supplier.id, Supplier.name)
        .filter(Supplier.tenant_id == tenant_id)
        .all()
    }

    return build_matrix(
        offers,
        history=history,
        catalog=catalog,
        supplier_names=supplier_names,
        product_names=product_names,
        today=_date.today(),
    )
