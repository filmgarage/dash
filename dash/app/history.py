"""History and camera answers for the viewer (contract 10.0, section 0k).

The viewer asks for a history graph (type entity, options.graph line) and for camera stills (type camera).
Both use the same rules as `states`: the screen token or Ingress, and only the entities the caller may use.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from aiohttp import web

from app_keys import HA, PICTURE_SLOTS
from errors import ApiError

HOURS_DEFAULT, HOURS_MIN, HOURS_MAX = 24, 1, 168
POINTS_DEFAULT, POINTS_MIN, POINTS_MAX = 120, 10, 500
WIDTH_MIN, WIDTH_MAX = 64, 1920


def int_param(query, name, default, low, high):
    raw = query.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(f"{name} must be a whole number from {low} to {high}", 400)
    if not low <= value <= high:
        raise ApiError(f"{name} must be a whole number from {low} to {high}", 400)
    return value


def iso_utc(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def number_or_none(state):
    """A numeric state as a float. Text, 'unknown' and 'unavailable' give None (the viewer shows a gap)."""
    try:
        value = float(state)
    except (TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float("inf") else None


def segments_from_rows(rows, start, end):
    """Home Assistant history rows, sorted by time, as (begin, finish, value) in seconds since start.
    The first state is taken from the start of the period; a missing start state counts as unknown."""
    changes = []
    for row in rows:
        stamp = row.get("last_changed") or row.get("last_updated")
        if not stamp:
            continue
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        t = min(max((moment - start).total_seconds(), 0.0), (end - start).total_seconds())
        changes.append((t, number_or_none(row.get("state"))))
    changes.sort(key=lambda item: item[0])
    total = (end - start).total_seconds()
    if not changes or changes[0][0] > 0:
        changes.insert(0, (0.0, None))
    out = []
    for index, (t, value) in enumerate(changes):
        finish = changes[index + 1][0] if index + 1 < len(changes) else total
        if finish > t:
            out.append((t, finish, value))
    return out


def reduce_history(rows, start, end, points):
    """The points of the graph: one per bucket of equal length. Numbers are the time-weighted average of the
    bucket; a bucket without a numeric state is null."""
    total = (end - start).total_seconds()
    length = total / points
    segments = segments_from_rows(rows, start, end)
    out = []
    first = 0
    for i in range(points):
        b0, b1 = i * length, (i + 1) * length
        while first < len(segments) and segments[first][1] <= b0:
            first += 1
        weight = acc = 0.0
        k = first
        while k < len(segments) and segments[k][0] < b1:
            s0, s1, value = segments[k]
            overlap = min(s1, b1) - max(s0, b0)
            if overlap > 0 and value is not None:
                weight += overlap
                acc += value * overlap
            k += 1
        v = round(acc / weight, 3) if weight > 0 else None
        out.append({"t": iso_utc(start + timedelta(seconds=b0)), "v": v})
    return out


async def history_answer(app, entity_id, query):
    """The history answer of section 0k. The caller has already checked the entity."""
    hours = int_param(query, "hours", HOURS_DEFAULT, HOURS_MIN, HOURS_MAX)
    points = int_param(query, "points", POINTS_DEFAULT, POINTS_MIN, POINTS_MAX)
    ha = app[HA]
    current = await ha.state(entity_id)
    if current is None:
        raise ApiError("entity not found", 404)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    rows = await ha.history(entity_id, start, end)
    unit = (current.get("attributes") or {}).get("unit_of_measurement")
    body = {"entity": entity_id, "unit": unit, "start": iso_utc(start), "end": iso_utc(end),
            "points": reduce_history(rows, start, end, points)}
    return web.json_response(body, headers={"Cache-Control": "no-store"})


async def camera_answer(app, entity_id, query):
    """The current still of a camera. Width is accepted and checked, but the App does not scale the image."""
    int_param(query, "width", WIDTH_MIN, WIDTH_MIN, WIDTH_MAX)
    if not entity_id.startswith("camera."):
        raise ApiError("entity is not a camera", 400)
    ha = app[HA]
    current = await ha.state(entity_id)
    if current is None:
        raise ApiError("entity not found", 404)
    picture = (current.get("attributes") or {}).get("entity_picture")
    if current.get("state") in ("unavailable", "off", "unknown") or not picture:
        raise ApiError("camera unavailable", 503)
    async with app[PICTURE_SLOTS]:
        data, content_type = await ha.picture(picture)
    return web.Response(body=data, content_type=content_type, headers={"Cache-Control": "no-store"})
