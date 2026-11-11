from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select

from . import service, weather
from .models import Crew, Person, SessionLocal, Site, init_db
from .seed import seed_demo

log = logging.getLogger("heatguard")
CYCLE_SECONDS = int(os.getenv("CYCLE_SECONDS", "900"))      # 15 minutes
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "heatguard-verify")
STATIC = Path(__file__).parent / "static"


async def _loop():
    while True:
        try:
            with SessionLocal() as db:
                service.run_cycle(db)
        except Exception:
            log.exception("cycle failed; will retry next interval")
        await asyncio.sleep(CYCLE_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        needs_seed = not db.scalars(select(Site)).first()
        # Release this session's transaction now. seed_demo() runs slow DDL
        # (drop_all/create_all) on a separate engine-level connection; if we
        # leave the SELECT's transaction open on `db` while that DDL runs
        # against a cold-starting Neon compute, Neon kills this session for
        # sitting idle-in-transaction before seed_demo ever gets to use it.
        db.commit()
        if needs_seed:
            seed_demo(db)
    task = asyncio.create_task(_loop())
    yield
    task.cancel()


app = FastAPI(title="HeatGuard", version="0.1.0", lifespan=lifespan,
              description="Heat-risk early warning for outdoor crews. Future Health Digital "
                          "Innovation Challenge, Challenge 07.")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/state")
def get_state():
    with SessionLocal() as db:
        return service.state(db)


@app.get("/api/phones")
def get_phones():
    with SessionLocal() as db:
        return service.phone_view(db)


@app.get("/api/metrics")
def get_metrics():
    with SessionLocal() as db:
        return service.metrics(db)


@app.post("/api/cycle")
def cycle():
    with SessionLocal() as db:
        return service.run_cycle(db)


class CrewUpdate(BaseModel):
    workload: str | None = None
    clothing: str | None = None
    acclimatised_days: int | None = None
    shaded: bool | None = None
    shift_start: str | None = None
    shift_end: str | None = None


@app.patch("/api/crews/{crew_id}")
def update_crew(crew_id: int, body: CrewUpdate):
    with SessionLocal() as db:
        crew = db.get(Crew, crew_id)
        if not crew:
            raise HTTPException(404, "crew not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(crew, k, v)
        db.commit()
        return service.run_cycle(db)


@app.post("/api/escalations/{esc_id}/ack")
def ack(esc_id: int):
    with SessionLocal() as db:
        if not service.ack_escalation(db, esc_id, "Dashboard"):
            raise HTTPException(404, "not found or already handled")
        return {"ok": True}


# ---------- simulator (demo only) ----------

PRESETS = {
    "heatwave": {"temp_c": 46, "rh": 25, "radiation": 950, "label": "Heatwave: 46°C, dry, full sun"},
    "humid": {"temp_c": 37, "rh": 65, "radiation": 700, "label": "Humid coast: 37°C, 65% humidity"},
    "warm": {"temp_c": 33, "rh": 45, "radiation": 600, "label": "Warm day: 33°C"},
}


class SimHeat(BaseModel):
    site_id: int
    preset: str | None = None
    temp_c: float | None = None
    rh: float | None = None
    radiation: float | None = None
    hours: int = 4


@app.post("/api/sim/heat")
def sim_heat(body: SimHeat):
    with SessionLocal() as db:
        site = db.get(Site, body.site_id)
        if not site:
            raise HTTPException(404, "site not found")
        p = PRESETS.get(body.preset or "", {})
        site.sim = {"temp_c": body.temp_c or p.get("temp_c", 40), "rh": body.rh or p.get("rh", 30),
                    "radiation": body.radiation if body.radiation is not None else p.get("radiation", 800),
                    "hours": body.hours, "label": p.get("label", "Custom conditions")}
        db.commit()
        return service.run_cycle(db)


@app.delete("/api/sim/heat/{site_id}")
def sim_clear(site_id: int):
    with SessionLocal() as db:
        site = db.get(Site, site_id)
        site.sim = None
        db.commit()
        return service.run_cycle(db)


class Minutes(BaseModel):
    minutes: int = 20


@app.post("/api/sim/advance")
def sim_advance(body: Minutes):
    with SessionLocal() as db:
        service.advance_clock(db, max(1, min(body.minutes, 240)))
        db.commit()
        return service.run_cycle(db)


class Feed(BaseModel):
    down: bool


@app.post("/api/sim/feed")
def sim_feed(body: Feed):
    weather.FAIL_FEED["on"] = body.down
    with SessionLocal() as db:
        if body.down:
            # force a refresh attempt so the outage shows immediately
            for s in db.scalars(select(Site)).all():
                s.weather_fetched_at = None if s.weather is None else s.weather_fetched_at
                s.weather_status = "cache" if s.weather else "fallback"
        db.commit()
        return service.run_cycle(db)


class SimReply(BaseModel):
    person_id: int
    text: str


@app.post("/api/sim/reply")
def sim_reply(body: SimReply):
    with SessionLocal() as db:
        p = db.get(Person, body.person_id)
        if not p:
            raise HTTPException(404, "person not found")
        return service.handle_inbound(db, p.phone, body.text)


@app.post("/api/demo/reset")
def reset():
    weather.FAIL_FEED["on"] = False
    with SessionLocal() as db:
        seed_demo(db)
        return service.run_cycle(db)


# ---------- WhatsApp Cloud API webhook ----------

@app.get("/webhook", include_in_schema=False)
def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "verification failed")


@app.post("/webhook", include_in_schema=False)
async def receive(request: Request):
    data = await request.json()
    handled = 0
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []):
                phone = "+" + m.get("from", "")
                if m.get("type") == "interactive":
                    text = m["interactive"].get("button_reply", {}).get("id", "")
                elif m.get("type") == "button":
                    text = m.get("button", {}).get("payload", "")
                else:
                    text = m.get("text", {}).get("body", "")
                with SessionLocal() as db:
                    service.handle_inbound(db, phone, text)
                handled += 1
    return {"handled": handled}
