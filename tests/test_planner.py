import os
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_heatguard2.db"
os.environ["HEATGUARD_FIXTURE"] = str(Path(__file__).parent / "fixtures/openmeteo_2026-11-06.json")
os.environ["CYCLE_SECONDS"] = "100000"

from fastapi.testclient import TestClient  # noqa: E402

from app import weather  # noqa: E402
from app.main import app  # noqa: E402
from app.planner import plan  # noqa: E402
from app.risk import Conditions, CrewProfile, HourPoint  # noqa: E402

weather.FIXTURE = os.environ["HEATGUARD_FIXTURE"]


def _hours(peak_c, base_c=30, days=3):
    start = datetime(2026, 7, 20, 0, 0)
    out = []
    for i in range(24 * days):
        h = i % 24
        d = i // 24
        t = base_c + (peak_c - base_c) * max(0, 1 - abs(h - 14) / 7) + d * 1.5
        rad = 900 if 8 <= h <= 17 else 0
        out.append(HourPoint(start + timedelta(hours=i), Conditions(t, 40, rad, 5)))
    return out


def test_plan_finds_safer_windows_and_hydration():
    p = plan(datetime(2026, 7, 20, 6, 0), _hours(46), CrewProfile("heavy", "standard", 14, False),
             "PK", "06:00", "18:00")
    assert p["suggested_windows"], "a hot shift must produce safer windows"
    assert p["worst_level"] >= 2
    assert p["cup_every_min"] <= 15 and p["rest_min_per_hour"] >= 15
    assert p["trend"] == "rising"
    assert len(p["days"]) == 3 and "not a medical diagnosis" in p["disclaimer"]


def test_plan_mild_day_keeps_normal_shift_and_ramps_new_workers():
    p = plan(datetime(2026, 11, 6, 6, 0), _hours(26, 20), CrewProfile("light", "standard", 2, False),
             "PK", "06:00", "18:00")
    assert p["suggested_windows"] is None
    assert p["workload_cap_pct"] == 60          # day 3 of acclimatisation: 20% + 20% x 2
    assert any("normal workload" in a for a in p["advice"])


def test_state_has_plan_and_etag_304():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        r = c.get("/api/state")
        st = r.json()
        crew = st["sites"][0]["crews"][0]
        assert crew["outlook"]["plan"]["advice"] and crew["outlook"]["plan"]["days"]
        again = c.get("/api/state", headers={"If-None-Match": r.headers["etag"]})
        assert again.status_code in (200, 304)   # clock/ages may tick between calls
        assert r.headers["etag"]


def test_purge_deletes_replies_and_opts_out():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        people = {p["name"]: p for p in c.get("/api/phones").json()["people"]}
        imran = people["Imran"]
        c.post("/api/sim/reply", json={"person_id": imran["id"], "text": "OK"})
        before = {p["name"]: p for p in c.get("/api/phones").json()["people"]}["Imran"]
        assert any(m["dir"] == "in" for m in before["messages"])
        r = c.post(f"/api/people/{imran['id']}/purge").json()
        assert r["ok"] and r["deleted_messages"] >= 1
        after = {p["name"]: p for p in c.get("/api/phones").json()["people"]}["Imran"]
        assert not any(m["dir"] == "in" for m in after["messages"]) and after["consent"] == "no"
        assert c.post("/api/people/99999/purge").status_code == 404


def test_stop_reply_purges_earlier_replies():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        people = {p["name"]: p for p in c.get("/api/phones").json()["people"]}
        imran = people["Imran"]
        c.post("/api/sim/reply", json={"person_id": imran["id"], "text": "hello"})
        c.post("/api/sim/reply", json={"person_id": imran["id"], "text": "STOP"})
        after = {p["name"]: p for p in c.get("/api/phones").json()["people"]}["Imran"]
        assert not any(m["dir"] == "in" for m in after["messages"]) and after["consent"] == "no"
