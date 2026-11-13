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
5. **WBGT / ISO 7243 cross-check** (`app/wbgt.py`): a WBGT estimate from the same temperature/humidity/solar/wind fields (Stull wet-bulb regression + a solar- and wind-scaled globe-temperature estimate), checked against ISO 7243's reference limits for the crew's workload class and acclimatisation. HeatGuard takes the worse of this and the heat-index level -- it can only raise a warning, never suppress one. This exists because heat index alone can under-call humid-but-moderate conditions; see the back-test below for how often that actually happened over a real summer.
6. UAE midday break: no outdoor work 12:30–15:00, 15 June – 15 September.
7. No fresh data: the last forecast is used for up to 6 hours, then a cautious default schedule (Caution all day, High 11:00–16:00). Never lower.

Every score lists its reasons, so supervisors can see why an alert fired.

## 2025 hot-season back-test

`scripts/backtest_2025.py` runs the real risk engine over Open-Meteo's recorded archive for the whole 1 Jun – 15 Sep 2025 window (not a 1-2 day sample), for both Abu Dhabi (Mussafah) and Karachi (Port Qasim):

- The WBGT/ISO 7243 cross-check raised the risk level above what heat index alone said in **1,490 of 10,272 crew-hours (14.5%)** across the window -- most of it in Karachi, where moderate temperatures with very high humidity are exactly the condition heat index underrates.
- On each site's single hottest real day, a typical crew was at High or Extreme for **24/24 hours in Abu Dhabi** (29 Jul, peak 46.6 °C) and **20/24 hours in Karachi** (16 Jun, peak 38.0 °C) -- there is effectively no safe window on the worst days, which is why HeatGuard treats protection as continuous rather than a single peak-hour alert.
- On the hottest day that still had a below-High morning, HeatGuard's outlook warned a typical crew **180 minutes ahead in Abu Dhabi** (18 Jul) and **60 minutes ahead in Karachi** (1 Jun).

Full numbers: `backtest_data/results.md` (summary) and `backtest_data/results.csv` (all 10,272 crew-hours). Run it yourself with `PYTHONPATH=. python scripts/backtest_2025.py`.

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
| Open-Meteo archive API | 2025 hot-season back-test data | Same licence as above |
| OSHA heat-index guidance | Risk bands and protective actions | Public guidance |
| ISO 7243 reference WBGT limits | WBGT/ISO 7243 cross-check | Public standard reference values |
| UAE midday break rule | Legal stop window | Public regulation |
| Demo crews and people | Demo only | Fictional, created by IMADI Tech |

`tests/fixtures/openmeteo_2026-11-06.json` is real Open-Meteo data for Mussafah (Abu Dhabi) and Port Qasim (Karachi) on 6 November 2026, used for tests and offline runs. `backtest_data/*_2025_summer.json` is real Open-Meteo **archive** data for both sites, 1 Jun – 15 Sep 2025, used for the back-test above.

## Worker protection

- Workers join only by replying YES; STOP removes them.
- Stored: phone number, crew, language and replies. No location tracking, no health history.
- Supervisors see crew-level status; a first name appears only while an escalation is open.
- Replies are deleted after 30 days.
- HeatGuard is not a medical device and doesn't diagnose; anyone unwell is routed to a person.

## Limitations

- Translations should be reviewed by native speakers before a real pilot.
- WhatsApp only allows free-form and button messages within 24 hours of a worker's last message; a real deployment needs approved message templates for alerts outside that window.
- WBGT here is estimated from weather-API fields (temperature, humidity, solar radiation, wind), using published closed-form approximations (Stull wet-bulb; a solar/wind-scaled globe-temperature estimate) -- not a measurement from an actual natural-wet-bulb and black-globe thermometer (ISO 7726). It's good enough to flag "this crew is in ISO 7243 territory", not instrument-grade.
- The fixture replay and simulator are for demonstration; results in the Results view come from simulated use.

## Licence and third-party components

Code © 2026 IMADI Tech (Maria Aziz). Uses FastAPI, SQLAlchemy, Uvicorn and httpx (MIT/BSD licences), Google Fonts Archivo and Noto (SIL Open Font License).
