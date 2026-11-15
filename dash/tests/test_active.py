import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from active import ActiveSet  # noqa: E402


class ActiveSetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "active.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_union_and_reasons(self):
        active = ActiveSet(self.path)
        active.set_page("kitchen/morning", ["light.a", "sensor.b"])
        active.set_page("test", ["sensor.b"])
        self.assertEqual(active.entities, {"light.a", "sensor.b"})
        self.assertEqual(active.reasons()["sensor.b"], ["kitchen/morning", "test"])

    def test_removing_a_page_keeps_shared_entities(self):
        active = ActiveSet(self.path)
        active.set_page("kitchen/morning", ["light.a", "sensor.b"])
        active.set_page("test", ["sensor.b"])
        added, removed = active.remove_page("kitchen/morning")
        self.assertEqual(added, [])
        self.assertEqual(removed, ["light.a"])
        self.assertEqual(active.entities, {"sensor.b"})

    def test_changes_are_reported_and_persisted(self):
        calls = []
        active = ActiveSet(self.path)
        active.listeners.append(lambda added, removed: calls.append((added, removed)))
        self.assertEqual(active.set_page("test", ["light.a"]), (["light.a"], []))
        self.assertEqual(active.set_page("test", ["light.a"]), ([], []))
        self.assertEqual(calls, [(["light.a"], [])])
        self.assertEqual(ActiveSet(self.path).entities, {"light.a"})


if __name__ == "__main__":
    unittest.main()
