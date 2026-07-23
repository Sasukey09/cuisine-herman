"""Numérotation des documents d'achat : devis, commandes, réceptions.

Un seul endroit. La règle était déjà écrite deux fois dans ``crud_quote``
(``DEV-`` et ``CMD-``) ; avec les réceptions elle l'aurait été trois fois, et
trois copies d'une règle de numérotation, c'est trois occasions de diverger sur
le format ou sur la remise à zéro annuelle.

Format : ``PREFIXE-ANNEE-NNNN``, séquentiel **par organisation et par année**.
Deux restaurants ont chacun leur DEV-2026-0001 ; c'est voulu — un client ne doit
pas déduire le volume d'affaires d'un autre à partir de ses numéros.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

QUOTE = "DEV"
ORDER = "CMD"
RECEIPT = "REC"


def next_reference(
    db: Session,
    tenant_id: str,
    prefix: str,
    model: Any,
    column: Any = None,
    year: int | None = None,
) -> str:
    """Prochaine référence libre pour ce préfixe, cette organisation, cette année.

    Compte les documents déjà numérotés sur l'année plutôt que de tenir un
    compteur : pas de table de séquences à maintenir, et un document supprimé ne
    laisse pas un trou qui décalerait tout le reste.

    Le compte est fait sous le verrou de la transaction appelante ; deux
    créations simultanées dans la même organisation sont possibles en théorie —
    le doublon serait alors visible et corrigeable, ce qui vaut mieux qu'un
    numéro sauté silencieusement.
    """
    col = column if column is not None else model.reference
    y = year or datetime.now().year
    head = f"{prefix}-{y}-"
    count = (
        db.query(func.count(model.id))
        .filter(model.tenant_id == tenant_id, col.like(head + "%"))
        .scalar()
        or 0
    )
    return f"{head}{count + 1:04d}"
