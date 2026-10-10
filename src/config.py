"""Central configuration: paths, settings.json, environment variables, logging."""
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


SETTINGS = _load_json(CONFIG_DIR / "settings.json")

API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
API_BASE_URL = SETTINGS["api"]["base_url"]
API_TIMEOUT = SETTINGS["api"]["timeout_seconds"]
API_MAX_RETRIES = SETTINGS["api"]["max_retries"]
API_BACKOFF = SETTINGS["api"]["backoff_seconds"]

DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "database" / "weather_data.db"))
LOG_DIR = BASE_DIR / "logs"
REPORT_DIR = BASE_DIR / "reports"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

SCHEDULE_INTERVAL_MINUTES = SETTINGS["schedule"]["interval_minutes"]
THRESHOLDS = SETTINGS["thresholds"]
VALID_RANGES = {k: tuple(v) for k, v in SETTINGS["valid_ranges"].items()}
STALE_AFTER_MINUTES = SETTINGS["monitoring"]["stale_after_minutes"]


def load_cities():
    """Return the list of cities to track from config/cities.json."""
    return _load_json(CONFIG_DIR / "cities.json")


_LOGGING_READY = False


def setup_logging(level=None):
    """Configure console + rotating file logging (safe to call many times)."""
    global _LOGGING_READY
    if _LOGGING_READY:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(level or LOG_LEVEL)

    file_handler = RotatingFileHandler(
        LOG_DIR / "pipeline.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(console)
    _LOGGING_READY = True
