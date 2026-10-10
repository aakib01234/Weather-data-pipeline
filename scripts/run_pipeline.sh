#!/usr/bin/env bash
# Cron-friendly wrapper. Example crontab entry (hourly):
#   0 * * * * /path/to/weather-data-pipeline/scripts/run_pipeline.sh >> /path/to/weather-data-pipeline/logs/cron.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d venv ] && source venv/bin/activate
python main.py run "$@"
