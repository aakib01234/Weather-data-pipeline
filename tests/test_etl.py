import unittest

from src.api_client import APIError, DemoWeatherClient
from src.etl_pipeline import TransformError, load_record, run_pipeline, transform
from tests.helpers import CITY, make_db, raw_payload


class TransformTests(unittest.TestCase):
    def test_transform_maps_fields(self):
        rec = transform(raw_payload(rain={"1h": 2.5}), CITY)
        self.assertEqual(rec["city"], "Mumbai")
        self.assertEqual(rec["temperature_c"], 28.5)
        self.assertEqual(rec["humidity"], 65)
        self.assertEqual(rec["rain_1h_mm"], 2.5)
        self.assertEqual(rec["condition"], "clear sky")
        self.assertRegex(rec["observed_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_transform_defaults_rain_to_zero(self):
        self.assertEqual(transform(raw_payload(), CITY)["rain_1h_mm"], 0.0)

    def test_malformed_payload_raises(self):
        with self.assertRaises(TransformError):
            transform({"nonsense": True}, CITY)

    def test_non_numeric_value_raises(self):
        with self.assertRaises(TransformError):
            transform(raw_payload(main={"temp": "hot", "humidity": 50}), CITY)


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_load_and_deduplicate(self):
        rec = transform(raw_payload(), CITY)
        with self.db.connect() as conn:
            self.assertIsNotNone(load_record(conn, rec))
            self.assertIsNone(load_record(conn, rec))  # same city + time
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM weather_data")[0]["n"], 1)

    def test_alert_created_and_cooldown_applied(self):
        hot = transform(raw_payload(main={"temp": 44, "humidity": 40, "pressure": 1000}), CITY)
        later = dict(hot, observed_at="2025-01-15 12:00:00")  # 3h later: inside 6h cooldown
        with self.db.connect() as conn:
            load_record(conn, hot)
            load_record(conn, later)
        alerts = self.db.query("SELECT alert_type FROM alerts")
        self.assertEqual([a["alert_type"] for a in alerts], ["HIGH_TEMPERATURE"])


class FailingClient:
    def fetch_current(self, city, country=None):
        raise APIError("boom")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        self.cities = [{"name": "Mumbai", "country": "IN"}, {"name": "Delhi", "country": "IN"}]

    def test_successful_run(self):
        summary = run_pipeline(self.db, DemoWeatherClient(), self.cities)
        self.assertEqual(summary["status"], "SUCCESS")
        self.assertEqual(summary["loaded"], 2)
        run = self.db.query("SELECT * FROM pipeline_runs")[0]
        self.assertEqual(run["status"], "SUCCESS")

    def test_api_failure_is_logged_not_raised(self):
        summary = run_pipeline(self.db, FailingClient(), self.cities)
        self.assertEqual(summary["status"], "FAILED")
        self.assertEqual(summary["rejected"], 2)
        self.assertIn("boom", self.db.query("SELECT error_message FROM pipeline_runs")[0]["error_message"])

    def test_invalid_data_is_rejected(self):
        class BadClient:
            def fetch_current(self, city, country=None):
                return raw_payload(main={"temp": 500, "humidity": 50, "pressure": 1000})
        summary = run_pipeline(self.db, BadClient(), self.cities[:1])
        self.assertEqual(summary["rejected"], 1)
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM weather_data")[0]["n"], 0)


if __name__ == "__main__":
    unittest.main()
