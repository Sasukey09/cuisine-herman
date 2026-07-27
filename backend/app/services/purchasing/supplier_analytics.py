"""Fiche fournisseur 360° : tout ce que le domaine Achats sait d'un fournisseur.

Un fournisseur n'est pas une ligne de carnet d'adresses : c'est un partenaire
qu'on juge sur des faits. Combien on lui achète, s'il livre à l'heure, s'il
livre conforme, si ses prix dérivent. Ces faits existent désormais — commandes,
réceptions, factures, historique d'achat — il ne restait qu'à les rassembler.

Le cœur (``scorecard``) est **pur** : des listes de dictionnaires en entrée, un
tableau de bord en sortie. Deux partis pris de rigueur, parce que la mission
préfère une donnée juste à une donnée flatteuse :

- **Le score n'est pas inventé.** Il ne se calcule que sur des faits réels
  (conformité des réceptions, ponctualité) et vaut ``None`` tant qu'aucune
  réception ne permet de juger. Un fournisseur sans historique n'a pas un
  « score de 0 » — il n'a pas encore de score.
- **On n'affiche pas un « montant économisé » ici.** Le chiffrer honnêtement
  demande les comparatifs de devis ; ce sera le travail de la Phase 7 (KPI
  Achats). Mieux vaut ne rien annoncer qu'un chiffre décoratif.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    Invoice,
    Product,
    PurchaseHistory,
    PurchaseOrder,
    Quote,
    Receipt,
    ReceiptLine,
    ReceiptLineIssue,
    Supplier,
)
from app.services.purchasing import order_service, savings_service


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


# --------------------------------------------------------------------------- #
# Pur : le tableau de bord
# --------------------------------------------------------------------------- #
def scorecard(
    orders: List[Dict[str, Any]],
    receipts: List[Dict[str, Any]],
    invoices: List[Dict[str, Any]],
    purchases: List[Dict[str, Any]],
    quote_count: int,
    today: date,
) -> Dict[str, Any]:
    """Agrège l'activité d'un fournisseur en indicateurs.

    - ``orders`` : ``{status, total_amount, ordered_at: date|None}``
    - ``receipts`` : ``{received_at: date|None, expected_date: date|None,
      issue_count: int}`` — ``expected_date`` est celle de la commande liée.
    - ``invoices`` : ``{total_amount, date: date|None}``
    - ``purchases`` : ``{purchase_date: date|None, total_price, product_id,
      product_name}`` (historique d'achat = ce qui a été payé)
    """
    year_ago = today - timedelta(days=365)

    # --- volumes ----------------------------------------------------------
    active_orders = [o for o in orders if o.get("status") != order_service.CANCELLED]
    ordered_total = sum(_f(o.get("total_amount")) or 0.0 for o in active_orders)
    billed_total = sum(_f(i.get("total_amount")) or 0.0 for i in invoices)

    # Montant annuel : 12 mois glissants, sur ce qui a été PAYÉ (l'historique
    # d'achat), pas sur ce qui a été commandé — c'est la dépense réelle.
    annual_amount = round(
        sum(
            _f(p.get("total_price")) or 0.0
            for p in purchases
            if p.get("purchase_date") and p["purchase_date"] >= year_ago
        ),
        2,
    )

    # --- évolution mensuelle (12 mois) ------------------------------------
    monthly: Dict[str, float] = {}
    for p in purchases:
        d = p.get("purchase_date")
        if d and d >= year_ago:
            key = f"{d.year:04d}-{d.month:02d}"
            monthly[key] = round(monthly.get(key, 0.0) + (_f(p.get("total_price")) or 0.0), 2)
    monthly_series = [{"month": k, "amount": v} for k, v in sorted(monthly.items())]

    # --- produits achetés -------------------------------------------------
    by_product: Dict[str, Dict[str, Any]] = {}
    for p in purchases:
        pid = p.get("product_id")
        if not pid:
            continue
        row = by_product.setdefault(
            pid, {"product_id": pid, "product_name": p.get("product_name"), "amount": 0.0, "count": 0}
        )
        row["amount"] = round(row["amount"] + (_f(p.get("total_price")) or 0.0), 2)
        row["count"] += 1
    top_products = sorted(by_product.values(), key=lambda r: -r["amount"])

    # --- conformité et ponctualité (les vrais juges) ----------------------
    checked = receipts  # une réception ici est déjà validée côté appelant
    receipt_count = len(checked)
    conform = sum(1 for r in checked if (r.get("issue_count") or 0) == 0)
    conformity_rate = round(conform / receipt_count, 3) if receipt_count else None

    # Retard : reçu après la date annoncée. Ne se juge que si les deux dates
    # existent — un fournisseur sans date promise n'est pas « en retard ».
    datable = [
        r for r in checked if r.get("received_at") and r.get("expected_date")
    ]
    late = [r for r in datable if r["received_at"] > r["expected_date"]]
    on_time_rate = (
        round((len(datable) - len(late)) / len(datable), 3) if datable else None
    )

    # --- score : seulement s'il y a de quoi juger -------------------------
    components = []
    if conformity_rate is not None:
        components.append(conformity_rate)
    if on_time_rate is not None:
        components.append(on_time_rate)
    score = round(100 * sum(components) / len(components)) if components else None

    # --- inflation subie : prix moyen payé, 6 premiers mois vs 6 derniers --
    price_trend_pct = _price_trend(purchases, today)

    return {
        "order_count": len(active_orders),
        "quote_count": quote_count,
        "invoice_count": len(invoices),
        "receipt_count": receipt_count,
        "ordered_total": round(ordered_total, 2),
        "billed_total": round(billed_total, 2),
        "annual_amount": annual_amount,
        "monthly": monthly_series,
        "top_products": top_products,
        "distinct_products": len(by_product),
        "conformity_rate": conformity_rate,
        "on_time_rate": on_time_rate,
        "late_count": len(late),
        "score": score,
        # Les composantes sont exposées : un score sans son détail n'aide pas à
        # décider s'il faut garder le fournisseur.
        "score_basis": {
            "conformity": conformity_rate,
            "punctuality": on_time_rate,
            "receipts_judged": receipt_count,
        },
        "price_trend_pct": price_trend_pct,
        "orders_by_status": _count_by_status(orders),
    }


def _count_by_status(orders: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for o in orders:
        s = o.get("status") or "draft"
        out[s] = out.get(s, 0) + 1
    return out


def _price_trend(purchases: List[Dict[str, Any]], today: date) -> Optional[float]:
    """Évolution du prix unitaire moyen payé chez ce fournisseur, sur un an.

    Compare la moyenne des 6 mois les plus anciens à celle des 6 plus récents.
    C'est l'inflation qu'on subit chez LUI — un signal de négociation, pas une
    fatalité de marché."""
    year_ago = today - timedelta(days=365)
    mid = today - timedelta(days=182)
    old_costs, new_costs = [], []
    for p in purchases:
        d = p.get("purchase_date")
        c = _f(p.get("unit_cost_standard"))
        if d is None or c is None or d < year_ago:
            continue
        (new_costs if d >= mid else old_costs).append(c)
    if not old_costs or not new_costs:
        return None
    old_avg = sum(old_costs) / len(old_costs)
    new_avg = sum(new_costs) / len(new_costs)
    if old_avg == 0:
        return None
    return round((new_avg - old_avg) / old_avg * 100, 1)


# --------------------------------------------------------------------------- #
# Enveloppes base de données
# --------------------------------------------------------------------------- #
def overview(db: Session, tenant_id: str, supplier: Supplier, today: date) -> Dict[str, Any]:
    """Le 360° d'un fournisseur, assemblé depuis toutes les tables du domaine."""
    sid = str(supplier.id)

    orders = [
        {"status": o.status, "total_amount": _f(o.total_amount), "ordered_at": o.ordered_at}
        for o in db.query(PurchaseOrder).filter(
            PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.supplier_id == sid
        )
    ]

    # Réceptions VALIDÉES uniquement : un brouillon n'engage pas le fournisseur.
    # Le nombre d'anomalies se lit sur les lignes filles (issues) + les lignes
    # livrées hors commande.
    issue_counts = dict(
        db.query(ReceiptLine.receipt_id, func.count(ReceiptLineIssue.id))
        .join(ReceiptLineIssue, ReceiptLineIssue.receipt_line_id == ReceiptLine.id)
        .filter(ReceiptLine.tenant_id == tenant_id)
        .group_by(ReceiptLine.receipt_id)
        .all()
    )
    expected_dates = dict(
        db.query(Receipt.id, PurchaseOrder.expected_date)
        .join(PurchaseOrder, PurchaseOrder.id == Receipt.order_id)
        .filter(Receipt.tenant_id == tenant_id, Receipt.supplier_id == sid)
        .all()
    )
    receipts = [
        {
            "received_at": r.received_at,
            "expected_date": expected_dates.get(r.id),
            "issue_count": int(issue_counts.get(r.id, 0)),
        }
        for r in db.query(Receipt).filter(
            Receipt.tenant_id == tenant_id,
            Receipt.supplier_id == sid,
            Receipt.status == "checked",
        )
    ]

    invoices = [
        {"total_amount": _f(i.total_amount), "date": i.date}
        for i in db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id, Invoice.supplier_id == sid
        )
    ]

    quote_count = (
        db.query(func.count(Quote.id))
        .filter(Quote.tenant_id == tenant_id, Quote.supplier_id == sid)
        .scalar()
        or 0
    )

    names = dict(db.query(Product.id, Product.name).filter(Product.tenant_id == tenant_id).all())
    purchases = [
        {
            "purchase_date": p.purchase_date,
            "total_price": _f(p.total_price),
            "unit_cost_standard": _f(p.unit_cost_standard),
            "product_id": str(p.product_id) if p.product_id else None,
            "product_name": names.get(p.product_id),
        }
        for p in db.query(PurchaseHistory).filter(
            PurchaseHistory.tenant_id == tenant_id, PurchaseHistory.supplier_id == sid
        )
    ]

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
