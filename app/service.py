"""HeatGuard core loop: assess every crew, alert, check in, escalate, measure."""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import i18n, weather
from .messaging import send
from .models import (Assessment, CheckIn, Crew, Escalation, Message, Person, Setting, Site,
                     Warning)
from .risk import (CAUTION, EXTREME, HIGH, LEVELS, CrewProfile, fallback_level, outlook)

COMPANY = "Demo Contracting LLC"
CHECKIN_DUE = {HIGH: timedelta(minutes=30), EXTREME: timedelta(minutes=15)}
REPEAT_ALERT = timedelta(minutes=60)
WARN_WINDOW_MIN = 180
RETENTION = timedelta(days=30)


# ---------- clock (the simulator can fast-forward time) ----------

def _setting(db, key, default=""):
    s = db.get(Setting, key)
    return s.value if s else default


def _set(db, key, value):
    s = db.get(Setting, key)
    if s:
        s.value = str(value)
    else:
        db.add(Setting(key=key, value=str(value)))


def now_utc(db) -> datetime:
    off = int(_setting(db, "clock_offset_min", "0") or 0)
    return datetime.now(timezone.utc).replace(tzinfo=None).replace(microsecond=0) + timedelta(minutes=off)


def advance_clock(db, minutes: int):
    _set(db, "clock_offset_min", int(_setting(db, "clock_offset_min", "0") or 0) + minutes)


def local(site: Site, utc: datetime) -> datetime:
    return utc + timedelta(seconds=site.tz_offset_s)


def _in_shift(crew: Crew, now_local: datetime) -> bool:
    t = now_local.strftime("%H:%M")
    return crew.shift_start <= t < crew.shift_end


def _profile(crew: Crew) -> CrewProfile:
    return CrewProfile(crew.workload, crew.clothing, crew.acclimatised_days, crew.shaded)


# ---------- weather per site ----------

def site_conditions(db, site: Site, now: datetime):
    """Returns (current Conditions or None, hourly list, source)."""
    if site.weather_fetched_at is None or now - site.weather_fetched_at >= weather.REFRESH:
        try:
            data = weather.fetch(site.lat, site.lon)
            site.weather, site.weather_fetched_at = data, now
            site.tz_offset_s = int(data.get("utc_offset_seconds", site.tz_offset_s))
            site.weather_error, fresh = "", True
        except Exception as e:
            site.weather_error, fresh = str(e)[:300], False
    else:
        fresh = site.weather_status == "live"
    now_local = local(site, now)
    cur, hours, source = None, [], "fallback"
    if site.weather and site.weather_fetched_at and now - site.weather_fetched_at <= weather.CACHE_MAX_AGE:
        live_cur, hours, _ = weather.parse(site.weather)
        if fresh:
            cur, source = live_cur, "live"
        else:
            cur, source = weather.current_from_hourly(hours, now_local), "cache"
            if cur is None:
                source = "fallback"
    if site.sim:
        cur, hours = weather.apply_sim(site.sim, hours or _flat_hours(now_local), now_local)
        source = "sim"
    site.weather_status = source
    return cur, hours, source


def _flat_hours(now_local):
    from .risk import Conditions, HourPoint
    base = now_local.replace(minute=0, second=0, microsecond=0)
    return [HourPoint(base + timedelta(hours=i), Conditions(30, 40, 500)) for i in range(-1, 12)]


# ---------- the cycle ----------

def run_cycle(db) -> dict:
    now = now_utc(db)
    summary = {"at": now.isoformat(), "alerts": 0, "warnings": 0, "escalations": 0}
    for site in db.scalars(select(Site)).all():
        cur, hours, source = site_conditions(db, site, now)
        now_local = local(site, now)
        for crew in site.crews:
            if source == "fallback" or cur is None:
                risk = fallback_level(now_local)
                out = {"current": risk.to_dict(), "peak_level": risk.level,
                       "peak_name": risk.name, "peak_at": None, "first_high_at": None,
                       "lead_minutes": None, "hours": []}
                first_high = None
            else:
                o = outlook(now_local, cur, hours, _profile(crew), site.country, horizon_h=6)
                out = o.to_dict(now_local)
                first_high = o.first_high_at
            out["source"] = source
            out["at_local"] = now_local.isoformat()
            crew.current = out
            db.add(Assessment(crew_id=crew.id, at=now, level=out["current"]["level"],
                              source=source))
            if _in_shift(crew, now_local):
                summary["alerts"] += _alert_crew(db, site, crew, out, now)
                summary["warnings"] += _warn_ahead(db, site, crew, out, first_high, now)
    summary["escalations"] += _escalate_overdue(db, now)
    _resolve_warnings(db, now)
    _purge(db, now)
    db.commit()
    return summary


