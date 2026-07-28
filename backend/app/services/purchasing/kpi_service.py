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
