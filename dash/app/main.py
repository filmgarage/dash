"""DASH add-on.

- Ingress UI (port 8099, only reachable from the Home Assistant sidebar): choose the entities the screens may see.
- Screen API (port 8092, read token): snapshot, live updates over a websocket, and service calls.
Layouts and publishing come in a later version.
"""
import asyncio
import json
import logging
import os
import re
import secrets
from pathlib import Path

from aiohttp import ClientSession, WSMsgType, web

from ha_bridge import HaBridge, public_view

log = logging.getLogger("dash")
APP_VERSION = "0.1.4"

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
OPTIONS_PATH = Path(os.environ.get("OPTIONS_PATH", "/data/options.json"))
SELECTION_PATH = DATA_DIR / "selection.json"
SUPERVISOR_URL = os.environ.get("SUPERVISOR_URL", "http://supervisor")
HA_WS_URL = os.environ.get("HA_WS_URL", "http://supervisor/core/api/websocket")  # same path AppDaemon uses
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
UI_PORT = int(os.environ.get("UI_PORT", "8099"))
SCREEN_PORT = int(os.environ.get("SCREEN_PORT", "8092"))

ENTITY_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
KEY_RE = re.compile(r"^[a-z_]+$")
ALLOWED_SERVICES = {
    "toggle", "turn_on", "turn_off", "press",
    "open_cover", "close_cover", "stop_cover", "set_cover_position",
    "lock", "unlock",
    "set_temperature", "set_hvac_mode", "set_preset_mode", "set_fan_mode",
    "select_option", "set_value", "set_percentage",
    "media_play_pause", "media_next_track", "media_previous_track",
}
INGRESS_HEADER = "X-Ingress-Path"


def read_options():
    try:
        return json.loads(OPTIONS_PATH.read_text())
    except (OSError, ValueError):
        return {}


def supervisor_headers():
    return {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}


def error(message, status):
    return web.json_response({"error": message}, status=status)


class Selection:
    """The entities the screens may see. Stored in /data, so it survives restarts."""

    def __init__(self, path):
        self.path = path
        self.entities = set()
        self.listeners = []
        if path.exists():
            try:
                self.entities = set(json.loads(path.read_text())["entities"])
            except (OSError, ValueError, KeyError):
                log.error("Could not read %s; starting with an empty selection", path)

    def save(self, entities):
        clean = sorted(set(entities))
        bad = [e for e in clean if not ENTITY_RE.match(e)]
        if bad:
            raise ValueError(f"invalid entity id: {bad[0]}")
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"entities": clean}, indent=2))
        tmp.replace(self.path)
        self.entities = set(clean)
        for listener in self.listeners:
            listener()


class Hub:
    """Connected screens, and the entities each one subscribed to."""

    def __init__(self):
        self.clients = {}  # websocket -> set of entity ids

    async def broadcast(self, entity_id, view):
        if view is None:
            message = {"type": "removed", "entity_id": entity_id}
        else:
            message = {"type": "state", "entity_id": entity_id, "data": view}
        for ws, subs in list(self.clients.items()):
            if entity_id in subs:
                try:
                    await ws.send_json(message)
                except Exception:  # the screen went away; its handler removes it
                    log.debug("could not send to a screen")


@web.middleware
async def ingress_only(request, handler):
    if INGRESS_HEADER not in request.headers:
        return error("open DASH from the Home Assistant sidebar", 403)
    return await handler(request)


def screen_auth(request):
    """None when the request carries the screen token, otherwise an error response."""
    token = request.app["read_token"]
    if not token:
        return error("no screen token set in the add-on options", 503)
    given = request.query.get("token", "")
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        given = header[len("Bearer "):]
    if not given or not secrets.compare_digest(given.encode(), token.encode()):
        return error("unauthorized", 401)
    return None


# ---------- Ingress UI (port 8099) ----------

async def ui_index(request):
    return web.FileResponse(APP_DIR / "ui" / "index.html")


async def ui_status(request):
    app = request.app
    return web.json_response({
        "ha_connected": app["bridge"].connected,
        "selected": len(app["selection"].entities),
        "screen_token_set": bool(app["read_token"]),
        "screen_port": SCREEN_PORT,
    })


async def ui_ha_entities(request):
    if not SUPERVISOR_TOKEN:
        return error("no Supervisor token: homeassistant_api is not active. Rebuild the add-on after "
                     "updating config.yaml (version 0.1.1 or later)", 503)
    async with request.app["http"].get(f"{SUPERVISOR_URL}/core/api/states",
                                       headers=supervisor_headers()) as r:
        if r.status != 200:
            return error(f"Home Assistant answered {r.status} to the entity list", 502)
        states = await r.json()
    items = []
    for s in states:
        eid = s.get("entity_id", "")
        if not ENTITY_RE.match(eid):
            continue
        attrs = s.get("attributes") or {}
        items.append({"entity_id": eid, "domain": eid.split(".", 1)[0],
                      "name": attrs.get("friendly_name", eid),
                      "device_class": attrs.get("device_class", "") or ""})
    items.sort(key=lambda i: i["entity_id"])
    return web.json_response({"entities": items})


