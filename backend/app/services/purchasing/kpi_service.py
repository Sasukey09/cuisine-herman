"""Pilotage Achats : assemblage tenant-wide des moteurs Achats.

Ce module N'A PAS de logique métier neuve : le cœur pur ``assemble`` structure
et dérive (écarts, classements) des données déjà calculées par les moteurs
existants ; l'enveloppe ``purchasing_kpi`` (plus bas) rassemble ces données en
appelant ces moteurs. Doctrine : on assemble, on ne duplique pas.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    PurchaseOrder, Invoice, Receipt, ReceiptLine,
    ReceiptLineIssue, PurchaseHistory,
)
from app.services.purchasing import order_service, reception_service, savings_service
from app.services.purchasing import purchase_service
from app.services.quotes import quote_matrix
from app.services.dashboard import dashboard_service
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
    ordered_by_status = {s: round(float(t or 0), 2) for s, t in order_rows}
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
    suppliers = _supplier_rows(db, tenant_id, since, realized_by_supplier)

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


def _supplier_rows(db, tenant_id, since, realized_by_supplier):
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
    for r in db.query(Receipt).filter(
        Receipt.tenant_id == tenant_id, Receipt.status == "checked",
        Receipt.received_at >= since,
    ):
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
