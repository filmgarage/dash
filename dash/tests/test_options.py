import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from active import ActiveSet  # noqa: E402
from settings import load_options  # noqa: E402
from web_common import is_allowed  # noqa: E402


def options_from(raw):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "options.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)
        return load_options(path)


class OptionsTests(unittest.TestCase):
    def test_locks_and_alarms_are_excluded_by_default(self):
        opts = options_from({})
        self.assertFalse(is_allowed(opts, "lock.front_door"))
        self.assertFalse(is_allowed(opts, "alarm_control_panel.home"))
        self.assertNotIn("unlock", opts["read_services"])
        self.assertNotIn("alarm_disarm", opts["read_services"])
        self.assertTrue(is_allowed(opts, "light.kitchen"))

    def test_empty_exclude_list_excludes_nothing(self):
        opts = options_from({"exclude_domains": [], "exclude_read_services": [], "read_services": ["unlock"]})
        self.assertTrue(is_allowed(opts, "lock.front_door"))
        self.assertIn("unlock", opts["read_services"])

    def test_allow_entities_adds_single_entities(self):
        # vacuum is not in the default domains, so only the listed entity is allowed
        opts = options_from({"allow_entities": ["vacuum.robot"]})
        self.assertTrue(is_allowed(opts, "vacuum.robot"))
        self.assertFalse(is_allowed(opts, "vacuum.other"))

    def test_exclude_entities_wins_over_allow(self):
        opts = options_from({"allow_entities": ["light.kitchen"], "exclude_entities": ["light.kitchen"]})
        self.assertFalse(is_allowed(opts, "light.kitchen"))

    def test_allow_domains_replaces_the_defaults(self):
        options = options_from({"allow_domains": ["light"]})
        self.assertEqual(options["allow_domains"], {"light"})

    def test_empty_allow_domains_uses_the_defaults(self):
        options = options_from({"allow_domains": []})
        self.assertIn("light", options["allow_domains"])
        self.assertIn("sensor", options["allow_domains"])

    def test_allow_read_services_adds_to_defaults(self):
        opts = options_from({"allow_read_services": ["custom_action"], "exclude_read_services": ["toggle"]})
        self.assertIn("custom_action", opts["read_services"])
        self.assertNotIn("toggle", opts["read_services"])


class ActiveFilterTests(unittest.TestCase):
    def test_excluded_entities_are_never_monitored(self):
        opts = options_from({})
        with tempfile.TemporaryDirectory() as tmp:
            active = ActiveSet(os.path.join(tmp, "active.json"),
                               allowed=lambda e: is_allowed(opts, e))
            active.set_page("kitchen/morning", ["light.kitchen", "lock.front_door"])
            self.assertEqual(active.entities, {"light.kitchen"})


if __name__ == "__main__":
    unittest.main()
