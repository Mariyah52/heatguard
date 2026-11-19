"""Forecast-based shift and hydration planner.

Pure functions. Reads the multi-day hourly forecast, scores every hour with the same
risk engine as the live alerts, and turns the result into plain advice for supervisors:
which hours to avoid, a safer shift window, how much water and rest, and how fast a
newly arrived crew should build up its workload.

This is guidance from published rules of thumb (OSHA / NIOSH heat-stress guidance), not
a medical assessment and not a diagnosis. Anyone who feels unwell goes to a person.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .risk import CAUTION, EXTREME, HIGH, LEVELS, CrewProfile, HourPoint, assess

DISCLAIMER = ("Automated heat-stress guidance, not a medical diagnosis. "
              "If someone feels unwell, a supervisor, first-aider or emergency services decide.")

# level -> (drink a cup every N minutes, rest minutes per hour in shade)
HYDRATION = {0: (30, 0), CAUTION: (20, 5), HIGH: (15, 15), EXTREME: (15, 30)}
WORKDAY = (4, 20)     # hours of the day considered when looking for a safer window


def _windows(hours: list[int]) -> list[str]:
    """[5,6,7,17,18] -> ['05:00–08:00', '17:00–19:00']"""
    out, start, prev = [], None, None
    for h in sorted(hours):
        if start is None:
            start = prev = h
        elif h == prev + 1:
            prev = h
        else:
            out.append(f"{start:02d}:00–{prev + 1:02d}:00")
            start = prev = h
    if start is not None:
        out.append(f"{start:02d}:00–{prev + 1:02d}:00")
    return out


def plan(now_local: datetime, hourly: list[HourPoint], profile: CrewProfile, country: str,
         shift_start: str, shift_end: str) -> dict:
    scored = [(h.local_dt, assess(h.cond, profile, country, h.local_dt)) for h in hourly
              if h.local_dt >= now_local.replace(minute=0, second=0, microsecond=0)]
    by_day: dict = defaultdict(list)
    for t, r in scored:
        by_day[t.date()].append((t, r))

    days = []
    for d in sorted(by_day):
        rows = by_day[d]
        peak_t, peak_r = max(rows, key=lambda x: (x[1].level, x[1].heat_index_f))
        in_shift = [r for t, r in rows if shift_start <= t.strftime("%H:%M") < shift_end]
        days.append({
            "date": d.isoformat(), "hours": len(rows),
            "peak_level": peak_r.level, "peak_name": LEVELS[peak_r.level],
            "peak_at": peak_t.strftime("%H:%M"), "peak_feels_c": peak_r.feels_like_c,
            "risky_shift_hours": sum(1 for r in in_shift if r.level >= HIGH),
        })

    trend = "steady"
    full = [d for d in days if d["hours"] >= 12]
    if len(full) >= 2:
        delta = full[-1]["peak_feels_c"] - full[0]["peak_feels_c"]
        trend = "rising" if delta >= 2 else "easing" if delta <= -2 else "steady"

    # safer windows for the first day that has any risky hour in the crew's shift
    suggestion, suggestion_day = None, None
    for d in sorted(by_day):
        rows = by_day[d]
        risky = [t for t, r in rows if shift_start <= t.strftime("%H:%M") < shift_end and r.level >= HIGH]
        if risky:
            safe = [t.hour for t, r in rows if WORKDAY[0] <= t.hour < WORKDAY[1] and r.level < HIGH]
            suggestion, suggestion_day = _windows(safe), d.isoformat()
            break

    shift_levels = [r.level for t, r in scored[:24] if shift_start <= t.strftime("%H:%M") < shift_end]
    worst = max(shift_levels, default=0)
    cup_every, rest = HYDRATION[worst]
    if profile.workload == "heavy":
        rest = min(45, rest + 5) if worst >= CAUTION else rest
        cup_every = min(cup_every, 15) if worst >= CAUTION else cup_every
    water_ml_per_hour = int(60 / cup_every * 250)

    ramp = None
    if profile.acclimatised_days < 5:
        ramp = min(100, 20 * (profile.acclimatised_days + 1))   # NIOSH: new workers 20% day 1, +20% a day

    advice = []
    if suggestion is not None:
        if suggestion:
            advice.append(f"Heat reaches High or worse during the shift. Safer hours: {', '.join(suggestion)}.")
        else:
            advice.append("Heat reaches High or worse for the whole working day: keep outdoor work to essential tasks.")
    else:
        advice.append("No High-risk hours expected during this shift in the forecast.")
    advice.append(f"Water: a cup every {cup_every} minutes (about {water_ml_per_hour} ml an hour)."
                  + (f" Shade rest: {rest} minutes each hour." if rest else ""))
    if ramp is not None:
        advice.append(f"New to the heat: limit to about {ramp}% of a normal workload today, adding 20% a day.")
    if trend == "rising":
        advice.append("The next days are hotter. Plan harder tasks for the cooler part of today.")
    elif trend == "easing":
        advice.append("The next days ease off. Keep today's precautions.")

    return {"days": days[:4], "trend": trend, "suggested_windows": suggestion,
            "suggested_day": suggestion_day, "worst_level": worst, "worst_name": LEVELS[worst],
            "cup_every_min": cup_every, "water_ml_per_hour": water_ml_per_hour,
            "rest_min_per_hour": rest, "workload_cap_pct": ramp, "advice": advice,
            "disclaimer": DISCLAIMER}
