"""Quote comparator (#1) — price a basket of products across suppliers.

The heart of the feature is :func:`compare_basket`, a **pure** function (no DB):
given the basket, the last standardized cost per (product, supplier) and the
supplier catalog attributes, it returns one row per supplier with the basket
total, coverage, lead time and the cheapest / best-coverage flags. It is
unit-tested in isolation. :func:`comparison` and :func:`order_totals` wrap it
with the DB reads, reusing ``purchase_service.aggregate_supplier_prices`` (the
same price source as the product "Fournisseurs" tab) for consistency.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import Unit, Product, Supplier
from app.crud import crud_purchase, crud_supplier_product
from app.services.purchasing.purchase_service import aggregate_supplier_prices


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# pure comparison core (unit-tested, no DB)
# --------------------------------------------------------------------------- #
def compare_basket(
    lines: List[Dict[str, Any]],
    prices_by_product: Dict[str, Dict[str, float]],
    catalog_by_product: Dict[str, Dict[str, Dict[str, Any]]],
    supplier_names: Dict[str, str],
) -> Dict[str, Any]:
    """Compare a basket across suppliers. Pure — all inputs are plain data.

    - ``lines``: basket rows, each ``{product_id, product_name, qty, unit_ratio}``.
      ``unit_ratio`` converts the line qty to the product's base unit (the unit the
      standardized cost is expressed in); defaults to 1.0.
    - ``prices_by_product``: ``{product_id: {supplier_id: last_cost_per_base_unit}}``.
    - ``catalog_by_product``: ``{product_id: {supplier_id: {available, preferred,
      lead_time_days}}}``.
    - ``supplier_names``: ``{supplier_id: name}``.

    Returns per-supplier totals + coverage, ranked (full coverage first, then
    cheapest), with the cheapest and best-coverage suppliers flagged.
    """
    priceable = [l for l in lines if l.get("product_id")]
    priceable_count = len(priceable)

    supplier_ids: set = set()
    for l in priceable:
        supplier_ids |= set(prices_by_product.get(l["product_id"], {}).keys())
    supplier_ids.discard("None")
    supplier_ids.discard(None)

    rows: List[Dict[str, Any]] = []
    for sid in supplier_ids:
        covered = 0
        total = 0.0
        missing: List[Dict[str, Any]] = []
        lead_times: List[int] = []
        preferred_count = 0
        line_rows: List[Dict[str, Any]] = []
        for l in priceable:
            pid = l["product_id"]
            qty = _f(l.get("qty"))
            ratio = _f(l.get("unit_ratio")) or 1.0
            std_qty = qty * ratio if qty is not None else None
            cost = prices_by_product.get(pid, {}).get(sid)
            cat = catalog_by_product.get(pid, {}).get(sid) or {}
            available = cat.get("available", True)
            if cat.get("lead_time_days") is not None:
                lead_times.append(cat["lead_time_days"])
            if cat.get("preferred"):
                preferred_count += 1
            line_cost = None
            if cost is not None:
                covered += 1
                if std_qty is not None:
                    line_cost = round(cost * std_qty, 4)
                    total += line_cost
            else:
                missing.append(
                    {"product_id": pid, "product_name": l.get("product_name")}
                )
            line_rows.append(
                {
                    "product_id": pid,
                    "product_name": l.get("product_name"),
                    "qty": qty,
                    "unit_cost": cost,
                    "line_cost": line_cost,
                    "available": bool(available),
                }
            )
        rows.append(
            {
                "supplier_id": sid,
                "supplier_name": supplier_names.get(sid),
                "covered_count": covered,
                "priceable_count": priceable_count,
                "missing": missing,
                "total": round(total, 2),
                "max_lead_time_days": max(lead_times) if lead_times else None,
                "preferred": preferred_count > 0,
                "is_full_coverage": covered == priceable_count and priceable_count > 0,
                "lines": line_rows,
            }
        )

    # Full coverage first, then lowest total.
    rows.sort(key=lambda r: (not r["is_full_coverage"], r["total"]))
    full = [r for r in rows if r["is_full_coverage"]]
    cheapest_id = (
        full[0]["supplier_id"]
        if full
        else (rows[0]["supplier_id"] if rows else None)
    )
    best_cov_id = None
    if rows:
        best = max(rows, key=lambda r: (r["covered_count"], -r["total"]))
        best_cov_id = best["supplier_id"]
    for r in rows:
        r["is_cheapest"] = r["supplier_id"] == cheapest_id
        r["is_best_coverage"] = r["supplier_id"] == best_cov_id

    return {
        "line_count": len(lines),
        "priceable_count": priceable_count,
        "suppliers": rows,
        "cheapest_supplier_id": cheapest_id,
        "best_coverage_supplier_id": best_cov_id,
    }


# --------------------------------------------------------------------------- #
# DB wrappers
# --------------------------------------------------------------------------- #
def _unit_ratios(db: Session) -> Dict[int, float]:
    return {u.id: (float(u.ratio_to_base or 1) or 1.0) for u in db.query(Unit).all()}


def _basket_inputs(db: Session, tenant_id: str, lines) -> Dict[str, Any]:
    """Resolve the per-product price + catalog maps and the basket rows the pure
    comparator needs, from a quote's ORM lines."""
    ratios = _unit_ratios(db)
    product_ids = [str(l.product_id) for l in lines if l.product_id]
    names = {
        str(p.id): p.name
        for p in db.query(Product.id, Product.name)
        .filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids or ["-"]))
        .all()
    }
    supplier_names = {
        str(s.id): s.name
        for s in db.query(Supplier.id, Supplier.name)
        .filter(Supplier.tenant_id == tenant_id)
        .all()
    }

    prices_by_product: Dict[str, Dict[str, float]] = {}
    catalog_by_product: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for pid in set(product_ids):
        agg = aggregate_supplier_prices(
            crud_purchase.product_purchases(db, tenant_id, pid)
        )
        prices_by_product[pid] = {
            sid: e["last_cost"]
            for sid, e in agg.items()
            if sid != "None" and e.get("last_cost") is not None
        }
        catalog_by_product[pid] = {
            str(link.supplier_id): {
                "available": bool(link.available) if link.available is not None else True,
                "preferred": bool(link.preferred) if link.preferred else False,
                "lead_time_days": link.lead_time_days,
            }
            for link in crud_supplier_product.list_links(db, tenant_id, pid)
        }

    basket = [
        {
            "product_id": str(l.product_id) if l.product_id else None,
            "product_name": names.get(str(l.product_id)) if l.product_id else l.description,
            "qty": _f(l.qty),
            "unit_ratio": ratios.get(l.unit_id, 1.0) if l.unit_id else 1.0,
        }
        for l in lines
    ]
    return {
        "basket": basket,
        "prices_by_product": prices_by_product,
        "catalog_by_product": catalog_by_product,
        "supplier_names": supplier_names,
    }


def comparison(db: Session, tenant_id: str, quote, lines) -> Dict[str, Any]:
    """Full per-supplier comparison of a quote's basket."""
    ins = _basket_inputs(db, tenant_id, lines)
    result = compare_basket(
        ins["basket"],
        ins["prices_by_product"],
        ins["catalog_by_product"],
        ins["supplier_names"],
    )
    result["quote_id"] = str(quote.id)
    return result


def supplier_totals(db: Session, tenant_id: str, lines, supplier_id: str) -> Dict[str, Any]:
    """The single supplier's row from the comparison (used to snapshot an order):
    per-line unit cost + total for ``supplier_id``. Returns ``{total, lines}``
    where each line carries ``product_id`` and ``unit_cost``."""
    ins = _basket_inputs(db, tenant_id, lines)
    result = compare_basket(
        ins["basket"],
        ins["prices_by_product"],
        ins["catalog_by_product"],
        ins["supplier_names"],
    )
    for row in result["suppliers"]:
        if row["supplier_id"] == supplier_id:
            return {"total": row["total"], "lines": row["lines"]}
    return {"total": 0.0, "lines": []}
