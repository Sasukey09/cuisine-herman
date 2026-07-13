"""What the assistant should already know before the chef says a word.

Until now the assistant started every conversation blind: to learn that butter
had jumped 18% it had to guess that a tool call might be worth making. So the
chef had to already know the problem in order to ask about it — which defeats
the point of having an analyst.

This builds a compact briefing of what is actually happening in *this*
restaurant right now, and pins it to the system prompt. It is deliberately small
(a few hundred tokens): it costs one extra paragraph per call, not a tool round
trip, and it means "Que dois-je regarder aujourd'hui ?" has a real answer.
"""
from typing import Any, Dict, List

from sqlalchemy.orm import Session

_MAX_ITEMS = 5


def _fmt_pct(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "?"
    return f"{'+' if v > 0 else ''}{v:.1f} %"


def _fmt_eur(value) -> str:
    try:
        return f"{float(value):.2f} €"
    except (TypeError, ValueError):
        return "?"


def build_situation(db: Session, tenant_id: str) -> Dict[str, Any]:
    """Read the tenant's current pain points. Never raises: a briefing that
    fails must not take the assistant down with it."""
    from app.services.dashboard import dashboard_service
    from app.services.purchasing import purchase_service

    situation: Dict[str, Any] = {
        "increases": [],
        "decreases": [],
        "savings": [],
        "margin_alerts": [],
    }

    try:
        board = purchase_service.price_dashboard(db, tenant_id)
        situation["increases"] = (board.get("most_increased") or [])[:_MAX_ITEMS]
        situation["decreases"] = (board.get("most_decreased") or [])[:_MAX_ITEMS]
        situation["savings"] = (board.get("savings_opportunities") or [])[:_MAX_ITEMS]
    except Exception:
        pass

    try:
        situation["margin_alerts"] = (dashboard_service.margin_alerts(db, tenant_id) or [])[:_MAX_ITEMS]
    except Exception:
        pass

    return situation


def render_briefing(situation: Dict[str, Any]) -> str:
    """Turn the situation into the paragraph appended to the system prompt."""
    lines: List[str] = []

    increases = situation.get("increases") or []
    if increases:
        items = ", ".join(
            f"{i.get('product_name') or 'Produit'} ({_fmt_pct(i.get('change_pct'))}, "
            f"{_fmt_eur(i.get('old_cost'))} → {_fmt_eur(i.get('new_cost'))})"
            for i in increases
        )
        lines.append(f"Hausses de prix récentes : {items}.")

    savings = situation.get("savings") or []
    if savings:
        items = ", ".join(
            f"{s.get('product_name') or 'Produit'} moins cher chez "
            f"{s.get('cheapest_supplier') or 'un autre fournisseur'} "
            f"({_fmt_eur(s.get('cheapest_cost'))}/{s.get('unit_code') or 'u'})"
            for s in savings
        )
        lines.append(f"Économies possibles en changeant de fournisseur : {items}.")

    alerts = situation.get("margin_alerts") or []
    if alerts:
        items = ", ".join(
            f"{a.get('recipe_name') or 'Recette'} (coût matière {a.get('food_cost_pct')} %)"
            for a in alerts
        )
        lines.append(f"Recettes dont la marge se dégrade : {items}.")

    if not lines:
        return (
            "\n\nSITUATION ACTUELLE DU RESTAURANT : aucune hausse de prix, aucune alerte de "
            "marge et aucune économie fournisseur détectée pour l'instant. Si l'utilisateur "
            "demande ce qu'il doit surveiller, dis-le franchement plutôt que d'inventer, et "
            "explique qu'il faut importer plusieurs factures contenant les mêmes produits "
            "pour que des variations apparaissent."
        )

    return (
        "\n\nSITUATION ACTUELLE DU RESTAURANT (données réelles, déjà chargées — "
        "inutile d'appeler un outil pour les retrouver) :\n- "
        + "\n- ".join(lines)
        + "\n\nAppuie-toi dessus quand c'est pertinent, et termine par une ACTION CONCRÈTE "
        "(quel produit renégocier, quel fournisseur changer, quel prix de vente ajuster et "
        "de combien). Ne répète pas ces chiffres si l'utilisateur parle d'autre chose."
    )


def suggestions(situation: Dict[str, Any]) -> List[str]:
    """Questions worth asking *for this restaurant*, not generic filler.

    The chat used to offer the same three canned prompts to everyone, whether or
    not they meant anything for that tenant's data.
    """
    out: List[str] = []

    for item in (situation.get("increases") or [])[:2]:
        name = item.get("product_name")
        if name:
            out.append(
                f"{name} a augmenté de {_fmt_pct(item.get('change_pct'))} : "
                f"quelles recettes sont touchées et de combien ?"
            )

    for item in (situation.get("savings") or [])[:1]:
        name = item.get("product_name")
        supplier = item.get("cheapest_supplier")
        if name and supplier:
            out.append(f"Combien j'économiserais par mois en achetant {name} chez {supplier} ?")

    for item in (situation.get("margin_alerts") or [])[:1]:
        name = item.get("recipe_name")
        if name:
            out.append(f"Comment redresser la marge de « {name} » sans changer la recette ?")

    if not out:
        out = [
            "Quelles sont mes recettes les moins rentables ?",
            "Quels produits ont le plus augmenté ce mois-ci ?",
            "Où puis-je économiser en changeant de fournisseur ?",
        ]

    return out[:4]
