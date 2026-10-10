import unittest

from src.api_client import DemoWeatherClient
from src.etl_pipeline import run_pipeline
from src.monitor import health_check, render_dashboard
from src.reporter import evaluate_alerts
from tests.helpers import make_db


class AlertTests(unittest.TestCase):
    def test_multiple_alerts(self):
        rec = {"city": "X", "temperature_c": 41, "humidity": 90, "wind_speed_mps": 20}
        kinds = {a["type"] for a in evaluate_alerts(rec)}
        self.assertEqual(kinds, {"HIGH_TEMPERATURE", "HIGH_HUMIDITY", "HIGH_WIND"})

    def test_no_alerts_for_normal_weather(self):
        rec = {"city": "X", "temperature_c": 25, "humidity": 60, "wind_speed_mps": 3}
        self.assertEqual(evaluate_alerts(rec), [])


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_never_run_is_critical(self):
        self.assertEqual(health_check(self.db)["status"], "CRITICAL")

    def test_healthy_after_successful_run(self):
        run_pipeline(self.db, DemoWeatherClient(), [{"name": "Mumbai", "country": "IN"}])
        health = health_check(self.db)
        self.assertEqual(health["status"], "HEALTHY")
        self.assertIn("SYSTEM STATUS: HEALTHY", render_dashboard(self.db))


if __name__ == "__main__":
    unittest.main()
