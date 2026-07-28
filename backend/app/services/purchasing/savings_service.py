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

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.crud import crud_supplier_product
from app.models.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    QuoteLine,
)
from app.services.purchasing import order_service
from app.services.quotes.pack_parser import price_per_base_unit

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


def _comparable(chosen, competitors):
    """Ramène choisie + concurrentes à une base comparable, ou ``None`` si on ne
    peut pas comparer honnêtement.

    Le comparateur maison (``quote_matrix``) classe les offres au **prix à
    l'unité de base** (``pack_parser.price_per_base_unit``), pas au prix unitaire
    brut : METRO 10 €/5 kg (2,00 €/kg) est plus cher que TRANSGOURMET 14 €/10 kg
    (1,40 €/kg). Comparer le brut inverserait le classement. On aligne donc le
    moteur d'économies sur la même base :

    - si TOUTES les offres se normalisent au prix/unité de base ET partagent la
      même unité de base → on compare sur le prix/unité de base ;
    - si AUCUNE ne se normalise (aucun conditionnement lisible) → on compare le
      prix unitaire brut (offres implicitement de même unité) ;
    - sinon (mixte : certaines normalisent, d'autres non, ou unités de base
      différentes) → ``None`` : on ne compare pas ce qui n'est pas comparable.

    Chaque offre est un dict ``{unit_price, pack_size, description,
    discount_pct}``. Retourne ``(chosen_value, [competing_values])`` ou ``None``.
    """
    offers = [chosen] + list(competitors)
    ppus = [
        price_per_base_unit(
            _f(o.get("unit_price")),
            pack_size=o.get("pack_size"),
            description=o.get("description"),
            discount_pct=_f(o.get("discount_pct")),
        )
        for o in offers
    ]
    have = [p for p in ppus if p]
    if len(have) == len(offers):
        bases = {p[1] for p in have}
        if len(bases) == 1:
            values = [p[0] for p in ppus]
            return values[0], values[1:]
        return None  # unités de base différentes → non comparable
    if not have:
        # aucun conditionnement lisible → prix unitaire brut, même unité implicite
        return _f(chosen.get("unit_price")), [_f(c.get("unit_price")) for c in competitors]
    return None  # conditionnements mixtes → non comparable


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
    # On ne filtre PAS `Quote.status` à dessein : une offre qui était sur la table et
    # valide au moment de commander compte, même si le devis a depuis été
    # archivé/commandé — la validité se juge à `quote.date`/`valid_until`, pas au statut.
    offers_by_product: Dict[str, List[Dict[str, Any]]] = {}
    for ql, quote in (
        db.query(QuoteLine, Quote)
        .join(Quote, Quote.id == QuoteLine.quote_id)
        .filter(
            QuoteLine.tenant_id == tenant_id,
            Quote.tenant_id == tenant_id,
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
                "pack_size": ql.pack_size,
                "description": ql.description,
                "discount_pct": _f(ql.discount_pct),
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

    def competing(pid: str, chosen_sid: Optional[str], order_d: date) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
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
            out.append(
                {
                    "unit_price": off["unit_price"],
                    "pack_size": off["pack_size"],
                    "description": off["description"],
                    "discount_pct": off["discount_pct"],
                }
            )
        return out

    inputs: List[Dict[str, Any]] = []
    for l in kept:
        pid = str(l.product_id)
        comp = competing(pid, osupplier.get(l.order_id), odate[l.order_id])
        if not comp:
            continue  # pas de concurrence → ligne ignorée
        chosen = {
            "unit_price": _f(l.unit_price),
            "pack_size": l.pack_size,
            "description": l.description,
            "discount_pct": _f(l.discount_pct),
        }
        pair = _comparable(chosen, comp)
        if pair is None:
            continue  # conditionnements non comparables → on n'invente pas
        chosen_value, competing_values = pair
        inputs.append(
            {
                "product_id": pid,
                "supplier_id": osupplier.get(l.order_id),
                "qty": _f(l.qty_ordered),
                "chosen_unit_price": chosen_value,
                "competing_prices": competing_values,
            }
        )
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


def for_product(db: Session, tenant_id: str, product_id: str, today: date) -> Dict[str, Any]:
    """Économies réalisées sur CE produit, 12 mois glissants (miroir de for_supplier)."""
    since = today - timedelta(days=365)
    res = _savings_for_order_lines(db, tenant_id, product_id=str(product_id), since=since, today=today)
    return {
        "realized": res["realized"], "missed": res["missed"], "possible": res["possible"],
        "best_choice_rate": res["best_choice_rate"], "compared_lines": res["compared_lines"],
        "labels": SAVINGS_LABELS,
    }


def for_tenant(db: Session, tenant_id: str, today: date) -> Dict[str, Any]:
    """Économies réalisées sur TOUT le tenant, 12 mois glissants. Renvoie en plus
    le détail par ligne (``lines``) — nécessaire pour agréger par fournisseur dans
    le pilotage — là où ``for_supplier`` le laisse tomber."""
    since = today - timedelta(days=365)
    res = _savings_for_order_lines(db, tenant_id, since=since, today=today)
    return {
        "realized": res["realized"], "missed": res["missed"], "possible": res["possible"],
        "best_choice_rate": res["best_choice_rate"], "compared_lines": res["compared_lines"],
        "labels": SAVINGS_LABELS, "lines": res["lines"],
    }
