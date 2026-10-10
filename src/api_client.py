"""OpenWeatherMap client (with retries) and an offline demo client."""
import logging
import math
import random
import time
from datetime import datetime, timezone

import requests

from . import config

log = logging.getLogger(__name__)


class APIError(Exception):
    """Raised when weather data cannot be fetched."""


class WeatherAPIClient:
    """Fetch current weather from OpenWeatherMap with retry + backoff."""

    def __init__(self, api_key=None, base_url=None, timeout=None,
                 max_retries=None, backoff=None):
        self.api_key = api_key or config.API_KEY
        if not self.api_key:
            raise APIError(
                "OPENWEATHER_API_KEY is not set. Copy config/.env.example to .env "
                "and add your key (or use --demo)."
            )
        self.base_url = base_url or config.API_BASE_URL
        self.timeout = timeout or config.API_TIMEOUT
        self.max_retries = max_retries or config.API_MAX_RETRIES
        self.backoff = config.API_BACKOFF if backoff is None else backoff
        self.session = requests.Session()
        self._sleep = time.sleep  # replaceable in tests

    def _redact(self, text):
        """Never let the API key leak into logs or the database."""
        return str(text).replace(self.api_key, "***")

    def fetch_current(self, city, country=None):
        query = f"{city},{country}" if country else city
        params = {"q": query, "appid": self.api_key, "units": "metric"}
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(self.base_url, params=params, timeout=self.timeout)
                if resp.status_code == 401:
                    raise APIError("Invalid API key (HTTP 401)")
                if resp.status_code == 404:
                    raise APIError(f"City not found: {query}")
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                log.debug("Fetched %s on attempt %d", query, attempt)
                return resp.json()
            except APIError:
                raise  # permanent errors: do not retry
            except (requests.RequestException, ValueError) as exc:
                last_error = self._redact(exc)
                log.warning("API attempt %d/%d failed for %s: %s",
                            attempt, self.max_retries, query, last_error)
                if attempt < self.max_retries:
                    self._sleep(self.backoff * attempt)

        raise APIError(f"Failed to fetch {query} after {self.max_retries} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Demo mode: realistic synthetic data in the same shape as the real API.
# ---------------------------------------------------------------------------
# name: (annual mean C, seasonal amplitude, daily amplitude, lat, lon)
DEMO_PROFILES = {
    "Mumbai":    (27.5, 3.0, 3.5, 19.0760, 72.8777),
    "Delhi":     (25.0, 10.0, 6.0, 28.6139, 77.2090),
    "Bangalore": (24.0, 2.5, 4.5, 12.9716, 77.5946),
    "Chennai":   (29.0, 3.5, 3.5, 13.0827, 80.2707),
    "Kolkata":   (27.0, 5.0, 4.5, 22.5726, 88.3639),
    "Hyderabad": (26.5, 5.0, 5.0, 17.3850, 78.4867),
    "Pune":      (25.0, 4.5, 6.0, 18.5204, 73.8567),
    "Ahmedabad": (28.0, 7.0, 6.0, 23.0225, 72.5714),
    "Jaipur":    (26.0, 9.0, 6.5, 26.9124, 75.7873),
    "Lucknow":   (25.5, 10.0, 6.0, 26.8467, 80.9462),
}
DEFAULT_PROFILE = (25.0, 5.0, 5.0, 20.0, 78.0)
DEMO_TZ_OFFSET = 19800  # IST, seconds


def build_demo_payload(city, country, ts):
    """Build an OpenWeatherMap-shaped payload for `city` at epoch seconds `ts`."""
    mean, s_amp, d_amp, lat, lon = DEMO_PROFILES.get(city, DEFAULT_PROFILE)
    rng = random.Random(f"{city}-{ts}")  # deterministic per city+time
    local = datetime.fromtimestamp(ts + DEMO_TZ_OFFSET, tz=timezone.utc)
    hour = local.hour + local.minute / 60
    doy = local.timetuple().tm_yday
    monsoon = 6 <= local.month <= 9

    temp = (mean
            + s_amp * math.sin(2 * math.pi * (doy - 60) / 365)   # peaks ~June
            + d_amp * math.sin(2 * math.pi * (hour - 9) / 24)    # peaks ~15:00
            + rng.gauss(0, 0.8))
    raining = rng.random() < (0.30 if monsoon else 0.04)
    if raining:
        temp -= rng.uniform(1.5, 3.5)
    humidity = (60 - 1.2 * (temp - mean) + (12 if monsoon else 0)
                + (15 if raining else 0) + rng.gauss(0, 4))
    humidity = int(max(20, min(100, round(humidity))))

    if raining:
        desc = rng.choice(["light rain", "moderate rain"])
    elif humidity > 75:
        desc = rng.choice(["overcast clouds", "broken clouds"])
    elif humidity > 55:
        desc = rng.choice(["scattered clouds", "few clouds"])
    else:
        desc = rng.choice(["clear sky", "few clouds"])

    payload = {
        "coord": {"lon": lon, "lat": lat},
        "weather": [{"main": desc.split()[-1].title(), "description": desc}],
        "main": {
            "temp": round(temp, 2),
            "humidity": humidity,
            "pressure": round(1010 - (4 if monsoon else 0) + rng.gauss(0, 2), 1),
        },
        "wind": {"speed": round(abs(rng.gauss(3, 1.5)) + (2 if monsoon else 0), 2)},
        "dt": int(ts),
        "sys": {"country": country},
        "timezone": DEMO_TZ_OFFSET,
        "name": city,
    }
    if raining:
        payload["rain"] = {"1h": round(rng.uniform(0.2, 8.0), 2)}
    return payload


class DemoWeatherClient:
    """Drop-in replacement for WeatherAPIClient that needs no API key."""

    def fetch_current(self, city, country=None):
        return build_demo_payload(city, country or "IN", int(time.time()))
