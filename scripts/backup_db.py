#!/usr/bin/env python3
"""Make a consistent timestamped backup of the SQLite database."""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # noqa: E402


def main():
    backup_dir = config.BASE_DIR / "database" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"weather_data_{datetime.now():%Y%m%d_%H%M%S}.db.bak"
    src = sqlite3.connect(config.DB_PATH)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)  # safe even while the pipeline is writing
    src.close()
    dst.close()
    print(f"Backup created: {target}")


if __name__ == "__main__":
    main()
