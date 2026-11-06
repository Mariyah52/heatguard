"""Weather for each site, with retries, a cached forecast, and a safe fallback.

Order of preference:
  1. simulator override (demo only)
  2. live Open-Meteo data (refreshed every 15 minutes)
  3. the last good forecast, if under 6 hours old  ("cache")
  4. no usable data → the risk engine's cautious default ("fallback")
"""

from __future__ import annotations

import json
import os
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .risk import Conditions, HourPoint

API = "https://api.open-meteo.com/v1/forecast"
FIELDS = "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation"
REFRESH = timedelta(minutes=15)
CACHE_MAX_AGE = timedelta(hours=6)
FIXTURE = os.getenv("HEATGUARD_FIXTURE")          # offline/testing: replay saved real data
FAIL_FEED = {"on": False}                          # simulator: pretend the feed is down


def fetch(lat: float, lon: float, retries: int = 2) -> dict:
    if FAIL_FEED["on"]:
        raise RuntimeError("weather feed unavailable (simulated outage)")
    if FIXTURE:
        return _fixture_for(lat)
    params = {"latitude": lat, "longitude": lon, "current": FIELDS, "hourly": FIELDS,
              "forecast_days": 2, "timezone": "auto"}
    last = None
    for attempt in range(retries + 1):
        try:
            r = httpx.get(API, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            if "hourly" not in data or "current" not in data:
                raise ValueError("weather response missing fields")
            return data
        except Exception as e:  # network, HTTP or shape error
            last = e
            _time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"weather fetch failed after {retries + 1} tries: {last}")


def _fixture_for(lat: float) -> dict:
    """Replay a real saved day, shifted to today, so offline runs look realistic."""
    data = json.loads(Path(FIXTURE).read_text())
    site = "karachi" if lat > 24.6 else "abudhabi"
    d = json.loads(json.dumps(data[site]))
    off = timedelta(seconds=d["utc_offset_seconds"])
    today = (datetime.now(timezone.utc).replace(tzinfo=None) + off).date()
    first = datetime.fromisoformat(d["hourly"]["time"][0]).date()
    shift = today - first
    d["hourly"]["time"] = [(datetime.fromisoformat(t) + shift).isoformat(timespec="minutes")
                           for t in d["hourly"]["time"]]
    now_local = (datetime.now(timezone.utc).replace(tzinfo=None) + off).replace(minute=0, second=0, microsecond=0)
    i = d["hourly"]["time"].index(now_local.isoformat(timespec="minutes"))
    d["current"] = {"time": d["hourly"]["time"][i],
                    **{k: d["hourly"][k][i] for k in FIELDS.split(",")}}
    return d


def parse(data: dict) -> tuple[Conditions, list[HourPoint], int]:
    c = data["current"]
    cur = Conditions(c["temperature_2m"], c["relative_humidity_2m"],
                     c.get("shortwave_radiation"), c.get("wind_speed_10m"))
    h = data["hourly"]
    hours = [HourPoint(datetime.fromisoformat(t),
                       Conditions(h["temperature_2m"][i], h["relative_humidity_2m"][i],
                                  h["shortwave_radiation"][i], h["wind_speed_10m"][i]))
             for i, t in enumerate(h["time"])
             if h["temperature_2m"][i] is not None and h["relative_humidity_2m"][i] is not None]
    return cur, hours, int(data.get("utc_offset_seconds", 0))


def current_from_hourly(hours: list[HourPoint], now_local: datetime) -> Conditions | None:
    """Pick the hour that covers 'now' from a cached forecast."""
    best = None
    for hp in hours:
        if hp.local_dt <= now_local:
            best = hp
    return best.cond if best else None


def apply_sim(sim: dict, hours: list[HourPoint], now_local: datetime):
    """Simulator: replace the next few hours with chosen conditions."""
    cond = Conditions(sim["temp_c"], sim["rh"], sim.get("radiation", 900), 3.0)
    until = now_local + timedelta(hours=sim.get("hours", 4))
    new_hours = [HourPoint(h.local_dt, cond) if now_local - timedelta(hours=1) <= h.local_dt <= until
                 else h for h in hours]
    return cond, new_hours
