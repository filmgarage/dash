"""P1: scenes, scripts and buttons are excluded by default, so a user switches them on by removing them from exclude_domains."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import stat
import tempfile

from settings import DEFAULT_DOMAINS, DEFAULT_EXCLUDE_DOMAINS  # noqa: E402
from screens import ScreenStore  # noqa: E402


class DefaultDomainTests(unittest.TestCase):
    def test_scene_script_and_buttons_are_excluded_by_default(self):
        for domain in ("scene", "script", "button", "input_button"):
            self.assertIn(domain, DEFAULT_DOMAINS)
            self.assertIn(domain, DEFAULT_EXCLUDE_DOMAINS)

    def test_locks_and_alarm_panels_stay_excluded_by_default(self):
        self.assertIn("lock", DEFAULT_EXCLUDE_DOMAINS)
        self.assertIn("alarm_control_panel", DEFAULT_EXCLUDE_DOMAINS)

    def test_screen_token_file_is_owner_only(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "screens.json")
            ScreenStore(path).save_screen("kitchen", "kitchen/morning")
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
