import os
import re
import unittest

VIEWER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "ui", "viewer.html")

# The viewer runs in two places (contract 8.5, section 6.1). It may use its own push channel and the read token
# on port 8092, but it must still be self-contained and must not use the old paths or AppDaemon.
FORBIDDEN = [
    (re.compile(r"https?://"), "external URL in the viewer (skins may use their own font URL, not the viewer)"),
    (re.compile(r"unpkg|jsdelivr|cdnjs|googleapis|gstatic"), "external CDN or font host"),
    (re.compile(r"/local/"), "Home Assistant www path"),
    (re.compile(r"appdaemon", re.IGNORECASE), "AppDaemon route or code"),
    (re.compile(r"<iframe", re.IGNORECASE), "iframe"),
]


def find_problems(text):
    return [label for pattern, label in FORBIDDEN if pattern.search(text)]


class ViewerTests(unittest.TestCase):
    def test_viewer_is_self_contained(self):
        with open(VIEWER_FILE, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(find_problems(text), [], "viewer breaks contract 6.1")

    def test_viewer_names_its_contract_version(self):
        with open(VIEWER_FILE, encoding="utf-8") as f:
            first = f.readline()
        self.assertIn("contract 8.6", first)


if __name__ == "__main__":
    unittest.main()
