"""DASH in Home Assistant: text sensors for published pages and for screens.

- Page sensor: sensor.dash_<page path>. State is the page URL on the screen server (no token).
- Screen sensor: sensor.dash_screen_<name>. State is the complete viewer URL of the screen, token included,
  so an automation can give it to a display as its start URL.

Home Assistant keeps the states that the App writes only until its next restart, so the App writes them again at
startup. A deleted page or screen gets the state "removed". Screen sensors hold the token: Home Assistant stores
their history in its recorder.
"""
import asyncio
import logging
import re
from urllib.parse import quote

import aiohttp

from app_keys import DETECTED_IP, HA, OPTIONS, SAVED, SCREENS, STORE
from errors import ApiError
from network import resolve_screen_host
from settings import PUBLISH_URL, SCREEN_PORT

log = logging.getLogger("dash.pages")
SLUG_RE = re.compile(r"[^a-z0-9]+")
ATTRIBUTION = "DASH HA App"
ICON = "mdi:monitor-dashboard"


def _slug(text):
    return SLUG_RE.sub("_", text.lower()).strip("_")


def sensor_id(path):
    return f"sensor.dash_{_slug(path)}"


def screen_sensor_id(name):
    return f"sensor.dash_screen_{_slug(name)}"


def page_name(path):
    """The readable name of a page in Home Assistant, for example "thuis / woonkamer"."""
    return " / ".join(path.split("/"))


def page_url(host, path):
    return f"http://{host}:{SCREEN_PORT}{PUBLISH_URL}/{path}.html"


def screen_url(host, layout, token):
    """The viewer for a layout, with the screen token after # so that it is not sent in the request line."""
    return f"http://{host}:{SCREEN_PORT}{PUBLISH_URL}/viewer.html?layout={quote(layout, safe='/')}#token={token}"


def placeholder_url(host):
    """Shown on a screen whose layout is not published (no token needed)."""
    return f"http://{host}:{SCREEN_PORT}{PUBLISH_URL}/placeholder.html"


def _screen_state(store, host, screen):
    """The screen's sensor state: the viewer URL with its token, or the placeholder while its layout is unpublished."""
    if not host:
        return "no screen address"
    parts = screen["layout"].split("/")
    if not store.is_published(parts):
        return placeholder_url(host)
    return screen_url(host, screen["layout"], screen["token"])


def _page_state(store, screens, host, path):
    """A page's sensor state. The page needs a token: the token of a screen with the same layout is used.
    Without such a screen, or while the layout is unpublished, the placeholder is shown."""
    if not host:
        return "no screen address"
    if not store.is_published(path.split("/")):
        return placeholder_url(host)
    for screen in screens:
        if screen["layout"] == path:
            return f"{page_url(host, path)}#token={screen['token']}"
    return placeholder_url(host)


def _attributes(kind, key, removed, **extra):
    return {"attribution": ATTRIBUTION, "kind": kind, "key": key, "removed": removed,
            "icon": ICON, **extra}


async def _write(ha, entity_id, state, attributes):
    try:
        await ha.set_state(entity_id, state, attributes)
    except (ApiError, OSError, aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning("Could not write %s: %s", entity_id, e)
        return False
    return True


def _host(options, saved, detected):
    host, _source = resolve_screen_host(options, saved or {}, detected)
    return host


# --- pages -------------------------------------------------------------------------------------------------

async def write_page(app, path):
    host = _host(app[OPTIONS], app.get(SAVED), app.get(DETECTED_IP))
    state = _page_state(app[STORE], app[SCREENS].list(), host, path)
    return await _write(app[HA], sensor_id(path), state,
                        _attributes("page", path, False, friendly_name=page_name(path)))


async def publish_page(app, parts):
    """Writes the sensor of one page. Used after a page is saved; a failure does not fail the save."""
    path = "/".join(parts)
    ok = await write_page(app, path)
    await _refresh_screens(app, path)
    return ok


async def unpublish_page(app, parts):
    path = "/".join(parts)
    ok = await _write(app[HA], sensor_id(path), "removed",
                      _attributes("page", path, True, friendly_name=page_name(path)))
    await _refresh_screens(app, path)
    return ok


async def _refresh_screens(app, layout):
    """A screen shows its layout or the placeholder, so its sensor changes when the layout is published or not."""
    for screen in app[SCREENS].list():
        if screen["layout"] == layout:
            await write_screen(app, screen)


# --- screens -----------------------------------------------------------------------------------------------

async def write_screen(app, screen):
    """Writes the sensor of one screen, token included. Used after a screen is saved, rotated or deleted in the App."""
    host = _host(app[OPTIONS], app.get(SAVED), app.get(DETECTED_IP))
    state = _screen_state(app[STORE], host, screen)
    ok = await _write(app[HA], screen_sensor_id(screen["name"]), state,
                      _attributes("screen", screen["name"], False, friendly_name=f"DASH screen {screen['name']}",
                                  layout=screen["layout"]))
    await write_page(app, screen["layout"])
    return ok


async def remove_screen(app, name, layout):
    ok = await _write(app[HA], screen_sensor_id(name), "removed",
                      _attributes("screen", name, True, friendly_name=f"DASH screen {name}"))
    await write_page(app, layout)
    return ok


# --- startup -----------------------------------------------------------------------------------------------

async def sync_all(ha, store, screens, options, saved, detected):
    """Writes the sensors of all published pages and all screens. Called at startup."""
    host = _host(options, saved, detected)
    written = 0
    for page in store.publish_list():
        if page["type"] != "html":
            continue
        path = page["path"]
        if await _write(ha, sensor_id(path), _page_state(store, screens.list(), host, path),
                        _attributes("page", path, False, friendly_name=page_name(path))):
            written += 1
    for screen in screens.list():
        if await _write(ha, screen_sensor_id(screen["name"]), _screen_state(store, host, screen),
                        _attributes("screen", screen["name"], False, friendly_name=f"DASH screen {screen['name']}",
                                    layout=screen["layout"])):
            written += 1
    log.info("Wrote %d page and screen sensor(s) to Home Assistant", written)
    return written
