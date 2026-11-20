"""Editor API. Served through Home Assistant Ingress only, so it needs no token."""
import asyncio
from aiohttp import web

from errors import ApiError
import page_sensors
from network import resolve_screen_host, save_saved, valid_ipv4
from settings import APP_VERSION, PUBLISH_URL, SCREEN_PORT, UI_DIR
from store import checked, parse_path
from ha_bridge import public_view, rest_view
from web_common import (ENTITY_ATTRIBUTE_KEYS, MAX_IDS, SERVICE_NAME_RE, call_params, handle_errors, is_allowed, json_body, json_etag,
                        picture_entry, picture_http, picture_response, service_data)
from app_keys import ACTIVE, APP_SETTINGS_PATH, BRIDGE, DETECTED_IP, HA, HUB, INTERNAL_URL, OPTIONS, SAVED, SCREENS, STORE


@handle_errors
async def index(request):
    return web.FileResponse(UI_DIR / "index.html")


def screen_address(app):
    host, source = resolve_screen_host(app[OPTIONS], app.get(SAVED) or {}, app.get(DETECTED_IP))
    return {"screen_address_mode": app[OPTIONS]["screen_address_mode"], "screen_host": host,
            "screen_host_source": source}


@handle_errors
async def save_screen_ip(request):
    body = await json_body(request)
    ip = valid_ipv4(body.get("screen_ip"))
    if not ip:
        raise ApiError("screen_ip must be an IPv4 address such as 192.168.1.10", 400)
    app = request.app
    app[SAVED]["screen_ip"] = ip  # the dict is shared with the state; the app itself is not changed
    save_saved(app[APP_SETTINGS_PATH], app[SAVED])
    return web.json_response(screen_address(app))


@handle_errors
async def status_page(request):
    return web.FileResponse(UI_DIR / "status.html")


@handle_errors
async def viewer_page(request):
    return web.FileResponse(UI_DIR / "viewer.html")


@handle_errors
async def favicon(request):
    return web.FileResponse(UI_DIR / "assets" / "favicon.png")


@handle_errors
async def published_layout(request):
    parts = checked(parse_path(request.query.get("path")))
    return web.json_response({"layout": request.app[STORE].load_published(parts)})


@handle_errors
async def status(request):
    app = request.app
    return web.json_response({
        "version": APP_VERSION,
        "state": "running",
        "ha_connected": app[BRIDGE].connected,
        "active_entities": len(app[ACTIVE].entities),
        "allowed_domains": sorted(app[OPTIONS]["allow_domains"] - app[OPTIONS]["exclude_domains"]),
        "excluded_domains": sorted(app[OPTIONS]["exclude_domains"]),
        **screen_address(app),
        "screen_port": SCREEN_PORT,
        "publish_url_prefix": PUBLISH_URL + "/",
        "internal_url": app.get(INTERNAL_URL),
    })


@handle_errors
async def entities(request):
    app = request.app
    app[HA].require_token()
    items = []
    for s in await app[HA].states():
        entity_id = s.get("entity_id", "")
        if not is_allowed(app[OPTIONS], entity_id):
            continue
        attrs = s.get("attributes") or {}
        items.append({
            "entity_id": entity_id,
            "name": attrs.get("friendly_name", entity_id),
            "icon": attrs.get("icon", "") or "",
            "device_class": attrs.get("device_class", "") or "",
            "unit": attrs.get("unit_of_measurement", "") or "",
            "state_class": attrs.get("state_class", "") or "",
            "area": "",
            "attributes": {k: attrs.get(k) for k in ENTITY_ATTRIBUTE_KEYS},
        })
    items.sort(key=lambda item: item["entity_id"])
    return web.json_response({"entities": items})


FALLBACK_CONCURRENCY = 8  # REST requests for missing states at the same time
FALLBACK_DEADLINE = 5  # seconds for all REST requests together; entities that are not back in time are left out


