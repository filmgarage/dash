"""Find and store the address that screens use (the LAN address of the Home Assistant host)."""
import ipaddress
import json
import logging
import os
import urllib.parse

log = logging.getLogger("dash.network")
DOCKER_PREFIX = "172.30."  # the Supervisor's internal network, never a screen address


def valid_ipv4(text):
    try:
        return str(ipaddress.IPv4Address(str(text).strip()))
    except ValueError:
        return None


SCREEN_HOST_ENTITY = "sensor.local_ip"  # from the Local IP Address integration, if the user added it


async def read_internal_url(ha):
    """internal_url from the Home Assistant configuration, or None when the user has not set it."""
    try:
        config = await ha.config()
    except Exception as exc:  # network errors must not stop the add-on
        log.warning("Could not read the Home Assistant configuration: %s", exc)
        return None
    url = config.get("internal_url") if isinstance(config, dict) else None
    return url if isinstance(url, str) and url else None


def ip_from_url(url):
    """The IPv4 address in a URL such as http://192.168.1.10:8123, or None (also for host names)."""
    if not url:
        return None
    try:
        host = urllib.parse.urlsplit(url).hostname
    except ValueError:
        return None
    ip = valid_ipv4(host) if host else None
    return None if ip is None or ip.startswith((DOCKER_PREFIX, "127.")) else ip


async def detect_lan_ip(ha, internal_url=None):
    """The LAN address of the Home Assistant host, read once at start. Order: the IPv4 address in internal_url,
    then sensor.local_ip (Local IP Address integration). None when neither gives an address; the designer asks then.
    Docker addresses are never used."""
    ip = ip_from_url(internal_url)
    if ip:
        log.info("Detected LAN address %s from internal_url", ip)
        return ip
    try:
        s = await ha.state(SCREEN_HOST_ENTITY)
    except Exception as exc:  # network errors must not stop the add-on
        log.warning("Could not read %s: %s", SCREEN_HOST_ENTITY, exc)
        return None
    if s is None:
        log.info("No usable internal_url and no %s: set the screen address in the designer, or add the Local IP "
                 "Address integration", SCREEN_HOST_ENTITY)
        return None
    ip = valid_ipv4(s.get("state"))
    if ip is None or ip.startswith((DOCKER_PREFIX, "127.")):
        log.warning("%s does not hold a usable LAN address", SCREEN_HOST_ENTITY)
        return None
    log.info("Detected LAN address %s from %s", ip, SCREEN_HOST_ENTITY)
    return ip


def resolve_screen_host(options, saved, detected):
    """Return (address, source). Order: the option, the address saved by the designer, the detected address."""
    for source, value in (("option", options.get("screen_ip")), ("saved", saved.get("screen_ip")),
                          ("detected", detected)):
        ip = valid_ipv4(value) if value else None
        if ip:
            return ip, source
    return None, None


def load_saved(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_saved(path, data):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)
