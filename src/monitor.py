"""Pipeline health checks and a text dashboard."""
import logging
from datetime import datetime, timezone

from . import config
from .validators import run_quality_checks

log = logging.getLogger(__name__)
_TS = "%Y-%m-%d %H:%M:%S"


def _age_minutes(ts):
    then = datetime.strptime(ts, _TS).replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 60


def health_check(db, stale_after_minutes=None):
    """Return a dict describing pipeline health. status: HEALTHY / WARNING / CRITICAL."""
    stale_after = stale_after_minutes or config.STALE_AFTER_MINUTES
    last = db.query("SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT 1")
    runs = db.query(
        """SELECT COUNT(*) AS total, SUM(status = 'SUCCESS') AS ok
           FROM pipeline_runs WHERE started_at >= datetime('now', '-24 hours')""")[0]
    last_error = db.query(
        """SELECT started_at, error_message FROM pipeline_runs
           WHERE error_message IS NOT NULL ORDER BY run_id DESC LIMIT 1""")
    quality = run_quality_checks(db)

    issues = []
    status = "HEALTHY"
    last_run = last[0] if last else None
    if last_run is None:
        status = "CRITICAL"
        issues.append("pipeline has never run")
    else:
        age = _age_minutes(last_run["started_at"])
        if last_run["status"] == "FAILED":
            status = "CRITICAL"
            issues.append("last run FAILED")
        elif last_run["status"] == "PARTIAL":
            status = "WARNING"
            issues.append("last run was PARTIAL (some cities failed)")
        if age > stale_after:
            if status == "HEALTHY":
                status = "WARNING"
            issues.append(f"no run in the last {int(age)} minutes (limit {stale_after})")
    if not quality["passed"]:
        status = "CRITICAL" if status != "CRITICAL" else status
        issues.append("data quality checks failed")

    total, ok = runs["total"] or 0, runs["ok"] or 0
    db_size_kb = round(db.path.stat().st_size / 1024, 1) if db.path.exists() else 0
    return {
        "status": status,
        "issues": issues,
        "last_run": last_run,
        "runs_24h": total,
        "success_rate_24h": round(100 * ok / total, 1) if total else None,
        "last_error": last_error[0] if last_error else None,
        "quality": quality,
        "db_size_kb": db_size_kb,
    }


def latest_snapshot(db, limit=10):
    return db.query(
        """SELECT c.city_name AS city, w.temperature_c AS temp, w.humidity,
                  wc.description AS condition, w.observed_at
           FROM weather_data w
           JOIN cities c ON c.city_id = w.city_id
           LEFT JOIN weather_conditions wc ON wc.condition_id = w.condition_id
           WHERE w.observed_at = (SELECT MAX(observed_at) FROM weather_data
                                  WHERE city_id = w.city_id)
           ORDER BY c.city_name LIMIT ?""", (limit,))


def render_dashboard(db):
    """Return the dashboard as text (also used by `main.py health`)."""
    h = health_check(db)
    q = h["quality"]
    icon = {"HEALTHY": "✅", "WARNING": "⚠️", "CRITICAL": "❌"}[h["status"]]
    lines = ["WEATHER DATA PIPELINE SYSTEM", "=" * 29, ""]
    lines.append(f"📊 SYSTEM STATUS: {h['status']} {icon}")
    lr = h["last_run"]
    if lr:
        lines += [
            f"⏰ Last Run: {lr['started_at']} UTC",
            f"✅ Status: {lr['status']}",
            f"📈 Records Loaded: {lr['records_loaded']} (rejected: {lr['records_rejected']})",
        ]
    rate = "n/a" if h["success_rate_24h"] is None else f"{h['success_rate_24h']}%"
    lines.append(f"🔁 Runs (24h): {h['runs_24h']}  |  Success rate: {rate}")
    if h["issues"]:
        lines += ["", "🚨 ISSUES:"] + [f"  • {i}" for i in h["issues"]]

    lines += ["", "🌤️ CURRENT WEATHER SNAPSHOT:", "-" * 33]
    for r in latest_snapshot(db):
        lines.append(f"📍 {r['city']}: {r['temp']}°C, {r['humidity']}% humidity, "
                     f"{(r['condition'] or 'n/a').capitalize()}")

    lines += [
        "", "📊 DATABASE STATISTICS:",
        f"• Total records: {q['total_records']:,}",
        f"• Cities tracked: {q['cities_tracked']}",
        f"• Data coverage (last 24h): {q['coverage_pct']}%",
        f"• Duplicates: {q['duplicate_records']}  |  Out-of-range: {q['out_of_range_records']}",
        f"• Database size: {h['db_size_kb']} KB",
        f"• Last error: {h['last_error']['error_message'][:80] if h['last_error'] else 'None'}",
    ]
    return "\n".join(lines)
