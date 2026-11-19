"""Screen tokens (contract 9.0): storage and what a screen token may reach. There is no master token."""
from app_keys import ACTIVE, APP_SETTINGS_PATH, BRIDGE, DETECTED_IP, HA, HUB, IMAGES, INTERNAL_URL, OPTIONS, PICTURE_LOCKS, PICTURE_SLOTS, SAVED, SCREENS, STORE
import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from screens import TOKEN_PREFIX, ScreenStore  # noqa: E402
import test_api as api_tests  # noqa: E402  (module import: its test classes are not collected twice)

LAYOUT = api_tests.LAYOUT
INGRESS = api_tests.INGRESS


class ScreenStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "screens.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_screen_gets_its_own_prefixed_token_and_keeps_it_on_change(self):
        store = ScreenStore(self.path)
        first = store.save_screen("Kitchen", "kitchen/morning")
        self.assertTrue(first["token"].startswith(TOKEN_PREFIX))
        again = store.save_screen("Kitchen", "hall/evening")
        self.assertEqual(again["token"], first["token"])
        self.assertEqual(again["layout"], "hall/evening")

    def test_tokens_are_unique_and_found_by_token(self):
        store = ScreenStore(self.path)
        a = store.save_screen("A", "x")
        b = store.save_screen("B", "y")
        self.assertNotEqual(a["token"], b["token"])
        self.assertEqual(store.find_by_token(b["token"])["name"], "B")
        self.assertIsNone(store.find_by_token("nope"))

    def test_rotate_and_delete(self):
        store = ScreenStore(self.path)
        old = store.save_screen("A", "x")
        new = store.rotate("A")
        self.assertNotEqual(new["token"], old["token"])
        self.assertIsNone(store.find_by_token(old["token"]))
        self.assertTrue(store.delete("A"))
        self.assertFalse(store.delete("A"))

    def test_saved_to_disk(self):
        ScreenStore(self.path).save_screen("A", "x")
        self.assertEqual(ScreenStore(self.path).get("A")["layout"], "x")

    def test_names_are_checked(self):
        store = ScreenStore(self.path)
        for bad in ("", "../x", "a" * 41, " lead", "x/y"):
            with self.assertRaises(ValueError, msg=bad):
                store.save_screen(bad, "x")


class ScopeTests(unittest.IsolatedAsyncioTestCase):
    """Uses the API test setup from test_api.py (not inherited, so its tests are not run twice)."""

    async def asyncSetUp(self):
        await api_tests.ApiTests.asyncSetUp(self)
        self.store.save_layout(["kitchen", "morning"], LAYOUT, "")
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.snapshot_layout(["kitchen", "morning"])
        self.store.save_layout(["hall", "evening"], {"title": "Evening", "tiles": [
            {"id": "t2", "type": "light", "entity": "light.hall", "x": 0, "y": 0, "w": 2, "h": 2}]}, "")
        self.store.publish_html(["hall", "evening"], "<html></html>")
        self.store.snapshot_layout(["hall", "evening"])
        self.active.set_page("kitchen/morning", ["light.kitchen"])
        self.active.set_page("hall/evening", ["light.hall"])
        self.screen_record = self.screens_store().save_screen("Kitchen", "kitchen/morning")

    async def asyncTearDown(self):
        await api_tests.ApiTests.asyncTearDown(self)

    def screens_store(self):
        return self.editor.app[SCREENS]

    def auth(self):
        return {"Authorization": f"Bearer {self.screen_record['token']}"}

    async def test_a_screen_token_sees_only_its_own_entities(self):
        resp = await self.screen.get("/states?ids=light.kitchen,light.hall", headers=self.auth())
        self.assertEqual(resp.status, 200)
        states = (await resp.json())["states"]
        self.assertIn("light.kitchen", states)
        self.assertNotIn("light.hall", states)

    async def test_a_screen_token_loads_only_its_own_layout(self):
        own = await self.screen.get("/layout_load?path=kitchen/morning", headers=self.auth())
        self.assertEqual(own.status, 200)
        other = await self.screen.get("/layout_load?path=hall/evening", headers=self.auth())
        self.assertEqual(other.status, 403)

    async def test_a_screen_token_controls_only_its_own_entities(self):
        other = await self.screen.post("/service?entity_id=light.hall&service=toggle&layout=hall/evening",
                                      headers=self.auth())
        self.assertEqual(other.status, 403)
        own = await self.screen.post("/service?entity_id=light.kitchen&service=toggle&layout=hall/evening",
                                    headers=self.auth())
        self.assertEqual(own.status, 403)  # the layout is fixed by the token, the request names another one
        ok = await self.screen.post("/service?entity_id=light.kitchen&service=toggle", headers=self.auth())
        self.assertEqual(ok.status, 200)

    async def test_a_screen_token_gets_no_other_pictures(self):
        self.assertEqual((await self.screen.get("/image?entity=image.qr", headers=self.auth())).status, 403)

    async def test_a_request_without_a_screen_token_is_refused(self):
        self.assertEqual((await self.screen.get("/states")).status, 401)
        self.assertEqual((await self.screen.get(f"/states?token={api_tests.TOKEN}")).status, 200)  # the test screen

    async def test_an_unknown_token_is_refused(self):
        resp = await self.screen.get("/states", headers={"Authorization": "Bearer autotoken_unknown"})
        self.assertEqual(resp.status, 401)

    async def test_the_push_channel_of_a_screen_token_gets_its_own_entities(self):
        async with self.screen.ws_connect(f"/ws?token={self.screen_record['token']}") as ws:
            first = await ws.receive_json()
            self.assertEqual(set(first["states"]), {"light.kitchen"})

    async def test_rotating_closes_the_open_push_channel_and_the_old_token_stops(self):
        old = self.screen_record["token"]
        ws = await self.screen.ws_connect(f"/ws?token={old}")
        await ws.receive_json()
        resp = await self.editor.post("/api/screen_rotate?name=Kitchen", headers=INGRESS)
        self.assertEqual(resp.status, 200)
        await ws.receive()
        self.assertEqual(ws.close_code, 4401)
        self.assertEqual((await self.screen.get("/states", headers={"Authorization": f"Bearer {old}"})).status, 401)

    async def test_screen_management_is_only_through_ingress_and_needs_a_published_layout(self):
        self.assertEqual((await self.editor.get("/api/screens")).status, 403)
        listed = await (await self.editor.get("/api/screens", headers=INGRESS)).json()
        self.assertIn("Kitchen", [s["name"] for s in listed["screens"]])
        unpublished = await self.editor.post("/api/screen_save?name=Den&layout=den/x", headers=INGRESS)
        self.assertEqual(unpublished.status, 400)
        created = await self.editor.post("/api/screen_save?name=Den&layout=hall/evening", headers=INGRESS)
        self.assertEqual(created.status, 200)
        deleted = await self.editor.post("/api/screen_delete?name=Den", headers=INGRESS)
        self.assertEqual(deleted.status, 200)


if __name__ == "__main__":
    unittest.main()
