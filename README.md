# 🌤️ Weather Data Pipeline System

An end-to-end **data engineering project**: it extracts live weather data from the
[OpenWeatherMap API](https://openweathermap.org/api), cleans and validates it, loads it into a
normalized **SQLite** database, and provides scheduling, historical analysis, automated
reports, alerts, and pipeline monitoring.

> **Version implemented:** *Standard* (multiple cities, scheduled collection) plus alerts,
> a monitoring dashboard and a demo mode, which covers parts of the *Advanced* option.

## ✨ Features

| Area | What it does |
|------|--------------|
| **Database** | SQLite, 5 normalized (3NF) tables, foreign keys, CHECK constraints, indexes, duplicate protection |
| **Extract** | API client with timeouts, retries + backoff, and API-key redaction in logs |
| **Transform** | Flattens the JSON payload, converts types, rounds values, handles missing fields |
| **Validate** | Required-field and range checks per record, plus database-wide quality checks |
| **Load** | Idempotent inserts (same city + timestamp is never stored twice) |
| **Scheduling** | Built-in interval scheduler (or cron via `scripts/run_pipeline.sh`) |
| **Analysis** | 5 ready-made queries (hottest city, trends, humidity vs rain, seasons, peak hours) |
| **Reports & alerts** | Daily text + CSV report; threshold alerts with a cooldown to avoid spam |
| **Monitoring** | Health status (HEALTHY / WARNING / CRITICAL), run history, data coverage, staleness check |
| **Demo mode** | `--demo` generates realistic synthetic data, so the project runs with **no API key** |

## 📁 Project structure

```
weather-data-pipeline/
├── main.py                 # CLI entry point
├── requirements.txt
├── config/
│   ├── settings.json       # thresholds, valid ranges, API + schedule settings
│   ├── cities.json         # cities to track
│   └── .env.example        # template for your API key
├── src/
│   ├── config.py           # settings, paths, logging
│   ├── database.py         # SQLite access layer
│   ├── api_client.py       # OpenWeatherMap client + demo client
│   ├── etl_pipeline.py     # extract -> transform -> validate -> load
│   ├── validators.py       # record validation + quality checks
│   ├── analytics.py        # historical analysis queries
│   ├── reporter.py         # alerts + daily reports
│   ├── scheduler.py        # automated scheduling
│   └── monitor.py          # health checks + dashboard
├── database/               # schema.sql + sample weather_data.db (synthetic history)
├── tests/                  # unit + integration tests (30 tests)
├── docs/                   # architecture, data dictionary, deployment guide
├── scripts/                # seed_demo_data.py, backup_db.py, run_pipeline.sh
├── logs/                   # sample_pipeline.log
└── reports/                # sample generated reports
```

## 🚀 Quick start

```bash
git clone https://github.com/<your-username>/weather-data-pipeline.git
cd weather-data-pipeline
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Try it immediately (no API key):**

```bash
python main.py run --demo        # one ETL cycle with synthetic data
python main.py health            # monitoring dashboard
python main.py analyze           # historical analysis
python main.py report            # daily report -> reports/
```

**Use real data:**

```bash
cp config/.env.example .env      # then put your OpenWeatherMap key in .env
python main.py run               # one real ETL cycle
python main.py schedule          # keep collecting (default: every 60 min)
```

> New OpenWeatherMap keys can take up to a couple of hours to activate.
> **Never commit `.env`**; it is already in `.gitignore`.

## 🖥️ Commands

| Command | Description |
|---------|-------------|
| `python main.py init` | Create the database and tables |
| `python main.py run [--demo] [--city NAME]` | Run the ETL pipeline once |
| `python main.py schedule [--interval MIN] [--demo]` | Run repeatedly; a daily report is generated automatically |
| `python main.py report [--date YYYY-MM-DD]` | Generate the daily report |
| `python main.py analyze [--days N]` | Run the 5 analysis queries |
| `python main.py health` | Show the monitoring dashboard |
| `python scripts/seed_demo_data.py --days 365` | Fill the DB with synthetic history |
| `python scripts/backup_db.py` | Create a consistent backup of the database |

## 📊 Sample output

```
📊 SYSTEM STATUS: HEALTHY ✅
✅ Status: SUCCESS
📈 Records Loaded: 10 (rejected: 0)

🌤️ CURRENT WEATHER SNAPSHOT:
📍 Chennai: 28.46°C, 64% humidity, Few clouds
📍 Delhi: 22.67°C, 65% humidity, Scattered clouds
...
📊 DATABASE STATISTICS:
• Total records: 29,250
• Cities tracked: 10
• Duplicates: 0  |  Out-of-range: 0
```

The analysis command answers the project questions:

1. **Which city has the highest average temperature?** `avg_temp_by_city()`
2. **Temperature trend over the last 30 days?** `temperature_trend()` / `trend_summary()`
3. **How does humidity correlate with rainfall?** `humidity_rainfall_correlation()`
4. **Which seasons are most extreme?** `seasonal_extremes()` (Winter, Summer, Monsoon, Post-monsoon)
5. **Peak temperature hour per city?** `peak_temperature_hours()` (in each city's local time)

> ⚠️ The bundled `database/weather_data.db` contains **synthetic demo data** so that the
> analysis works out of the box. Delete it and run `python main.py init` to start with a real,
> empty database.

## 🧪 Testing

```bash
python -m unittest discover -s tests -t . -v
# or, if you use pytest:
pytest
```

Tests cover validation, transforms, deduplication, alert cooldown, retry logic, the full
pipeline (including failure paths), analytics queries and health monitoring. They use
temporary databases and never touch the network.

## 🏗️ Design decisions

- **Normalized schema:** cities, weather conditions, observations, runs and alerts live in
  separate tables; observations reference cities and conditions via foreign keys.
- **Idempotent loads:** `UNIQUE(city_id, observed_at)` + `INSERT OR IGNORE`, so re-running is safe.
- **Fault isolation:** one failing city never stops the run. The run is recorded as
  `SUCCESS`, `PARTIAL` or `FAILED` in `pipeline_runs`.
- **UTC everywhere:** timestamps are stored in UTC; local hour is derived from each city's
  timezone offset for peak-hour analysis.
- **Config over code:** thresholds, ranges and cities are edited in `config/`, not in Python.

See [`docs/`](docs) for the architecture diagram, data dictionary and deployment notes.

## 🔭 Ideas for extension

- Switch to PostgreSQL (the SQL is standard; only `database.py` needs a new driver)
- Add a Streamlit dashboard on top of `analytics.py`
- Send alerts via email or Telegram
- Dockerize and deploy on a small cloud VM with cron

## 📄 License

MIT, see [LICENSE](LICENSE).
