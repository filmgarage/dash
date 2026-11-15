import base64
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from errors import ApiError  # noqa: E402
from store import Store, clean_image_base, parse_path  # noqa: E402

PNG = "data:image/png;base64," + base64.b64encode(b"png-bytes").decode()
JPEG = "data:image/jpeg;base64," + base64.b64encode(b"jpeg-bytes").decode()


def layout(entity="light.kitchen", src=None):
    tile = {"id": "t1", "type": "light", "entity": entity, "x": 0, "y": 0, "w": 2, "h": 2}
    if src:
        tile["props"] = {"src": src}
    return {"title": "Morning", "columns": 12, "rows": 8, "tiles": [tile]}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.publish_dir = os.path.join(self.tmp.name, "www")
        self.store = Store(os.path.join(self.tmp.name, "layouts"), self.publish_dir, "/dash",
                           os.path.join(self.tmp.name, "published"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_path_rules(self):
        self.assertEqual(parse_path("kitchen/morning"), ["kitchen", "morning"])
        for bad in ["", "../etc", "a/b/c/d/e", "bad name", "/lead", "trail/"]:
            self.assertIsNone(parse_path(bad), bad)

    def test_save_and_load(self):
        saved = self.store.save_layout(["kitchen", "morning"], layout(), "")
        loaded = self.store.load_layout(["kitchen", "morning"])
        self.assertEqual(loaded["saved"], saved)
        self.assertEqual(loaded["version"], 1)
        self.assertEqual(self.store.published_entities(["kitchen", "morning"]), set())
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.snapshot_layout(["kitchen", "morning"])
        self.assertEqual(self.store.published_entities(["kitchen", "morning"]), {"light.kitchen"})

    def test_screen_sees_the_published_version_not_the_draft(self):
        self.store.save_layout(["kitchen", "morning"], layout(), "")
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.snapshot_layout(["kitchen", "morning"])
        self.store.save_layout(["kitchen", "morning"], layout(entity="light.hall"), "")
        published = self.store.load_published(["kitchen", "morning"])
        self.assertEqual(published["tiles"][0]["entity"], "light.kitchen")
        self.assertEqual(self.store.published_entities(["kitchen", "morning"]), {"light.kitchen"})

    def test_deleting_a_page_removes_the_published_copy(self):
        self.store.save_layout(["kitchen", "morning"], layout(), "")
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.snapshot_layout(["kitchen", "morning"])
        self.store.delete_page(["kitchen", "morning"])
        with self.assertRaises(ApiError):
            self.store.load_published(["kitchen", "morning"])

    def test_if_saved_conflict(self):
        saved = self.store.save_layout(["morning"], layout(), "")
        self.store.save_layout(["morning"], layout(), str(saved))
        with self.assertRaises(ApiError) as ctx:
            self.store.save_layout(["morning"], layout(), "1")
        self.assertEqual(ctx.exception.status, 409)

    def test_skins_are_reserved(self):
        with self.assertRaises(ApiError) as ctx:
            self.store.save_layout(["skins", "night"], layout(), "")
        self.assertEqual(ctx.exception.status, 400)

    def test_invalid_entity_is_refused(self):
        with self.assertRaises(ApiError):
            self.store.save_layout(["morning"], layout(entity="Light.Kitchen"), "")

    def test_publish_and_list(self):
        url = self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.assertEqual(url, "/dash/kitchen/morning.html")
        pages = self.store.publish_list()
        self.assertEqual(pages, [{"path": "kitchen/morning", "type": "html", "url": url}])

    def test_published_layout_cannot_be_deleted_or_moved(self):
        self.store.save_layout(["kitchen", "morning"], layout(), "")
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        with self.assertRaises(ApiError) as ctx:
            self.store.delete_layout(["kitchen", "morning"])
        self.assertEqual(ctx.exception.status, 409)
        with self.assertRaises(ApiError) as ctx:
            self.store.move_layout(["kitchen", "morning"], ["archive", "old"])
        self.assertEqual(ctx.exception.status, 409)
        self.store.delete_page(["kitchen", "morning"])
        self.store.delete_layout(["kitchen", "morning"])

    def test_move_rewrites_image_urls_and_moves_files(self):
        self.store.save_layout(["kitchen", "morning"], layout(), "")
        upload = self.store.upload_image(("layout", ["kitchen", "morning"]), "Photo Garden.JPG", JPEG)
        self.assertEqual(upload["name"], "photo-garden.jpg")
        src = "/dash/kitchen/morning/photo-garden.jpg"
        self.store.save_layout(["kitchen", "morning"], layout(src=src), "")

        self.store.move_layout(["kitchen", "morning"], ["archive", "old"])

        moved = self.store.load_layout(["archive", "old"])
        self.assertEqual(moved["tiles"][0]["props"]["src"], "/dash/archive/old/photo-garden.jpg")
        self.assertTrue(os.path.isfile(os.path.join(self.publish_dir, "archive", "old", "photo-garden.jpg")))
        with self.assertRaises(ApiError):
            self.store.load_layout(["kitchen", "morning"])

    def test_image_names_are_cleaned_and_made_unique(self):
        self.assertEqual(clean_image_base("Photo Garden.JPG"), "photo-garden")
        owner = ("layout", ["kitchen", "morning"])
        first = self.store.upload_image(owner, "Photo Garden.JPG", JPEG)
        second = self.store.upload_image(owner, "Photo Garden.JPG", JPEG)
        self.assertEqual(first["name"], "photo-garden.jpg")
        self.assertEqual(second["name"], "photo-garden-2.jpg")

    def test_image_rules(self):
        owner = ("layout", ["kitchen", "morning"])
        cases = {
            "data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode(): 415,
            "data:image/png;base64,": 400,
            "data:image/png;base64,!!!": 400,
            "not a data url": 400,
        }
        for data_url, status in cases.items():
            with self.assertRaises(ApiError) as ctx:
                self.store.upload_image(owner, "x.png", data_url)
            self.assertEqual(ctx.exception.status, status, data_url[:30])

    def test_skin_pointer_must_name_an_existing_skin(self):
        self.store.publish_skin(["skins", "night"], {"name": "Night"})
        self.store.publish_skin(["skins", "_default"], {"skin": "night"})
        for body in ({"skin": "missing"}, {"skin": "night", "extra": 1}, {"skin": "_default"}):
            with self.assertRaises(ApiError) as ctx:
                self.store.publish_skin(["skins", "_default"], body)
            self.assertEqual(ctx.exception.status, 400)

    def test_deleting_a_skin_removes_its_images(self):
        self.store.publish_skin(["skins", "night"], {"name": "Night"})
        self.store.upload_image(("skin", "night"), "stars.png", PNG)
        self.store.delete_skin(["skins", "night"])
        self.assertFalse(os.path.exists(os.path.join(self.publish_dir, "skins", "night")))

    def test_publish_list_hides_images_and_lists_skins(self):
        self.store.publish_html(["kitchen", "morning"], "<html></html>")
        self.store.publish_skin(["skins", "night"], {"name": "Night"})
        self.store.upload_image(("layout", ["kitchen", "morning"]), "a.png", PNG)
        kinds = [(p["type"], p["path"]) for p in self.store.publish_list()]
        self.assertEqual(kinds, [("html", "kitchen/morning"), ("json", "skins/night")])


if __name__ == "__main__":
    unittest.main()
