"""Unit conversion service (Decimal-based).

Linear conversions within a category use ``ratio_to_base`` (every unit stores its
factor to the category base, e.g. mass base = kg, volume base = L, count base =
pièce). Cross-category conversions (e.g. volume↔mass, which need a density) are
only possible when an explicit pair exists in ``unit_conversions``.

The service accepts any unit-like object exposing ``code``, ``category`` and
``ratio_to_base`` (the SQLAlchemy ``Unit`` model qualifies), so it is trivially
unit-testable with lightweight stubs.
"""
from decimal import Decimal
from typing import Iterable, Optional, Dict, Any


class UnitConversionError(Exception):
    pass


def _dec(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class UnitConversionService:
    def __init__(self, units: Iterable[Any], conversions: Optional[Iterable[dict]] = None):
        self._by_code: Dict[str, Any] = {}
        self._by_id: Dict[int, Any] = {}
        for u in units:
            self._by_code[str(u.code).lower()] = u
            uid = getattr(u, "id", None)
            if uid is not None:
                self._by_id[uid] = u
        # explicit cross-category factors: {(from_code, to_code): factor}
        self._pairs: Dict[tuple, Decimal] = {}
        for c in conversions or []:
            self._pairs[(str(c["from"]).lower(), str(c["to"]).lower())] = _dec(c["factor"])

    @classmethod
    def from_db(cls, db) -> "UnitConversionService":
        from app.models.models import Unit, UnitConversion

        units = db.query(Unit).all()
        id_to_code = {u.id: u.code for u in units}
        conversions = []
        for c in db.query(UnitConversion).all():
            f, t = id_to_code.get(c.from_unit_id), id_to_code.get(c.to_unit_id)
            if f and t:
                conversions.append({"from": f, "to": t, "factor": c.factor})
        return cls(units, conversions)

    def ratio_map(self) -> Dict[int, Decimal]:
        """unit_id -> ratio_to_base (Decimal), consumed by the cost engine."""
        return {u.id: _dec(u.ratio_to_base) for u in self._by_id.values()}

    def _resolve(self, unit):
        if isinstance(unit, int):
            u = self._by_id.get(unit)
        else:
            u = self._by_code.get(str(unit).lower())
        if u is None:
            raise UnitConversionError(f"unknown unit: {unit!r}")
        return u

    def convert(self, quantity, from_unit, to_unit) -> Decimal:
        """Convert ``quantity`` from ``from_unit`` to ``to_unit`` (codes or ids)."""
        q = _dec(quantity)
        if str(from_unit).lower() == str(to_unit).lower():
            return q
        fu, tu = self._resolve(from_unit), self._resolve(to_unit)
        if fu.category == tu.category:
            return q * (_dec(fu.ratio_to_base) / _dec(tu.ratio_to_base))
        key = (str(fu.code).lower(), str(tu.code).lower())
        if key in self._pairs:
            return q * self._pairs[key]
        raise UnitConversionError(
            f"no conversion from {fu.code} to {tu.code} (categories {fu.category} != {tu.category})"
        )
