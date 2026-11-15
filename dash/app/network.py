"""Find and store the address that screens use (the LAN address of the Home Assistant host)."""
import ipaddress
import json
import logging
import os

from aiohttp import ClientTimeout

log = logging.getLogger("dash.network")
DOCKER_PREFIX = "172.30."  # the Supervisor's internal network, never a screen address


def valid_ipv4(text):
    try:
        return str(ipaddress.IPv4Address(str(text).strip()))
    except ValueError:
        return None


def pick_lan_ip(payload):
    """Pick the primary LAN address from a Supervisor /network/info answer. Docker addresses are skipped."""
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    candidates = []
    for iface in data.get("interfaces") or []:
        if not isinstance(iface, dict):
            continue
        for addr in (iface.get("ipv4") or {}).get("address") or []:
            ip = valid_ipv4(str(addr).split("/")[0])
            if ip and not ip.startswith((DOCKER_PREFIX, "127.")):
                candidates.append((0 if iface.get("primary") else 1, ip))
    return min(candidates)[1] if candidates else None


async def detect_lan_ip(session, supervisor_url, token):
    if not token:
        return None
    try:
        async with session.get(supervisor_url + "/network/info",
                               headers={"Authorization": "Bearer " + token},
                               timeout=ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                log.warning("Could not read network info from the Supervisor (HTTP %s); "
                            "the designer will ask for the address", resp.status)
                return None
            ip = pick_lan_ip(await resp.json())
    except Exception as exc:  # network errors must not stop the add-on
        log.warning("Could not read network info from the Supervisor: %s", exc)
        return None
    log.info("Detected LAN address %s", ip) if ip else log.warning("No LAN address found in network info")
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
