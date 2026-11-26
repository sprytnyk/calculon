"""Pint registry with Calculon's definitions, loaded on the first physical unit calculation."""

from pint import UnitRegistry

registry = UnitRegistry(autoconvert_offset_to_baseunit=True)
for prefix in ("", "kilo", "mega", "giga", "tera"):
    registry.define(f"{prefix}bit_per_second = {prefix}bit / second")
    registry.define(f"{prefix}byte_per_second = {prefix}byte / second")
registry.define("night = day")
# The average Gregorian year, as Soulver uses. Pint's own year is 365.25 days.
registry.define("year = 365.2425 * day = a = yr = julian_year")
# Pint's "decade" is a ratio (as in decades of frequency).
registry.define("decade_of_years = 10 * year")
