from app_keys import ACTIVE, APP_SETTINGS_PATH, BRIDGE, DETECTED_IP, HA, HUB, IMAGES, INTERNAL_URL, OPTIONS, PICTURE_LOCKS, PICTURE_SLOTS, SAVED, SCREENS, STORE
from errors import ApiError
import asyncio
import base64
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

import editor_api  # noqa: E402
import screen_api  # noqa: E402
from active import ActiveSet  # noqa: E402
from ha_bridge import HaBridge  # noqa: E402
from hub import Hub  # noqa: E402
from screens import ScreenStore
from store import Store  # noqa: E402
from web_common import build_app, ingress_only  # noqa: E402

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/test"}
TOKEN = "autotoken_test-screen"  # the screen "Test", on layout kitchen/morning
JPEG = "data:image/jpeg;base64," + base64.b64encode(b"jpeg-bytes").decode()
LAYOUT = {"title": "Morning", "tiles": [
    {"id": "t1", "type": "light", "entity": "light.kitchen", "x": 0, "y": 0, "w": 2, "h": 2}]}


class FakeHa:
    token = "supervisor"

    def __init__(self):
        self.entities = {
            "light.kitchen": {"entity_id": "light.kitchen", "state": "off",
                              "last_changed": "2026-11-15T00:00:00+00:00",
                              "attributes": {"friendly_name": "Kitchen"}},
            "light.hall": {"entity_id": "light.hall", "state": "on", "attributes": {}},
            "image.qr": {"entity_id": "image.qr", "state": "2026", "last_updated": "t1",
                         "attributes": {"entity_picture": "/api/image_proxy/image.qr?token=x"}},
            "sensor.temp": {"entity_id": "sensor.temp", "state": "20.5",
                            "attributes": {"unit_of_measurement": "°C"}},
            "camera.front": {"entity_id": "camera.front", "state": "idle",
                             "attributes": {"entity_picture": "/api/camera_proxy/camera.front?token=x"}},
            "camera.off": {"entity_id": "camera.off", "state": "unavailable",
                           "attributes": {"entity_picture": "/api/camera_proxy/camera.off?token=y"}},
        }
        self.history_rows = {"sensor.temp": [{"state": "20.5", "last_changed": "2026-11-21T00:00:00+00:00"}]}
        self.devices = [{"id": "dev1", "name": "Kitchen tablet", "config_entries": ["fk1"]},
                        {"id": "dev2", "name": "Hall lamp", "config_entries": ["zigbee1"]}]
        self.entity_registry = [{"entity_id": "sensor.kitchen_tablet_battery", "device_id": "dev1"}]
        self.fully_entries = [{"entry_id": "fk1", "domain": "fully_kiosk", "data": {"host": "192.168.1.40"}}]
        self.entities["sensor.kitchen_tablet_battery"] = {"entity_id": "sensor.kitchen_tablet_battery",
                                                          "state": "87", "attributes": {}}
        self.action_error = None
        self.calls = []
        self.internal_url = None

    def require_token(self):
        pass

    async def set_state(self, entity_id, state, attributes):
        self.calls.append(("set_state", entity_id, state))

    async def states(self):
        return list(self.entities.values())

    async def state(self, entity_id):
        return self.entities.get(entity_id)

    async def call_service(self, entity_id, service, data):
        self.calls.append((entity_id, service, data))

    async def config(self):
        return {INTERNAL_URL: self.internal_url}

    async def picture(self, entity_picture):
        return b"png-bytes", "image/png"

    async def history(self, entity_id, start, end):
        return self.history_rows.get(entity_id, [])

    async def ws_calls(self, commands):
        out = []
        for command in commands:
            if command["type"] == "config/device_registry/list":
                out.append(self.devices)
            elif command["type"] == "config/entity_registry/list":
                out.append(self.entity_registry)
            elif command["type"] == "config_entries/get":
                out.append(self.fully_entries)
        return out

    async def call_action(self, domain, service, data):
        self.calls.append((domain, service, data))
        if self.action_error:
            raise ApiError(self.action_error, 502)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        with open(os.path.join(root, "screens.json"), "w", encoding="utf-8") as f:
            json.dump({"screens": [{"name": "Test", "layout": "kitchen/morning", "token": TOKEN}]}, f)
        self.screens = ScreenStore(os.path.join(root, "screens.json"))
        self.store = Store(os.path.join(root, "layouts"), os.path.join(root, "www"), "/dash",
                           os.path.join(root, "published"))
        self.active = ActiveSet(os.path.join(root, "active.json"))
        self.ha = FakeHa()
        self.bridge = HaBridge("ws://unused", "supervisor", self.active)
        self.bridge.states = {
            "light.kitchen": {"s": "off", "a": {"friendly_name": "Kitchen"}, "lu": 0},
            "light.hall": {"s": "on", "a": {}, "lu": 0},
        }
        self.hub = Hub(self.active, self.bridge)
        state = {
            OPTIONS: {"log_level": "info",
                        "allow_domains": {"light", "sensor", "image", "camera"},
                        "screen_address_mode": "ip", "screen_ip": "",
                        "allow_entities": set(), "exclude_domains": {"lock", "alarm_control_panel"},
                        "exclude_entities": set(),
                        "services": {"toggle", "turn_on"}, "read_services": {"toggle"}},
            STORE: self.store, ACTIVE: self.active, BRIDGE: self.bridge,
            HUB: self.hub, HA: self.ha, IMAGES: {}, PICTURE_LOCKS: {}, PICTURE_SLOTS: asyncio.Semaphore(4), SCREENS: self.screens, SAVED: {}, DETECTED_IP: "192.168.69.248",
            APP_SETTINGS_PATH: os.path.join(self.tmp.name, "settings.json"),
        }
        self.editor = TestClient(TestServer(build_app(editor_api.add_routes, state, [ingress_only])))
        self.screen = TestClient(TestServer(build_app(screen_api.add_routes, state)))
        await self.editor.start_server()
        await self.screen.start_server()

    def publish_screen_layout(self, tiles=None):
        """Publishes kitchen/morning, the layout of the test screen, with the given tiles (default: LAYOUT)."""
        layout = LAYOUT if tiles is None else {"title": "Morning", "tiles": tiles}
        self.store.save_layout(["kitchen", "morning"], layout, "")
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.snapshot_layout(["kitchen", "morning"])

    async def asyncTearDown(self):
        await self.editor.close()
        await self.screen.close()
        self.tmp.cleanup()

    async def test_editor_refuses_requests_outside_ingress(self):
        resp = await self.editor.get("/api/status")
        self.assertEqual(resp.status, 403)

    async def test_status_through_ingress(self):
        resp = await self.editor.get("/api/status", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        self.assertEqual((await resp.json())["version"], "0.12.4")

    async def test_publishing_adds_and_unpublishing_removes_entities(self):
        resp = await self.editor.post("/api/layout_save?path=kitchen/morning", json=LAYOUT, headers=INGRESS)
        self.assertEqual(resp.status, 200)
        resp = await self.editor.post("/api/publish_save?path=kitchen/morning",
                                      json={"html": "<html></html>"}, headers=INGRESS)
        data = await resp.json()
        self.assertEqual(data["added"], ["light.kitchen"])
        self.assertEqual(data["url"], "/dash/kitchen/morning.html")

        resp = await self.editor.get("/api/active", headers=INGRESS)
        active = (await resp.json())["active"]
        self.assertEqual(active, [{"entity_id": "light.kitchen", "layouts": ["kitchen/morning"],
                                   "missing": False}])

        resp = await self.editor.post("/api/publish_delete?path=kitchen/morning",
                                      headers=INGRESS)
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.active.entities, set())

    async def test_screen_needs_the_read_token(self):
        self.assertEqual((await self.screen.get("/states")).status, 401)
        self.assertEqual((await self.screen.get("/states?token=wrong")).status, 401)
        self.assertEqual((await self.screen.get(f"/states?token={TOKEN}")).status, 200)

    async def test_screen_only_sees_active_entities_on_its_layout(self):
        self.publish_screen_layout()
        self.active.set_page("kitchen/morning", ["light.kitchen"])
        resp = await self.screen.get(f"/states?token={TOKEN}")
        states = (await resp.json())["states"]
        self.assertEqual(list(states), ["light.kitchen"])

    async def test_layout_load_only_for_published_layouts(self):
        self.store.save_layout(["kitchen", "morning"], LAYOUT, "")
        resp = await self.screen.get(f"/layout_load?path=kitchen/morning&token={TOKEN}")
        self.assertEqual(resp.status, 404)
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.snapshot_layout(["kitchen", "morning"])
        resp = await self.screen.get(f"/layout_load?path=kitchen/morning&token={TOKEN}")
        self.assertEqual(resp.status, 200)

    async def test_screen_service_only_on_entities_of_the_published_layout(self):
        self.store.save_layout(["kitchen", "morning"], LAYOUT, "")
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.snapshot_layout(["kitchen", "morning"])
        self.active.set_page("kitchen/morning", ["light.kitchen"])

        ok = await self.screen.post(
            f"/service?entity_id=light.kitchen&service=toggle&layout=kitchen/morning&token={TOKEN}")
        self.assertEqual(ok.status, 200)
        self.assertEqual(self.ha.calls, [("light.kitchen", "toggle", {})])

        other = await self.screen.post(
            f"/service?entity_id=light.hall&service=toggle&layout=kitchen/morning&token={TOKEN}")
        self.assertEqual(other.status, 403)

        not_read = await self.screen.post(
            f"/service?entity_id=light.kitchen&service=turn_on&layout=kitchen/morning&token={TOKEN}")
        self.assertEqual(not_read.status, 403)

    async def test_editor_routes_are_not_on_the_screen_port(self):
        resp = await self.screen.get(f"/api/layouts?token={TOKEN}")
        self.assertEqual(resp.status, 404)

    async def test_status_page_only_through_ingress(self):
        resp = await self.editor.get("/status", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.headers["Content-Type"])
        self.assertEqual((await self.editor.get("/status")).status, 403)
        self.assertEqual((await self.screen.get("/status")).status, 404)

    async def test_viewer_on_screen_port_and_ingress(self):
        resp = await self.screen.get("/dash/viewer.html")
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.headers["Content-Type"])
        resp = await self.editor.get("/viewer", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        self.assertEqual((await self.editor.get("/viewer")).status, 403)

    async def test_published_layout_only_through_ingress(self):
        resp = await self.editor.get("/api/published_layout?path=kitchen/morning", headers=INGRESS)
        self.assertEqual(resp.status, 404)
        await self.editor.post("/api/layout_save?path=kitchen/morning", json=LAYOUT, headers=INGRESS)
        await self.editor.post("/api/publish_save?path=kitchen/morning",
                               json={"html": "<html></html>"}, headers=INGRESS)
        resp = await self.editor.get("/api/published_layout?path=kitchen/morning", headers=INGRESS)
        self.assertEqual((await resp.json())["layout"]["title"], "Morning")
        self.assertEqual((await self.editor.get("/api/published_layout?path=kitchen/morning")).status, 403)

    async def test_editor_assets_through_ingress_only(self):
        resp = await self.editor.get("/assets/mdi-icons.txt", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        self.assertEqual((await self.editor.get("/assets/mdi-icons.txt")).status, 403)

    async def test_token_cannot_unlock_a_lock(self):
        # Even with the token, an unlock on a lock is refused before Home Assistant is called.
        resp = await self.screen.post(
            f"/service?entity_id=lock.front_door&service=unlock&layout=entry/door&token={TOKEN}")
        self.assertEqual(resp.status, 403)
        self.assertEqual(self.ha.calls, [])

    async def test_publishing_refuses_excluded_entities(self):
        lock = {"title": "Door", "tiles": [
            {"id": "t1", "type": "lock", "entity": "lock.front_door", "x": 0, "y": 0, "w": 2, "h": 2}]}
        await self.editor.post("/api/layout_save?path=entry/door", json=lock, headers=INGRESS)
        resp = await self.editor.post("/api/publish_save?path=entry/door",
                                      json={"html": "<html></html>"}, headers=INGRESS)
        self.assertEqual(resp.status, 400)
        self.assertIn("lock.front_door", (await resp.json())["error"])
        self.assertEqual(self.active.entities, set())

    async def test_favicon_on_both_servers(self):
        self.assertEqual((await self.screen.get("/dash/favicon.png")).status, 200)
        self.assertEqual((await self.editor.get("/favicon.png", headers=INGRESS)).status, 200)

    async def test_status_gives_the_screen_address_and_settings_save_it(self):
        resp = await self.editor.get("/api/status", headers=INGRESS)
        body = await resp.json()
        self.assertEqual(body["screen_host"], "192.168.69.248")
        self.assertEqual(body["screen_host_source"], "detected")
        bad = await self.editor.post("/api/settings", json={"screen_ip": "not an ip"}, headers=INGRESS)
        self.assertEqual(bad.status, 400)
        ok = await self.editor.post("/api/settings", json={"screen_ip": "10.0.0.9"}, headers=INGRESS)
        self.assertEqual((await ok.json())["screen_host"], "10.0.0.9")
        with open(os.path.join(self.tmp.name, "settings.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"screen_ip": "10.0.0.9"})

    async def test_settings_panel_saves_lists_formats_and_warnings(self):
        resp = await self.editor.post("/api/settings", json={
            "allow_domains": ["light", "cover"], "allow_entities": ["sensor.outside"],
            "language": "en", "date_format": "DD-MM-YYYY", "time_format": "12h",
            "warnings": {"tile-override-seen": True}}, headers=INGRESS)
        self.assertEqual(resp.status, 200)
        body = await resp.json()
        self.assertEqual(body["allow_domains"], ["cover", "light"])
        self.assertEqual(body["allow_entities"], ["sensor.outside"])
        self.assertEqual(body["warnings"], {"tile-override-seen": True})
        self.assertEqual(self.state_options()["allow_domains"], {"cover", "light"})
        status = await (await self.editor.get("/api/status", headers=INGRESS)).json()
        self.assertEqual(status["date_format"], "DD-MM-YYYY")
        with open(os.path.join(self.tmp.name, "settings.json"), encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["allow_domains"], ["cover", "light"])
        self.assertEqual(saved["time_format"], "12h")

    async def test_settings_panel_refuses_invalid_values_and_keeps_the_old_ones(self):
        before = self.state_options()["allow_domains"]
        bad_bodies = [
            {"allow_domains": ["Light!"]},
            {"allow_entities": ["light"]},
            {"language": "nl"},
            {"date_format": "YYYY"},
            {"time_format": "24"},
            {"warnings": {"unknown-flag": True}},
            {"warnings": {"tile-override-seen": "yes"}},
            {"not_a_setting": 1},
            {"default_skin": "../evil"},
        ]
        for body in bad_bodies:
            resp = await self.editor.post("/api/settings", json=body, headers=INGRESS)
            self.assertEqual(resp.status, 400, body)
        self.assertEqual(self.state_options()["allow_domains"], before)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "settings.json")))

    def state_options(self):
        return self.editor.app[OPTIONS]

    async def test_viewer_cannot_be_published_by_the_editor(self):
        resp = await self.editor.post("/api/publish_save?path=viewer",
                                      json={"html": "<html></html>"}, headers=INGRESS)
        self.assertEqual(resp.status, 400)

    async def test_screen_sends_no_cors_headers(self):
        resp = await self.screen.get(f"/states?token={TOKEN}")
        self.assertNotIn("Access-Control-Allow-Origin", resp.headers)

    async def test_socket_with_a_wrong_token_is_closed_with_4401(self):
        async with self.screen.ws_connect("/ws?token=wrong") as ws:
            await ws.receive()
            self.assertEqual(ws.close_code, 4401)

    async def test_screen_service_takes_a_json_post_body(self):
        self.store.save_layout(["kitchen", "morning"], LAYOUT, "")
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.snapshot_layout(["kitchen", "morning"])
        self.active.set_page("kitchen/morning", ["light.kitchen"])
        resp = await self.screen.post(
            "/service?layout=kitchen/morning", json={"entity_id": "light.kitchen", "service": "toggle"},
            headers={"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.ha.calls[-1], ("light.kitchen", "toggle", {}))

    async def test_post_refuses_a_body_that_is_not_an_object(self):
        resp = await self.screen.post(f"/service?token={TOKEN}", data="not json",
                                      headers={"Content-Type": "application/json"})
        self.assertEqual(resp.status, 400)

    async def test_socket_accepts_the_token_as_first_message(self):
        async with self.screen.ws_connect("/ws") as ws:
            await ws.send_json({"type": "auth", "token": TOKEN})
            first = await ws.receive_json()
            self.assertEqual(first["type"], "states")

    async def test_socket_with_a_wrong_first_message_is_closed_with_4401(self):
        ws = await self.screen.ws_connect("/ws")
        await ws.send_json({"type": "auth", "token": "wrong"})
        await ws.receive()
        self.assertEqual(ws.close_code, 4401)

    async def test_status_gives_the_internal_url_for_the_designer(self):
        resp = await self.editor.get("/api/status", headers=INGRESS)
        self.assertIn("internal_url", await resp.json())

    async def test_socket_gets_states_and_layout_changes(self):
        async with self.screen.ws_connect(f"/ws?token={TOKEN}") as ws:
            first = await ws.receive_json()
            self.assertEqual(first["type"], "states")
            await self.editor.post("/api/layout_save?path=kitchen/morning", json=LAYOUT, headers=INGRESS)
            await self.editor.post("/api/publish_save?path=kitchen/morning",
                                   json={"html": "<html></html>"}, headers=INGRESS)
            message = await ws.receive_json()
            self.assertEqual(message["type"], "layout")
            self.assertEqual(message["path"], "kitchen/morning")
            self.assertIsNotNone(message["saved"])

    async def test_published_pages_are_served_on_the_screen_port_without_login(self):
        self.store.publish_html(["kitchen", "morning"], "<html>page</html>")
        resp = await self.screen.get("/dash/kitchen/morning.html")
        self.assertEqual(resp.status, 200)
        self.assertEqual(await resp.text(), "<html>page</html>")
        self.assertNotEqual((await self.screen.get("/dash/")).status, 200)

    async def test_editor_preview_reads_published_files_through_ingress(self):
        self.store.publish_html(["kitchen", "morning"], "<html>page</html>")
        resp = await self.editor.get("/api/file?path=kitchen/morning.html", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        resp = await self.editor.get("/api/file?path=../secret", headers=INGRESS)
        self.assertEqual(resp.status, 400)

    async def test_status_never_contains_a_token(self):
        resp = await self.editor.get("/api/status", headers=INGRESS)
        self.assertNotIn("read_token", await resp.json())

    async def test_editor_imagedata_is_not_limited_to_active_entities(self):
        resp = await self.editor.get("/api/imagedata?entity=image.qr", headers=INGRESS)
        self.assertEqual(resp.status, 200)

    async def test_imagedata_returns_unchanged_for_the_same_hash(self):
        self.publish_screen_layout([{"id": "c1", "type": "haimage", "entity": "image.qr",
                                     "x": 0, "y": 0, "w": 2, "h": 2}])
        self.active.set_page("kitchen/morning", ["image.qr"])
        first = await (await self.screen.get(f"/imagedata?entity=image.qr&token={TOKEN}")).json()
        self.assertIn("data_url", first)
        again = await self.screen.get(f"/imagedata?entity=image.qr&hash={first['hash']}&token={TOKEN}")
        self.assertEqual(await again.json(), {"unchanged": True, "hash": first["hash"]})


    async def test_image_endpoint_serves_binary_bytes_with_etag(self):
        self.publish_screen_layout([{"id": "c1", "type": "haimage", "entity": "image.qr",
                                     "x": 0, "y": 0, "w": 2, "h": 2}])
        self.active.set_page("kitchen/morning", ["image.qr"])
        resp = await self.screen.get(f"/image?entity=image.qr&token={TOKEN}")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers["Content-Type"], "image/png")
        self.assertEqual(await resp.read(), b"png-bytes")
        self.assertTrue(resp.headers["ETag"].startswith('"'))
        self.assertEqual(resp.headers["Cache-Control"], "no-cache")

    async def test_image_endpoint_answers_304_for_the_same_etag(self):
        self.publish_screen_layout([{"id": "c1", "type": "haimage", "entity": "image.qr",
                                     "x": 0, "y": 0, "w": 2, "h": 2}])
        self.active.set_page("kitchen/morning", ["image.qr"])
        first = await self.screen.get(f"/image?entity=image.qr&token={TOKEN}")
        etag = first.headers["ETag"]
        again = await self.screen.get(f"/image?entity=image.qr&token={TOKEN}",
                                      headers={"If-None-Match": etag})
        self.assertEqual(again.status, 304)

    async def test_image_endpoint_needs_the_token_and_an_active_entity(self):
        self.publish_screen_layout([{"id": "c1", "type": "haimage", "entity": "image.qr",
                                     "x": 0, "y": 0, "w": 2, "h": 2}])
        self.active.set_page("kitchen/morning", ["image.qr"])
        self.assertEqual((await self.screen.get("/image?entity=image.qr")).status, 401)
        self.assertEqual((await self.screen.get(f"/image?entity=light.kitchen&token={TOKEN}")).status, 403)
        self.assertEqual((await self.screen.get(f"/image?entity=image.other&token={TOKEN}")).status, 403)


    async def test_screen_states_answers_304_for_unchanged_states(self):
        self.active.set_page("lights", ["light.kitchen"])
        first = await self.screen.get(f"/states?ids=light.kitchen&token={TOKEN}")
        etag = first.headers["ETag"]
        again = await self.screen.get(f"/states?ids=light.kitchen&token={TOKEN}",
                                      headers={"If-None-Match": etag})
        self.assertEqual(again.status, 304)

    async def test_editor_states_come_from_the_live_table_with_attributes(self):
        async def no_rest(entity_id):
            raise AssertionError("REST must not be called for a monitored entity")
        self.ha.state = no_rest
        resp = await self.editor.get("/api/states?ids=light.kitchen", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        view = (await resp.json())["states"]["light.kitchen"]
        self.assertEqual(view["state"], "off")
        self.assertEqual(view["name"], "Kitchen")
        self.assertIn("attributes", view)
        self.assertIsInstance(view["last_changed"], int)

    async def test_editor_states_ask_home_assistant_only_for_entities_missing_from_the_table(self):
        del self.bridge.states["light.hall"]
        calls = []
        original = self.ha.state
        async def counting(entity_id):
            calls.append(entity_id)
            return await original(entity_id)
        self.ha.state = counting
        resp = await self.editor.get("/api/states?ids=light.kitchen,light.hall", headers=INGRESS)
        self.assertEqual(calls, ["light.hall"])
        self.assertEqual((await resp.json())["states"]["light.hall"]["state"], "on")

    async def test_editor_states_answers_304_for_unchanged_states(self):
        first = await self.editor.get("/api/states?ids=light.kitchen", headers=INGRESS)
        etag = first.headers["ETag"]
        again = await self.editor.get("/api/states?ids=light.kitchen", headers={**INGRESS, "If-None-Match": etag})
        self.assertEqual(again.status, 304)

    async def test_editor_image_serves_bytes_with_etag_and_304(self):
        first = await self.editor.get("/api/image?entity=image.qr", headers=INGRESS)
        self.assertEqual(first.status, 200)
        self.assertEqual(first.headers["Content-Type"], "image/png")
        self.assertEqual(await first.read(), b"png-bytes")
        again = await self.editor.get("/api/image?entity=image.qr",
                                      headers={**INGRESS, "If-None-Match": first.headers["ETag"]})
        self.assertEqual(again.status, 304)

    async def test_editor_image_refuses_other_entities_and_requests_outside_ingress(self):
        self.assertEqual((await self.editor.get("/api/image?entity=light.kitchen", headers=INGRESS)).status, 403)
        self.assertNotEqual((await self.editor.get("/api/image?entity=image.qr")).status, 200)


    async def test_version_3_skins_are_refused_with_a_message_that_names_them(self):
        resp = await self.editor.post("/api/publish_save?path=skins/old&type=json", headers=INGRESS,
                                      json={"json": {"version": 3, "name": "old"}})
        self.assertEqual(resp.status, 400)
        self.assertIn("skin old is in version 3", (await resp.json())["error"])
        resp = await self.editor.post("/api/publish_save?path=skins/new&type=json", headers=INGRESS,
                                      json={"json": {"version": 1, "name": "new"}})
        self.assertEqual(resp.status, 200)

    async def test_screen_history_only_for_entities_on_its_layout(self):
        self.publish_screen_layout([{"id": "t1", "type": "entity", "entity": "sensor.temp",
                                     "x": 0, "y": 0, "w": 2, "h": 2}])
        self.active.set_page("kitchen/morning", ["sensor.temp"])
        resp = await self.screen.get(f"/history?entity=sensor.temp&token={TOKEN}")
        self.assertEqual(resp.status, 200)
        body = await resp.json()
        self.assertEqual(body["unit"], "°C")
        self.assertEqual(len(body["points"]), 120)
        self.assertEqual(resp.headers["Cache-Control"], "no-store")
        self.assertEqual((await self.screen.get("/history?entity=sensor.temp")).status, 401)
        self.assertEqual((await self.screen.get(f"/history?entity=light.kitchen&token={TOKEN}")).status, 403)

    async def test_history_refuses_bad_parameters_with_json_errors(self):
        self.publish_screen_layout([{"id": "t1", "type": "entity", "entity": "sensor.temp",
                                     "x": 0, "y": 0, "w": 2, "h": 2}])
        self.active.set_page("kitchen/morning", ["sensor.temp"])
        for query in ("hours=0", "hours=169", "points=5", "points=many"):
            resp = await self.screen.get(f"/history?entity=sensor.temp&{query}&token={TOKEN}")
            self.assertEqual(resp.status, 400, query)
            self.assertIn("error", await resp.json())

    async def test_editor_history_and_camera_follow_the_options(self):
        resp = await self.editor.get("/api/history?entity=sensor.temp", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        self.assertEqual((await self.editor.get("/api/history?entity=lock.front", headers=INGRESS)).status, 403)
        self.assertNotEqual((await self.editor.get("/api/history?entity=sensor.temp")).status, 200)
        resp = await self.editor.get("/api/camera?entity=camera.front", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        self.assertEqual(await resp.read(), b"png-bytes")
        self.assertEqual(resp.headers["Cache-Control"], "no-store")

    async def test_camera_still_on_the_screen_and_unavailable_cameras(self):
        self.publish_screen_layout([{"id": "c1", "type": "camera", "entity": "camera.front",
                                     "x": 0, "y": 0, "w": 2, "h": 2},
                                    {"id": "c2", "type": "camera", "entity": "camera.off",
                                     "x": 2, "y": 0, "w": 2, "h": 2},
                                    {"id": "t1", "type": "entity", "entity": "sensor.temp",
                                     "x": 4, "y": 0, "w": 2, "h": 2}])
        self.active.set_page("kitchen/morning", ["camera.front", "camera.off", "sensor.temp"])
        resp = await self.screen.get(f"/camera?entity=camera.front&token={TOKEN}&width=640&v=123")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers["Content-Type"], "image/png")
        self.assertEqual(await resp.read(), b"png-bytes")
        off = await self.screen.get(f"/camera?entity=camera.off&token={TOKEN}")
        self.assertEqual(off.status, 503)
        self.assertEqual((await off.json())["error"], "camera unavailable")
        self.assertEqual((await self.screen.get(f"/camera?entity=sensor.temp&token={TOKEN}")).status, 400)
        self.assertEqual((await self.screen.get(f"/camera?entity=camera.front&width=9000&token={TOKEN}")).status, 400)


    def actions(self):
        return [c for c in self.ha.calls if c[0] == "fully_kiosk"]

    async def test_fully_devices_lists_the_tablets_of_the_integration(self):
        self.publish_screen_layout()
        resp = await self.editor.get("/api/fully_devices", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        devices = (await resp.json())["devices"]
        self.assertEqual(len(devices), 1)
        tablet = devices[0]
        self.assertEqual(tablet["name"], "Kitchen tablet")
        self.assertTrue(tablet["online"])
        self.assertIsNone(tablet["screen"])
        self.assertEqual(tablet["admin_url"], "http://192.168.1.40:2323")
        self.assertFalse(tablet["start"])

    async def test_fully_show_creates_the_screen_and_loads_the_page(self):
        self.publish_screen_layout()
        resp = await self.editor.post("/api/fully_show", headers=INGRESS,
                                      json={"device_id": "dev1", "layout": "kitchen/morning", "start": True})
        self.assertEqual(resp.status, 200)
        body = await resp.json()
        self.assertEqual(body["screen"], "Kitchen tablet")
        self.assertIn("/dash/viewer.html?layout=kitchen/morning#token=", body["url"])
        self.assertEqual(self.actions()[0], ("fully_kiosk", "load_url", {"device_id": "dev1", "url": body["url"]}))
        self.assertEqual(self.actions()[1][1], "set_config")
        self.assertEqual(self.actions()[1][2], {"device_id": "dev1", "key": "startURL", "value": body["url"]})
        token = body["url"].split("#token=")[1]
        again = await self.editor.post("/api/fully_show", headers=INGRESS,
                                       json={"device_id": "dev1", "layout": "kitchen/morning"})
        self.assertEqual((await again.json())["url"].split("#token=")[1], token)
        self.assertEqual(len(self.actions()), 3)
        listed = (await (await self.editor.get("/api/fully_devices", headers=INGRESS)).json())["devices"][0]
        self.assertEqual((listed["screen"], listed["layout"]), ("Kitchen tablet", "kitchen/morning"))

    async def test_fully_show_refusals(self):
        self.publish_screen_layout()
        unpublished = await self.editor.post("/api/fully_show", headers=INGRESS,
                                             json={"device_id": "dev1", "layout": "kitchen/none"})
        self.assertEqual(unpublished.status, 400)
        self.assertEqual((await unpublished.json())["error"], "layout is not published")
        unknown = await self.editor.post("/api/fully_show", headers=INGRESS,
                                         json={"device_id": "dev9", "layout": "kitchen/morning"})
        self.assertEqual(unknown.status, 404)
        self.ha.action_error = "Device is offline"
        failed = await self.editor.post("/api/fully_show", headers=INGRESS,
                                        json={"device_id": "dev1", "layout": "kitchen/morning"})
        self.assertEqual(failed.status, 502)
        self.assertIn("Device is offline", (await failed.json())["error"])


    async def test_screen_rename_keeps_the_token_and_refuses_bad_names(self):
        self.publish_screen_layout()
        for name in ("Hall", "Kitchen"):
            made = await self.editor.post(f"/api/screen_save?name={name}&layout=kitchen/morning", headers=INGRESS)
            self.assertEqual(made.status, 200)
        token = self.app_screens().get("Hall")["token"]
        ok = await self.editor.post("/api/screen_rename?from=Hall&to=Garden", headers=INGRESS)
        self.assertEqual(ok.status, 200)
        self.assertEqual(self.app_screens().get("Garden")["token"], token)
        self.assertIsNone(self.app_screens().get("Hall"))
        self.assertTrue(any(c[0] == "set_state" and c[1] == "sensor.dash_screen_garden" for c in self.ha.calls))
        self.assertEqual((await self.editor.post("/api/screen_rename?from=Nope&to=X", headers=INGRESS)).status, 404)
        self.assertEqual((await self.editor.post("/api/screen_rename?from=Garden&to=Kitchen", headers=INGRESS)).status, 409)
        self.assertEqual((await self.editor.post("/api/screen_rename?from=Garden&to=bad/name", headers=INGRESS)).status, 400)

    def app_screens(self):
        return {s["name"]: s for s in self.screens.list()}

    async def test_sun_is_an_allowed_domain_by_default(self):
        from settings import DEFAULT_DOMAINS
        self.assertIn("sun", DEFAULT_DOMAINS)


    async def test_fonts_are_served_to_the_viewer_on_the_screen_port(self):
        resp = await self.screen.get("/dash/assets/fonts/Roboto-Variable.woff2")
        self.assertEqual(resp.status, 200)
        self.assertEqual(len(await resp.read()) > 100000, True)
        self.assertEqual((await self.screen.get("/dash/assets/fonts/OFL-Archivo.txt")).status, 200)
        self.assertEqual((await self.editor.get("/assets/fonts/Archivo-Variable.woff2", headers=INGRESS)).status, 200)
        self.assertEqual((await self.screen.get("/dash/assets/fonts/Roboto-Italic-Variable.woff2")).status, 200)
        self.assertEqual((await self.editor.get("/assets/fonts/Archivo-Italic-Variable.woff2", headers=INGRESS)).status, 200)


class UnreachableHaTests(unittest.TestCase):
    def test_unreachable_home_assistant_is_a_502_without_traceback(self):
        import asyncio as _asyncio
        import aiohttp as _aiohttp
        from web_common import handle_errors

        @handle_errors
        async def handler(request):
            raise _aiohttp.ClientConnectionError("down")

        with self.assertLogs("dash.api", level="WARNING") as logs:
            for _ in range(3):
                resp = _asyncio.run(handler(None))
                self.assertEqual(resp.status, 502)
        self.assertEqual(len(logs.records), 1)
        self.assertNotIn("Traceback", logs.output[0])


if __name__ == "__main__":
    unittest.main()
