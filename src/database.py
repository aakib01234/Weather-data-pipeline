"""SQLite access layer: connection handling, schema creation and write helpers."""
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

log = logging.getLogger(__name__)
SCHEMA_PATH = config.BASE_DIR / "database" / "schema.sql"


class Database:
    def __init__(self, path=None):
        self.path = Path(path or config.DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        """Yield a connection; commit on success, roll back on error."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self):
        with self.connect() as conn:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        log.info("Database ready at %s", self.path)

    def query(self, sql, params=()):
        """Run a SELECT and return a list of dicts."""
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # ---- dimension helpers -------------------------------------------------
    @staticmethod
    def get_or_create_city(conn, name, country, lat=None, lon=None, tz_offset=0):
        conn.execute(
            "INSERT OR IGNORE INTO cities (city_name, country) VALUES (?, ?)",
            (name, country),
        )
        conn.execute(
            """UPDATE cities
               SET latitude = COALESCE(?, latitude),
                   longitude = COALESCE(?, longitude),
                   timezone_offset_s = ?
               WHERE city_name = ? AND country = ?""",
            (lat, lon, tz_offset or 0, name, country),
        )
        row = conn.execute(
            "SELECT city_id FROM cities WHERE city_name = ? AND country = ?",
            (name, country),
        ).fetchone()
        return row["city_id"]

    @staticmethod
    def get_or_create_condition(conn, description):
        conn.execute(
            "INSERT OR IGNORE INTO weather_conditions (description) VALUES (?)",
            (description,),
        )
        row = conn.execute(
            "SELECT condition_id FROM weather_conditions WHERE description = ?",
            (description,),
        ).fetchone()
        return row["condition_id"]

    # ---- fact helpers ------------------------------------------------------
    @staticmethod
    def insert_weather(conn, city_id, condition_id, rec):
        """Insert one observation. Returns record_id, or None if it already exists."""
        cur = conn.execute(
            """INSERT OR IGNORE INTO weather_data
               (city_id, condition_id, observed_at, temperature_c, humidity,
                pressure_hpa, wind_speed_mps, rain_1h_mm)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                city_id, condition_id, rec["observed_at"], rec["temperature_c"],
                rec["humidity"], rec.get("pressure_hpa"), rec.get("wind_speed_mps"),
                rec.get("rain_1h_mm") or 0.0,
            ),
        )
        return cur.lastrowid if cur.rowcount else None

    @staticmethod
    def alert_in_cooldown(conn, city_id, alert_type, observed_at, hours):
        row = conn.execute(
            """SELECT 1 FROM alerts
               WHERE city_id = ? AND alert_type = ?
                 AND observed_at > datetime(?, ?) AND observed_at <= ?
               LIMIT 1""",
            (city_id, alert_type, observed_at, f"-{hours} hours", observed_at),
        ).fetchone()
        return row is not None

    @staticmethod
    def insert_alert(conn, city_id, record_id, alert, observed_at):
        conn.execute(
            """INSERT INTO alerts
               (city_id, record_id, alert_type, message, value, threshold, observed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (city_id, record_id, alert["type"], alert["message"],
             alert["value"], alert["threshold"], observed_at),
        )

    # ---- pipeline run log (own connection so it survives load failures) ----
    def start_run(self, cities_attempted):
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO pipeline_runs (cities_attempted) VALUES (?)",
                (cities_attempted,),
            )
            return cur.lastrowid

    def finish_run(self, run_id, status, loaded, rejected, error=None):
        with self.connect() as conn:
            conn.execute(
                """UPDATE pipeline_runs
                   SET finished_at = CURRENT_TIMESTAMP, status = ?,
                       records_loaded = ?, records_rejected = ?, error_message = ?
                   WHERE run_id = ?""",
                (status, loaded, rejected, error, run_id),
            )
