import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from aiohttp import ClientSession  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

import main  # noqa: E402
from ha_bridge import HaBridge, apply_event, public_view  # noqa: E402


class EventTests(unittest.TestCase):
    def test_full_state_then_diff(self):
        states = {}
        changed = apply_event(states, {"a": {"light.kitchen": {"s": "off", "a": {"friendly_name": "Kitchen"}, "lu": 1}}})
        self.assertEqual(changed, {"light.kitchen"})
        apply_event(states, {"c": {"light.kitchen": {
            "+": {"s": "on", "a": {"brightness": 200}, "lu": 2}, "-": {"a": ["friendly_name"]}}}})
        self.assertEqual(states["light.kitchen"]["s"], "on")
        self.assertEqual(states["light.kitchen"]["a"], {"brightness": 200})

    def test_removed_entity(self):
        states = {"sensor.x": {"s": "1", "a": {}, "lu": 0}}
        self.assertEqual(apply_event(states, {"r": ["sensor.x"]}), {"sensor.x"})
        self.assertNotIn("sensor.x", states)
        self.assertIsNone(public_view("sensor.x", states.get("sensor.x")))

    def test_public_view_keeps_only_allowed_attributes(self):
        view = public_view("light.kitchen", {"s": "on", "a": {"friendly_name": "Kitchen", "brightness": 120,
                                                              "secret_value": "no"}, "lu": 1.5})
        self.assertEqual(view["name"], "Kitchen")
        self.assertEqual(view["attributes"], {"brightness": 120})
        self.assertEqual(view["last_changed"], 1500)


class SelectionTests(unittest.TestCase):
    def test_save_notifies_and_reloads(self):
        path = Path(tempfile.mkdtemp()) / "selection.json"
        sel = main.Selection(path)
        calls = []
        sel.listeners.append(lambda: calls.append(1))
        sel.save(["light.kitchen", "light.kitchen", "switch.fan"])
        self.assertEqual(sel.entities, {"light.kitchen", "switch.fan"})
        self.assertEqual(calls, [1])
        self.assertEqual(main.Selection(path).entities, {"light.kitchen", "switch.fan"})

    def test_rejects_invalid_ids_and_keeps_old_selection(self):
        sel = main.Selection(Path(tempfile.mkdtemp()) / "selection.json")
        sel.save(["light.kitchen"])
        with self.assertRaises(ValueError):
            sel.save(["light.kitchen", "../etc/passwd"])
        self.assertEqual(sel.entities, {"light.kitchen"})


class EndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.http = ClientSession()
        self.selection = main.Selection(Path(tempfile.mkdtemp()) / "selection.json")
        self.hub = main.Hub()
        self.bridge = HaBridge("ws://unused", "x", self.selection, self.hub.broadcast)
        self.bridge.states = {"light.kitchen": {"s": "on", "a": {"friendly_name": "Kitchen"}, "lu": 1}}
        self.selection.save(["light.kitchen"])
        ctx = {"selection": self.selection, "bridge": self.bridge, "hub": self.hub, "http": self.http,
               "read_token": "secret"}
        self.ui, self.screens = main.build_apps(ctx)
        self.ui_client = TestClient(TestServer(self.ui))
        self.screen_client = TestClient(TestServer(self.screens))
        await self.ui_client.start_server()
        await self.screen_client.start_server()

    async def asyncTearDown(self):
        await self.ui_client.close()
        await self.screen_client.close()
        await self.http.close()

    async def test_ui_refuses_direct_access(self):
        r = await self.ui_client.get("/api/selection")
        self.assertEqual(r.status, 403)

    async def test_ui_saves_selection_through_ingress(self):
        headers = {main.INGRESS_HEADER: "/api/hassio_ingress/dash"}
        r = await self.ui_client.put("/api/selection", json={"entities": ["switch.fan"]}, headers=headers)
        self.assertEqual(r.status, 200)
        r = await self.ui_client.put("/api/selection", json={"entities": ["bad id"]}, headers=headers)
        self.assertEqual(r.status, 400)

    async def test_screen_needs_token(self):
        r = await self.screen_client.get("/api/states")
        self.assertEqual(r.status, 401)
        r = await self.screen_client.get("/api/states?token=secret")
        self.assertEqual(r.status, 200)
        body = await r.json()
        self.assertEqual(list(body["states"]), ["light.kitchen"])

    async def test_screen_service_only_for_selected_entities(self):
        r = await self.screen_client.post("/api/service?token=secret",
                                          json={"entity_id": "switch.other", "service": "toggle"})
        self.assertEqual(r.status, 403)
        r = await self.screen_client.post("/api/service?token=secret",
                                          json={"entity_id": "light.kitchen", "service": "delete_everything"})
        self.assertEqual(r.status, 403)


if __name__ == "__main__":
    unittest.main()
