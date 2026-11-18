"""Screen API on port 8092. Every route except health needs the read token. No CORS headers are sent."""
import json
import logging

from aiohttp import WSMsgType, web

from errors import ApiError
from ha_bridge import public_view
from store import checked, parse_path
from settings import UI_DIR
from web_common import (SERVICE_NAME_RE, check_screen_token, handle_errors, is_allowed, json_etag,
                        picture_entry, picture_http, picture_response, service_data)

log = logging.getLogger("dash.screen")
WS_CLOSE_UNAUTHORIZED = 4401


@handle_errors
async def health(request):
    return web.json_response({"ok": True})


@handle_errors
async def states(request):
    check_screen_token(request)
    app = request.app
    active = app["active"].entities
    ids = [i for i in request.query.get("ids", "").split(",") if i] or sorted(active)
    out = {}
    for entity_id in ids:
        if entity_id in active and entity_id in app["bridge"].states:
            out[entity_id] = public_view(entity_id, app["bridge"].states[entity_id])
    return json_etag(request, {"states": out})


@handle_errors
async def layout_load(request):
    check_screen_token(request)
    parts = checked(parse_path(request.query.get("path")))
    return web.json_response({"layout": request.app["store"].load_published(parts)})


@handle_errors
async def service(request):
    check_screen_token(request)
    app = request.app
    options = app["options"]
    store = app["store"]
    entity_id = request.query.get("entity_id", "")
    name = request.query.get("service", "")
    layout = parse_path(request.query.get("layout"))
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
    app["ha"].require_token()
    data = service_data(request.query)
    s = await app["ha"].state(entity_id)
    if s is None:
        raise ApiError("entity not found", 404)
    if s.get("state") == "unavailable":
        raise ApiError("entity unavailable", 503)
    await app["ha"].call_service(entity_id, name, data)
    return web.json_response({"ok": True})


@handle_errors
async def imagedata(request):
    check_screen_token(request)
    app = request.app
    entity_id = request.query.get("entity", "")
    if not entity_id.startswith("image.") or not is_allowed(app["options"], entity_id) \
            or entity_id not in app["active"].entities:
        raise ApiError("no allowed image entity", 403)
    app["ha"].require_token()
    return await picture_response(app, entity_id, request.query.get("hash", ""))


@handle_errors
async def image(request):
    """The picture as plain image bytes, with an ETag. The browser asks again with If-None-Match."""
    check_screen_token(request)
    app = request.app
    entity_id = request.query.get("entity", "")
    if not entity_id.startswith("image.") or not is_allowed(app["options"], entity_id) \
            or entity_id not in app["active"].entities:
        raise ApiError("no allowed image entity", 403)
    app["ha"].require_token()
    return picture_http(request, await picture_entry(app, entity_id))


async def live(request):
    ws = web.WebSocketResponse(heartbeat=30)
    try:
        check_screen_token(request)
    except ApiError:
        await ws.prepare(request)
        await ws.close(code=WS_CLOSE_UNAUTHORIZED)
        return ws

    app = request.app
    hub = app["hub"]
    await ws.prepare(request)
    hub.add(ws)
    await ws.send_json({"type": "states", "states": hub.snapshot()})
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
            entities = data.get("entities")
            wanted = {e for e in (entities if isinstance(entities, list) else [])
                      if isinstance(e, str) and e in app["active"].entities}
            hub.subscribe(ws, wanted)
            await ws.send_json({"type": "states", "states": hub.snapshot(wanted)})
    finally:
        hub.remove(ws)
    return ws


@handle_errors
async def viewer_page(request):
    return web.FileResponse(UI_DIR / "viewer.html")


@handle_errors
async def favicon(request):
    return web.FileResponse(UI_DIR / "assets" / "favicon.png")


def add_routes(app):
    store = app["store"]
    router = app.router
    # The viewer is part of the HA App. It is registered before the static route, so an old copy in
    # the publish folder is never served.
    router.add_get(store.publish_url + "/viewer.html", viewer_page)
    router.add_get(store.publish_url + "/favicon.png", favicon)
    router.add_static(store.publish_url, store.publish_dir, show_index=False)
    router.add_get("/health", health)
    router.add_get("/states", states)
    router.add_get("/layout_load", layout_load)
    router.add_get("/service", service)
    router.add_get("/imagedata", imagedata)
    router.add_get("/image", image)
    router.add_get("/ws", live)
