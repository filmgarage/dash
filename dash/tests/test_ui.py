import os
import re
import unittest

UI_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "ui", "index.html")

# The editor runs through Ingress (contract 4.2 and 8.2). It must not:
# - call the screen port, or hard-code it,
# - use absolute paths, external hosts or the old Home Assistant www path,
# - keep AppDaemon routes, in the editor or in code it exports,
# - open a websocket or XHR of its own, or embed a read token in its code.
FORBIDDEN = [
    (re.compile(r"8092"), "port 8092 (the screen server)"),
    (re.compile(r"https?://|wss?://"), "absolute or external URL"),
    (re.compile(r"unpkg|jsdelivr|cdnjs|googleapis|gstatic"), "external CDN or font host"),
    (re.compile(r"""(?:fetch|src|href|action)\s*[=(]\s*["'`]/"""), "absolute path in a request"),
    (re.compile(r"""["'`]/(?:api|local|dash)/"""), "absolute API, /local/ or /dash/ path"),
    (re.compile(r"/local/"), "Home Assistant www path"),
    (re.compile(r"appdaemon", re.IGNORECASE), "AppDaemon route or code"),
    (re.compile(r"new\s+WebSocket|EventSource|XMLHttpRequest"), "direct websocket or XHR"),
    (re.compile(r"<iframe", re.IGNORECASE), "iframe (the viewer is a separate page)"),
    (re.compile(r"""push\(\s*['"]token="""), "API helper adds a read token to editor requests"),
    (re.compile(r"\bconst\s+TOKEN\s*="), "token embedded in exported code"),
]


def find_problems(text):
    return [label for pattern, label in FORBIDDEN if pattern.search(text)]


class EditorUiTests(unittest.TestCase):
    def test_editor_page_follows_contract(self):
        with open(UI_FILE, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(find_problems(text), [], "editor page breaks contract 4.2 / 8.2")

    def test_rules_catch_known_violations(self):
        self.assertIn("port 8092 (the screen server)", find_problems("const p = 8092;"))
        self.assertIn("AppDaemon route or code", find_problems('const BASE = "/api/appdaemon/";'))
        self.assertIn("external CDN or font host", find_problems('<script src="https://unpkg.com/x.js">'))


if __name__ == "__main__":
    unittest.main()
