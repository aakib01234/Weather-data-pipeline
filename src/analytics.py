"""Query system for historical weather analysis (returns pandas DataFrames)."""
import pandas as pd

SEASON_SQL = """CASE
    WHEN CAST(strftime('%m', w.observed_at) AS INTEGER) IN (12, 1, 2) THEN 'Winter'
    WHEN CAST(strftime('%m', w.observed_at) AS INTEGER) IN (3, 4, 5)  THEN 'Summer'
    WHEN CAST(strftime('%m', w.observed_at) AS INTEGER) IN (6, 7, 8, 9) THEN 'Monsoon'
    ELSE 'Post-monsoon' END"""


def _df(db, sql, params=()):
    return pd.DataFrame(db.query(sql, params))


def avg_temp_by_city(db):
    """Q1: Which city has the highest average temperature?"""
    return _df(db, """
        SELECT c.city_name AS city, ROUND(AVG(w.temperature_c), 2) AS avg_temp_c,
               COUNT(*) AS records
        FROM weather_data w JOIN cities c ON c.city_id = w.city_id
        GROUP BY c.city_id ORDER BY avg_temp_c DESC""")


def temperature_trend(db, city=None, days=30):
    """Q2: Daily average temperature over the last `days` days."""
    sql = """
        SELECT date(w.observed_at) AS day, c.city_name AS city,
               ROUND(AVG(w.temperature_c), 2) AS avg_temp_c
        FROM weather_data w JOIN cities c ON c.city_id = w.city_id
        WHERE w.observed_at >= datetime('now', ?)"""
    params = [f"-{int(days)} days"]
    if city:
        sql += " AND c.city_name = ?"
        params.append(city)
    sql += " GROUP BY day, c.city_id ORDER BY c.city_name, day"
    return _df(db, sql, params)


def trend_summary(db, days=30):
    """Per-city change between the first and last week of the trend window."""
    df = temperature_trend(db, days=days)
    if df.empty:
        return df
    rows = []
    for city, g in df.groupby("city"):
        g = g.sort_values("day")
        first, last = g.head(7)["avg_temp_c"].mean(), g.tail(7)["avg_temp_c"].mean()
        rows.append({"city": city, "first_week_avg": round(first, 2),
                     "last_week_avg": round(last, 2), "change_c": round(last - first, 2)})
    return pd.DataFrame(rows).sort_values("change_c", ascending=False)


def humidity_rainfall_correlation(db):
    """Q3: Pearson correlation between humidity and rainfall (overall + per city)."""
    df = _df(db, """
        SELECT c.city_name AS city, w.humidity, w.rain_1h_mm
        FROM weather_data w JOIN cities c ON c.city_id = w.city_id""")
    if df.empty:
        return df
    rows = [{"city": "ALL CITIES", "correlation": round(df["humidity"].corr(df["rain_1h_mm"]), 3)}]
    for city, g in df.groupby("city"):
        rows.append({"city": city, "correlation": round(g["humidity"].corr(g["rain_1h_mm"]), 3)})
    return pd.DataFrame(rows)


def seasonal_extremes(db):
    """Q4: Temperature extremes and variability per season."""
    return _df(db, f"""
        SELECT {SEASON_SQL} AS season,
               ROUND(MIN(w.temperature_c), 1) AS min_temp_c,
               ROUND(MAX(w.temperature_c), 1) AS max_temp_c,
               ROUND(MAX(w.temperature_c) - MIN(w.temperature_c), 1) AS range_c,
               ROUND(MAX(w.humidity), 0) AS max_humidity,
               ROUND(MAX(w.wind_speed_mps), 1) AS max_wind_mps,
               ROUND(SUM(w.rain_1h_mm), 1) AS total_rain_mm,
               COUNT(*) AS records
        FROM weather_data w
        GROUP BY season ORDER BY range_c DESC""")


def peak_temperature_hours(db):
    """Q5: Local hour of day with the highest average temperature, per city."""
    df = _df(db, """
        SELECT c.city_name AS city,
               CAST(strftime('%H', datetime(w.observed_at, c.timezone_offset_s || ' seconds')) AS INTEGER) AS local_hour,
               AVG(w.temperature_c) AS avg_temp_c
        FROM weather_data w JOIN cities c ON c.city_id = w.city_id
        GROUP BY c.city_id, local_hour""")
    if df.empty:
        return df
    idx = df.groupby("city")["avg_temp_c"].idxmax()
    out = df.loc[idx, ["city", "local_hour", "avg_temp_c"]].copy()
    out["avg_temp_c"] = out["avg_temp_c"].round(2)
    out["peak_time"] = out["local_hour"].map(lambda h: f"{int(h):02d}:00")
    return out.sort_values("avg_temp_c", ascending=False)[["city", "peak_time", "avg_temp_c"]]
