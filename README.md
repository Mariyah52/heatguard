# HeatGuard

Heat-risk early warning for outdoor crews. Built by IMADI Tech for the Future Health Digital Innovation Challenge, Challenge 07: Climate-Resilient Worker Health.

HeatGuard reads live weather for each work site, adjusts the risk for each crew's workload, clothing and acclimatisation, warns supervisors before the heat peaks, and sends crews WhatsApp alerts in English, Urdu, Arabic or Hindi. Workers tap "I'm OK" or "Feeling unwell"; an unwell report, or no reply, goes straight to the supervisor and first-aider.

## Try the demo

Open the app and choose **Continue as guest**. The demo company has fictional crews in Abu Dhabi and Karachi.

1. On **Sites**, pick a site and press **Heatwave 46°C**. Crews go to Extreme and alerts go out.
2. Open **Phones**, choose a worker, and tap **Feeling unwell**. The supervisor and first-aider get an escalation at once.
3. Press **Skip ahead 20 minutes**. Workers who didn't answer are escalated.
4. Reply **ACK** as the supervisor, or press **Mark as handled**.
5. Press **Cut the weather feed** to see the safe fallback.
6. Open **Results** for lead time, false alarms, response rates and the language fairness check.

## How risk is calculated

`app/risk.py` is pure, tested code:

1. Heat index from air temperature and humidity (US National Weather Service Rothfusz regression with its adjustments).
2. Sun: up to +15 °F in direct sun, scaled by measured solar radiation (OSHA notes direct sun can add up to 15 °F).
3. Bands from OSHA heat-index guidance: below 91 °F Low, 91–103 °F Caution, 103–115 °F High, above 115 °F Extreme.
4. One level up for heavy work or non-breathable clothing (OSHA), one more for workers with under 7 days in the heat. Applied only from a heat index of 80 °F, so cool mornings don't raise false alarms. At most two levels.
5. UAE midday break: no outdoor work 12:30–15:00, 15 June – 15 September.
6. No fresh data: the last forecast is used for up to 6 hours, then a cautious default schedule (Caution all day, High 11:00–16:00). Never lower.

Every score lists its reasons, so supervisors can see why an alert fired.

## Run locally

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
# offline: replay a real saved day instead of calling the weather service
HEATGUARD_FIXTURE=tests/fixtures/openmeteo_2026-11-06.json uvicorn app.main:app
pytest
```

## Deploy (Render)

`render.yaml` defines the service. Set:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL (for example Neon). SQLite is used if unset. |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` | Meta WhatsApp Cloud API. Without them, messages stay in the dashboard outbox. |
| `WHATSAPP_LIVE_NUMBERS` | Comma-separated numbers allowed to receive real messages, so fictional demo numbers are never messaged. |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification token (callback URL: `/webhook`). |

## Data sources

| Source | Use | Licence |
| --- | --- | --- |
| Open-Meteo forecast API | Temperature, humidity, wind, solar radiation | CC BY 4.0; free tier is non-commercial. A paid pilot needs a paid plan. |
| OSHA heat-index guidance | Risk bands and protective actions | Public guidance |
| UAE midday break rule | Legal stop window | Public regulation |
| Demo crews and people | Demo only | Fictional, created by IMADI Tech |

`tests/fixtures/openmeteo_2026-11-06.json` is real Open-Meteo data for Mussafah (Abu Dhabi) and Port Qasim (Karachi) on 6 November 2026, used for tests and offline runs.

## Worker protection

- Workers join only by replying YES; STOP removes them.
- Stored: phone number, crew, language and replies. No location tracking, no health history.
- Supervisors see crew-level status; a first name appears only while an escalation is open.
- Replies are deleted after 30 days.
- HeatGuard is not a medical device and doesn't diagnose; anyone unwell is routed to a person.

## Limitations

- Translations should be reviewed by native speakers before a real pilot.
- WhatsApp only allows free-form and button messages within 24 hours of a worker's last message; a real deployment needs approved message templates for alerts outside that window.
- The heat index is a shade-based measure; it is a practical proxy, not a substitute for on-site WBGT measurement.
- The fixture replay and simulator are for demonstration; results in the Results view come from simulated use.

## Licence and third-party components

Code © 2026 IMADI Tech (Maria Aziz). Uses FastAPI, SQLAlchemy, Uvicorn and httpx (MIT/BSD licences), Google Fonts Archivo and Noto (SIL Open Font License).
