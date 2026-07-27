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
