import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from forecasts import Forecasts, forecast_entries, wanted_kinds  # noqa: E402
from ha_bridge import public_view  # noqa: E402


class FakeHa:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    async def forecast(self, entity_id, kind):
        self.calls.append((entity_id, kind))
        if isinstance(self.answers.get(kind), Exception):
            raise self.answers[kind]
        return self.answers.get(kind, [])


class FakeActive:
    def __init__(self, entities):
        self.entities = set(entities)


class ForecastTests(unittest.TestCase):
    def test_entries_keep_the_contract_fields_and_limits(self):
        raw = [{"datetime": "2026-11-16T12:00:00+00:00", "condition": "rainy", "temperature": 9, "templow": 4,
                "precipitation_probability": 70, "wind_bearing": "N"}, {"condition": "sunny"}]
        self.assertEqual(forecast_entries(raw, 7), [{"datetime": "2026-11-16T12:00:00+00:00",
                                                     "condition": "rainy", "temperature": 9, "templow": 4,
                                                     "precipitation_probability": 70}])
        self.assertEqual(len(forecast_entries([{"datetime": "x"}] * 30, 24)), 24)

    def test_wanted_kinds_follow_the_supported_features(self):
        self.assertEqual([k[0] for k in wanted_kinds({"supported_features": 3})], ["daily", "hourly"])
        self.assertEqual([k[0] for k in wanted_kinds({"supported_features": 1})], ["daily"])
        self.assertEqual(wanted_kinds({}), [])

    def test_refresh_puts_the_forecast_in_the_attributes_and_publishes(self):
        states = {"weather.home": {"s": "rainy", "a": {"supported_features": 3, "temperature": 9}, "lu": 1}}
        published = []

        async def publish(entity_id, view):
            published.append((entity_id, view))

        ha = FakeHa({"daily": [{"datetime": "d1", "condition": "rainy", "temperature": 9}],
                     "hourly": [{"datetime": "h1", "condition": "sunny", "temperature": 8}]})
        forecasts = Forecasts(ha, states, FakeActive({"weather.home"}), publish)
        self.assertTrue(asyncio.run(forecasts.refresh("weather.home")))
        attrs = states["weather.home"]["a"]
        self.assertEqual(attrs["forecast_daily"][0]["datetime"], "d1")
        self.assertEqual(attrs["forecast_hourly"][0]["datetime"], "h1")
        self.assertEqual(published[0][0], "weather.home")
        self.assertEqual(published[0][1]["attributes"]["forecast_daily"][0]["datetime"], "d1")
        # the same forecast again changes nothing
        self.assertFalse(asyncio.run(forecasts.refresh("weather.home")))

    def test_a_failed_forecast_does_not_stop_the_other(self):
        states = {"weather.home": {"s": "rainy", "a": {"supported_features": 3}, "lu": 1}}

        async def publish(entity_id, view):
            pass

        ha = FakeHa({"daily": RuntimeError("boom"), "hourly": [{"datetime": "h1"}]})
        forecasts = Forecasts(ha, states, FakeActive({"weather.home"}), publish)
        asyncio.run(forecasts.refresh("weather.home"))
        self.assertNotIn("forecast_daily", states["weather.home"]["a"])
        self.assertEqual(states["weather.home"]["a"]["forecast_hourly"][0]["datetime"], "h1")


class ViewTests(unittest.TestCase):
    def test_climate_and_weather_use_the_temperature_unit(self):
        climate = {"s": "heat", "a": {"friendly_name": "Woonkamer", "temperature_unit": "°C",
                                      "target_temp_low": 19, "preset_mode": "home"}, "lu": 1}
        view = public_view("climate.woonkamer", climate)
        self.assertEqual(view["unit"], "°C")
        self.assertEqual(view["attributes"]["target_temp_low"], 19)
        self.assertEqual(view["attributes"]["preset_mode"], "home")
        sensor = {"s": "21", "a": {"unit_of_measurement": "°C", "temperature_unit": "°F"}, "lu": 1}
        self.assertEqual(public_view("sensor.temp", sensor)["unit"], "°C")


if __name__ == "__main__":
    unittest.main()
