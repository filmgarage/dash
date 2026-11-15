import os
import re
import unittest

UI_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "ui", "index.html")

# The editor runs through Ingress. It must never call the screen port or use absolute or external URLs.
FORBIDDEN = [
    (re.compile(r"8092"), "port 8092 (the screen server)"),
    (re.compile(r"https?://|wss?://"), "absolute or external URL"),
    (re.compile(r"""(?:fetch|src|href|action)\s*[=(]\s*["'`]/"""), "absolute path (breaks Ingress)"),
    (re.compile(r"/local/"), "Home Assistant www path"),
    (re.compile(r"new\s+WebSocket|EventSource|XMLHttpRequest"), "direct websocket or XHR"),
    (re.compile(r"token="), "read token in the editor"),
]


class EditorUiTests(unittest.TestCase):
    def test_editor_page_follows_contract(self):
        with open(UI_FILE, encoding="utf-8") as f:
            text = f.read()
        problems = [label for pattern, label in FORBIDDEN if pattern.search(text)]
        self.assertEqual(problems, [], "editor page breaks contract 4.2")


if __name__ == "__main__":
    unittest.main()
