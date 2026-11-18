"""Limits and checks added in 0.7.6: service data per service, security headers, screen limit and one download per picture."""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

import screen_api  # noqa: E402
from errors import ApiError  # noqa: E402
from web_common import picture_entry, security_headers, service_data  # noqa: E402
import test_api as api_tests  # noqa: E402  (module import: its test classes are not collected twice)


class ServiceDataTests(unittest.TestCase):
    def test_thermostat_keys_of_contract_12_3(self):
        self.assertEqual(service_data({"entity_id": "climate.a", "service": "set_temperature",
                                       "temperature": "21.5", "layout": "x"}, "set_temperature"),
                         {"temperature": 21.5})
        self.assertEqual(service_data({"target_temp_low": "19", "target_temp_high": "23"}, "set_temperature"),
                         {"target_temp_low": 19, "target_temp_high": 23})
        self.assertEqual(service_data({"hvac_mode": "heat"}, "set_hvac_mode"), {"hvac_mode": "heat"})

    def test_a_key_the_service_does_not_take_is_refused(self):
        with self.assertRaises(ApiError):
            service_data({"temperature": "21"}, "turn_on")
        with self.assertRaises(ApiError):
            service_data({"anything": "1"}, "unknown_service")

    def test_services_without_data_refuse_all_data(self):
        self.assertEqual(service_data({}, "toggle"), {})
        with self.assertRaises(ApiError):
            service_data({"brightness": "10"}, "toggle")

    def test_numbers_must_be_numbers(self):
        for bad in ("true", "abc", "nan", "inf"):
            with self.assertRaises(ApiError, msg=bad):
                service_data({"temperature": bad}, "set_temperature")

    def test_text_keeps_its_type_and_has_a_length_limit(self):
        self.assertEqual(service_data({"option": "1"}, "select_option"), {"option": "1"})
        with self.assertRaises(ApiError):
            service_data({"option": "x" * 65}, "select_option")
        with self.assertRaises(ApiError):
            service_data({"option": ""}, "select_option")


class SecurityHeaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_answer_has_no_referrer_and_nosniff(self):
        async def page(request):
            return web.Response(text="ok")
        app = web.Application(middlewares=[security_headers])
        app.router.add_get("/page", page)
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            resp = await client.get("/page")
            self.assertEqual(resp.headers["Referrer-Policy"], "no-referrer")
            self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        finally:
            await client.close()


class PictureLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_requests_download_the_picture_once(self):
        calls = []

        class SlowHa:
            async def state(self, entity_id):
                return {"last_updated": "t1", "attributes": {"entity_picture": "/api/image_proxy/image.x"}}

            async def picture(self, path):
                calls.append(path)
                await asyncio.sleep(0.05)
                return b"bytes", "image/png"

        app = {"ha": SlowHa(), "images": {}, "picture_locks": {}}
        results = await asyncio.gather(*(picture_entry(app, "image.x") for _ in range(5)))
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(r["data"] == b"bytes" for r in results))


class ScreenLimitTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = api_tests.ApiTests.asyncSetUp
    asyncTearDown = api_tests.ApiTests.asyncTearDown

    async def test_a_screen_beyond_the_limit_is_closed_with_1013(self):
        original = screen_api.MAX_SCREENS
        screen_api.MAX_SCREENS = 0
        try:
            ws = await self.screen.ws_connect(f"/ws?token={api_tests.TOKEN}")
            await ws.receive()
            self.assertEqual(ws.close_code, screen_api.WS_CLOSE_TOO_MANY)
            await ws.close()
        finally:
            screen_api.MAX_SCREENS = original


if __name__ == "__main__":
    unittest.main()
