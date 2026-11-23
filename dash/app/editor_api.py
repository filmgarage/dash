"""Editor API. Served through Home Assistant Ingress only, so it needs no token."""
import asyncio
import re
from aiohttp import web

from errors import ApiError
from history import history_answer, camera_answer
import page_sensors
from network import resolve_screen_host, save_saved, valid_ipv4
from settings import (APP_VERSION, DATE_FORMATS, LANGUAGES, PUBLISH_URL, SAVED_LIST_KEYS, SCREEN_PORT, TIME_FORMATS, UI_DIR,
                      WARNING_KEYS, apply_saved_options)
from store import checked, parse_path
from urllib.parse import quote
from ha_bridge import public_view, rest_view
from web_common import (ENTITY_ATTRIBUTE_KEYS, ENTITY_RE, MAX_IDS, SERVICE_NAME_RE, call_params, handle_errors, is_allowed, json_body, json_etag,
                        picture_entry, picture_http, picture_response, service_data)
from app_keys import ACTIVE, APP_SETTINGS_PATH, BRIDGE, DETECTED_IP, HA, HUB, INTERNAL_URL, OPTIONS, SAVED, SCREENS, STORE


@handle_errors
async def index(request):
    return web.FileResponse(UI_DIR / "index.html")


def screen_address(app):
    host, source = resolve_screen_host(app[OPTIONS], app.get(SAVED) or {}, app.get(DETECTED_IP))
    return {"screen_address_mode": app[OPTIONS]["screen_address_mode"], "screen_host": host,
            "screen_host_source": source}


DOMAIN_RE = re.compile(r"^[a-z_]+$")
SKIN_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_LIST_ITEMS = 500


def settings_view(app):
    """The settings the App panel shows. The same keys are returned by /api/status and after a save."""
    options = app[OPTIONS]
    saved = app.get(SAVED) or {}
    return {
        **screen_address(app),
        "allow_domains": sorted(options["allow_domains"]),
        "allow_entities": sorted(options["allow_entities"]),
        "exclude_domains": sorted(options["exclude_domains"]),
        "exclude_entities": sorted(options["exclude_entities"]),
        "language": saved.get("language", LANGUAGES[0]),
        "date_format": saved.get("date_format", DATE_FORMATS[0]),
        "time_format": saved.get("time_format", TIME_FORMATS[0]),
        "warnings": saved.get("warnings", {}),
    }


def settings_updates(body):
    """Checks a settings body. Returns the values to save, or raises ApiError for the first problem."""
    updates = {}
    for key, value in body.items():
        if key == "screen_ip":
            ip = valid_ipv4(value)
            if not ip:
                raise ApiError("screen_ip must be an IPv4 address such as 192.168.1.10", 400)
            updates[key] = ip
        elif key in SAVED_LIST_KEYS:
            if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
                raise ApiError(f"{key} must be a list of at most {MAX_LIST_ITEMS} items", 400)
            pattern = DOMAIN_RE if key.endswith("domains") else ENTITY_RE
            for item in value:
                if not isinstance(item, str) or not pattern.match(item):
                    raise ApiError(f"{key} has an invalid value: {item!r}", 400)
            updates[key] = sorted(set(value))
        elif key == "language":
            if value not in LANGUAGES:
                raise ApiError("language must be one of: " + ", ".join(LANGUAGES), 400)
            updates[key] = value
        elif key == "date_format":
            if value not in DATE_FORMATS:
                raise ApiError("date_format must be one of: " + ", ".join(DATE_FORMATS), 400)
            updates[key] = value
        elif key == "time_format":
            if value not in TIME_FORMATS:
                raise ApiError("time_format must be one of: " + ", ".join(TIME_FORMATS), 400)
            updates[key] = value
        elif key == "default_skin":
            if not isinstance(value, str) or not SKIN_NAME_RE.match(value):
                raise ApiError("default_skin is not a valid skin name", 400)
            updates[key] = value
        elif key == "warnings":
            if not isinstance(value, dict):
                raise ApiError("warnings must be an object", 400)
            for flag, flag_value in value.items():
                if flag not in WARNING_KEYS:
                    raise ApiError(f"unknown warning: {flag}", 400)
                if not isinstance(flag_value, bool):
                    raise ApiError(f"warning {flag} must be true or false", 400)
            updates[key] = dict(value)
        else:
            raise ApiError(f"unknown setting: {key}", 400)
    return updates