def _workers(crew: Crew):
    return [p for p in crew.people if p.role == "worker" and p.consent == "yes"]


def _site_staff(db, site_id: int, roles=("supervisor", "first_aider")):
    return db.scalars(select(Person).where(Person.site_id == site_id,
                                           Person.role.in_(roles))).all()


def _alert_crew(db, site, crew, out, now) -> int:
    level = out["current"]["level"]
    if level < (crew.last_alert_level if crew.last_alert_level >= 0 else 0):
        crew.last_alert_level = level          # risk fell; a later rise alerts again
    if level < CAUTION:
        return 0
    rising = level > crew.last_alert_level
    repeat = level >= HIGH and (crew.last_alert_at is None or now - crew.last_alert_at >= REPEAT_ALERT)
    if not (rising or repeat):
        return 0
    c = out["current"]["feels_like_c"]
    c_txt = "—" if c != c else f"{c:.0f}"   # NaN in fallback mode
    sent = 0
    for w in _workers(crew):
        lang = w.language
        body = i18n.t("alert", lang, level=i18n.level_name(level, lang), site=site.name,
                      c=c_txt, action=i18n.action(level, lang))
        buttons = None
        if level >= HIGH:
            body += "\n" + i18n.t("ask_ok", lang)
            buttons = [{"id": "OK", "title": i18n.t("btn_ok", lang)},
                       {"id": "UNWELL", "title": i18n.t("btn_unwell", lang)}]
            db.add(CheckIn(person_id=w.id, crew_id=crew.id, level=level, sent_at=now,
                           due_at=now + CHECKIN_DUE[level]))
        send(db, w, body, "alert", now, level, buttons)
        sent += 1
    why = "; ".join(out["current"]["reasons"])
    for s in _site_staff(db, site.id, ("supervisor",)):
        send(db, s, i18n.t("sup_alert", s.language, crew=crew.name, site=site.name,
                           level=i18n.level_name(level, s.language), c=c_txt, why=why,
                           action=i18n.action(level, s.language)), "alert", now, level)
    crew.last_alert_level, crew.last_alert_at = level, now
    return sent


def _warn_ahead(db, site, crew, out, first_high, now) -> int:
    lead = out.get("lead_minutes")
    if first_high is None or lead is None or not (0 < lead <= WARN_WINDOW_MIN):
        return 0
    predicted_utc = first_high - timedelta(seconds=site.tz_offset_s)
    exists = db.scalar(select(Warning).where(Warning.crew_id == crew.id,
                                             Warning.predicted_for == predicted_utc))
    if exists:
        return 0
    lvl = next(h["level"] for h in out["hours"] if h["t"] == first_high.isoformat())
    db.add(Warning(crew_id=crew.id, sent_at=now, predicted_level=lvl, predicted_for=predicted_utc))
    for s in _site_staff(db, site.id, ("supervisor",)):
        send(db, s, i18n.t("sup_warning", s.language, crew=crew.name, site=site.name,
                           level=i18n.level_name(lvl, s.language),
                           time=first_high.strftime("%H:%M"), mins=lead), "warning", now, lvl)
    return 1


