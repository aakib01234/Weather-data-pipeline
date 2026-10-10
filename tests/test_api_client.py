import unittest
from unittest.mock import MagicMock, patch

import requests

from src.api_client import APIError, WeatherAPIClient


def response(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body or {"ok": True}
    r.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(str(status))
    return r


def make_client(*responses):
    client = WeatherAPIClient(api_key="test", max_retries=3, backoff=0)
    client._sleep = lambda s: None
    client.session = MagicMock()
    client.session.get.side_effect = list(responses)
    return client


class ApiClientTests(unittest.TestCase):
    def test_missing_key_raises(self):
        with patch("src.api_client.config.API_KEY", ""):  # ignore any real key in .env
            with self.assertRaises(APIError):
                WeatherAPIClient(api_key="")

    def test_success(self):
        self.assertEqual(make_client(response()).fetch_current("Mumbai", "IN"), {"ok": True})

    def test_retries_on_server_error_then_succeeds(self):
        client = make_client(response(500), response(503), response())
        self.assertEqual(client.fetch_current("Mumbai"), {"ok": True})
        self.assertEqual(client.session.get.call_count, 3)

    def test_gives_up_after_max_retries(self):
        client = make_client(response(500), response(500), response(500))
        with self.assertRaises(APIError):
            client.fetch_current("Mumbai")

    def test_retries_on_timeout(self):
        client = make_client(requests.Timeout("slow"), response())
        self.assertEqual(client.fetch_current("Mumbai"), {"ok": True})

    def test_api_key_is_redacted_from_errors(self):
        err = requests.ConnectionError("failed: https://x/?appid=test&q=Mumbai")
        client = make_client(err, err, err)
        with self.assertRaises(APIError) as ctx:
            client.fetch_current("Mumbai")
        self.assertNotIn("appid=test", str(ctx.exception))
        self.assertIn("appid=***", str(ctx.exception))

    def test_bad_key_is_not_retried(self):
        client = make_client(response(401))
        with self.assertRaises(APIError):
            client.fetch_current("Mumbai")
        self.assertEqual(client.session.get.call_count, 1)

    def test_unknown_city(self):
        with self.assertRaises(APIError):
            make_client(response(404)).fetch_current("Nowhereville")


if __name__ == "__main__":
    unittest.main()
