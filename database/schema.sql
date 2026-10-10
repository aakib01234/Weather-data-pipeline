-- Weather Data Pipeline: normalized schema (3NF)
-- Timestamps are stored in UTC as 'YYYY-MM-DD HH:MM:SS'.

PRAGMA foreign_keys = ON;

-- 1. Cities (one row per tracked city)
CREATE TABLE IF NOT EXISTS cities (
    city_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    city_name         TEXT    NOT NULL,
    country           TEXT    NOT NULL,
    latitude          REAL,
    longitude         REAL,
    timezone_offset_s INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (city_name, country)
);

-- 2. Weather conditions lookup (removes repeated text from the fact table)
CREATE TABLE IF NOT EXISTS weather_conditions (
    condition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description  TEXT NOT NULL UNIQUE
);

-- 3. Weather observations (fact table)
CREATE TABLE IF NOT EXISTS weather_data (
    record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id        INTEGER NOT NULL,
    condition_id   INTEGER,
    observed_at    TEXT    NOT NULL,
    temperature_c  REAL    NOT NULL,
    humidity       INTEGER NOT NULL CHECK (humidity BETWEEN 0 AND 100),
    pressure_hpa   REAL,
    wind_speed_mps REAL CHECK (wind_speed_mps IS NULL OR wind_speed_mps >= 0),
    rain_1h_mm     REAL NOT NULL DEFAULT 0 CHECK (rain_1h_mm >= 0),
    ingested_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id)      REFERENCES cities (city_id),
    FOREIGN KEY (condition_id) REFERENCES weather_conditions (condition_id),
    UNIQUE (city_id, observed_at)          -- prevents duplicate loads
);
CREATE INDEX IF NOT EXISTS idx_weather_city_time ON weather_data (city_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_weather_time      ON weather_data (observed_at);

-- 4. Pipeline run log (used by monitoring)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at      TEXT,
    status           TEXT NOT NULL DEFAULT 'RUNNING'
                     CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED')),
    cities_attempted INTEGER NOT NULL DEFAULT 0,
    records_loaded   INTEGER NOT NULL DEFAULT 0,
    records_rejected INTEGER NOT NULL DEFAULT 0,
    error_message    TEXT
);

-- 5. Alerts raised when thresholds are crossed
CREATE TABLE IF NOT EXISTS alerts (
    alert_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id     INTEGER NOT NULL,
    record_id   INTEGER,
    alert_type  TEXT NOT NULL,
    message     TEXT NOT NULL,
    value       REAL,
    threshold   REAL,
    observed_at TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id)   REFERENCES cities (city_id),
    FOREIGN KEY (record_id) REFERENCES weather_data (record_id)
);
CREATE INDEX IF NOT EXISTS idx_alerts_lookup ON alerts (city_id, alert_type, observed_at);