@handle_errors
async def save_settings(request):
    body = await json_body(request)
    if body is None:
        raise ApiError("no settings body found", 400)
    updates = settings_updates(body)
    app = request.app
    saved = app[SAVED]  # shared with the state; the app itself is not changed
    if "default_skin" in updates:
        app[STORE].publish_skin(["skins", "_default"], {"skin": updates.pop("default_skin")})
    if "screen_ip" in updates:
        saved["screen_ip"] = updates.pop("screen_ip")
    if "warnings" in updates:
        saved["warnings"] = {**saved.get("warnings", {}), **updates.pop("warnings")}
    for key in list(updates):
        saved[key] = updates.pop(key)
    apply_saved_options(app[OPTIONS], saved)
    save_saved(app[APP_SETTINGS_PATH], saved)
    return web.json_response(settings_view(app))


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
        **settings_view(app),
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
async def history(request):
    """History of one entity for the Ingress viewer (contract 10.0). Same rules as states."""
    app = request.app
    app[HA].require_token()
    entity_id = request.query.get("entity", "")
    if not is_allowed(app[OPTIONS], entity_id):
        raise ApiError("entity not allowed", 403)
    return await history_answer(app, entity_id, request.query)


@handle_errors
async def camera(request):
    app = request.app
    app[HA].require_token()
    entity_id = request.query.get("entity", "")
    if not is_allowed(app[OPTIONS], entity_id):
        raise ApiError("entity not allowed", 403)
    return await camera_answer(app, entity_id, request.query)


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


FULLY_DOMAIN = "fully_kiosk"
FULLY_ADMIN_PORT = 2323
DEVICE_NAME_CHARS = re.compile(r"[^A-Za-z0-9 _.-]+")


def device_screen_name(name):
    """A device name as a screen name: the characters the screen names allow, at most 40."""
    cleaned = DEVICE_NAME_CHARS.sub(" ", name or "").strip()[:40].strip()
    return cleaned or "Fully Kiosk"


async def fully_inventory(app):
    """The Fully Kiosk tablets in Home Assistant, with their screen (contract 10.0, section 0l)."""
    ha = app[HA]
    ha.require_token()
    devices, entities, entries = await ha.ws_calls([
        {"type": "config/device_registry/list"},
        {"type": "config/entity_registry/list"},
        {"type": "config_entries/get", "domain": FULLY_DOMAIN},
    ])
    states = {s["entity_id"]: s for s in await ha.states()}
    entry_by_id = {e["entry_id"]: e for e in entries or [] if e.get("domain") == FULLY_DOMAIN}
    screens = {s.get("device_id"): s for s in app[SCREENS].list() if s.get("device_id")}
    entities_of = {}
    for entity in entities or []:
        if entity.get("device_id"):
            entities_of.setdefault(entity["device_id"], []).append(entity["entity_id"])
    tablets = []
    for device in devices or []:
        if not entry_by_id.keys() & set(device.get("config_entries") or []):
            continue
        ids = entities_of.get(device["id"], [])
        online = any(states.get(eid) and states[eid].get("state") != "unavailable" for eid in ids)
        screen = screens.get(device["id"])
        host = None
        for entry_id in device.get("config_entries") or []:
            if entry_id in entry_by_id:
                host = (entry_by_id[entry_id].get("data") or {}).get("host")
        tablets.append({
            "device_id": device["id"],
            "name": device.get("name_by_user") or device.get("name") or device["id"],
            "online": online,
            "screen": screen["name"] if screen else None,
            "layout": screen["layout"] if screen else None,
            "admin_url": f"http://{host}:{FULLY_ADMIN_PORT}" if host else None,
            # The start URL of the tablet is not read by this App yet, so start is false (section 0l).
            "start": False,
        })
    return tablets


