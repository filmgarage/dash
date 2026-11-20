"""Page and screen sensors in Home Assistant: names, the complete screen URL as state, and the sync."""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from app_keys import DETECTED_IP, HA, OPTIONS, SAVED, SCREENS, STORE  # noqa: E402
import page_sensors  # noqa: E402
from errors import ApiError  # noqa: E402
from page_sensors import page_url, screen_sensor_id, screen_url, sensor_id, sync_all  # noqa: E402


class FakeHa:
    def __init__(self, fail=False):
        self.written = []
        self.fail = fail

    async def set_state(self, entity_id, state, attributes):
        if self.fail:
            raise ApiError("Home Assistant answered 500", 502)
        self.written.append((entity_id, state, attributes))


class UnreachableHa:
    async def set_state(self, entity_id, state, attributes):
        import aiohttp
        raise aiohttp.ClientConnectionError("no connection")


class FakeStore:
    def __init__(self, pages, published=("thuis/woonkamer",)):
        self.pages = pages
        self.published = set(published)

    def publish_list(self):
        return self.pages

    def is_published(self, parts):
        return "/".join(parts) in self.published


class FakeScreens:
    def __init__(self, screens):
        self.screens = screens

    def list(self):
        return list(self.screens)


PAGES = [
    {"path": "thuis/woonkamer", "type": "html", "url": "/dash/thuis/woonkamer.html"},
    {"path": "skins/minimal", "type": "json", "url": "/dash/skins/minimal.json"},
]
SCREEN_RECORDS = [{"name": "Woonkamer", "layout": "thuis/woonkamer", "token": "autotoken_abc"}]


class NamesAndUrlsTests(unittest.TestCase):
    def test_sensor_ids_are_valid_entity_ids(self):
        self.assertEqual(sensor_id("thuis/woonkamer"), "sensor.dash_thuis_woonkamer")
        self.assertEqual(screen_sensor_id("Hal 2"), "sensor.dash_screen_hal_2")

    def test_page_name_is_readable(self):
        self.assertEqual(page_sensors.page_name("thuis/woonkamer"), "thuis / woonkamer")

    def test_a_page_without_screen_shows_the_placeholder(self):
        ha = FakeHa()
        asyncio.run(sync_all(ha, FakeStore(PAGES, published=("thuis/woonkamer", "thuis/keuken")), FakeScreens([]),
                             {}, {}, "192.168.69.248"))
        by_id = {entity: state for entity, state, _a in ha.written}
        self.assertEqual(by_id["sensor.dash_thuis_woonkamer"], "http://192.168.69.248:8092/dash/placeholder.html")

    def test_page_url_has_no_token(self):
        self.assertEqual(page_url("192.168.69.248", "thuis/woonkamer"),
                         "http://192.168.69.248:8092/dash/thuis/woonkamer.html")

    def test_screen_url_has_the_token_after_the_hash(self):
        self.assertEqual(screen_url("192.168.69.248", "thuis/woonkamer", "autotoken_abc"),
                         "http://192.168.69.248:8092/dash/viewer.html?layout=thuis/woonkamer#token=autotoken_abc")


class SyncTests(unittest.TestCase):
    def test_sync_writes_html_pages_and_screens(self):
        ha = FakeHa()
        written = asyncio.run(sync_all(ha, FakeStore(PAGES), FakeScreens(SCREEN_RECORDS), {}, {}, "192.168.69.248"))
        self.assertEqual(written, 2)
        by_id = {entity: (state, attrs) for entity, state, attrs in ha.written}
        self.assertEqual(by_id["sensor.dash_thuis_woonkamer"][0],
                         "http://192.168.69.248:8092/dash/thuis/woonkamer.html#token=autotoken_abc")
        self.assertIn("autotoken_abc", by_id["sensor.dash_screen_woonkamer"][0])
        self.assertEqual(by_id["sensor.dash_screen_woonkamer"][1]["layout"], "thuis/woonkamer")

    def test_sync_without_address_writes_a_placeholder(self):
        ha = FakeHa()
        asyncio.run(sync_all(ha, FakeStore(PAGES), FakeScreens(SCREEN_RECORDS), {}, {}, None))
        self.assertTrue(all(state == "no screen address" for _e, state, _a in ha.written))

    def test_a_failing_home_assistant_does_not_stop_the_sync(self):
        written = asyncio.run(sync_all(FakeHa(fail=True), FakeStore(PAGES), FakeScreens(SCREEN_RECORDS), {}, {},
                                       "192.168.69.248"))
        self.assertEqual(written, 0)

    def test_an_unpublished_layout_shows_the_placeholder(self):
        ha = FakeHa()
        screens = [{"name": "Keuken", "layout": "thuis/keuken", "token": "autotoken_x"}]
        asyncio.run(sync_all(ha, FakeStore(PAGES, published=()), FakeScreens(screens), {}, {}, "192.168.69.248"))
        self.assertEqual(ha.written[-1][1], "http://192.168.69.248:8092/dash/placeholder.html")
        self.assertNotIn("autotoken_x", ha.written[-1][1])

    def test_publishing_a_layout_switches_the_screen_to_its_viewer(self):
        ha = FakeHa()
        screens = [{"name": "Keuken", "layout": "thuis/keuken", "token": "autotoken_x"}]
        app = {HA: ha, OPTIONS: {}, SAVED: {}, DETECTED_IP: "192.168.69.248", STORE: FakeStore(PAGES),
               SCREENS: FakeScreens(screens)}
        asyncio.run(page_sensors.publish_page(app, ["thuis", "keuken"]))
        screen_writes = [w for w in ha.written if w[0] == "sensor.dash_screen_keuken"]
        self.assertEqual(screen_writes[-1][1], "http://192.168.69.248:8092/dash/placeholder.html")
        # The layout is published now: the screen gets the viewer URL with its token.
        app[STORE].published.add("thuis/keuken")
        asyncio.run(page_sensors.publish_page(app, ["thuis", "keuken"]))
        screen_writes = [w for w in ha.written if w[0] == "sensor.dash_screen_keuken"]
        self.assertIn("#token=autotoken_x", screen_writes[-1][1])

    def test_removing_a_page_and_a_screen_sets_removed(self):
        app = {HA: FakeHa(), OPTIONS: {}, SAVED: {}, DETECTED_IP: None, STORE: FakeStore(PAGES), SCREENS: FakeScreens([])}
        asyncio.run(page_sensors.unpublish_page(app, ["thuis", "woonkamer"]))
        asyncio.run(page_sensors.remove_screen(app, "Woonkamer", "thuis/woonkamer"))
        states = [(e, s) for e, s, _a in app[HA].written]
        self.assertIn(("sensor.dash_thuis_woonkamer", "removed"), states)
        self.assertIn(("sensor.dash_screen_woonkamer", "removed"), states)


class UnreachableTests(unittest.TestCase):
    def test_publishing_still_succeeds_when_home_assistant_is_unreachable(self):
        app = {HA: UnreachableHa(), OPTIONS: {}, SAVED: {}, DETECTED_IP: "192.168.69.248",
               STORE: FakeStore(PAGES), SCREENS: FakeScreens([])}
        self.assertFalse(asyncio.run(page_sensors.publish_page(app, ["thuis", "woonkamer"])))


if __name__ == "__main__":
    unittest.main()
