"""Lire le conditionnement d'un libellé produit, pour comparer à unité égale.

Deux offres ne se comparent qu'au même dénominateur : un **sac de 25 kg à
18,50 €** et une **plaquette de 500 g à 4,20 €** n'ont de sens côte à côte
qu'une fois ramenés au **prix au kilo** (0,74 €/kg contre 8,40 €/kg). Sans ça,
le « moins cher » du comparateur est faux.

Ce module lit ce que le fournisseur écrit — « sac 25kg », « bidon 5L »,
« plaquette 500g », « carton de 6x1L » — et rend une quantité dans l'unité de
base (kg / L / piece).

Tout est **pur** (texte -> valeurs) : testé sans BDD ni réseau.
"""
import re
from typing import Optional, Tuple

# Facteur vers l'unité de base, par unité écrite.
_TO_BASE = {
    # masse -> kg
    "kg": ("kg", 1.0),
    "kilo": ("kg", 1.0),
    "kilos": ("kg", 1.0),
    "kilogramme": ("kg", 1.0),
    "kilogrammes": ("kg", 1.0),
    "g": ("kg", 0.001),
    "gr": ("kg", 0.001),
    "gramme": ("kg", 0.001),
    "grammes": ("kg", 0.001),
    "mg": ("kg", 0.000001),
    # volume -> L
    "l": ("L", 1.0),
    "litre": ("L", 1.0),
    "litres": ("L", 1.0),
    "dl": ("L", 0.1),
    "cl": ("L", 0.01),
    "ml": ("L", 0.001),
}

_UNIT_ALT = "|".join(sorted(_TO_BASE, key=len, reverse=True))
_NUM = r"\d+(?:[.,]\d+)?"

# « 6x1L », « 6 x 1 L », « carton de 6 x 75cl » -> multipack
_MULTI_RE = re.compile(
    rf"(?<![\d,.])(?P<count>\d+)\s*[x×]\s*(?P<qty>{_NUM})\s*(?P<unit>{_UNIT_ALT})\b",
    re.IGNORECASE,
)
# « 25kg », « 500 g », « 1,5 L »
_SIMPLE_RE = re.compile(
    rf"(?<![\d,.])(?P<qty>{_NUM})\s*(?P<unit>{_UNIT_ALT})\b", re.IGNORECASE
)


def _to_float(raw: str) -> Optional[float]:
    try:
        return float(raw.replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_pack(text: Optional[str]) -> Optional[Tuple[float, str]]:
    """(quantité, unité de base) contenue dans un conditionnement.

    « sac 25kg » -> (25.0, 'kg') · « plaquette 500g » -> (0.5, 'kg')
    « bidon 5L » -> (5.0, 'L')   · « carton de 6x1L » -> (6.0, 'L')

    Rend ``None`` quand le libellé ne dit rien d'exploitable (« carton de 6 » :
    6 de quoi ? — on préfère ne rien affirmer plutôt que comparer à tort).
    """
    if not text:
        return None
    t = str(text)

    # Le multipack d'abord : « 6x1L » doit valoir 6 L, pas 1 L.
    m = _MULTI_RE.search(t)
    if m:
        count = _to_float(m.group("count"))
        qty = _to_float(m.group("qty"))
        base = _TO_BASE.get(m.group("unit").lower())
        if count and qty is not None and base:
            unit, factor = base
            return round(count * qty * factor, 6), unit

    m = _SIMPLE_RE.search(t)
    if m:
        qty = _to_float(m.group("qty"))
        base = _TO_BASE.get(m.group("unit").lower())
        if qty is not None and base:
            unit, factor = base
            return round(qty * factor, 6), unit

    return None


def price_per_base_unit(
    unit_price: Optional[float],
    pack_size: Optional[str] = None,
    description: Optional[str] = None,
    discount_pct: Optional[float] = None,
) -> Optional[Tuple[float, str]]:
    """Prix ramené à l'unité de base (€/kg, €/L), remise déduite.

    Le conditionnement est cherché d'abord dans ``pack_size`` (le champ dédié),
    puis dans ``description`` — les fournisseurs l'écrivent souvent dans le
    libellé (« Farine T55 sac 25kg »).

    Rend ``None`` si le conditionnement est illisible : mieux vaut ne pas
    afficher de prix au kilo que d'en afficher un faux.
    """
    if unit_price is None:
        return None
    pack = parse_pack(pack_size) or parse_pack(description)
    if pack is None:
        return None
    qty, unit = pack
    if not qty or qty <= 0:
        return None
    net = float(unit_price)
    if discount_pct:
        net = net * (1 - float(discount_pct) / 100.0)
    return round(net / qty, 6), unit
