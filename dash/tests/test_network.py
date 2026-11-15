import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from network import pick_lan_ip, resolve_screen_host, valid_ipv4  # noqa: E402

SAMPLE = {"data": {"interfaces": [
    {"interface": "hassio", "ipv4": {"address": ["172.30.32.1/23"]}},
    {"interface": "eth0", "primary": True, "ipv4": {"address": ["192.168.69.248/24"], "method": "static"}},
]}}


class NetworkTests(unittest.TestCase):
    def test_primary_lan_address_wins_and_docker_is_skipped(self):
        self.assertEqual(pick_lan_ip(SAMPLE), "192.168.69.248")

    def test_no_usable_address(self):
        self.assertIsNone(pick_lan_ip({"data": {"interfaces": [
            {"interface": "hassio", "ipv4": {"address": ["172.30.32.1/23"]}}]}}))
        self.assertIsNone(pick_lan_ip({}))

    def test_valid_ipv4(self):
        self.assertEqual(valid_ipv4(" 192.168.1.10 "), "192.168.1.10")
        self.assertIsNone(valid_ipv4("badassist.duckdns.org"))
        self.assertIsNone(valid_ipv4("192.168.1.300"))

    def test_resolve_order(self):
        self.assertEqual(resolve_screen_host({"screen_ip": "10.0.0.2"}, {"screen_ip": "10.0.0.3"}, "10.0.0.4"),
                         ("10.0.0.2", "option"))
        self.assertEqual(resolve_screen_host({"screen_ip": ""}, {"screen_ip": "10.0.0.3"}, "10.0.0.4"),
                         ("10.0.0.3", "saved"))
        self.assertEqual(resolve_screen_host({"screen_ip": ""}, {}, "10.0.0.4"), ("10.0.0.4", "detected"))
        self.assertEqual(resolve_screen_host({"screen_ip": "nonsense"}, {}, None), (None, None))


if __name__ == "__main__":
    unittest.main()
