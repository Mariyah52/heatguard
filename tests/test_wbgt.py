import pytest

from app.risk import CAUTION, EXTREME, HIGH, LOW, Conditions, CrewProfile, assess
from app.wbgt import (globe_temp_c, iso7243_band, iso7243_limit_c,
                      natural_wet_bulb_c, wbgt_estimate_c)


def test_natural_wet_bulb_drops_with_dryness():
    # dry air pulls the wet-bulb well below air temperature; saturated air
    # keeps it close to air temperature
    dry = natural_wet_bulb_c(35, 15)
    humid = natural_wet_bulb_c(35, 95)
    assert dry < humid
    assert humid == pytest.approx(35, abs=2)


def test_globe_temp_rises_with_sun_and_falls_with_wind():
    shaded = globe_temp_c(30, 0, 2)
    sunny_still = globe_temp_c(30, 800, 0)
    sunny_windy = globe_temp_c(30, 800, 8)
    assert shaded == pytest.approx(30, abs=0.1)
    assert sunny_still > sunny_windy > 30


def test_wbgt_lower_than_dry_bulb_in_dry_heat_and_closer_in_humid_heat():
    dry_heat = wbgt_estimate_c(40, 10, 700, 2)
    humid_heat = wbgt_estimate_c(32, 85, 400, 2)
    assert dry_heat < 40
    assert humid_heat > 28  # humidity keeps WBGT close to a lower air temperature


def test_iso7243_limits_get_stricter_with_workload_and_acclimatisation():
    assert iso7243_limit_c("light", 14) > iso7243_limit_c("moderate", 14) > iso7243_limit_c("heavy", 14)
    assert iso7243_limit_c("heavy", 14) > iso7243_limit_c("heavy", 1)


def test_iso7243_band_matches_margins():
    limit = iso7243_limit_c("moderate", 14)
    assert iso7243_band(limit - 4, "moderate", 14) == LOW
    assert iso7243_band(limit - 1, "moderate", 14) == CAUTION
    assert iso7243_band(limit + 1, "moderate", 14) == HIGH
    assert iso7243_band(limit + 4, "moderate", 14) == EXTREME


def test_humid_moderate_heat_is_caught_by_wbgt_even_when_heat_index_is_caution():
    """29°C at 90% RH: the NWS heat-index band alone (even with its own sun
    adjustment) only reaches Caution for a moderate crew, but ISO 7243's WBGT
    limit for moderate work is already exceeded here -- this is exactly the
    humid-heat blind spot WBGT exists to catch, and it must be able to push
    the final level past what heat index says."""
    cond = Conditions(temp_c=29, rh=90, radiation_wm2=50, wind_kmh=5)
    r = assess(cond, CrewProfile(workload="moderate", acclimatised_days=14))
    assert r.wbgt_c is not None
    assert r.wbgt_level is not None and r.wbgt_level >= HIGH
    assert r.level >= r.wbgt_level  # WBGT only ever raises the final level
    assert any("ISO 7243" in x for x in r.reasons)


def test_wbgt_never_lowers_the_heat_index_level():
    """Dry, very hot conditions: heat index alone already says Extreme; WBGT
    (which runs cooler in dry air) must not pull that back down."""
    cond = Conditions(temp_c=46, rh=12, radiation_wm2=850, wind_kmh=10)
    r = assess(cond, CrewProfile(workload="heavy", acclimatised_days=14))
    assert r.level == EXTREME


def test_shaded_crew_gets_no_solar_globe_heating():
    cond = Conditions(temp_c=30, rh=40, radiation_wm2=900, wind_kmh=5)
    shaded = assess(cond, CrewProfile(workload="light", shaded=True, acclimatised_days=14))
    exposed = assess(cond, CrewProfile(workload="light", shaded=False, acclimatised_days=14))
    assert shaded.wbgt_c < exposed.wbgt_c
