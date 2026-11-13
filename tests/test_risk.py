import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.risk import (CAUTION, EXTREME, HIGH, LOW, Conditions, CrewProfile, HourPoint,
                      assess, band_for, f_to_c, fallback_level, heat_index_f,
                      in_uae_midday_ban, outlook, sun_adjustment_f)

FIX = json.loads((Path(__file__).parent / "fixtures/openmeteo_2026-11-06.json").read_text())
HOT = json.loads((Path(__file__).parent / "fixtures/openmeteo_2026-07-20_hot.json").read_text())


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


def _hours(site, fixture=FIX):
    h = fixture[site]["hourly"]
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
    # Genuinely cool and dry, not just low air temperature with high humidity --
    # see test_wbgt.py for the case where humidity alone makes a moderate
    # temperature dangerous under ISO 7243 even though the heat index misses it.
    r = assess(Conditions(20, 50, 0), CrewProfile(workload="heavy", clothing="non_breathable",
                                                   acclimatised_days=1))
    assert r.level == LOW
    assert any("still cool" in x for x in r.reasons)


# --- Real hot-day data, pulled from Open-Meteo's historical archive for actual
# summer heat (not a mild November day): Abu Dhabi peaked at 47.6°C on
# 20 Jul 2026 (13% RH) and Karachi's hottest day in Jun-Jul 2026 was 11 Jun
# (34.9°C at 93% RH — a dangerous humid heat day even though the raw
# temperature is lower than Abu Dhabi's). These are the real recorded
# conditions, not a synthetic or mild-season fixture.

def test_real_abu_dhabi_july_heatwave_warns_well_before_the_peak():
    """20 Jul 2026, Abu Dhabi: a real recorded 47.6 °C peak at 14:00 (vs ~30 °C overnight).
    A moderate crew is only at Caution in the 07:00 morning reading, so the engine must
    warn at least an hour ahead of the real High/Extreme hours that follow."""
    hours = _hours("abudhabi", HOT)
    now = datetime(2026, 7, 20, 7, 0)
    cur = hours[7].cond
    crew = CrewProfile()  # moderate workload, standard clothing, acclimatised
    o = outlook(now, cur, hours, crew, "AE", horizon_h=8)
    assert o.current.level < HIGH                 # 07:00 is still only Caution for this crew
    assert o.peak_level == EXTREME                 # the real recorded peak is well past 115°F heat index
    assert o.first_high_at is not None
    assert o.warning_lead_minutes(now) >= 60        # warned at least an hour ahead of the real peak
    # at the real 14:00 peak the UAE's mandated midday work ban is also in force
    peak_assess = assess(hours[14].cond, crew, "AE", hours[14].local_dt)
    assert peak_assess.legal_stop


def test_real_abu_dhabi_july_distinguishes_cooler_hours_from_the_peak():
    """Even on the hottest recorded day of the window, the engine should still read the
    relatively cooler pre-dawn hours (30.6 °C, 03:00) as lower risk than the 47.6 °C peak —
    i.e. it isn't just flagging the whole day as Extreme regardless of the data."""
    hours = _hours("abudhabi", HOT)
    crew = CrewProfile()
    cooler = assess(hours[3].cond, crew, "AE", hours[3].local_dt)   # 03:00, 30.6°C
    peak = assess(hours[14].cond, crew, "AE", hours[14].local_dt)   # 14:00, 47.6°C (real recorded peak)
    assert cooler.level < peak.level
    assert peak.level == EXTREME


def test_real_karachi_june_humid_heat_hits_high_for_exposed_crew():
    """11 Jun 2026, Karachi: only 34.9°C at the peak, but 93% RH makes it dangerous —
    this is the real recorded hot day for the city in Jun-Jul 2026, replacing the
    6 Nov off-season test date."""
    hours = _hours("karachi", HOT)
    now = datetime(2026, 6, 11, 8, 0)
    exposed = CrewProfile(workload="heavy", clothing="non_breathable")
    o = outlook(now, hours[8].cond, hours, exposed, "PK", horizon_h=8)
    assert o.peak_level >= HIGH
    assert o.warning_lead_minutes(now) is None or o.warning_lead_minutes(now) >= 60


def test_real_karachi_june_shaded_light_crew_stays_lower_than_exposed():
    """11 Jun 2026, Karachi: humid heat (93% RH) keeps risk elevated even at a modest
    34.9°C peak. In the evening cool-down (20:00-23:00) a shaded, light-duty crew drops
    to Caution while a heavy, non-breathable-PPE crew is still at High — the real data
    shows job factors matter as much as the raw temperature here."""
    hours = _hours("karachi", HOT)
    now = datetime(2026, 6, 11, 19, 0)
    shaded = CrewProfile(workload="light", shaded=True)
    exposed = CrewProfile(workload="heavy", clothing="non_breathable")
    o1 = outlook(now, hours[19].cond, hours, shaded, "PK", horizon_h=4)
    o2 = outlook(now, hours[19].cond, hours, exposed, "PK", horizon_h=4)
    assert o1.peak_level < o2.peak_level
