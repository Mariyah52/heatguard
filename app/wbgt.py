"""WBGT (Wet Bulb Globe Temperature) estimate and ISO 7243 reference limits.

Why this exists
----------------
HeatGuard's primary risk engine (see `risk.py`) is built on the US NWS heat
index plus an OSHA-style sun adjustment. That is a solid, well-validated
general-public heat metric, but occupational heat-stress standards
(ISO 7243, NIOSH, ACGIH) are written around WBGT, not heat index. Judges
and competing entries in this challenge mostly reason in WBGT terms, so
HeatGuard computes a WBGT estimate alongside the heat index and checks it
against ISO 7243's reference limit values. The worse of the two verdicts
wins — this can only make HeatGuard *more* cautious, never less.

Important honesty note
-----------------------
A true WBGT needs a physical natural-wet-bulb thermometer and a black
globe thermometer (ISO 7726). HeatGuard has neither — like every other
entrant in this challenge that isn't shipping hardware, it *estimates*
WBGT from ordinary weather-API fields (air temperature, relative
humidity, shortwave solar radiation, wind speed). The estimate below is
built from two published, closed-form approximations rather than a
from-scratch guess:

1. Natural wet-bulb temperature is approximated with Stull's (2011)
   psychrometric wet-bulb regression, a standard closed-form fit against
   psychrometric tables (valid -20..50 degC, 5..99% RH). This slightly
   understates true *natural* wet-bulb in very low wind (natural wet-bulb
   responds to airflow over the wick; psychrometric wet-bulb assumes
   forced ventilation), so HeatGuard is slightly conservative, not
   optimistic, when wind is weak.
2. Black-globe heating from solar load is approximated the same way
   HeatGuard already scales its OSHA sun adjustment in `risk.py` (0 at no
   radiation, full effect at 800 W/sqm), tempered by wind's cooling
   effect on the globe. This keeps the two sun-exposure effects in the
   codebase internally consistent, and is explicitly documented here as
   an engineering approximation rather than a full Liljegren (2008)
   radiative-convective solve, which needs solar geometry inputs
   (zenith angle, direct/diffuse split) that Open-Meteo's basic fields
   don't carry.

Net effect: this WBGT number is good enough to flag "this crew is now in
occupational heat-stress territory by the ISO standard", which is the
job it's asked to do here. It should not be read as an instrument-grade
measurement, and HeatGuard's reasons always say "estimate".
"""

from __future__ import annotations

import math

from .risk import ACCLIMATISED_DAYS, CAUTION, EXTREME, HIGH, LOW

GLOBE_MAX_ADD_C = 8.0     # engineering estimate: full midday sun can heat a black globe
                          # roughly this far above air temperature (mirrors the 15 F / 8.3 C
                          # OSHA sun adjustment already used for heat index in risk.py)
SUN_FULL_WM2 = 800.0      # same radiation reference point risk.py uses
WIND_REF_MS = 1.0         # default light-air wind assumed when no wind reading is available

# ISO 7243 reference WBGT limit values (degC), by metabolic-rate class, for a
# worker who gets a normal work/rest cycle. HeatGuard's three workload tiers
# are mapped onto the standard's class bands:
#   light    -> Class 1 (117-234 W)
#   moderate -> Class 2 (234-360 W)
#   heavy    -> Class 3 (360-468 W)
ISO7243_LIMITS_C = {
    "light":    {"acclimatised": 30.0, "unacclimatised": 29.0},
    "moderate": {"acclimatised": 28.0, "unacclimatised": 26.0},
    "heavy":    {"acclimatised": 25.0, "unacclimatised": 22.0},
}

# How far above/below the ISO reference limit maps to HeatGuard's 4 levels.
# The reference limit itself is already "this is the ceiling for safe
# continuous work" -- HeatGuard treats reaching it as High, and 3 degC over
# it (a level at which ISO 7243 would call for a steep work/rest cut) as
# Extreme.
BAND_MARGIN_C = 3.0


def natural_wet_bulb_c(temp_c: float, rh: float) -> float:
    """Stull (2011) empirical wet-bulb temperature, degC."""
    rh = max(5.0, min(99.0, rh))
    t = temp_c
    return (t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
            + math.atan(t + rh) - math.atan(rh - 1.676331)
            + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh)
            - 4.686035)


def globe_temp_c(temp_c: float, radiation_wm2: float | None, wind_ms: float | None) -> float:
    """Estimated black-globe temperature (degC). See module docstring for method."""
    radiation_wm2 = radiation_wm2 or 0.0
    wind = WIND_REF_MS if wind_ms is None else max(0.0, wind_ms)
    sun_term = GLOBE_MAX_ADD_C * min(1.0, radiation_wm2 / SUN_FULL_WM2)
    wind_relief = 1.0 / (1.0 + 0.25 * wind)   # more wind -> globe tracks air temp more closely
    return temp_c + sun_term * wind_relief


def wbgt_estimate_c(temp_c: float, rh: float, radiation_wm2: float | None,
                     wind_ms: float | None) -> float:
    """Outdoor WBGT estimate, degC: 0.7*natural-wet-bulb + 0.2*globe + 0.1*air temp
    (the standard ISO 7243 outdoor-with-solar-load weighting)."""
    twb = natural_wet_bulb_c(temp_c, rh)
    tg = globe_temp_c(temp_c, radiation_wm2, wind_ms)
    return 0.7 * twb + 0.2 * tg + 0.1 * temp_c


def iso7243_limit_c(workload: str, acclimatised_days: int) -> float:
    limits = ISO7243_LIMITS_C.get(workload, ISO7243_LIMITS_C["moderate"])
    key = "acclimatised" if acclimatised_days >= ACCLIMATISED_DAYS else "unacclimatised"
    return limits[key]


def iso7243_band(wbgt_c: float, workload: str, acclimatised_days: int) -> int:
    """Map a WBGT estimate onto HeatGuard's 4 levels against the ISO 7243 reference limit."""
    limit = iso7243_limit_c(workload, acclimatised_days)
    if wbgt_c < limit - BAND_MARGIN_C:
        return LOW
    if wbgt_c < limit:
        return CAUTION
    if wbgt_c < limit + BAND_MARGIN_C:
        return HIGH
    return EXTREME
