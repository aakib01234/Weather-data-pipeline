"""ETL workflow: Extract (API) -> Transform (clean) -> Validate -> Load (SQLite)."""
import logging
from datetime import datetime, timezone

from . import config
from .api_client import APIError
from .database import Database
from .reporter import evaluate_alerts
from .validators import validate_record

log = logging.getLogger(__name__)


class TransformError(Exception):
    """Raised when a raw API payload cannot be converted into a record."""


def _num(value, cast=float):
    if value is None:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError) as exc:
        raise TransformError(f"non-numeric value {value!r}") from exc


# ---- Extract ---------------------------------------------------------------
def extract(client, city):
    return client.fetch_current(city["name"], city.get("country"))


# ---- Transform -------------------------------------------------------------
def transform(raw, city):
    """Flatten the raw API payload into a clean record dict."""
    try:
        observed = datetime.fromtimestamp(int(raw["dt"]), tz=timezone.utc)
        main = raw["main"]
        weather = raw.get("weather") or [{}]
        coord = raw.get("coord", {})
        temp = _num(main.get("temp"))
        pressure = _num(main.get("pressure"))
        wind = _num(raw.get("wind", {}).get("speed"))
        rain = _num(raw.get("rain", {}).get("1h", 0.0)) or 0.0
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise TransformError(f"malformed payload: {exc!r}") from exc

    return {
        "city": city["name"],
        "country": city.get("country") or raw.get("sys", {}).get("country") or "??",
        "latitude": coord.get("lat"),
        "longitude": coord.get("lon"),
        "timezone_offset_s": raw.get("timezone", 0),
        "observed_at": observed.strftime("%Y-%m-%d %H:%M:%S"),
        "temperature_c": None if temp is None else round(temp, 2),
        "humidity": _num(main.get("humidity"), int),
        "pressure_hpa": None if pressure is None else round(pressure, 1),
        "wind_speed_mps": None if wind is None else round(wind, 2),
        "rain_1h_mm": round(rain, 2),
        "condition": (weather[0].get("description") or "unknown").strip().lower(),
    }


# ---- Load ------------------------------------------------------------------
def load_record(conn, rec):
    """Insert one validated record (+ alerts). Returns record_id or None if duplicate."""
    city_id = Database.get_or_create_city(
        conn, rec["city"], rec["country"], rec["latitude"], rec["longitude"],
        rec["timezone_offset_s"])
    cond_id = Database.get_or_create_condition(conn, rec["condition"])
    record_id = Database.insert_weather(conn, city_id, cond_id, rec)
    if record_id is None:
        return None

    cooldown = config.THRESHOLDS["alert_cooldown_hours"]
    for alert in evaluate_alerts(rec):
        if not Database.alert_in_cooldown(conn, city_id, alert["type"],
                                          rec["observed_at"], cooldown):
            Database.insert_alert(conn, city_id, record_id, alert, rec["observed_at"])
            log.warning(alert["message"])
    return record_id


# ---- Orchestration ---------------------------------------------------------
def run_pipeline(db, client, cities):
    """Run one full ETL cycle for all cities. Never raises for per-city failures."""
    run_id = db.start_run(len(cities))
    loaded = duplicates = rejected = 0
    errors = []
    log.info("Run %d started for %d cities", run_id, len(cities))

    for city in cities:
        name = city["name"]
        try:
            raw = extract(client, city)
            rec = transform(raw, city)
            problems = validate_record(rec)
            if problems:
                rejected += 1
                errors.append(f"{name}: invalid data ({'; '.join(problems)})")
                log.warning("Rejected %s: %s", name, problems)
                continue
            with db.connect() as conn:
                if load_record(conn, rec) is None:
                    duplicates += 1
                    log.info("Duplicate observation skipped for %s", name)
                else:
                    loaded += 1
                    log.info("Loaded %s: %.1f°C, %d%% humidity",
                             name, rec["temperature_c"], rec["humidity"])
        except (APIError, TransformError) as exc:
            rejected += 1
            errors.append(f"{name}: {exc}")
            log.error("Failed %s: %s", name, exc)
        except Exception as exc:  # keep pipeline alive on unexpected errors
            rejected += 1
            errors.append(f"{name}: unexpected {exc!r}")
            log.exception("Unexpected error for %s", name)

    failed = rejected
    if failed == 0:
        status = "SUCCESS"
    elif loaded + duplicates > 0:
        status = "PARTIAL"
    else:
        status = "FAILED"
    db.finish_run(run_id, status, loaded, rejected, "; ".join(errors)[:1000] or None)
    log.info("Run %d finished: %s (loaded=%d, duplicates=%d, rejected=%d)",
             run_id, status, loaded, duplicates, rejected)
    return {"run_id": run_id, "status": status, "attempted": len(cities),
            "loaded": loaded, "duplicates": duplicates, "rejected": rejected,
            "errors": errors}