@handle_errors
async def fully_devices(request):
    return web.json_response({"devices": await fully_inventory(request.app)})


@handle_errors
async def fully_show(request):
    """Sends a published layout to a Fully Kiosk tablet, optionally as its start page (section 0l)."""
    app = request.app
    body = await json_body(request) or {}
    device_id = body.get("device_id")
    if not isinstance(device_id, str) or not device_id:
        raise ApiError("device_id is required", 400)
    layout = parse_path(body.get("layout") if isinstance(body.get("layout"), str) else None)
    if layout is None or not app[STORE].is_published(layout):
        raise ApiError("layout is not published", 400)
    tablets = await fully_inventory(app)
    tablet = next((t for t in tablets if t["device_id"] == device_id), None)
    if tablet is None:
        raise ApiError("device not found", 404)
    try:
        screen = app[SCREENS].save_device_screen(device_id, device_screen_name(tablet["name"]), "/".join(layout))
    except ValueError as exc:
        raise ApiError(str(exc), 400)
    if tablet["layout"] is not None and tablet["layout"] != screen["layout"]:
        await app[HUB].close_for_token(screen["token"])
    await page_sensors.write_screen(app, screen)
    host = screen_address(app)["screen_host"]
    if not host:
        raise ApiError("no screen address: set it in the App panel first", 400)
    skin = app[STORE].load_published(layout).get("skin")
    url = (f"http://{host}:{SCREEN_PORT}{PUBLISH_URL}/viewer.html?layout={quote(screen['layout'], safe='/')}"
           + (f"&skin={quote(skin, safe='')}" if isinstance(skin, str) and skin else "")
           + f"#token={screen['token']}")
    await app[HA].call_action(FULLY_DOMAIN, "load_url", {"device_id": device_id, "url": url})
    if body.get("start") is True:
        await app[HA].call_action(FULLY_DOMAIN, "set_config", {"device_id": device_id, "key": "startURL", "value": url})
    return web.json_response({"screen": screen["name"], "url": url})


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
async def screen_rename(request):
    """Renames a screen. Its token, layout and address stay the same, and its open push channels stay connected (0m)."""
    app = request.app
    old_name = request.query.get("from", "")
    new_name = request.query.get("to", "")
    try:
        screen = app[SCREENS].rename(old_name, new_name)
    except LookupError:
        raise ApiError("no such screen", 404)
    except FileExistsError:
        raise ApiError("a screen with that name already exists", 409)
    except ValueError as exc:
        raise ApiError(str(exc), 400)
    if old_name != screen["name"]:
        await page_sensors.remove_screen(app, old_name, screen["layout"])
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
    router.add_post("/api/settings", save_settings)
    router.add_get("/favicon.png", favicon)
    # Static assets of the editor (icon set, sample images). Relative URLs such as assets/mdi-icons.txt resolve here.
    router.add_static("/assets", UI_DIR / "assets", show_index=False)
    router.add_get("/api/published_layout", published_layout)
    router.add_get("/api/status", status)
    router.add_get("/api/entities", entities)
    router.add_get("/api/states", states)
    router.add_get("/api/history", history)
    router.add_get("/api/camera", camera)
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
    router.add_get("/api/fully_devices", fully_devices)
    router.add_post("/api/fully_show", fully_show)
    router.add_post("/api/screen_save", screen_save)
    router.add_post("/api/screen_rotate", screen_rotate)
    router.add_post("/api/screen_rename", screen_rename)
    router.add_post("/api/screen_delete", screen_delete)
