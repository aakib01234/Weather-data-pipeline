"""Alert evaluation and report generation (text + CSV)."""
import csv
import logging
from datetime import datetime, timezone

from . import config

log = logging.getLogger(__name__)


def evaluate_alerts(rec):
    """Return alert dicts for any threshold crossed by this record."""
    t = config.THRESHOLDS
    city = rec["city"]
    alerts = []

    def add(kind, label, value, threshold, unit):
        alerts.append({
            "type": kind,
            "message": f"{label} alert: {city} ({value}{unit} vs threshold {threshold}{unit})",
            "value": value,
            "threshold": threshold,
        })

    if rec["temperature_c"] > t["high_temperature_c"]:
        add("HIGH_TEMPERATURE", "High temperature", rec["temperature_c"], t["high_temperature_c"], "°C")
    if rec["temperature_c"] < t["low_temperature_c"]:
        add("LOW_TEMPERATURE", "Low temperature", rec["temperature_c"], t["low_temperature_c"], "°C")
    if rec["humidity"] > t["high_humidity_pct"]:
        add("HIGH_HUMIDITY", "High humidity", rec["humidity"], t["high_humidity_pct"], "%")
    wind = rec.get("wind_speed_mps")
    if wind is not None and wind > t["high_wind_mps"]:
        add("HIGH_WIND", "High wind", wind, t["high_wind_mps"], " m/s")
    return alerts


def generate_daily_report(db, report_date=None):
    """Write reports/daily_report_<date>.txt and daily_summary_<date>.csv.

    Returns (text_path, csv_path, text).
    """
    report_date = report_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)

    rows = db.query(
        """SELECT c.city_name AS city, COUNT(*) AS records,
                  ROUND(MIN(w.temperature_c), 1) AS min_temp,
                  ROUND(AVG(w.temperature_c), 1) AS avg_temp,
                  ROUND(MAX(w.temperature_c), 1) AS max_temp,
                  ROUND(AVG(w.humidity), 0) AS avg_humidity,
                  ROUND(SUM(w.rain_1h_mm), 1) AS rain_mm
           FROM weather_data w JOIN cities c ON c.city_id = w.city_id
           WHERE date(w.observed_at) = ?
           GROUP BY c.city_id ORDER BY avg_temp DESC""",
        (report_date,),
    )
    alerts = db.query(
        """SELECT c.city_name AS city, a.alert_type, a.message, a.observed_at
           FROM alerts a JOIN cities c ON c.city_id = a.city_id
           WHERE date(a.observed_at) = ? ORDER BY a.observed_at""",
        (report_date,),
    )

    lines = [
        "WEATHER DATA PIPELINE SYSTEM - DAILY REPORT",
        "=" * 60,
        f"Report date : {report_date} (UTC)",
        f"Generated   : {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC",
        "",
        "CITY SUMMARY",
        "-" * 60,
        f"{'City':<12}{'Recs':>5}{'Min C':>8}{'Avg C':>8}{'Max C':>8}{'Hum %':>7}{'Rain mm':>9}",
    ]
    if rows:
        for r in rows:
            lines.append(
                f"{r['city']:<12}{r['records']:>5}{r['min_temp']:>8}{r['avg_temp']:>8}"
                f"{r['max_temp']:>8}{int(r['avg_humidity']):>7}{r['rain_mm']:>9}"
            )
    else:
        lines.append("No observations recorded for this date.")

    lines += ["", f"ALERTS ({len(alerts)})", "-" * 60]
    if alerts:
        lines += [f"{a['observed_at']}  {a['message']}" for a in alerts[:25]]
        if len(alerts) > 25:
            lines.append(f"... and {len(alerts) - 25} more")
    else:
        lines.append("No alerts for this date.")

    text = "\n".join(lines) + "\n"
    txt_path = config.REPORT_DIR / f"daily_report_{report_date}.txt"
    csv_path = config.REPORT_DIR / f"daily_summary_{report_date}.csv"
    txt_path.write_text(text, encoding="utf-8")

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["city", "records", "min_temp", "avg_temp",
                            "max_temp", "avg_humidity", "rain_mm"])
        writer.writeheader()
        writer.writerows(rows)

    log.info("Report written: %s", txt_path)
    return txt_path, csv_path, text
