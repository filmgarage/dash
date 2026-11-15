import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from ha_bridge import apply_event, public_view  # noqa: E402


class EventTests(unittest.TestCase):
    def test_added_state_is_stored_and_viewed(self):
        states = {}
        changed = apply_event(states, {"a": {"light.kitchen": {
            "s": "on", "a": {"friendly_name": "Kitchen", "brightness": 100, "secret": "x"}, "lu": 1.5}}})
        self.assertEqual(changed, {"light.kitchen"})
        view = public_view("light.kitchen", states["light.kitchen"])
        self.assertEqual(view["state"], "on")
        self.assertEqual(view["name"], "Kitchen")
        self.assertEqual(view["last_changed"], 1500)
        self.assertEqual(view["attributes"], {"brightness": 100})

    def test_changed_diff_updates_state_and_removes_attributes(self):
        states = {"light.kitchen": {"s": "on", "a": {"brightness": 100}, "lu": 1.0}}
        apply_event(states, {"c": {"light.kitchen": {"+": {"s": "off"}, "-": {"a": ["brightness"]}}}})
        self.assertEqual(states["light.kitchen"]["s"], "off")
        self.assertNotIn("brightness", states["light.kitchen"]["a"])

    def test_removed_entity_has_no_view(self):
        states = {"light.kitchen": {"s": "on", "a": {}, "lu": 1.0}}
        changed = apply_event(states, {"r": ["light.kitchen"]})
        self.assertEqual(changed, {"light.kitchen"})
        self.assertIsNone(public_view("light.kitchen", states.get("light.kitchen")))


if __name__ == "__main__":
    unittest.main()
