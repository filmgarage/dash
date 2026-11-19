"""Keys for the application state. aiohttp warns about plain string keys, so each shared object has one typed key.

The types are not imported here: several modules import this file, and importing the classes back would create
import cycles. Each key still carries a name and a type description in its docstring-like comment."""
import asyncio
from typing import Any

from aiohttp import web

OPTIONS = web.AppKey("options", dict)  # the App options, as loaded at start
STORE = web.AppKey("store", Any)  # store.Store: layouts and published pages
ACTIVE = web.AppKey("active", Any)  # active.ActiveSet: entities in use by published pages
BRIDGE = web.AppKey("bridge", Any)  # ha_bridge.HaBridge: the live state table
HUB = web.AppKey("hub", Any)  # hub.Hub: connected screens
HA = web.AppKey("ha", Any)  # ha.Supervisor: Home Assistant REST access
IMAGES = web.AppKey("images", dict)  # picture cache, entity id -> cached picture
PICTURE_LOCKS = web.AppKey("picture_locks", dict)  # one lock per entity that is being downloaded
PICTURE_SLOTS = web.AppKey("picture_slots", asyncio.Semaphore)  # limits concurrent picture downloads
SCREENS = web.AppKey("screens", Any)  # screens.ScreenStore: screens and their tokens
APP_SETTINGS_PATH = web.AppKey("settings_path", str)  # where saved settings are written
SAVED = web.AppKey("saved", dict)  # saved settings (screen address)
DETECTED_IP = web.AppKey("detected_ip", Any)  # LAN address found at start, or None
INTERNAL_URL = web.AppKey("internal_url", Any)  # Home Assistant internal URL, or None
