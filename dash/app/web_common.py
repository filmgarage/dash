"""Helpers shared by the editor API and the screen API."""
import base64
import functools
import hashlib
import logging
import re
import secrets
from datetime import datetime

from aiohttp import web

from errors import ApiError

log = logging.getLogger("dash.api")

ENTITY_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
SERVICE_NAME_RE = re.compile(r"^[a-z_]+$")
DATA_KEY_RE = re.compile(r"^[a-z_]+$")
RESERVED_QUERY_KEYS = {"token", "entity_id", "service", "layout"}
ENTITY_ATTRIBUTE_KEYS = ["min", "max", "options", "hvac_modes", "min_temp", "max_temp",
                         "target_temp_step", "supported_color_modes", "effect_list"]
INGRESS_HEADER = "X-Ingress-Path"


def error(message, status):
    return web.json_response({"error": message}, status=status)


def handle_errors(handler):
    @functools.wraps(handler)
    async def wrapper(request):
        try:
            return await handler(request)
        except ApiError as err:
            return error(err.message, err.status)
        except Exception as err:
            log.exception("%s failed", handler.__name__)
            return error(f"{type(err).__name__}: {err}", 500)
    return wrapper


@web.middleware
async def ingress_only(request, handler):
    if INGRESS_HEADER not in request.headers:
        return error("open DASH from the Home Assistant sidebar", 403)
    return await handler(request)


def build_app(add_routes, state, middlewares=()):
    app = web.Application(middlewares=list(middlewares))
    for key, value in state.items():
        app[key] = value
    add_routes(app)
    return app


async def json_body(request):
    """The request body as a dict, or None when it is missing or not a JSON object."""
    try:
        body = await request.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def to_ms(iso):
    if not iso:
        return 0
    try:
        return int(datetime.fromisoformat(str(iso)).timestamp() * 1000)
    except ValueError:
        return 0


def is_allowed(options, entity_id):
    """An entity is allowed when its domain or the entity itself is allowed, and it is not excluded."""
    if not ENTITY_RE.match(entity_id):
        return False
    domain = entity_id.split(".", 1)[0]
    if domain in options["exclude_domains"] or entity_id in options["exclude_entities"]:
        return False
    return domain in options["allow_domains"] or entity_id in options["allow_entities"]


def plain_state(entity_id, state):
    attrs = state.get("attributes") or {}
    return {
        "state": state.get("state"),
        "unit": attrs.get("unit_of_measurement", "") or "",
        "name": attrs.get("friendly_name", entity_id),
        "icon": attrs.get("icon", "") or "",
        "device_class": attrs.get("device_class", "") or "",
        "last_changed": to_ms(state.get("last_changed")),
    }


def coerce(value):
    """Query values are strings. Numbers and booleans are converted for service data."""
    if value in ("true", "false"):
        return value == "true"
    for convert in (int, float):
        try:
            return convert(value)
        except ValueError:
            pass
    return value


def service_data(query):
    data = {k: coerce(v) for k, v in query.items() if k not in RESERVED_QUERY_KEYS}
    if not all(DATA_KEY_RE.match(k) for k in data):
        raise ApiError("invalid service data key", 400)
    return data


def check_screen_token(request):
    """Raises unless the request carries the read token (query parameter or Bearer header)."""
    token = request.app["options"]["read_token"]
    if not token:
        raise ApiError("read token not configured", 503)
    given = request.query.get("token", "")
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        given = header[len("Bearer "):]
    if not given or not secrets.compare_digest(given.encode(), token.encode()):
        raise ApiError("unauthorized", 401)


async def picture_response(app, entity_id, client_hash):
    """The picture of an image entity, cached until Home Assistant reports a new last_updated."""
    ha = app["ha"]
    s = await ha.state(entity_id)
    if s is None:
        raise ApiError("entity not found", 404)
    stamp = s.get("last_updated")
    cache = app["images"]
    cached = cache.get(entity_id)
    if cached is None or cached["stamp"] != stamp:
        picture = (s.get("attributes") or {}).get("entity_picture")
        if not picture:
            raise ApiError("entity has no picture", 404)
        data, content_type = await ha.picture(picture)
        cached = {
            "stamp": stamp,
            "hash": hashlib.sha256(data).hexdigest(),
            "data_url": f"data:{content_type};base64," + base64.b64encode(data).decode("ascii"),
        }
        cache[entity_id] = cached
    if client_hash == cached["hash"]:
        return web.json_response({"unchanged": True, "hash": cached["hash"]})
    return web.json_response({"hash": cached["hash"], "data_url": cached["data_url"]})
