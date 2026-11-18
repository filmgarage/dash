import os
import re
import unittest

UI_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "ui", "index.html")

# The editor runs through Ingress (contract 4.2 and 8.2). It must not:
# - request anything from the screen port or from another origin (fetch, XHR, WebSocket, EventSource, img src),
# - hard-code the screen port (the port comes from api/status as screen_port),
# - use absolute paths, external CDNs, the old Home Assistant www path or AppDaemon routes,
# - keep an iframe, or embed a read token in its code.
# A plain link (<a href> or a string shown to the user) to a published page is allowed: it is a navigation
# to a new tab, not a request made by the editor (contract 4.2).
REQUEST_CALL = r"""(?:fetch|XMLHttpRequest|WebSocket|EventSource|\.open)\s*\(\s*[^)]{0,200}"""
FORBIDDEN = [
    (re.compile(r"8092"), "hard-coded port 8092 (use screen_port from api/status)"),
    (re.compile(REQUEST_CALL + r"""https?://|wss?://"""), "request to an absolute or external URL"),
    (re.compile(r"""src\s*=\s*["'`]https?://"""), "image or script from an absolute URL"),
    (re.compile(r"unpkg|jsdelivr|cdnjs|googleapis|gstatic"), "external CDN or font host"),
    (re.compile(r"""(?:fetch|src|action)\s*[=(]\s*["'`]/"""), "absolute path in a request"),
    (re.compile(r"""["'`]/(?:api|local|dash)/"""), "absolute API, /local/ or /dash/ path"),
    (re.compile(r"/local/"), "Home Assistant www path"),
    (re.compile(r"appdaemon", re.IGNORECASE), "AppDaemon route or code"),
    (re.compile(r"new\s+WebSocket|EventSource|XMLHttpRequest"), "direct websocket or XHR"),
    (re.compile(r"<iframe", re.IGNORECASE), "iframe (the viewer is a separate page)"),
    (re.compile(r"""push\(\s*['"]token="""), "API helper adds a read token to editor requests"),
    (re.compile(r"\bconst\s+TOKEN\s*="), "token embedded in exported code"),
]


# The bundler's ext_resources list only names the URLs that were packed into the file. The code itself is
# embedded (base64, keyed by uuid) and is loaded without network access, so that list is not checked.
BUNDLE_LIST = re.compile(r'<script type="__bundler/ext_resources">.*?</script>', re.S)


# The editor builds the address it shows for a screen with this fallback. It is text the owner copies, never a request.
SCREEN_ADDRESS_FALLBACK = "(this.pubPrefix || '/dash/')"


def find_problems(text):
    text = BUNDLE_LIST.sub("", text).replace(SCREEN_ADDRESS_FALLBACK, "")
    return [label for pattern, label in FORBIDDEN if pattern.search(text)]


class EditorUiTests(unittest.TestCase):
    def test_editor_page_follows_contract(self):
        with open(UI_FILE, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(find_problems(text), [], "editor page breaks contract 4.2 / 8.2")

    def test_rules_catch_known_violations(self):
        self.assertIn("hard-coded port 8092 (use screen_port from api/status)", find_problems("const p = 8092;"))
        self.assertIn("request to an absolute or external URL", find_problems('fetch("http://192.168.1.5:8092/x")'))
        self.assertEqual([], find_problems('const u = "http://" + host + ":" + port;'))
        self.assertEqual([], find_problems('<a href="http://192.168.1.5:9000/dash/x.html" target="_blank">x</a>'))
        self.assertIn("AppDaemon route or code", find_problems('const BASE = "/api/appdaemon/";'))
        self.assertIn("external CDN or font host", find_problems('<script src="https://unpkg.com/x.js">'))


if __name__ == "__main__":
    unittest.main()
