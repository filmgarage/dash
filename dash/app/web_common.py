"""Helpers shared by the editor API and the screen API."""
import asyncio
import base64
import functools
import hashlib
import json
import logging
import math
import re
import secrets
import time
from datetime import datetime

import aiohttp
from aiohttp import web

from errors import ApiError
from store import parse_path

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


UNREACHABLE_LOG_EVERY = 60  # seconds between two log lines about an unreachable Home Assistant
_last_unreachable_log = {"at": None}


def handle_errors(handler):
    @functools.wraps(handler)
    async def wrapper(request):
        try:
            return await handler(request)
        except ApiError as err:
            return error(err.message, err.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            # Home Assistant is unreachable. Screens and the editor poll every few seconds, so log one
            # short line per minute instead of a traceback for every request.
            now = time.monotonic()
            last = _last_unreachable_log["at"]
            if last is None or now - last >= UNREACHABLE_LOG_EVERY:
                _last_unreachable_log["at"] = now
                log.warning("%s: Home Assistant not reachable (%s)", handler.__name__, type(err).__name__)
            return error("Home Assistant not reachable", 502)
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


# Data keys each service may receive. A service that is not listed receives no data at all.
SERVICE_DATA_KEYS = {
    "set_temperature": {"temperature", "target_temp_low", "target_temp_high"},
    "set_hvac_mode": {"hvac_mode"},
    "set_preset_mode": {"preset_mode"},
    "set_fan_mode": {"fan_mode"},
    "set_value": {"value"},
    "set_cover_position": {"position"},
    "set_percentage": {"percentage"},
    "select_option": {"option"},
    "turn_on": {"brightness_pct"},
}
NUMBER_DATA_KEYS = {"temperature", "target_temp_low", "target_temp_high", "value", "position",
                    "percentage", "brightness_pct"}
TEXT_DATA_KEYS = {"hvac_mode", "preset_mode", "fan_mode", "option"}
MAX_TEXT_LENGTH = 64
MAX_IDS = 100  # entities in one states request or one subscription
MAX_SCREENS = 20  # screens with an open push channel at the same time
MAX_WS_MESSAGE = 65536  # bytes in one message from a screen


def service_data(query, service):
    """The data of a service call, only for the keys this service may receive (contract 12.3). Text keys are kept
    as typed, so an option named \"1\" stays text."""
    allowed = SERVICE_DATA_KEYS.get(service, set())
    data = {}
    for key, raw in query.items():
        if key in RESERVED_QUERY_KEYS:
            continue
        if key not in allowed:
            raise ApiError("this service does not take that data", 400)
        if key in NUMBER_DATA_KEYS:
            value = coerce(raw)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ApiError("data must be a number", 400)
        elif key in TEXT_DATA_KEYS:
            value = raw
            if not raw or len(raw) > MAX_TEXT_LENGTH:
                raise ApiError("data is empty or too long", 400)
        data[key] = value
    return data


@web.middleware
async def security_headers(request, handler):
    """No referrer leaks the token of a page, and browsers do not guess content types."""
    response = await handler(request)
    if not response.prepared:
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


def request_token(request):
    """The token in the Authorization header (preferred) or the token query parameter, or ''."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):]
    return request.query.get("token", "")


def screen_scope(request):
    """The screen record for the token of the request (Bearer header or token query parameter). 401 otherwise.
    The record limits the request to its layout (contract 9.0)."""
    given = request_token(request)
    record = request.app["screens"].find_by_token(given) if given else None
    if record is None:
        raise ApiError("unauthorized", 401)
    return record


def scoped_entities(app, scope):
    """The entities a screen may use: the published entities of its layout that are monitored."""
    return set(app["store"].published_entities(parse_path(scope["layout"]))) & set(app["active"].entities)


async def call_params(request):
    """The parameters of a request: the query string, and for POST also a JSON object body. Non-text values
    from the body are written as JSON text, so the same checks apply to both ways of calling."""
    params = dict(request.query)
    if request.method == "POST" and request.can_read_body:
        body = await json_body(request)
        if body is None:
            raise ApiError("body must be a JSON object", 400)
        for key, value in body.items():
            params[key] = value if isinstance(value, str) else json.dumps(value)
    return params


MAX_CACHED_PICTURES = 32


async def picture_entry(app, entity_id):
    """The picture of an image entity as bytes, cached until Home Assistant reports a new last_updated."""
    ha = app["ha"]
    s = await ha.state(entity_id)
    if s is None:
        raise ApiError("entity not found", 404)
    stamp = s.get("last_updated")
    cache = app["images"]
    # One download per entity at a time: other requests wait and then find the picture in the cache.
    lock = app["picture_locks"].setdefault(entity_id, asyncio.Lock())
    async with lock:
        cached = cache.get(entity_id)
        if cached is None or cached["stamp"] != stamp:
            picture = (s.get("attributes") or {}).get("entity_picture")
            if not picture:
                raise ApiError("entity has no picture", 404)
            data, content_type = await ha.picture(picture)
            cached = {"stamp": stamp, "hash": hashlib.sha256(data).hexdigest(),
                      "data": data, "content_type": content_type}
            cache.pop(entity_id, None)
            cache[entity_id] = cached
            while len(cache) > MAX_CACHED_PICTURES:  # oldest first; bounds the memory a screen can use
                cache.pop(next(iter(cache)))
    return cached


async def picture_response(app, entity_id, client_hash):
    """Base64 form for the editor and the older viewer. The binary endpoint /image is preferred."""
    cached = await picture_entry(app, entity_id)
    if client_hash == cached["hash"]:
        return web.json_response({"unchanged": True, "hash": cached["hash"]})
    data_url = f"data:{cached['content_type']};base64," + base64.b64encode(cached["data"]).decode("ascii")
    return web.json_response({"hash": cached["hash"], "data_url": data_url})


def etag_matches(header, etag):
    """True when an If-None-Match header names the given ETag."""
    return any(part.strip().removeprefix("W/") == etag for part in (header or "").split(","))


def json_etag(request, payload):
    """A JSON answer with an ETag. An unchanged answer comes back as 304 without a body."""
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if etag_matches(request.headers.get("If-None-Match"), etag):
        return web.Response(status=304, headers=headers)
    return web.Response(body=body, content_type="application/json", headers=headers)


def picture_http(request, cached):
    """Plain image bytes with an ETag. An unchanged picture comes back as 304 without a body."""
    etag = f'"{cached["hash"]}"'
    headers = {"ETag": etag, "Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"}
    if etag_matches(request.headers.get("If-None-Match"), etag):
        return web.Response(status=304, headers=headers)
    return web.Response(body=cached["data"], content_type=cached["content_type"], headers=headers)