@handle_errors
async def states(request):
    """Live states from the bridge table (no Home Assistant call per entity). REST only for entities the table
    does not have yet, with bounded concurrency and one overall deadline."""
    app = request.app
    app[HA].require_token()
    ids = [i.strip() for i in request.query.get("ids", "").split(",") if i.strip()][:MAX_IDS]
    out = {}
    missing = []
    for entity_id in ids:
        if not is_allowed(app[OPTIONS], entity_id):
            continue
        if entity_id in app[BRIDGE].states:
            out[entity_id] = public_view(entity_id, app[BRIDGE].states[entity_id])
        else:
            missing.append(entity_id)
    if missing:
        slots = asyncio.Semaphore(FALLBACK_CONCURRENCY)

        async def fetch(entity_id):
            async with slots:
                return entity_id, await app[HA].state(entity_id)

        tasks = [asyncio.ensure_future(fetch(entity_id)) for entity_id in missing]
        done, pending = await asyncio.wait(tasks, timeout=FALLBACK_DEADLINE)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            if task.cancelled() or task.exception() is not None:
                continue  # one failing entity does not spoil the others
            entity_id, s = task.result()
            if s is not None:
                out[entity_id] = rest_view(entity_id, s)
    return json_etag(request, {"states": out})


@handle_errors
async def service(request):
    """Calls a Home Assistant service. POST only: a GET request must never change anything."""
    app = request.app
    app[HA].require_token()
    params = await call_params(request)
    entity_id = params.get("entity_id", "")
    name = params.get("service", "")
    if not is_allowed(app[OPTIONS], entity_id):
        raise ApiError("entity not allowed", 403)
    if not SERVICE_NAME_RE.match(name) or name not in app[OPTIONS]["services"]:
        raise ApiError("service not allowed", 403)
    data = service_data(params, name)
    s = await app[HA].state(entity_id)
    if s is None:
        raise ApiError("entity not found", 404)
    if s.get("state") == "unavailable":
        raise ApiError("entity unavailable", 503)
    await app[HA].call_service(entity_id, name, data)
    return web.json_response({"ok": True})


@handle_errors
async def layouts(request):
    store = request.app[STORE]
    return web.json_response({"layouts": store.names(), "tree": store.tree()})


@handle_errors
async def layout_load(request):
    parts = checked(parse_path(request.query.get("path") or request.query.get("name")))
    return web.json_response({"layout": request.app[STORE].load_layout(parts)})


@handle_errors
async def layout_save(request):
    parts = checked(parse_path(request.query.get("path") or request.query.get("name")))
    body = await json_body(request)
    if body is None or "tiles" not in body:
        raise ApiError("no layout body found", 400)
    saved = request.app[STORE].save_layout(parts, body, request.query.get("if_saved", ""))
    return web.json_response({"ok": True, "path": "/".join(parts), "saved": saved})


@handle_errors
async def layout_move(request):
    src = checked(parse_path(request.query.get("from")))
    dst = checked(parse_path(request.query.get("to")))
    request.app[STORE].move_layout(src, dst)
    return web.json_response({"ok": True, "path": "/".join(dst)})


@handle_errors
async def layout_delete(request):
    parts = checked(parse_path(request.query.get("path")))
    request.app[STORE].delete_layout(parts)
    return web.json_response({"ok": True})


@handle_errors
async def folder_create(request):
    parts = checked(parse_path(request.query.get("path")))
    request.app[STORE].create_folder(parts)
    return web.json_response({"ok": True})


@handle_errors
async def folder_delete(request):
    parts = checked(parse_path(request.query.get("path")))
    request.app[STORE].delete_folder(parts)
    return web.json_response({"ok": True})


def publish_kind(request):
    kind = request.query.get("type", "html")
    if kind not in ("html", "json"):
        raise ApiError("unknown type (use html or json)", 400)
    return kind


