# Deployment & maintenance

## Option A: built-in scheduler

```bash
nohup python main.py schedule --interval 60 > logs/scheduler.out 2>&1 &
```

The scheduler catches job errors and keeps running. It writes a daily report once per UTC day.

## Option B: cron (recommended on a server)

```cron
0 * * * *  /path/to/weather-data-pipeline/scripts/run_pipeline.sh >> /path/to/weather-data-pipeline/logs/cron.log 2>&1
5 0 * * *  cd /path/to/weather-data-pipeline && venv/bin/python main.py report
30 0 * * 0 cd /path/to/weather-data-pipeline && venv/bin/python scripts/backup_db.py
```

## Option C: systemd service

```ini
[Unit]
Description=Weather Data Pipeline
After=network-online.target

[Service]
WorkingDirectory=/opt/weather-data-pipeline
ExecStart=/opt/weather-data-pipeline/venv/bin/python main.py schedule
Restart=on-failure
EnvironmentFile=/opt/weather-data-pipeline/.env

[Install]
WantedBy=multi-user.target
```

## Operations checklist

- `python main.py health`: check status, last run and data coverage
- Logs: `logs/pipeline.log` (rotating, 1 MB x 3 files)
- Backups: `python scripts/backup_db.py` writes to `database/backups/`
- Rate limits: the free OpenWeatherMap tier allows 60 calls/minute and ~1,000,000 calls/month;
  10 cities hourly is about 7,200 calls/month
- Rotate the API key if it was ever committed or shared
