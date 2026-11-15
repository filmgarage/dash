"""Paths, limits and add-on options. Environment variables override the paths for local testing."""
import json
import logging
import os
from pathlib import Path

APP_VERSION = "0.7.0"

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
OPTIONS_PATH = Path(os.environ.get("OPTIONS_PATH", str(DATA_DIR / "options.json")))
LAYOUT_DIR = Path(os.environ.get("LAYOUT_DIR", str(DATA_DIR / "layouts")))
SETTINGS_PATH = DATA_DIR / "settings.json"
ACTIVE_PATH = Path(os.environ.get("ACTIVE_PATH", str(DATA_DIR / "active.json")))
PUBLISHED_DIR = Path(os.environ.get("PUBLISHED_DIR", str(DATA_DIR / "published")))
PUBLISH_DIR = Path(os.environ.get("PUBLISH_DIR", str(DATA_DIR / "www" / "dash")))
PUBLISH_URL = os.environ.get("PUBLISH_URL", "/dash")
UI_DIR = Path(__file__).resolve().parent / "ui"

UI_PORT = int(os.environ.get("UI_PORT", "8099"))
SCREEN_PORT = int(os.environ.get("SCREEN_PORT", "8092"))
HA_WS_URL = os.environ.get("HA_WS_URL", "http://supervisor/core/api/websocket")

S6_ENV_DIR = "/run/s6/container_environment"

DEFAULT_DOMAINS = [
    "light", "switch", "input_boolean", "scene", "script", "cover", "fan",
    "lock", "button", "input_button", "select", "input_select",
    "number", "input_number", "climate", "media_player",
    "sensor", "binary_sensor", "weather", "image",
]
# Locks and alarm panels are excluded by default. Remove them from these lists to allow them.
DEFAULT_EXCLUDE_DOMAINS = ["lock", "alarm_control_panel"]
LOCK_ALARM_SERVICES = [
    "lock", "unlock", "open", "alarm_arm_away", "alarm_arm_home", "alarm_arm_night",
    "alarm_arm_vacation", "alarm_arm_custom_bypass", "alarm_disarm", "alarm_trigger",
]
DEFAULT_SERVICES = [
    "toggle", "turn_on", "turn_off", "press",
    "open_cover", "close_cover", "stop_cover", "set_cover_position",
    "lock", "unlock",
    "set_temperature", "set_hvac_mode", "set_preset_mode", "set_fan_mode",
    "select_option", "set_value", "set_percentage",
    "media_play_pause", "media_next_track", "media_previous_track",
]


def read_env(name):
    """An environment variable, or the same value from the s6-overlay container environment store."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        with open(os.path.join(S6_ENV_DIR, name), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


SUPERVISOR_URL = read_env("SUPERVISOR_URL") or "http://supervisor"
SUPERVISOR_TOKEN = read_env("SUPERVISOR_TOKEN")


def load_options(path=OPTIONS_PATH):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    def names(key):
        return set(str(x) for x in (raw.get(key) or []))

    def excluded(key, default):
        # A missing key takes the default; an empty list excludes nothing.
        value = raw.get(key)
        return set(default) if value is None else set(str(x) for x in value)

    services = (set(raw.get("services") or DEFAULT_SERVICES) | names("allow_services")) \
        - excluded("exclude_services", LOCK_ALARM_SERVICES)
    read_services = (set(raw.get("read_services") or DEFAULT_SERVICES) | names("allow_read_services")) \
        - excluded("exclude_read_services", LOCK_ALARM_SERVICES)
    return {
        "read_token": str(raw.get("read_token") or ""),
        "log_level": str(raw.get("log_level") or "info"),
        "allow_domains": set(raw.get("allow_domains") or DEFAULT_DOMAINS),
        "allow_entities": names("allow_entities"),
        "exclude_domains": excluded("exclude_domains", DEFAULT_EXCLUDE_DOMAINS),
        "exclude_entities": names("exclude_entities"),
        "screen_address_mode": str(raw.get("screen_address_mode") or "ip"),
        "screen_ip": str(raw.get("screen_ip") or "").strip(),
        "services": services,
        "read_services": read_services,
    }


def log_level(name):
    return getattr(logging, str(name).upper(), logging.INFO)
