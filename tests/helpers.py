"""Shared test helpers."""
import tempfile
from pathlib import Path

from src.database import Database

CITY = {"name": "Mumbai", "country": "IN"}


def make_db():
    tmp = tempfile.TemporaryDirectory()
    db = Database(Path(tmp.name) / "test.db")
    db.init_schema()
    return tmp, db


def raw_payload(**over):
    payload = {
        "coord": {"lon": 72.88, "lat": 19.07},
        "weather": [{"main": "Clear", "description": "Clear Sky"}],
        "main": {"temp": 28.5, "humidity": 65, "pressure": 1009},
        "wind": {"speed": 3.4},
        "dt": 1736931600,
        "sys": {"country": "IN"},
        "timezone": 19800,
        "name": "Mumbai",
    }
    payload.update(over)
    return payload
