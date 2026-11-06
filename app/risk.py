"""HeatGuard heat-risk engine.

Pure functions, no I/O, so every number can be tested and explained.

Method
------
1. Heat index from air temperature and relative humidity, using the US National
   Weather Service (NWS) Rothfusz regression with its published adjustments.
2. Sun adjustment: OSHA notes direct sunlight can add up to 15 °F to the heat
   index. HeatGuard scales that 0–15 °F by measured solar radiation
   (full adjustment at 800 W/m² or more) for crews working unshaded.
3. Base risk band from OSHA's heat-index guidance:
       < 91 °F Lower · 91–103 °F Moderate · 103–115 °F High · > 115 °F Extreme
   HeatGuard calls these Low, Caution, High and Extreme.
4. Step-ups, each one level, at most two, capped at Extreme, and only once the
   sun-adjusted heat index reaches 80 °F (27 °C), so cool mornings don't raise
   false alarms:
     * heavy workload and/or non-breathable clothing: one level together
       (OSHA: strenuous work or heavy/non-breathable clothing → next higher level)
     * not yet acclimatised: fewer than 7 days working in the heat
5. Legal stop: in the UAE, outdoor work is banned 12:30–15:00 from 15 June to
   15 September. Inside that window HeatGuard tells crews to stop outdoor work.

When data is missing HeatGuard never guesses low: see `fallback_level`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time

LEVELS = ["Low", "Caution", "High", "Extreme"]
LOW, CAUTION, HIGH, EXTREME = 0, 1, 2, 3

# OSHA heat-index band edges in °F
BAND_EDGES_F = (91.0, 103.0, 115.0)

SUN_MAX_ADD_F = 15.0      # OSHA: direct sun can add up to 15 °F
SUN_FULL_WM2 = 800.0      # radiation at which the full sun adjustment applies
ACCLIMATISED_DAYS = 7
STEP_UP_FROM_F = 80.0     # job factors only raise risk once it is warm (NWS "Caution" starts at 80 °F)
MAX_STEP_UPS = 2          # job factors add at most two levels

WORKLOADS = ("light", "moderate", "heavy")
CLOTHING = ("standard", "non_breathable")


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def heat_index_f(temp_c: float, rh: float) -> float:
    """NWS heat index in °F (Rothfusz regression with adjustments)."""
    t = c_to_f(temp_c)
    rh = max(0.0, min(100.0, rh))
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (simple + t) / 2.0 < 80.0:
        return simple
    hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh
          - 0.22475541 * t * rh - 0.00683783 * t * t
          - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
          + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
    if rh < 13 and 80 <= t <= 112:
        hi -= ((13 - rh) / 4.0) * math.sqrt((17 - abs(t - 95.0)) / 17.0)
    elif rh > 85 and 80 <= t <= 87:
        hi += ((rh - 85) / 10.0) * ((87 - t) / 5.0)
    return hi


def sun_adjustment_f(radiation_wm2: float | None, shaded: bool) -> float:
    if shaded or not radiation_wm2 or radiation_wm2 <= 0:
        return 0.0
    return SUN_MAX_ADD_F * min(1.0, radiation_wm2 / SUN_FULL_WM2)


def band_for(hi_f: float) -> int:
    if hi_f < BAND_EDGES_F[0]:
        return LOW
    if hi_f < BAND_EDGES_F[1]:
        return CAUTION
    if hi_f < BAND_EDGES_F[2]:
        return HIGH
    return EXTREME


def in_uae_midday_ban(country: str, local_dt: datetime) -> bool:
    """UAE midday break: no outdoor work 12:30–15:00, 15 Jun – 15 Sep."""
    if country.upper() != "AE":
        return False
    d = local_dt.date()
    if not (date(d.year, 6, 15) <= d <= date(d.year, 9, 15)):
        return False
    return time(12, 30) <= local_dt.time() < time(15, 0)


@dataclass
class CrewProfile:
    workload: str = "moderate"          # light | moderate | heavy
    clothing: str = "standard"          # standard | non_breathable
    acclimatised_days: int = 14
    shaded: bool = False


@dataclass
class Conditions:
    temp_c: float
    rh: float
    radiation_wm2: float | None = 0.0
    wind_kmh: float | None = None


@dataclass
class Risk:
    level: int
    heat_index_f: float
    adjusted_f: float
    reasons: list[str] = field(default_factory=list)
    legal_stop: bool = False
    degraded: bool = False

    @property
    def name(self) -> str:
        return LEVELS[self.level]

    @property
    def feels_like_c(self) -> float:
        # the standard heat index ("feels like" in the shade); sun is shown as a separate reason
        return round(f_to_c(self.heat_index_f), 1)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "name": self.name,
            "heat_index_f": round(self.heat_index_f, 1),
            "adjusted_f": round(self.adjusted_f, 1),
            "feels_like_c": self.feels_like_c,
            "reasons": self.reasons,
            "legal_stop": self.legal_stop,
            "degraded": self.degraded,
        }


def assess(cond: Conditions, crew: CrewProfile, country: str = "",
           local_dt: datetime | None = None) -> Risk:
    """Risk for one crew under one set of conditions, with reasons."""
    hi = heat_index_f(cond.temp_c, cond.rh)
    sun = sun_adjustment_f(cond.radiation_wm2, crew.shaded)
    adjusted = hi + sun
    level = band_for(adjusted)
    reasons = [f"{cond.temp_c:.0f}°C air, {cond.rh:.0f}% humidity → feels like "
               f"{f_to_c(hi):.0f}°C"]
    if sun >= 1:
        reasons.append(f"strong sun adds {sun * 5 / 9:.0f}°C (working unshaded)")
    base = level
    if adjusted >= STEP_UP_FROM_F:
        steps = []
        job = [s for s, on in (("heavy physical work", crew.workload == "heavy"),
                               ("non-breathable clothing or PPE",
                                crew.clothing == "non_breathable")) if on]
        if job:
            # OSHA: strenuous work OR heavy/non-breathable clothing → one level higher
            steps.append(" and ".join(job))
        if crew.acclimatised_days < ACCLIMATISED_DAYS:
            steps.append(f"only {crew.acclimatised_days} day(s) acclimatised")
        for s in steps[:MAX_STEP_UPS]:
            reasons.append(f"{s} (+1 level)")
        if len(steps) > MAX_STEP_UPS:
            reasons.append(f"also: {', '.join(steps[MAX_STEP_UPS:])}")
        level += min(len(steps), MAX_STEP_UPS)
    elif crew.workload == "heavy" or crew.clothing == "non_breathable":
        reasons.append("job factors noted; conditions still cool")
    level = min(level, EXTREME)
    if level == base == LOW and len(reasons) == 1:
        reasons.append("no added job factors")
    legal = bool(local_dt and in_uae_midday_ban(country, local_dt))
    if legal:
        level = EXTREME
        reasons.append("UAE midday break in force: no outdoor work 12:30–15:00")
    return Risk(level=level, heat_index_f=hi, adjusted_f=adjusted,
                reasons=reasons, legal_stop=legal)


def fallback_level(local_dt: datetime) -> Risk:
    """Used when no fresh weather data exists. Errs on the side of safety:
    Caution all day, High from 11:00 to 16:00 (the usual hottest hours)."""
    hot_hours = time(11, 0) <= local_dt.time() < time(16, 0)
    level = HIGH if hot_hours else CAUTION
    return Risk(level=level, heat_index_f=float("nan"), adjusted_f=float("nan"),
                reasons=["weather data unavailable: using cautious default schedule"],
                degraded=True)


@dataclass
class HourPoint:
    local_dt: datetime
    cond: Conditions


@dataclass
class Outlook:
    """What the next hours look like for a crew."""
    current: Risk
    peak_level: int
    peak_at: datetime | None
    first_high_at: datetime | None     # first hour at High or worse, if not already
    hours: list[tuple[datetime, int]]

    def warning_lead_minutes(self, now_local: datetime) -> int | None:
        if self.first_high_at is None:
            return None
        return max(0, int((self.first_high_at - now_local).total_seconds() // 60))

    def to_dict(self, now_local: datetime) -> dict:
        return {
            "current": self.current.to_dict(),
            "peak_level": self.peak_level,
            "peak_name": LEVELS[self.peak_level],
            "peak_at": self.peak_at.isoformat() if self.peak_at else None,
            "first_high_at": self.first_high_at.isoformat() if self.first_high_at else None,
            "lead_minutes": self.warning_lead_minutes(now_local),
            "hours": [{"t": t.isoformat(), "level": lv} for t, lv in self.hours],
        }


def outlook(now_local: datetime, current: Conditions, hourly: list[HourPoint],
            crew: CrewProfile, country: str = "", horizon_h: int = 6) -> Outlook:
    cur = assess(current, crew, country, now_local)
    upcoming = [h for h in hourly
                if now_local < h.local_dt <= now_local.replace(minute=0, second=0, microsecond=0)
                + _hours(horizon_h)]
    hours = [(h.local_dt, assess(h.cond, crew, country, h.local_dt).level) for h in upcoming]
    peak_level, peak_at = cur.level, None
    for t, lv in hours:
        if lv > peak_level:
            peak_level, peak_at = lv, t
    first_high = None
    if cur.level < HIGH:
        for t, lv in hours:
            if lv >= HIGH:
                first_high = t
                break
    return Outlook(current=cur, peak_level=peak_level, peak_at=peak_at,
                   first_high_at=first_high, hours=hours)


def _hours(n: int):
    from datetime import timedelta
    return timedelta(hours=n)


ACTIONS = {
    LOW: "Drink water regularly and know the signs of heat illness.",
    CAUTION: "Drink a cup of water every 15–20 minutes, take shade breaks, and watch your work partner.",
    HIGH: "Rest in the shade more often, reduce heavy work, drink water every 15 minutes, and follow the supervisor's work/rest schedule.",
    EXTREME: "Stop non-essential heavy work now. Move to shade, drink water, and only continue essential tasks with strict rest breaks.",
}
