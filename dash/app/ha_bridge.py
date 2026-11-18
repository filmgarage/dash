"""One websocket to Home Assistant, subscribed to the active entities."""
import asyncio
import logging

from aiohttp import ClientSession, WSMsgType

from web_common import to_ms

log = logging.getLogger("dash.bridge")

VIEW_ATTRIBUTES = ["brightness", "brightness_pct", "min", "max", "options", "hvac_modes", "min_temp", "max_temp",
                   "target_temp_step", "supported_color_modes", "effect_list", "percentage",
                   "current_position", "temperature", "current_temperature", "hvac_action",
                   "target_temp_low", "target_temp_high", "preset_mode", "preset_modes", "temperature_unit",
                   "humidity", "wind_speed", "wind_speed_unit", "precipitation_unit",
                   "forecast_daily", "forecast_hourly"]
# Domains whose unit is the temperature unit (contract 12.1).
TEMPERATURE_DOMAINS = ("climate", "weather")


def apply_event(states, event):
    """Applies one subscribe_entities event to the state table. Returns the changed entity ids."""
    changed = set()
    for entity_id, new in (event.get("a") or {}).items():
        states[entity_id] = {"s": new.get("s"), "a": dict(new.get("a") or {}), "lu": new.get("lu")}
        changed.add(entity_id)
    for entity_id, diff in (event.get("c") or {}).items():
        current = states.setdefault(entity_id, {"s": None, "a": {}, "lu": None})
        plus = diff.get("+") or {}
        if "s" in plus:
            current["s"] = plus["s"]
        if "lu" in plus:
            current["lu"] = plus["lu"]
        current["a"].update(plus.get("a") or {})
        for key in (diff.get("-") or {}).get("a") or []:
            current["a"].pop(key, None)
        changed.add(entity_id)
    for entity_id in event.get("r") or []:
        states.pop(entity_id, None)
        changed.add(entity_id)
    return changed


def rest_view(entity_id, s):
    """The same shape as public_view, for a state read once over REST (when the live table is not ready yet)."""
    attrs = s.get("attributes") or {}
    unit = attrs.get("unit_of_measurement") or ""
    if not unit and entity_id.split(".", 1)[0] in TEMPERATURE_DOMAINS:
        unit = attrs.get("temperature_unit") or ""
    return {
        "state": s.get("state"),
        "name": attrs.get("friendly_name", entity_id),
        "unit": unit,
        "icon": attrs.get("icon", "") or "",
        "device_class": attrs.get("device_class", "") or "",
        "last_changed": to_ms(s.get("last_changed")),
        "attributes": {k: attrs[k] for k in VIEW_ATTRIBUTES if k in attrs},
    }


def public_view(entity_id, st):
    """What a screen receives for one entity. None when the entity is gone."""
    if st is None:
        return None
    attrs = st.get("a") or {}
    unit = attrs.get("unit_of_measurement") or ""
    if not unit and entity_id.split(".", 1)[0] in TEMPERATURE_DOMAINS:
        unit = attrs.get("temperature_unit") or ""
    return {
        "state": st.get("s"),
        "name": attrs.get("friendly_name", entity_id),
        "unit": unit,
        "icon": attrs.get("icon", "") or "",
        "device_class": attrs.get("device_class", "") or "",
        "last_changed": int((st.get("lu") or 0) * 1000),
        "attributes": {k: attrs[k] for k in VIEW_ATTRIBUTES if k in attrs},
    }


class HaBridge:
    def __init__(self, ws_url, token, active, on_state=None):
        self.ws_url = ws_url
        self.token = token
        self.active = active
        self.on_state = on_state  # async callable(entity_id, view_or_None)
        self.states = {}
        self.connected = False
        self._wake = None
        self._ws = None

    def active_changed(self):
        """Reconnects with the new entity list. Does nothing before run() has started."""
        if self._wake is None:
            return
        self._wake.set()
        if self._ws is not None and not self._ws.closed:
            asyncio.ensure_future(self._ws.close())

    async def run(self):
        self._wake = asyncio.Event()
        delay = 1
        while True:
            self._wake.clear()
            ids = sorted(self.active.entities)
            if not ids:
                log.info("No active entities; not subscribing")
                await self._wake.wait()
                continue
            try:
                await self._session(ids)
                delay = 1
            except Exception as err:
                log.warning("Home Assistant connection failed: %s", err)
                delay = min(delay * 2, 60)
            if not self._wake.is_set():
                try:
                    await asyncio.wait_for(self._wake.wait(), delay)
                except asyncio.TimeoutError:
                    pass

    async def _session(self, ids):
        async with ClientSession() as http:
            async with http.ws_connect(self.ws_url, heartbeat=30) as ws:
                self._ws = ws
                try:
                    await ws.receive_json()  # auth_required
                    await ws.send_json({"type": "auth", "access_token": self.token})
                    reply = await ws.receive_json()
                    if reply.get("type") != "auth_ok":
                        raise RuntimeError("Home Assistant did not accept the Supervisor token")
                    self.connected = True
                    log.info("Subscribed to %d entities", len(ids))
                    await ws.send_json({"id": 1, "type": "subscribe_entities", "entity_ids": ids})
                    async for msg in ws:
                        if self._wake.is_set():
                            break
                        if msg.type != WSMsgType.TEXT:
                            continue
                        data = msg.json()
                        if data.get("id") != 1 or data.get("type") != "event":
                            continue
                        for entity_id in apply_event(self.states, data.get("event") or {}):
                            if entity_id in self.active.entities and self.on_state is not None:
                                view = public_view(entity_id, self.states.get(entity_id))
                                await self.on_state(entity_id, view)
                finally:
                    self.connected = False
                    self._ws = None
