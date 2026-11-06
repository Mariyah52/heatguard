import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.risk import (CAUTION, EXTREME, HIGH, LOW, Conditions, CrewProfile, HourPoint,
                      assess, band_for, f_to_c, fallback_level, heat_index_f,
                      in_uae_midday_ban, outlook, sun_adjustment_f)

FIX = json.loads((Path(__file__).parent / "fixtures/openmeteo_2026-11-06.json").read_text())


@pytest.mark.parametrize("temp_f,rh,expected_f", [
    # Values from the NWS heat index chart (rounded to the chart's whole degrees)
    (90, 70, 106),
    (100, 40, 109),
    (96, 50, 108),
    (86, 90, 105),
    (80, 40, 80),
])
def test_heat_index_matches_nws_chart(temp_f, rh, expected_f):
    assert heat_index_f(f_to_c(temp_f), rh) == pytest.approx(expected_f, abs=1.5)


def test_osha_bands():
    assert band_for(90.9) == LOW
    assert band_for(91) == CAUTION
    assert band_for(103) == HIGH
    assert band_for(115) == EXTREME


def test_sun_adjustment_scales_and_respects_shade():
    assert sun_adjustment_f(800, False) == 15
    assert sun_adjustment_f(400, False) == 7.5
    assert sun_adjustment_f(1000, False) == 15
    assert sun_adjustment_f(800, True) == 0
    assert sun_adjustment_f(None, False) == 0


def test_job_factors_step_up_and_cap():
    cond = Conditions(temp_c=33, rh=40, radiation_wm2=0)  # ~Caution on its own
    base = assess(cond, CrewProfile(workload="moderate"))
    worst = assess(cond, CrewProfile(workload="heavy", clothing="non_breathable",
                                     acclimatised_days=2))
    assert worst.level == EXTREME
    assert worst.level > base.level
    assert any("heavy" in r for r in worst.reasons)
    assert any("acclimatised" in r for r in worst.reasons)


def test_reasons_always_explain_the_score():
    r = assess(Conditions(30, 50, 700), CrewProfile())
    assert r.reasons and "feels like" in r.reasons[0]
    assert any("sun" in x for x in r.reasons)


def test_uae_midday_ban_window():
    assert in_uae_midday_ban("AE", datetime(2026, 7, 1, 13, 0))
    assert not in_uae_midday_ban("AE", datetime(2026, 7, 1, 15, 0))
    assert not in_uae_midday_ban("AE", datetime(2026, 11, 6, 13, 0))
    assert not in_uae_midday_ban("PK", datetime(2026, 7, 1, 13, 0))
    r = assess(Conditions(30, 30, 0), CrewProfile(), "AE", datetime(2026, 8, 1, 13, 0))
    assert r.level == EXTREME and r.legal_stop


def test_fallback_is_never_low():
    assert fallback_level(datetime(2026, 11, 6, 7, 0)).level == CAUTION
    assert fallback_level(datetime(2026, 11, 6, 13, 0)).level == HIGH
    assert fallback_level(datetime(2026, 11, 6, 13, 0)).degraded


def _hours(site):
    h = FIX[site]["hourly"]
    return [HourPoint(datetime.fromisoformat(t),
                      Conditions(h["temperature_2m"][i], h["relative_humidity_2m"][i],
                                 h["shortwave_radiation"][i], h["wind_speed_10m"][i]))
            for i, t in enumerate(h["time"])]


def test_real_abu_dhabi_day_warns_before_the_peak():
    """6 Nov 2026, Mussafah: 23 °C at 07:00 rising to 37 °C mid-afternoon."""
    hours = _hours("abudhabi")
    now = datetime(2026, 11, 6, 7, 0)
    cur = hours[7].cond
    crew = CrewProfile(workload="heavy", clothing="non_breathable", acclimatised_days=14)
    o = outlook(now, cur, hours, crew, "AE", horizon_h=8)
    assert o.current.level < HIGH            # cool morning
    assert o.peak_level >= HIGH              # dangerous for a heavy, coverall crew by midday
    assert o.first_high_at is not None
    assert o.warning_lead_minutes(now) >= 60  # warned at least an hour ahead


def test_real_karachi_light_shaded_crew_stays_lower():
    hours = _hours("karachi")
    now = datetime(2026, 11, 6, 8, 0)
    shaded = CrewProfile(workload="light", shaded=True)
    exposed = CrewProfile(workload="heavy", clothing="non_breathable")
    o1 = outlook(now, hours[8].cond, hours, shaded, "PK", horizon_h=8)
    o2 = outlook(now, hours[8].cond, hours, exposed, "PK", horizon_h=8)
    assert o1.peak_level < o2.peak_level


def test_cool_conditions_do_not_raise_false_alarms():
    r = assess(Conditions(23, 87, 35), CrewProfile(workload="heavy", clothing="non_breathable",
                                                   acclimatised_days=1))
    assert r.level == LOW
    assert any("still cool" in x for x in r.reasons)
