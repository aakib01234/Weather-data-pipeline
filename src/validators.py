"""Data quality: per-record validation and database-wide quality checks."""
import logging

from . import config

log = logging.getLogger(__name__)

REQUIRED_FIELDS = ("city", "observed_at", "temperature_c", "humidity")


def validate_record(rec):
    """Return a list of problems with `rec` (empty list means the record is valid)."""
    errors = []
    for field in REQUIRED_FIELDS:
        if rec.get(field) in (None, ""):
            errors.append(f"missing required field '{field}'")

    for field, (low, high) in config.VALID_RANGES.items():
        value = rec.get(field)
        if value is None:
            continue  # optional fields may be absent; required ones were checked above
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{field} is not numeric: {value!r}")
        elif not low <= value <= high:
            errors.append(f"{field}={value} outside valid range [{low}, {high}]")
    return errors


def run_quality_checks(db, freshness_hours=24):
    """Database-wide quality report used by monitoring and reports."""
    total = db.query("SELECT COUNT(*) AS n FROM weather_data")[0]["n"]
    cities = db.query("SELECT COUNT(*) AS n FROM cities")[0]["n"]

    nulls = db.query(
        """SELECT SUM(pressure_hpa IS NULL) AS pressure_nulls,
                  SUM(wind_speed_mps IS NULL) AS wind_nulls,
                  SUM(condition_id IS NULL) AS condition_nulls
           FROM weather_data"""
    )[0]

    conds = []
    for field, (low, high) in config.VALID_RANGES.items():
        col = "humidity" if field == "humidity" else field
        conds.append(f"({col} IS NOT NULL AND ({col} < {low} OR {col} > {high}))")
    out_of_range = db.query(
        f"SELECT COUNT(*) AS n FROM weather_data WHERE {' OR '.join(conds)}"
    )[0]["n"]

    duplicates = db.query(
        """SELECT COUNT(*) AS n FROM (
               SELECT 1 FROM weather_data GROUP BY city_id, observed_at HAVING COUNT(*) > 1)"""
    )[0]["n"]

    fresh = db.query(
        """SELECT COUNT(DISTINCT city_id) AS n FROM weather_data
           WHERE observed_at >= datetime('now', ?)""",
        (f"-{freshness_hours} hours",),
    )[0]["n"]
    coverage = round(100.0 * fresh / cities, 1) if cities else 0.0

    result = {
        "total_records": total,
        "cities_tracked": cities,
        "null_counts": {k: (v or 0) for k, v in nulls.items()},
        "out_of_range_records": out_of_range,
        "duplicate_records": duplicates,
        "coverage_pct": coverage,
    }
    result["passed"] = out_of_range == 0 and duplicates == 0
    return result