async def ui_get_selection(request):
    return web.json_response({"entities": sorted(request.app["selection"].entities)})


async def ui_put_selection(request):
    try:
        body = await request.json()
    except ValueError:
        return error("body must be JSON", 400)
    entities = body.get("entities") if isinstance(body, dict) else None
    if not isinstance(entities, list) or not all(isinstance(e, str) for e in entities):
        return error('expected {"entities": ["light.kitchen", ...]}', 400)
    try:
        request.app["selection"].save(entities)
    except ValueError as err:
        return error(str(err), 400)
    return web.json_response({"ok": True, "count": len(request.app["selection"].entities)})


# ---------- Screen API (port 8092) ----------

async def screen_health(request):
    return web.json_response({"ok": True})


async def screen_states(request):
    denied = screen_auth(request)
    if denied:
        return denied
    app = request.app
    wanted = [e for e in request.query.get("ids", "").split(",") if e] or sorted(app["selection"].entities)
    states = {e: public_view(e, app["bridge"].states.get(e)) for e in wanted
              if e in app["selection"].entities and e in app["bridge"].states}
    return web.json_response({"states": states})


async def screen_service(request):
    denied = screen_auth(request)
    if denied:
        return denied
    app = request.app
    try:
        body = await request.json()
    except ValueError:
        return error("body must be JSON", 400)
    entity_id = body.get("entity_id", "")
    service = body.get("service", "")
    data = body.get("data") or {}
    if entity_id not in app["selection"].entities:
        return error("entity is not available on the screens", 403)
    if service not in ALLOWED_SERVICES:
        return error("service not allowed", 403)
    if not isinstance(data, dict) or not all(KEY_RE.match(k) for k in data):
        return error("invalid service data", 400)
    domain = entity_id.split(".", 1)[0]
    payload = {**data, "entity_id": entity_id}
    async with app["http"].post(f"{SUPERVISOR_URL}/core/api/services/{domain}/{service}",
                                json=payload, headers=supervisor_headers()) as r:
        if r.status >= 300:
            return error(f"Home Assistant answered {r.status}", 502)
    return web.json_response({"ok": True})


async def screen_ws(request):
    denied = screen_auth(request)
    if denied:
        return denied
    app = request.app
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    subs = set()
    app["hub"].clients[ws] = subs
    log.info("Screen connected (%d now)", len(app["hub"].clients))
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                await ws.send_json({"type": "error", "error": "invalid json"})
                continue
            if not isinstance(data, dict) or data.get("type") != "subscribe":
                continue
            wanted = [e for e in data.get("entities", [])
                      if isinstance(e, str) and e in app["selection"].entities]
            subs.clear()
            subs.update(wanted)
            states = {e: public_view(e, app["bridge"].states.get(e))
                      for e in wanted if e in app["bridge"].states}
            await ws.send_json({"type": "snapshot", "states": states})
    finally:
        app["hub"].clients.pop(ws, None)
        log.info("Screen disconnected (%d now)", len(app["hub"].clients))
    return ws


def build_apps(ctx):
    ui = web.Application(middlewares=[ingress_only])
    screens = web.Application()
    for app in (ui, screens):
        for key, value in ctx.items():
            app[key] = value
    ui.router.add_get("/", ui_index)
    ui.router.add_get("/api/status", ui_status)
    ui.router.add_get("/api/ha/entities", ui_ha_entities)
    ui.router.add_get("/api/selection", ui_get_selection)
    ui.router.add_put("/api/selection", ui_put_selection)
    screens.router.add_get("/health", screen_health)
    screens.router.add_get("/ws", screen_ws)
    screens.router.add_get("/api/states", screen_states)
    screens.router.add_post("/api/service", screen_service)
    return ui, screens


async def main():
    options = read_options()
    logging.basicConfig(level=str(options.get("log_level", "info")).upper(),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log.info("DASH add-on version %s", APP_VERSION)
    log.info("Supervisor environment variables present: %s",
             sorted(k for k in os.environ if "SUPERVISOR" in k or k.startswith("HASS")) or "none")
    log.debug("All environment variable names: %s", sorted(os.environ))
    if not SUPERVISOR_TOKEN:
        log.error("SUPERVISOR_TOKEN is missing. Check that the add-on runs version %s and that "
                  "homeassistant_api: true is in its config.yaml; then rebuild the add-on", APP_VERSION)
    selection = Selection(SELECTION_PATH)
    http = ClientSession()
    hub = Hub()
    bridge = HaBridge(HA_WS_URL, SUPERVISOR_TOKEN, selection, hub.broadcast)
    selection.listeners.append(bridge.selection_changed)
    ctx = {"selection": selection, "bridge": bridge, "hub": hub, "http": http,
           "read_token": str(options.get("read_token", ""))}
    ui, screens = build_apps(ctx)
    for app, port in ((ui, UI_PORT), (screens, SCREEN_PORT)):
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("DASH started: interface on %d, screens on %d", UI_PORT, SCREEN_PORT)
    await bridge.run()


if __name__ == "__main__":
    asyncio.run(main())