def escalate(db, person: Person, crew: Crew, reason: str, level: int, now,
             checkin: CheckIn | None = None) -> Escalation:
    if checkin:
        checkin.escalated = True
    esc = Escalation(crew_id=crew.id, person_id=person.id, reason=reason, level=level,
                     created_at=now)
    db.add(esc)
    site = crew.site
    emergency = i18n.EMERGENCY.get(site.country, "your local emergency number")
    t_local = local(site, now).strftime("%H:%M")
    for s in _site_staff(db, site.id):
        if reason == "unwell":
            body = i18n.t("esc_unwell", s.language, name=person.first_name, crew=crew.name,
                          site=site.name, time=t_local, emergency=emergency)
        else:
            mins = int((now - checkin.sent_at).total_seconds() // 60) if checkin else 0
            body = i18n.t("esc_no_reply", s.language, name=person.first_name, crew=crew.name,
                          site=site.name, level=i18n.level_name(level, s.language), mins=mins)
        send(db, s, body, "escalation", now, level)
    if reason == "unwell":
        send(db, person, i18n.t("unwell_reply", person.language, emergency=emergency),
             "info", now, level)
    return esc


def _escalate_overdue(db, now) -> int:
    n = 0
    overdue = db.scalars(select(CheckIn).where(CheckIn.reply.is_(None),
                                               CheckIn.escalated.is_(False),
                                               CheckIn.due_at <= now)).all()
    for ci in overdue:
        person, crew = db.get(Person, ci.person_id), db.get(Crew, ci.crew_id)
        if person.consent != "yes":
            ci.escalated = True
            continue
        escalate(db, person, crew, "no_reply", ci.level, now, ci)
        n += 1
    return n


def _resolve_warnings(db, now):
    for w in db.scalars(select(Warning).where(Warning.actual_level.is_(None),
                                              Warning.predicted_for <= now)).all():
        near = db.scalars(select(Assessment).where(
            Assessment.crew_id == w.crew_id,
            Assessment.at >= w.predicted_for - timedelta(minutes=35),
            Assessment.at <= w.predicted_for + timedelta(minutes=35))).all()
        if near:
            w.actual_level = max(a.level for a in near)


def _purge(db, now):
    old = db.scalars(select(Message).where(Message.direction == "in",
                                           Message.created_at < now - RETENTION)).all()
    for m in old:
        m.body = "[deleted after 30 days]"


# ---------- inbound replies (WhatsApp webhook or simulator) ----------

def handle_inbound(db, phone: str, text: str) -> dict:
    person = db.scalar(select(Person).where(Person.phone == phone))
    if not person:
        return {"ok": False, "error": "unknown number"}
    now = now_utc(db)
    raw = (text or "").strip()
    word = raw.upper()
    # a WhatsApp button reply arrives as its id; show what the worker actually tapped
    shown = {"OK": i18n.t("btn_ok", person.language),
             "UNWELL": i18n.t("btn_unwell", person.language)}.get(word, raw)
    db.add(Message(person_id=person.id, direction="in", kind="reply", body=shown,
                   created_at=now, delivery="received"))
    result = {"ok": True, "person": person.first_name, "action": "noted"}
    if word in ("YES", "Y", "JOIN"):
        person.consent, person.consent_at = "yes", now
        send(db, person, i18n.t("consent_yes", person.language), "consent", now)
        result["action"] = "consented"
    elif word in ("STOP", "UNSUBSCRIBE"):
        person.consent, person.consent_at = "no", now
        send(db, person, i18n.t("consent_stop", person.language), "consent", now)
        result["action"] = "opted_out"
    elif word == "ACK" and person.role in ("supervisor", "first_aider"):
        esc = db.scalar(select(Escalation).join(Crew).where(
            Crew.site_id == person.site_id, Escalation.acknowledged_at.is_(None))
            .order_by(Escalation.created_at))
        if esc:
            _ack(db, esc, person.first_name, now)
            site = db.get(Site, person.site_id)
            send(db, person, i18n.t("ack_thanks", person.language,
                                    time=local(site, now).strftime("%H:%M")), "info", now)
            result["action"] = "acknowledged"
    elif person.role == "worker" and person.consent == "yes" and (
            word in ("OK", "1", "UNWELL", "2", "SICK", "HELP")
            or raw in (i18n.t("btn_ok", person.language), i18n.t("btn_unwell", person.language))):
        unwell = word in ("UNWELL", "2", "SICK", "HELP") or raw == i18n.t("btn_unwell", person.language)
        ci = db.scalar(select(CheckIn).where(CheckIn.person_id == person.id,
                                             CheckIn.reply.is_(None))
                       .order_by(CheckIn.sent_at.desc()))
        if ci:
            ci.reply, ci.replied_at = ("unwell" if unwell else "ok"), now
        crew = person.crew
        if unwell:
            level = (crew.current or {}).get("current", {}).get("level", HIGH)
            escalate(db, person, crew, "unwell", level, now, ci)
            result["action"] = "escalated"
        else:
            send(db, person, i18n.t("thanks_ok", person.language), "info", now)
            result["action"] = "ok"
    db.commit()
    return result


def _ack(db, esc: Escalation, by: str, now):
    esc.acknowledged_at, esc.acknowledged_by = now, by


def ack_escalation(db, esc_id: int, by: str = "Dashboard") -> bool:
    esc = db.get(Escalation, esc_id)
    if not esc or esc.acknowledged_at:
        return False
    _ack(db, esc, by, now_utc(db))
    db.commit()
    return True


# ---------- metrics ----------

def metrics(db) -> dict:
    msgs = db.scalars(select(Message)).all()
    alerts = [m for m in msgs if m.kind == "alert" and m.direction == "out"]
    people = {p.id: p for p in db.scalars(select(Person)).all()}
    worker_alerts = [m for m in alerts if people[m.person_id].role == "worker"]
    by_level = {name: sum(1 for m in worker_alerts if m.level == i) for i, name in enumerate(LEVELS)}

    warns = db.scalars(select(Warning)).all()
    leads = [(w.predicted_for - w.sent_at).total_seconds() / 60 for w in warns]
    resolved = [w for w in warns if w.actual_level is not None]
    false_alarms = [w for w in resolved if w.actual_level < HIGH]

    cis = db.scalars(select(CheckIn)).all()
    now = now_utc(db)
    closed = [c for c in cis if c.reply or c.due_at <= now]
    replied = [c for c in closed if c.reply]
    ok = [c for c in replied if c.reply == "ok"]
    reply_mins = [(c.replied_at - c.sent_at).total_seconds() / 60 for c in replied]

    escs = db.scalars(select(Escalation)).all()
    acked = [e for e in escs if e.acknowledged_at]
    ack_mins = [(e.acknowledged_at - e.created_at).total_seconds() / 60 for e in acked]

    sources = db.scalars(select(Assessment.source)).all()
    src = {k: sources.count(k) for k in ("live", "cache", "sim", "fallback")}

    fairness = []
    for lang, label in i18n.LANGS.items():
        lc = [c for c in closed if people[c.person_id].language == lang]
        lr = [c for c in lc if c.reply]
        if not lc:
            continue
        fairness.append({"language": label, "checkins": len(lc),
                         "response_rate": round(100 * len(lr) / len(lc)),
                         "median_reply_min": round(statistics.median(
                             [(c.replied_at - c.sent_at).total_seconds() / 60 for c in lr]), 1)
                         if lr else None})

    def med(xs):
        return round(statistics.median(xs), 1) if xs else None

    return {
        "alerts_sent": len(worker_alerts),
        "alerts_by_level": by_level,
        "warnings_sent": len(warns),
        "median_lead_min": med(leads),
        "warnings_checked": len(resolved),
        "false_alarm_rate": round(100 * len(false_alarms) / len(resolved)) if resolved else None,
        "checkins": len(closed),
        "response_rate": round(100 * len(replied) / len(closed)) if closed else None,
        "ok_rate": round(100 * len(ok) / len(replied)) if replied else None,
        "median_reply_min": med(reply_mins),
        "unwell_reports": sum(1 for e in escs if e.reason == "unwell"),
        "no_reply_escalations": sum(1 for e in escs if e.reason == "no_reply"),
        "open_escalations": sum(1 for e in escs if not e.acknowledged_at),
        "median_ack_min": med(ack_mins),
        "data_sources": src,
        "fairness": fairness,
    }


# ---------- dashboard state ----------

def state(db) -> dict:
    now = now_utc(db)
    sites = []
    for s in db.scalars(select(Site)).all():
        crews = []
        for c in s.crews:
            cis = db.scalars(select(CheckIn).where(CheckIn.crew_id == c.id)
                             .order_by(CheckIn.sent_at.desc())).all()
            latest = {}
            for ci in cis:
                latest.setdefault(ci.person_id, ci)
            open_ci = [ci for ci in latest.values() if ci.reply is None and not ci.escalated]
            workers = [p for p in c.people if p.role == "worker"]
            crews.append({
                "id": c.id, "name": c.name, "task": c.task, "workload": c.workload,
                "clothing": c.clothing, "acclimatised_days": c.acclimatised_days,
                "shaded": c.shaded, "shift": f"{c.shift_start}–{c.shift_end}",
                "in_shift": _in_shift(c, local(s, now)),
                "outlook": c.current,
                "workers": len(workers),
                "consented": sum(1 for p in workers if p.consent == "yes"),
                "checkins": {"ok": sum(1 for ci in latest.values() if ci.reply == "ok"),
                             "unwell": sum(1 for ci in latest.values() if ci.reply == "unwell"),
                             "waiting": len(open_ci),
                             "no_reply": sum(1 for ci in latest.values()
                                             if ci.reply is None and ci.escalated)},
            })
        sites.append({"id": s.id, "name": s.name, "city": s.city, "country": s.country,
                      "local_time": local(s, now).strftime("%a %d %b, %H:%M"),
                      "weather_status": s.weather_status, "weather_error": s.weather_error,
                      "weather_age_min": int((now - s.weather_fetched_at).total_seconds() // 60)
                      if s.weather_fetched_at else None,
                      "sim": s.sim, "crews": crews})
    escs = []
    for e in db.scalars(select(Escalation).order_by(Escalation.created_at.desc())).all()[:30]:
        crew, p = db.get(Crew, e.crew_id), db.get(Person, e.person_id)
        escs.append({"id": e.id, "reason": e.reason, "level": e.level,
                     "level_name": LEVELS[e.level], "crew": crew.name, "site": crew.site.name,
                     # first name only, and only while the escalation is open: safety need, not a record
                     "person": p.first_name if not e.acknowledged_at else "worker",
                     "minutes_ago": int((now - e.created_at).total_seconds() // 60),
                     "acknowledged": bool(e.acknowledged_at),
                     "acknowledged_by": e.acknowledged_by,
                     "ack_minutes": int((e.acknowledged_at - e.created_at).total_seconds() // 60)
                     if e.acknowledged_at else None})
    return {"now_utc": now.isoformat(), "clock_offset_min": int(_setting(db, "clock_offset_min", "0") or 0),
            "feed_down": weather.FAIL_FEED["on"], "company": COMPANY,
            "sites": sites, "escalations": escs}


def phone_view(db) -> dict:
    """Simulated phones for the demo: each person's WhatsApp thread."""
    people = db.scalars(select(Person).order_by(Person.site_id, Person.crew_id, Person.id)).all()
    out = []
    for p in people:
        msgs = db.scalars(select(Message).where(Message.person_id == p.id)
                          .order_by(Message.created_at.desc(), Message.id.desc())).all()[:25]
        msgs.reverse()
        site = db.get(Site, p.site_id) if p.site_id else None
        has_open = db.scalar(select(CheckIn).where(CheckIn.person_id == p.id,
                                                   CheckIn.reply.is_(None))) is not None
        out.append({"id": p.id, "name": p.first_name, "role": p.role, "language": p.language,
                    "phone": p.phone, "consent": p.consent,
                    "crew": p.crew.name if p.crew else None,
                    "site": site.name if site else None,
                    "open_checkin": has_open,
                    "messages": [{"id": m.id, "dir": m.direction, "kind": m.kind, "body": m.body,
                                  "buttons": m.buttons, "delivery": m.delivery,
                                  "at": (local(site, m.created_at) if site else m.created_at).isoformat()} for m in msgs]})
    return {"people": out}
