"""Historique des OFFRES reçues pour un produit (§10).

À ne pas confondre avec ``purchase_service.product_price_history``, qui retrace
ce qui a été **payé**. Ici on retrace ce qui a été **proposé** : les prix des
devis reçus, y compris ceux qu'on n'a pas retenus.

Les deux histoires sont distinctes et complémentaires — et c'est justement
pourquoi les lignes de devis n'alimentent pas ``product_prices`` : un food cost
calculé sur un prix jamais payé serait faux. Mais pour négocier, savoir qu'un
fournisseur proposait 18,50 € il y a trois mois et 21,00 € aujourd'hui vaut
autant que l'historique d'achat.

La partie calcul (`build_history`) est **pure** : elle prend des lignes déjà
lues et rend le classement + les variations. Testable sans BDD.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Quote, QuoteLine, Supplier


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def _net_unit_price(unit_price: Optional[float], discount_pct: Optional[float]) -> Optional[float]:
    """Prix réellement offert : une remise de ligne fait partie de l'offre.

    Comparer un prix catalogue à un prix déjà remisé donnerait une fausse
    hausse."""
    if unit_price is None:
        return None
    if discount_pct:
        return round(unit_price * (1 - discount_pct / 100.0), 4)
    return round(unit_price, 4)


def build_history(offers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Trie les offres de la plus récente à la plus ancienne et calcule, pour
    chacune, l'écart avec l'offre précédente du MÊME fournisseur.

    Comparer à l'offre précédente toutes sources confondues n'aurait aucun sens :
    passer d'un grossiste à un autre n'est pas une hausse de prix, c'est une
    autre offre.
    """
    rows: List[Dict[str, Any]] = []
    for o in offers:
        price = _net_unit_price(_f(o.get("unit_price")), _f(o.get("discount_pct")))
        rows.append(
            {
                "quote_id": o.get("quote_id"),
                "quote_reference": o.get("quote_reference"),
                "quote_number": o.get("quote_number"),
                "status": o.get("status"),
                "date": o.get("date"),
                "valid_until": o.get("valid_until"),
                "supplier_id": o.get("supplier_id"),
                "supplier_name": o.get("supplier_name"),
                "unit_price": _f(o.get("unit_price")),
                "net_unit_price": price,
                "discount_pct": _f(o.get("discount_pct")),
                "vat_rate": _f(o.get("vat_rate")),
                "qty": _f(o.get("qty")),
                "pack_size": o.get("pack_size"),
                "brand": o.get("brand"),
                "min_qty": _f(o.get("min_qty")),
                "delta_pct_vs_previous": None,
                "is_best": False,
            }
        )

    # Une offre sans date est la plus incertaine : on la met en fin de liste
    # plutôt que de lui inventer une position dans la chronologie.
    rows.sort(key=lambda r: (r["date"] is not None, r["date"] or date.min), reverse=True)

    # Variation par fournisseur, du plus ancien au plus récent.
    by_supplier: Dict[Any, List[Dict[str, Any]]] = {}
    for r in rows:
        by_supplier.setdefault(r["supplier_id"], []).append(r)
    for series in by_supplier.values():
        chronological = list(reversed(series))
        for prev, cur in zip(chronological, chronological[1:]):
            if prev["net_unit_price"] and cur["net_unit_price"] is not None:
                cur["delta_pct_vs_previous"] = round(
                    (cur["net_unit_price"] - prev["net_unit_price"]) / prev["net_unit_price"] * 100,
                    2,
                )

    priced = [r for r in rows if r["net_unit_price"] is not None]
    best = min(priced, key=lambda r: r["net_unit_price"], default=None)
    if best is not None:
        best["is_best"] = True

    latest = priced[0] if priced else None
    return {
        "offers": rows,
        "count": len(rows),
        "supplier_count": len({r["supplier_id"] for r in rows if r["supplier_id"]}),
        "best_price": best["net_unit_price"] if best else None,
        "best_supplier_id": best["supplier_id"] if best else None,
        "best_supplier_name": best["supplier_name"] if best else None,
        "latest_price": latest["net_unit_price"] if latest else None,
        "avg_price": (
            round(sum(r["net_unit_price"] for r in priced) / len(priced), 4) if priced else None
        ),
    }


def product_quote_history(db: Session, tenant_id: str, product_id: str) -> Dict[str, Any]:
    """Toutes les offres reçues pour ce produit, tous devis confondus."""
    rows = (
        db.query(QuoteLine, Quote, Supplier)
        .join(Quote, QuoteLine.quote_id == Quote.id)
        .outerjoin(
            Supplier,
            # Le fournisseur est porté par la ligne quand le devis en mélange
            # plusieurs (comparatif), sinon par l'en-tête du devis importé.
            Supplier.id == func.coalesce(QuoteLine.supplier_id, Quote.supplier_id),
        )
        .filter(QuoteLine.tenant_id == tenant_id, QuoteLine.product_id == product_id)
        .all()
    )
    offers = [
        {
            "quote_id": line.quote_id,
            "quote_reference": quote.reference,
            "quote_number": quote.quote_number,
            "status": quote.status,
            "date": quote.date or (quote.created_at.date() if quote.created_at else None),
            "valid_until": quote.valid_until,
            "supplier_id": line.supplier_id or quote.supplier_id,
            "supplier_name": supplier.name if supplier else None,
            "unit_price": line.unit_price,
            "discount_pct": line.discount_pct,
            "vat_rate": line.vat_rate,
            "qty": line.qty,
            "pack_size": line.pack_size,
            "brand": line.brand,
            "min_qty": line.min_qty,
        }
        for line, quote, supplier in rows
    ]
    return build_history(offers)
