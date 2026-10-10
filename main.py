#!/usr/bin/env python3
"""Command-line entry point for the Weather Data Pipeline System."""
import argparse
import sys

from src import analytics, config
from src.api_client import APIError, DemoWeatherClient, WeatherAPIClient
from src.database import Database
from src.etl_pipeline import run_pipeline
from src.monitor import render_dashboard
from src.reporter import generate_daily_report
from src.scheduler import run_scheduler


def _show(title, df):
    print(f"\n=== {title} ===")
    print("(no data)" if df is None or df.empty else df.to_string(index=False))


def cmd_init(args):
    Database().init_schema()
    print(f"Database initialised at {config.DB_PATH}")


def cmd_run(args):
    db = Database()
    db.init_schema()
    cities = config.load_cities()
    if args.city:
        cities = [c for c in cities if c["name"].lower() == args.city.lower()]
        if not cities:
            print(f"City '{args.city}' not found in config/cities.json")
            return 2
    try:
        client = DemoWeatherClient() if args.demo else WeatherAPIClient()
    except APIError as exc:
        print(f"Error: {exc}")
        return 2
    summary = run_pipeline(db, client, cities)
    print(f"Run {summary['run_id']}: {summary['status']} - loaded {summary['loaded']}, "
          f"duplicates {summary['duplicates']}, rejected {summary['rejected']}")
    for err in summary["errors"]:
        print(f"  ! {err}")
    return 0 if summary["status"] != "FAILED" else 1


def cmd_schedule(args):
    run_scheduler(interval_minutes=args.interval, demo=args.demo)


def cmd_report(args):
    db = Database()
    db.init_schema()
    txt, csv_path, text = generate_daily_report(db, args.date)
    print(text)
    print(f"Saved: {txt}\nSaved: {csv_path}")


def cmd_analyze(args):
    db = Database()
    db.init_schema()
    _show("Q1. Average temperature by city (highest first)", analytics.avg_temp_by_city(db))
    _show(f"Q2. Temperature trend, last {args.days} days (first vs last week)",
          analytics.trend_summary(db, args.days))
    _show("Q3. Humidity vs rainfall correlation", analytics.humidity_rainfall_correlation(db))
    _show("Q4. Seasonal extremes", analytics.seasonal_extremes(db))
    _show("Q5. Peak temperature hour per city (local time)", analytics.peak_temperature_hours(db))


def cmd_health(args):
    db = Database()
    db.init_schema()
    print(render_dashboard(db))


def build_parser():
    p = argparse.ArgumentParser(description="Weather Data Pipeline System")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the database schema").set_defaults(func=cmd_init)

    r = sub.add_parser("run", help="run the ETL pipeline once")
    r.add_argument("--demo", action="store_true", help="use synthetic data (no API key)")
    r.add_argument("--city", help="run for a single city")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("schedule", help="run the pipeline repeatedly")
    s.add_argument("--interval", type=int, help="minutes between runs")
    s.add_argument("--demo", action="store_true")
    s.set_defaults(func=cmd_schedule)

    rp = sub.add_parser("report", help="generate the daily report")
    rp.add_argument("--date", help="YYYY-MM-DD (UTC), default today")
    rp.set_defaults(func=cmd_report)

    a = sub.add_parser("analyze", help="run the historical analysis queries")
    a.add_argument("--days", type=int, default=30)
    a.set_defaults(func=cmd_analyze)

    sub.add_parser("health", help="show monitoring dashboard").set_defaults(func=cmd_health)
    return p


def main(argv=None):
    config.setup_logging()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
