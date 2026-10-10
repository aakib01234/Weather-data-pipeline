"""Automated scheduling: run the ETL pipeline at a fixed interval."""
import logging
import time
from datetime import datetime, timezone

from . import config
from .api_client import APIError, DemoWeatherClient, WeatherAPIClient
from .database import Database
from .etl_pipeline import run_pipeline
from .monitor import health_check
from .reporter import generate_daily_report

log = logging.getLogger(__name__)


def run_job(db=None, demo=False, cities=None):
    """One scheduled job: ETL cycle followed by a health check."""
    db = db or Database()
    db.init_schema()
    client = DemoWeatherClient() if demo else WeatherAPIClient()
    summary = run_pipeline(db, client, cities or config.load_cities())
    health = health_check(db)
    log.info("Health after run: %s %s", health["status"], health["issues"] or "")
    return summary


def run_scheduler(interval_minutes=None, demo=False, max_runs=None):
    """Run forever (or `max_runs` times). Errors never stop the loop."""
    interval = (interval_minutes or config.SCHEDULE_INTERVAL_MINUTES) * 60
    db = Database()
    last_report_date = None
    runs = 0
    log.info("Scheduler started: every %d minutes (demo=%s)", interval // 60, demo)

    while max_runs is None or runs < max_runs:
        started = time.monotonic()
        try:
            run_job(db=db, demo=demo)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if today != last_report_date:
                generate_daily_report(db, today)
                last_report_date = today
        except APIError as exc:
            log.error("Scheduler could not start job: %s", exc)
        except Exception:
            log.exception("Scheduled job crashed; will retry next interval")
        runs += 1
        if max_runs is not None and runs >= max_runs:
            break
        sleep_for = max(0, interval - (time.monotonic() - started))
        try:
            time.sleep(sleep_for)
        except KeyboardInterrupt:
            log.info("Scheduler stopped by user")
            break
