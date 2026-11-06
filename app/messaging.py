"""Outgoing messages.

Every message is stored first (so the dashboard and metrics always see it), then
sent through the WhatsApp Cloud API when WHATSAPP_TOKEN and WHATSAPP_PHONE_ID are
set. Without them, messages stay in the dashboard outbox: the demo still works.
"""

from __future__ import annotations

import os

import httpx

from .models import Message, Person

TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
GRAPH = "https://graph.facebook.com/v21.0"
# Only numbers on this list get real WhatsApp messages (protects fake demo numbers).
LIVE_NUMBERS = {n.strip() for n in os.getenv("WHATSAPP_LIVE_NUMBERS", "").split(",") if n.strip()}


def send(db, person: Person, body: str, kind: str, now, level: int | None = None,
         buttons: list[dict] | None = None) -> Message:
    msg = Message(person_id=person.id, direction="out", kind=kind, level=level, body=body,
                  buttons=buttons, created_at=now, delivery="outbox")
    db.add(msg)
    db.flush()
    if TOKEN and PHONE_ID and person.phone in LIVE_NUMBERS:
        try:
            _send_whatsapp(person.phone, body, buttons)
            msg.delivery = "sent"
        except Exception as e:
            msg.delivery = "failed"
            msg.delivery_error = str(e)[:300]
    return msg


def _send_whatsapp(phone: str, body: str, buttons: list[dict] | None):
    to = phone.lstrip("+")
    if buttons:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "interactive",
                   "interactive": {"type": "button", "body": {"text": body[:1024]},
                                   "action": {"buttons": [
                                       {"type": "reply", "reply": {"id": b["id"],
                                                                   "title": b["title"][:20]}}
                                       for b in buttons[:3]]}}}
    else:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text",
                   "text": {"body": body[:4096]}}
    last = None
    for _ in range(2):
        try:
            r = httpx.post(f"{GRAPH}/{PHONE_ID}/messages", json=payload, timeout=10,
                           headers={"Authorization": f"Bearer {TOKEN}"})
            if r.status_code < 300:
                return
            last = RuntimeError(f"WhatsApp API {r.status_code}: {r.text[:200]}")
        except Exception as e:
            last = e
    raise last
