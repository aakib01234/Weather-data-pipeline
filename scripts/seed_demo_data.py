#!/usr/bin/env python3
"""Fill the database with N days of synthetic hourly history (demo / testing).

Usage: python scripts/seed_demo_data.py --days 365 --step-hours 3
"""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402
from src.api_client import build_demo_payload  # noqa: E402
from src.database import Database  # noqa: E402
from src.etl_pipeline import load_record, transform  # noqa: E402
from src.validators import validate_record  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--step-hours", type=int, default=3, help="hours between samples")
    args = ap.parse_args()
    logging.getLogger("src.etl_pipeline").setLevel(logging.ERROR)  # keep output quiet

    db = Database()
    db.init_schema()
    cities = config.load_cities()
    now = int(time.time()) // 3600 * 3600
    start = now - args.days * 24 * 3600
    loaded = rejected = 0

    with db.connect() as conn:
        for ts in range(start, now + 1, args.step_hours * 3600):
            for city in cities:
                rec = transform(build_demo_payload(city["name"], city["country"], ts), city)
                if validate_record(rec):
                    rejected += 1
                elif load_record(conn, rec) is not None:
                    loaded += 1
    print(f"Seeded {loaded} records ({rejected} rejected) for {len(cities)} cities.")


if __name__ == "__main__":
    main()
