import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import hub as hub_module  # noqa: E402
from hub import Hub  # noqa: E402
from web_common import MAX_CACHED_PICTURES, picture_entry  # noqa: E402


class FakeActive:
    entities = {"light.kitchen": 1}


class FastScreen:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


class StuckScreen:
    async def send_json(self, message):
        await asyncio.sleep(3600)


class HubTests(unittest.TestCase):
    def test_a_stuck_screen_does_not_hold_up_the_others_and_is_dropped(self):
        async def scenario():
            old = hub_module.SEND_TIMEOUT
            hub_module.SEND_TIMEOUT = 0.05
            try:
                hub = Hub(active=FakeActive(), bridge=None)
                fast, stuck = FastScreen(), StuckScreen()
                hub.clients = {stuck: None, fast: None}
                await asyncio.wait_for(hub.broadcast("light.kitchen", {"state": "on"}), 2)
                self.assertEqual(len(fast.messages), 1)
                self.assertNotIn(stuck, hub.clients)
                self.assertIn(fast, hub.clients)
            finally:
                hub_module.SEND_TIMEOUT = old
        asyncio.run(scenario())


class FakeHa:
    def __init__(self, count):
        self.count = count

    async def state(self, entity_id):
        return {"last_updated": "t1", "attributes": {"entity_picture": "/api/image_proxy/x"}}

    async def picture(self, entity_picture):
        return b"bytes", "image/png"


class PictureCacheTests(unittest.TestCase):
    def test_the_picture_cache_stays_bounded(self):
        async def scenario():
            app = {"ha": FakeHa(0), "images": {}, "picture_locks": {}}
            for i in range(MAX_CACHED_PICTURES + 20):
                await picture_entry(app, f"image.n{i}")
            self.assertEqual(len(app["images"]), MAX_CACHED_PICTURES)
            self.assertIn(f"image.n{MAX_CACHED_PICTURES + 19}", app["images"])
            self.assertNotIn("image.n0", app["images"])
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
