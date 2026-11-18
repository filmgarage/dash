import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import asyncio  # noqa: E402

from errors import ApiError  # noqa: E402
from network import detect_lan_ip, ip_from_url, resolve_screen_host, valid_ipv4  # noqa: E402


class FakeHa:
    """Answers for sensor.local_ip only: the value given, None (not there) or an error."""
    def __init__(self, answer):
        self.answer = answer

    async def state(self, entity_id):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def run(coro):
    return asyncio.run(coro)


class NetworkTests(unittest.TestCase):
    def test_address_from_the_local_ip_sensor(self):
        self.assertEqual(run(detect_lan_ip(FakeHa({"state": "192.168.69.248"}))), "192.168.69.248")

    def test_no_sensor_means_no_detection(self):
        self.assertIsNone(run(detect_lan_ip(FakeHa(None))))

    def test_unusable_values_are_ignored(self):
        self.assertIsNone(run(detect_lan_ip(FakeHa({"state": "unavailable"}))))
        self.assertIsNone(run(detect_lan_ip(FakeHa({"state": "172.30.32.1"}))))
        self.assertIsNone(run(detect_lan_ip(FakeHa({"state": "127.0.0.1"}))))

    def test_internal_url_with_an_address_wins(self):
        self.assertEqual(run(detect_lan_ip(FakeHa({"state": "10.0.0.9"}), "http://192.168.1.10:8123")), "192.168.1.10")

    def test_internal_url_with_a_host_name_falls_back_to_the_sensor(self):
        self.assertEqual(run(detect_lan_ip(FakeHa({"state": "10.0.0.9"}), "http://homeassistant.local:8123")),
                         "10.0.0.9")

    def test_ip_from_url(self):
        self.assertEqual(ip_from_url("https://192.168.2.5:8123/"), "192.168.2.5")
        self.assertIsNone(ip_from_url("http://172.30.32.1:8123"))
        self.assertIsNone(ip_from_url(None))
        self.assertIsNone(ip_from_url("not a url ]"))

    def test_home_assistant_errors_do_not_stop_the_add_on(self):
        self.assertIsNone(run(detect_lan_ip(FakeHa(ApiError("Home Assistant answered 500", 502)))))

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
