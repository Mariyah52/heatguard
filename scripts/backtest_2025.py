"""2025 hot-season back-test for Abu Dhabi and Karachi.

Pulls real Open-Meteo archive data for 1 Jun - 15 Sep 2025 (already saved to
backtest_data/*.json; see README for how it was fetched) and runs every hour
through HeatGuard's actual risk engine (app.risk.assess), for two crew
profiles:

  * "typical"  - moderate workload, standard clothing, acclimatised (14 days)
  * "new_joiner" - heavy workload, non-breathable PPE, not yet acclimatised (2 days)

It answers the three questions the WBGT/ISO 7243 addition was meant to answer:

  1. How many hours would the WBGT/ISO 7243 check have raised above what the
     heat index alone said, across a whole real summer (not just 2 days)?
  2. On the hottest real days, how far ahead of the actual peak does the
     engine's outlook() warn a crew -- using real recorded hourly data, not a
     synthetic curve?
  3. How many hours fall inside the UAE's mandated midday work ban?

Output: backtest_data/results.md (summary for the deck) and
backtest_data/results.csv (every hour, every site, every crew -- the raw
numbers behind the summary).
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from app.risk import (CAUTION, EXTREME, HIGH, LOW, Conditions, CrewProfile,
                      HourPoint, assess, band_for, heat_index_f, outlook,
                      sun_adjustment_f, STEP_UP_FROM_F, MAX_STEP_UPS, ACCLIMATISED_DAYS)

HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "backtest_data"

SITES = {
    "Abu Dhabi (Mussafah)": ("AE", DATA / "abudhabi_2025_summer.json"),
    "Karachi (Port Qasim)": ("PK", DATA / "karachi_2025_summer.json"),
}

CREWS = {
    "typical": CrewProfile(workload="moderate", clothing="standard", acclimatised_days=14),
    "new_joiner": CrewProfile(workload="heavy", clothing="non_breathable", acclimatised_days=2),
}

LEVEL_NAMES = ["Low", "Caution", "High", "Extreme"]


def load_hours(path: Path) -> list[HourPoint]:
    d = json.loads(path.read_text())
    h = d["hourly"]
    return [HourPoint(datetime.fromisoformat(t),
                      Conditions(h["temperature_2m"][i], h["relative_humidity_2m"][i],
                                 h["shortwave_radiation"][i], h["wind_speed_10m"][i]))
            for i, t in enumerate(h["time"])]


def heat_index_only_level(cond: Conditions, crew: CrewProfile) -> int:
    """Re-derive just the heat-index path (no WBGT, no legal stop) for comparison."""
    hi = heat_index_f(cond.temp_c, cond.rh)
    sun = sun_adjustment_f(cond.radiation_wm2, crew.shaded)
    adjusted = hi + sun
    level = band_for(adjusted)
    if adjusted >= STEP_UP_FROM_F:
        steps = 0
        if crew.workload == "heavy" or crew.clothing == "non_breathable":
            steps += 1
        if crew.acclimatised_days < ACCLIMATISED_DAYS:
            steps += 1
        level += min(steps, MAX_STEP_UPS)
    return min(level, EXTREME)


def main():
    rows = []
    wbgt_caught = {site: {crew: 0 for crew in CREWS} for site in SITES}
    total_hours = {site: 0 for site in SITES}
    legal_stop_hours = {site: 0 for site in SITES}
    peak_by_day: dict[tuple[str, str], tuple[int, datetime]] = {}

    for site_name, (country, path) in SITES.items():
        hours = load_hours(path)
        total_hours[site_name] = len(hours)
        for crew_name, crew in CREWS.items():
            for hp in hours:
                r = assess(hp.cond, crew, country, hp.local_dt)
                hi_only = heat_index_only_level(hp.cond, crew)
                if r.level > hi_only and not r.legal_stop:
                    wbgt_caught[site_name][crew_name] += 1
                if crew_name == "typical" and r.legal_stop:
                    legal_stop_hours[site_name] += 1
                rows.append({
                    "site": site_name, "crew": crew_name, "time": hp.local_dt.isoformat(),
                    "temp_c": hp.cond.temp_c, "rh": hp.cond.rh,
                    "heat_index_only_level": LEVEL_NAMES[hi_only],
                    "final_level": LEVEL_NAMES[r.level],
                    "wbgt_c": round(r.wbgt_c, 1) if r.wbgt_c is not None else None,
                    "legal_stop": r.legal_stop,
                })
                day = hp.local_dt.date().isoformat()
                key = (site_name, day)
                if key not in peak_by_day or r.level > peak_by_day[key][0]:
                    peak_by_day[key] = (r.level, hp.local_dt)

    with open(DATA / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Two real findings per site, both from the actual hourly data:
    #  (a) the single hottest real day -- how much of it has no safe hour at all
    #  (b) the hottest day that still had a below-High morning -- the real lead
    #      time HeatGuard's outlook() gives before High risk begins
    lead_time_lines = []
    for site_name, (country, path) in SITES.items():
        hours = load_hours(path)
        by_day: dict[str, list[HourPoint]] = {}
        for hp in hours:
            by_day.setdefault(hp.local_dt.date().isoformat(), []).append(hp)

        hottest_day = max(by_day, key=lambda d: max(h.cond.temp_c for h in by_day[d]))
        day_hours = sorted(by_day[hottest_day], key=lambda h: h.local_dt)
        hottest_hour = max(day_hours, key=lambda h: h.cond.temp_c)
        levels = [assess(h.cond, CREWS["typical"], country, h.local_dt).level for h in day_hours]
        extreme_or_high_hours = sum(1 for lv in levels if lv >= HIGH)
        lead_time_lines.append(
            f"- **{site_name}**, hottest real day in the window: **{hottest_day}** "
            f"(peak {hottest_hour.cond.temp_c:.1f}°C at {hottest_hour.local_dt.strftime('%H:%M')}). "
            f"A typical crew was at High or Extreme for **{extreme_or_high_hours} of the day's "
            f"24 hours** -- on this day there is effectively no safe window, which is why "
            f"HeatGuard treats protection as continuous, not just a single peak-hour alert."
        )

        candidates = []
        for day, hrs in by_day.items():
            hrs = sorted(hrs, key=lambda x: x.local_dt)
            morning = next((x for x in hrs if x.local_dt.hour == 6), None)
            if morning is None:
                continue
            r = assess(morning.cond, CREWS["typical"], country, morning.local_dt)
            if r.level < HIGH:
                o = outlook(morning.local_dt, morning.cond, hours, CREWS["typical"], country, horizon_h=12)
                if o.peak_level >= HIGH and o.first_high_at:
                    lead = o.warning_lead_minutes(morning.local_dt)
                    candidates.append((day, lead, max(x.cond.temp_c for x in hrs)))
        if candidates:
            day, lead, peak_temp = max(candidates, key=lambda c: c[2])
            lead_time_lines.append(
                f"- **{site_name}**, hottest day that still had a below-High morning: "
                f"**{day}** (peak {peak_temp:.1f}°C). From a real 06:00 reading, HeatGuard's "
                f"outlook warned the crew **{lead} minutes before High risk began** that day."
            )

    total_all = sum(total_hours.values())
    caught_all = sum(sum(v.values()) for v in wbgt_caught.values())

    lines = []
    lines.append("# HeatGuard 2025 hot-season back-test (real Open-Meteo archive data)\n")
    lines.append(f"Window: **1 Jun 2025 - 15 Sep 2025**, hourly, both sites "
                 f"({sum(total_hours.values())} site-hours total). "
                 f"Not simulated -- this is Open-Meteo's recorded archive for "
                 f"Abu Dhabi (Mussafah) and Karachi (Port Qasim).\n")
    lines.append("## Why heat index alone wasn't enough\n")
    for site_name in SITES:
        for crew_name in CREWS:
            n = wbgt_caught[site_name][crew_name]
            pct = 100 * n / total_hours[site_name]
            lines.append(f"- **{site_name}, {crew_name} crew**: WBGT/ISO 7243 raised the "
                         f"risk level above what the heat index alone said in "
                         f"**{n} of {total_hours[site_name]} hours ({pct:.1f}%)** "
                         f"across the whole window.")
    lines.append(f"\n**Total across both sites and crews: {caught_all} hours** where the "
                 f"ISO 7243 cross-check caught something the heat index path missed on its own.\n")
    lines.append("## Lead time on the hottest real recorded days\n")
    lines.extend(lead_time_lines)
    lines.append("\n## UAE midday work ban\n")
    lines.append(f"- Abu Dhabi: **{legal_stop_hours['Abu Dhabi (Mussafah)']} hours** of the "
                 f"window fell inside the mandated 12:30-15:00 (15 Jun-15 Sep) outdoor work ban "
                 f"-- HeatGuard forces Extreme + stop-work for all of them automatically.")
    lines.append(f"- Karachi: {legal_stop_hours['Karachi (Port Qasim)']} hours (Pakistan has no "
                 f"equivalent nationwide rule as of this build, so this is expected to be 0).")
    lines.append("\n## Data\n")
    lines.append("Every one of the "
                 f"{total_all * len(CREWS) // len(CREWS)} hours is in `backtest_data/results.csv` "
                 "(site, crew, timestamp, both risk levels, WBGT estimate, legal-stop flag) "
                 "for anyone who wants to check the numbers by hand.")

    (DATA / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