@handle_errors
async def publish_save(request):
    app = request.app
    store = app[STORE]
    kind = publish_kind(request)
    parts = parse_path(request.query.get("path"))
    if parts is None:
        raise ApiError("invalid path", 400)
    body = await json_body(request) or {}
    if kind == "json":
        skin = body.get("json")
        if not isinstance(skin, dict):
            raise ApiError('no skin in body (expected {"json": {...}})', 400)
        url = store.publish_skin(parts, skin)
        return web.json_response({"ok": True, "path": "/".join(parts), "url": url})

    if parts == ["viewer"]:
        raise ApiError("the viewer is part of the HA App and is not published", 400)
    if kind == "html" and store.has_layout(parts):
        tiles = store.load_layout(parts).get("tiles") or []
        refused = sorted({t["entity"] for t in tiles
                          if isinstance(t, dict) and t.get("entity") and not is_allowed(app[OPTIONS], t["entity"])})
        if refused:
            raise ApiError("not allowed by the HA App options: " + ", ".join(refused), 400)
    html = body.get("html")
    if not isinstance(html, str):
        raise ApiError('no html in body (expected {"html": "..."})', 400)
    url = store.publish_html(parts, html)
    key = "/".join(parts)
    await page_sensors.publish_page(app, parts)
    if store.has_layout(parts):
        saved = store.snapshot_layout(parts)
        added, removed = app[ACTIVE].set_page(key, store.published_entities(parts))
        await app[HUB].broadcast_layout(key, saved)
    else:
        added, removed = app[ACTIVE].remove_page(key)
    return web.json_response({
        "ok": True, "path": key, "url": url,
        "entities": sorted(store.published_entities(parts)),
        "added": added, "removed": removed,
    })


@handle_errors
async def publish_delete(request):
    app = request.app
    kind = publish_kind(request)
    parts = parse_path(request.query.get("path"))
    if parts is None:
        raise ApiError("invalid path", 400)
    if kind == "json":
        app[STORE].delete_skin(parts)
    else:
        key = "/".join(parts)
        app[STORE].delete_page(parts)
        app[ACTIVE].remove_page(key)
        await page_sensors.unpublish_page(app, parts)
        await app[HUB].broadcast_layout(key, None)
    return web.json_response({"ok": True})


@handle_errors
async def publish_list(request):
    return web.json_response({"pages": request.app[STORE].publish_list()})


def image_owner(request):
    layout = request.query.get("layout", "")
    skin = request.query.get("skin", "")
    if bool(layout) == bool(skin):
        raise ApiError("send exactly one of layout and skin", 400)
    if layout:
        return "layout", parse_path(layout)
    return "skin", skin


@handle_errors
async def image_upload(request):
    body = await json_body(request) or {}
    result = request.app[STORE].upload_image(image_owner(request), request.query.get("name", ""),
                                               body.get("data_url"))
    return web.json_response(result)


@handle_errors
async def image_list(request):
    return web.json_response(request.app[STORE].list_images(image_owner(request)))


@handle_errors
async def image_delete(request):
    request.app[STORE].delete_image(image_owner(request), request.query.get("name", ""))
    return web.json_response({"ok": True})


@handle_errors
async def published_file(request):
    return web.FileResponse(request.app[STORE].file_path(request.query.get("path", "")))


@handle_errors
async def imagedata(request):
    app = request.app
    entity_id = request.query.get("entity", "")
    if not entity_id.startswith("image.") or not is_allowed(app[OPTIONS], entity_id):
        raise ApiError("no allowed image entity", 403)
    app[HA].require_token()
    return await picture_response(app, entity_id, request.query.get("hash", ""))


@handle_errors
async def image(request):
    """Binary picture for the Ingress editor and viewer. Same checks as imagedata; ETag and 304 when unchanged."""
    app = request.app
    entity_id = request.query.get("entity", "")
    if not entity_id.startswith("image.") or not is_allowed(app[OPTIONS], entity_id):
        raise ApiError("no allowed image entity", 403)
    app[HA].require_token()
    return picture_http(request, await picture_entry(app, entity_id))


