"""Screen API on port 8092. Every route except health needs the read token. No CORS headers are sent."""
import asyncio
import json
import logging

from aiohttp import WSMsgType, web

from errors import ApiError
from ha_bridge import public_view
from store import checked, parse_path
from settings import UI_DIR
from web_common import (MAX_IDS, MAX_SCREENS, MAX_WS_MESSAGE, SERVICE_NAME_RE, call_params, handle_errors,
                        is_allowed, json_etag, picture_entry, picture_http, picture_response, request_token,
                        screen_scope, scoped_entities, service_data)
from app_keys import BRIDGE, HA, HUB, OPTIONS, SCREENS, STORE

log = logging.getLogger("dash.screen")
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_TOO_MANY = 1013  # "try again later": the screen limit is reached


@handle_errors
async def health(request):
    return web.json_response({"ok": True})


@handle_errors
async def states(request):
    scope = screen_scope(request)
    app = request.app
    allowed = scoped_entities(app, scope)
    ids = ([i for i in request.query.get("ids", "").split(",") if i] or sorted(allowed))[:MAX_IDS]
    out = {}
    for entity_id in ids:
        if entity_id in allowed and entity_id in app[BRIDGE].states:
            out[entity_id] = public_view(entity_id, app[BRIDGE].states[entity_id])
    return json_etag(request, {"states": out})


@handle_errors
async def layout_load(request):
    scope = screen_scope(request)
    parts = checked(parse_path(request.query.get("path")))
    if parts != parse_path(scope["layout"]):
        raise ApiError("this screen shows another layout", 403)
    return web.json_response({"layout": request.app[STORE].load_published(parts)})


@handle_errors
async def service(request):
    """POST only (contract 9.0): the parameters come from the query string and from a JSON object body."""
    scope = screen_scope(request)
    app = request.app
    options = app[OPTIONS]
    store = app[STORE]
    params = await call_params(request)
    if params.get("layout") not in (None, "", scope["layout"]):
        raise ApiError("this screen shows another layout", 403)
    params["layout"] = scope["layout"]
    entity_id = params.get("entity_id", "")
    name = params.get("service", "")
    layout = parse_path(params.get("layout"))
    if layout is None:
        raise ApiError("this token needs a valid layout", 403)
    if not is_allowed(options, entity_id):
        raise ApiError("entity not allowed", 403)
    if not SERVICE_NAME_RE.match(name) or name not in options["read_services"]:
        raise ApiError("service not allowed for this token", 403)
    if not store.is_published(layout):
        raise ApiError("layout is not published", 403)
    if entity_id not in store.published_entities(layout):
        raise ApiError("entity is not on this layout", 403)
    app[HA].require_token()
    data = service_data(params, name)
    s = await app[HA].state(entity_id)
    if s is None:
        raise ApiError("entity not found", 404)
    if s.get("state") == "unavailable":
        raise ApiError("entity unavailable", 503)
    await app[HA].call_service(entity_id, name, data)
    return web.json_response({"ok": True})


@handle_errors
async def imagedata(request):
    scope = screen_scope(request)
    app = request.app
    entity_id = request.query.get("entity", "")
    if not entity_id.startswith("image.") or not is_allowed(app[OPTIONS], entity_id) \
            or entity_id not in scoped_entities(app, scope):
        raise ApiError("no allowed image entity", 403)
    app[HA].require_token()
    return await picture_response(app, entity_id, request.query.get("hash", ""))


@handle_errors
async def image(request):
    """The picture as plain image bytes, with an ETag. The browser asks again with If-None-Match."""
    scope = screen_scope(request)
    app = request.app
    entity_id = request.query.get("entity", "")
    if not entity_id.startswith("image.") or not is_allowed(app[OPTIONS], entity_id) \
            or entity_id not in scoped_entities(app, scope):
        raise ApiError("no allowed image entity", 403)
    app[HA].require_token()
    return picture_http(request, await picture_entry(app, entity_id))


AUTH_TIMEOUT = 10  # seconds a screen has to send its auth message (contract 8.9)


async def live(request):
    """Push channel. The token comes in the URL or Bearer header, or in a first message {"type": "auth", "token": ...}
    (contract 8.9). A screen token limits the channel to the entities of its layout (contract 9.0)."""
    ws = web.WebSocketResponse(heartbeat=30, max_msg_size=MAX_WS_MESSAGE)
    app = request.app
    hub = app[HUB]
    if request_token(request) or request.query.get("token"):
        try:
            scope = screen_scope(request)
        except ApiError:
            await ws.prepare(request)
            await ws.close(code=WS_CLOSE_UNAUTHORIZED)
            return ws
        await ws.prepare(request)
    else:
        await ws.prepare(request)
        ok, scope = await _authenticate_by_message(app, ws)
        if not ok:
            await ws.close(code=WS_CLOSE_UNAUTHORIZED)
            return ws
    if len(hub.clients) >= MAX_SCREENS:
        await ws.close(code=WS_CLOSE_TOO_MANY)
        return ws
    allowed = scoped_entities(app, scope)
    # Everything from here on is inside try/finally, so the client is always removed, even if the first send fails.
    try:
        hub.add(ws, scope["token"])
        hub.subscribe(ws, allowed)
        await ws.send_json({"type": "states", "states": hub.snapshot(allowed)})
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
            entities = data.get("entities")
            entities = entities[:MAX_IDS] if isinstance(entities, list) else []
            wanted = {e for e in entities if isinstance(e, str) and e in allowed}
            hub.subscribe(ws, wanted)
            await ws.send_json({"type": "states", "states": hub.snapshot(wanted)})
    finally:
        hub.remove(ws)
    return ws


async def _authenticate_by_message(app, ws):
    """Waits for the first message and checks its screen token. Returns (ok, record); ok is False when the message
    is missing, late, or the token is not a screen token."""
    try:
        msg = await ws.receive(timeout=AUTH_TIMEOUT)
    except asyncio.TimeoutError:
        return False, None
    if msg.type != WSMsgType.TEXT:
        return False, None
    try:
        data = json.loads(msg.data)
    except ValueError:
        return False, None
    if not isinstance(data, dict) or data.get("type") != "auth":
        return False, None
    given = data.get("token")
    record = app[SCREENS].find_by_token(given) if isinstance(given, str) and given else None
    return record is not None, record


@handle_errors
async def viewer_page(request):
    return web.FileResponse(UI_DIR / "viewer.html")


async def placeholder_page(request):
    """Shown on a screen whose layout is not published. No token is needed."""
    return web.FileResponse(UI_DIR / "placeholder.html")


@handle_errors
async def favicon(request):
    return web.FileResponse(UI_DIR / "assets" / "favicon.png")


def add_routes(app):
    store = app[STORE]
    router = app.router
    # The viewer is part of the HA App. It is registered before the static route, so an old copy in
    # the publish folder is never served.
    router.add_get(store.publish_url + "/viewer.html", viewer_page)
    router.add_get(store.publish_url + "/placeholder.html", placeholder_page)
    router.add_get(store.publish_url + "/favicon.png", favicon)
    router.add_static(store.publish_url, store.publish_dir, show_index=False)
    router.add_get("/health", health)
    router.add_get("/states", states)
    router.add_get("/layout_load", layout_load)
    router.add_post("/service", service)
    router.add_get("/imagedata", imagedata)
    router.add_get("/image", image)
    router.add_get("/ws", live)
