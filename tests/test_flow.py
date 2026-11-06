import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_heatguard.db"
os.environ["HEATGUARD_FIXTURE"] = str(Path(__file__).parent / "fixtures/openmeteo_2026-11-06.json")
os.environ["CYCLE_SECONDS"] = "100000"

from fastapi.testclient import TestClient  # noqa: E402

from app import weather  # noqa: E402
from app.main import app  # noqa: E402

weather.FIXTURE = os.environ["HEATGUARD_FIXTURE"]


def _phones(c):
    return {p["name"]: p for p in c.get("/api/phones").json()["people"]}


def test_full_flow():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        st = c.get("/api/state").json()
        assert len(st["sites"]) == 3
        assert all(s["weather_status"] in ("live", "cache", "fallback") for s in st["sites"])

        # make all crews on shift for a deterministic test
        for s in st["sites"]:
            for cr in s["crews"]:
                c.patch(f"/api/crews/{cr['id']}", json={"shift_start": "00:00", "shift_end": "23:59"})

        # heatwave at Mussafah
        mussafah = st["sites"][0]["id"]
        c.post("/api/sim/heat", json={"site_id": mussafah, "preset": "heatwave"})
        st = c.get("/api/state").json()
        crews = st["sites"][0]["crews"]
        assert all(cr["outlook"]["current"]["name"] == "Extreme" for cr in crews)
        assert all(cr["outlook"]["source"] == "sim" for cr in crews)
        reasons = crews[0]["outlook"]["current"]["reasons"]
        assert any("sun" in r for r in reasons)

        ph = _phones(c)
        # Urdu-speaking worker got an Urdu alert with two buttons
        imran = ph["Imran"]
        alert = [m for m in imran["messages"] if m["kind"] == "alert"][-1]
        assert "ہیٹ گارڈ" in alert["body"] and len(alert["buttons"]) == 2
        # Hindi and Arabic too
        assert "हीटगार्ड" in [m for m in ph["Rajesh"]["messages"] if m["kind"] == "alert"][-1]["body"]
        assert "HeatGuard" in [m for m in ph["Ahmed"]["messages"] if m["kind"] == "alert"][-1]["body"]
        # pending-consent worker gets no alert
        assert not [m for m in ph["Joseph"]["messages"] if m["kind"] == "alert"]
        # supervisor got the reasons
        assert any("Why:" in m["body"] for m in ph["Hassan"]["messages"])

        # Imran reports feeling unwell -> immediate escalation
        r = c.post("/api/sim/reply", json={"person_id": imran["id"], "text": "UNWELL"}).json()
        assert r["action"] == "escalated"
        ph = _phones(c)
        assert any("998" in m["body"] for m in ph["Imran"]["messages"])
        assert any("⚠️" in m["body"] for m in ph["Priya"]["messages"])
        # Rajesh says OK
        assert c.post("/api/sim/reply", json={"person_id": ph["Rajesh"]["id"], "text": "OK"}).json()["action"] == "ok"

        # 20 minutes pass with no reply from others -> no-reply escalations
        c.post("/api/sim/advance", json={"minutes": 20})
        st = c.get("/api/state").json()
        reasons = {e["reason"] for e in st["escalations"]}
        assert reasons == {"unwell", "no_reply"}

        # supervisor acknowledges by WhatsApp
        r = c.post("/api/sim/reply", json={"person_id": ph["Hassan"]["id"], "text": "ACK"}).json()
        assert r["action"] == "acknowledged"
        # and one from the dashboard
        open_e = [e for e in c.get("/api/state").json()["escalations"] if not e["acknowledged"]]
        assert c.post(f"/api/escalations/{open_e[0]['id']}/ack").status_code == 200

        m = c.get("/api/metrics").json()
        assert m["alerts_sent"] > 0
        assert m["unwell_reports"] == 1 and m["no_reply_escalations"] >= 1
        assert m["response_rate"] is not None and m["median_ack_min"] is not None
        assert {f["language"] for f in m["fairness"]} >= {"اردو", "हिन्दी"}

        # consent: Joseph joins, Samir stays out
        ph = _phones(c)
        assert c.post("/api/sim/reply", json={"person_id": ph["Joseph"]["id"], "text": "YES"}).json()["action"] == "consented"

        # weather feed goes down -> cache, never silently low
        c.delete(f"/api/sim/heat/{mussafah}")
        c.post("/api/sim/feed", json={"down": True})
        c.post("/api/sim/advance", json={"minutes": 30})
        st = c.get("/api/state").json()
        assert all(s["weather_status"] in ("cache", "fallback") for s in st["sites"])
        c.post("/api/sim/feed", json={"down": False})


def test_webhook_verify_and_receive():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        r = c.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "heatguard-verify",
                                      "hub.challenge": "42"})
        assert r.text == "42"
        assert c.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x"}).status_code == 403
        ph = _phones(c)
        payload = {"entry": [{"changes": [{"value": {"messages": [
            {"from": ph["Joseph"]["phone"].lstrip("+"), "type": "text", "text": {"body": "yes"}}]}}]}]}
        assert c.post("/webhook", json=payload).json()["handled"] == 1
        assert _phones(c)["Joseph"]["consent"] == "yes"
