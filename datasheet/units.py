"""Best-effort SI-ish unit normalization (Pass 2).

Converts value_normalized into a common unit (unit_si + value_si) for the unit families
that appear in process datasheets. Returns (None, None) for unknown units or missing
values - we never fabricate a conversion.

Gauge vs absolute pressure is preserved (e.g. 'kg/cm2 g' -> 'bar g', 'psia' -> 'bar a'):
these are semantically distinct and must not be silently merged.
"""

from __future__ import annotations

from typing import Optional


def _pressure_suffix(u: str) -> str:
    if u.endswith("g") or u.endswith("g)") or " g" in u:
        return " g"
    if u.endswith("a") or u.endswith("a)") or " a" in u:
        return " a"
    return ""


def to_si(value: Optional[float], unit: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """Return (value_si, unit_si) or (None, None) if not convertible."""
    if value is None or unit is None:
        return (None, None)
    u = unit.strip().lower()

    # flow
    if u in ("m3/h", "m³/h"):
        return (value, "m3/h")
    if u == "gpm":  # US gallons per minute
        return (round(value * 0.227124, 4), "m3/h")

    # pressure (preserve gauge/absolute)
    if "kg/cm2" in u or "kg/cm²" in u:
        return (round(value * 0.980665, 4), f"bar{_pressure_suffix(u)}")
    if u.startswith("psi"):
        suffix = " g" if u == "psig" else (" a" if u == "psia" else "")
        return (round(value * 0.0689476, 4), f"bar{suffix}")
    if u.startswith("bar"):
        return (value, "bar" + _pressure_suffix(u))

    # head / length
    if u in ("m", "m. liq.", "m.liq.", "m liq", "m liq.", "m. liq", "m.c.l.", "mcl"):
        return (value, "m")
    if u == "ft":
        return (round(value * 0.3048, 4), "m")
    if u == "mm":
        return (round(value / 1000.0, 4), "m")

    # power
    if u == "kw":
        return (value, "kW")
    if u == "hp":
        return (round(value * 0.745699, 4), "kW")

    # density
    if u in ("kg/m3", "kg/m³"):
        return (value, "kg/m3")
    if u in ("lb/ft3", "lb/ft³"):
        return (round(value * 16.0185, 4), "kg/m3")

    # temperature
    if u in ("degc", "°c", "c"):
        return (value, "degC")
    if u in ("degf", "°f", "f"):
        return (round((value - 32) * 5.0 / 9.0, 4), "degC")

    return (None, None)
