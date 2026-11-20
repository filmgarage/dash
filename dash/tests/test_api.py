from app_keys import ACTIVE, APP_SETTINGS_PATH, BRIDGE, DETECTED_IP, HA, HUB, IMAGES, INTERNAL_URL, OPTIONS, PICTURE_LOCKS, PICTURE_SLOTS, SAVED, SCREENS, STORE
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
        }
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


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        with open(os.path.join(root, "screens.json"), "w", encoding="utf-8") as f:
            json.dump({"screens": [{"name": "Test", "layout": "kitchen/morning", "token": TOKEN}]}, f)
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
                        "allow_domains": {"light", "sensor", "image"},
                        "screen_address_mode": "ip", "screen_ip": "",
                        "allow_entities": set(), "exclude_domains": {"lock", "alarm_control_panel"},
                        "exclude_entities": set(),
                        "services": {"toggle", "turn_on"}, "read_services": {"toggle"}},
            STORE: self.store, ACTIVE: self.active, BRIDGE: self.bridge,
            HUB: self.hub, HA: self.ha, IMAGES: {}, PICTURE_LOCKS: {}, PICTURE_SLOTS: asyncio.Semaphore(4), SCREENS: ScreenStore(os.path.join(root, "screens.json")), SAVED: {}, DETECTED_IP: "192.168.69.248",
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
        self.assertEqual((await resp.json())["version"], "0.8.8")

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