@handle_errors
async def screens_list(request):
    return web.json_response({"screens": request.app[SCREENS].list()})


@handle_errors
async def screen_save(request):
    """Creates a screen for a published layout, or changes the layout of an existing screen. Keeps its token."""
    app = request.app
    layout = parse_path(request.query.get("layout"))
    if layout is None or not app[STORE].is_published(layout):
        raise ApiError("layout is not published", 400)
    name = request.query.get("name", "")
    before = app[SCREENS].get(name)
    try:
        screen = app[SCREENS].save_screen(name, "/".join(layout))
    except ValueError as exc:
        raise ApiError(str(exc), 400)
    # A changed layout changes what the screen may see. Its open push channels must reconnect and authenticate again.
    if before is not None and before["layout"] != screen["layout"]:
        await app[HUB].close_for_token(screen["token"])
    await page_sensors.write_screen(app, screen)
    return web.json_response({"screen": screen})


@handle_errors
async def screen_rotate(request):
    """A new token for a screen. The old token stops working at once, and its open push channels are closed."""
    app = request.app
    name = request.query.get("name", "")
    old = app[SCREENS].get(name)
    if old is None:
        raise ApiError("no such screen", 404)
    screen = app[SCREENS].rotate(name)
    await app[HUB].close_for_token(old["token"])
    await page_sensors.write_screen(app, screen)
    return web.json_response({"screen": screen})


@handle_errors
async def screen_delete(request):
    app = request.app
    name = request.query.get("name", "")
    old = app[SCREENS].get(name)
    if old is None:
        raise ApiError("no such screen", 404)
    app[SCREENS].delete(name)
    await app[HUB].close_for_token(old["token"])
    await page_sensors.remove_screen(app, name, old["layout"])
    return web.json_response({"ok": True})


@handle_errors
async def active(request):
    app = request.app
    reasons = app[ACTIVE].reasons()
    known = app[BRIDGE].states
    items = [{"entity_id": entity_id, "layouts": reasons.get(entity_id, []),
              "missing": entity_id not in known}
             for entity_id in sorted(app[ACTIVE].entities)]
    return web.json_response({"active": items})


def add_routes(app):
    router = app.router
    router.add_get("/", index)
    router.add_get("/status", status_page)
    router.add_get("/viewer", viewer_page)
    router.add_post("/api/settings", save_screen_ip)
    router.add_get("/favicon.png", favicon)
    # Static assets of the editor (icon set, sample images). Relative URLs such as assets/mdi-icons.txt resolve here.
    router.add_static("/assets", UI_DIR / "assets", show_index=False)
    router.add_get("/api/published_layout", published_layout)
    router.add_get("/api/status", status)
    router.add_get("/api/entities", entities)
    router.add_get("/api/states", states)
    router.add_post("/api/service", service)
    router.add_get("/api/layouts", layouts)
    router.add_get("/api/layout_load", layout_load)
    router.add_post("/api/layout_save", layout_save)
    router.add_post("/api/layout_move", layout_move)
    router.add_post("/api/layout_delete", layout_delete)
    router.add_post("/api/folder_create", folder_create)
    router.add_post("/api/folder_delete", folder_delete)
    router.add_post("/api/publish_save", publish_save)
    router.add_post("/api/publish_delete", publish_delete)
    router.add_get("/api/publish_list", publish_list)
    router.add_post("/api/image_upload", image_upload)
    router.add_get("/api/image_list", image_list)
    router.add_post("/api/image_delete", image_delete)
    router.add_get("/api/imagedata", imagedata)
    router.add_get("/api/image", image)
    router.add_get("/api/file", published_file)
    router.add_get("/api/active", active)
    router.add_get("/api/screens", screens_list)
    router.add_post("/api/screen_save", screen_save)
    router.add_post("/api/screen_rotate", screen_rotate)
    router.add_post("/api/screen_delete", screen_delete)
