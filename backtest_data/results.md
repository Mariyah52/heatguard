# HeatGuard 2025 hot-season back-test (real Open-Meteo archive data)

Window: **1 Jun 2025 - 15 Sep 2025**, hourly, both sites (5136 site-hours total). Not simulated -- this is Open-Meteo's recorded archive for Abu Dhabi (Mussafah) and Karachi (Port Qasim).

## Why heat index alone wasn't enough

- **Abu Dhabi (Mussafah), typical crew**: WBGT/ISO 7243 raised the risk level above what the heat index alone said in **168 of 2568 hours (6.5%)** across the whole window.
- **Abu Dhabi (Mussafah), new_joiner crew**: WBGT/ISO 7243 raised the risk level above what the heat index alone said in **44 of 2568 hours (1.7%)** across the whole window.
- **Karachi (Port Qasim), typical crew**: WBGT/ISO 7243 raised the risk level above what the heat index alone said in **685 of 2568 hours (26.7%)** across the whole window.
- **Karachi (Port Qasim), new_joiner crew**: WBGT/ISO 7243 raised the risk level above what the heat index alone said in **593 of 2568 hours (23.1%)** across the whole window.

**Total across both sites and crews: 1490 hours** where the ISO 7243 cross-check caught something the heat index path missed on its own.

## Lead time on the hottest real recorded days

- **Abu Dhabi (Mussafah)**, hottest real day in the window: **2025-07-29** (peak 46.6°C at 13:00). A typical crew was at High or Extreme for **24 of the day's 24 hours** -- on this day there is effectively no safe window, which is why HeatGuard treats protection as continuous, not just a single peak-hour alert.
- **Abu Dhabi (Mussafah)**, hottest day that still had a below-High morning: **2025-07-18** (peak 44.8°C). From a real 06:00 reading, HeatGuard's outlook warned the crew **180 minutes before High risk began** that day.
- **Karachi (Port Qasim)**, hottest real day in the window: **2025-06-16** (peak 38.0°C at 12:00). A typical crew was at High or Extreme for **20 of the day's 24 hours** -- on this day there is effectively no safe window, which is why HeatGuard treats protection as continuous, not just a single peak-hour alert.
- **Karachi (Port Qasim)**, hottest day that still had a below-High morning: **2025-06-01** (peak 37.7°C). From a real 06:00 reading, HeatGuard's outlook warned the crew **60 minutes before High risk began** that day.

## UAE midday work ban

- Abu Dhabi: **186 hours** of the window fell inside the mandated 12:30-15:00 (15 Jun-15 Sep) outdoor work ban -- HeatGuard forces Extreme + stop-work for all of them automatically.
- Karachi: 0 hours (Pakistan has no equivalent nationwide rule as of this build, so this is expected to be 0).

## Data

Every one of the 5136 hours is in `backtest_data/results.csv` (site, crew, timestamp, both risk levels, WBGT estimate, legal-stop flag) for anyone who wants to check the numbers by hand.
