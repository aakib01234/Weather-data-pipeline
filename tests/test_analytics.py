import unittest

from src import analytics
from src.etl_pipeline import load_record, transform
from tests.helpers import make_db, raw_payload

import time


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        now = int(time.time()) // 3600 * 3600
        cities = {"Hot": ({"name": "Hot", "country": "IN"}, 35.0),
                  "Cool": ({"name": "Cool", "country": "IN"}, 20.0)}
        with self.db.connect() as conn:
            for name, (city, base) in cities.items():
                for i in range(48):  # 48 hourly points
                    rain = {"1h": 5.0} if i % 2 == 0 else {}
                    payload = raw_payload(
                        dt=now - i * 3600,
                        main={"temp": base, "humidity": 90 if rain else 50, "pressure": 1000},
                        **({"rain": rain} if rain else {}))
                    load_record(conn, transform(payload, city))

    def test_hottest_city_first(self):
        df = analytics.avg_temp_by_city(self.db)
        self.assertEqual(df.iloc[0]["city"], "Hot")
        self.assertAlmostEqual(df.iloc[0]["avg_temp_c"], 35.0)

    def test_trend_has_rows_for_both_cities(self):
        df = analytics.temperature_trend(self.db, days=7)
        self.assertEqual(set(df["city"]), {"Hot", "Cool"})

    def test_humidity_rain_correlation_is_positive(self):
        df = analytics.humidity_rainfall_correlation(self.db)
        self.assertGreater(df.iloc[0]["correlation"], 0.9)

    def test_seasonal_and_peak_queries_return_data(self):
        self.assertFalse(analytics.seasonal_extremes(self.db).empty)
        self.assertEqual(len(analytics.peak_temperature_hours(self.db)), 2)


if __name__ == "__main__":
    unittest.main()
