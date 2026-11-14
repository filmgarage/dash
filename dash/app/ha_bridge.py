"""One websocket to Home Assistant, subscribed only to the entities that were selected."""
import asyncio
import logging

from aiohttp import ClientSession, WSMsgType

log = logging.getLogger("dash.bridge")

# The only attributes the screens receive. Everything else stays inside the add-on.
VIEW_ATTRIBUTES = ["brightness", "min", "max", "options", "hvac_modes", "min_temp", "max_temp",
                   "target_temp_step", "supported_color_modes", "effect_list", "percentage",
                   "current_position", "temperature", "current_temperature", "hvac_action"]


def apply_event(states, event):
    """Apply one subscribe_entities event to the local state table.
    Returns the set of entity ids that changed, including removed ones."""
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


def public_view(entity_id, st):
    """What a screen receives for one entity. None when the entity is gone."""
    if st is None:
        return None
    attrs = st.get("a") or {}
    return {
        "state": st.get("s"),
        "name": attrs.get("friendly_name", entity_id),
        "unit": attrs.get("unit_of_measurement", "") or "",
        "icon": attrs.get("icon", "") or "",
        "device_class": attrs.get("device_class", "") or "",
        "last_changed": int((st.get("lu") or 0) * 1000),
        "attributes": {k: attrs[k] for k in VIEW_ATTRIBUTES if k in attrs},
    }


class HaBridge:
    def __init__(self, ws_url, token, selection, on_state):
        self.ws_url = ws_url
        self.token = token
        self.selection = selection
        self.on_state = on_state      # async callable(entity_id, view_or_None)
        self.states = {}
        self.connected = False
        self.changed = None
        self._ws = None

    def selection_changed(self):
        """Called after the selection is saved. Reconnects with the new list."""
        if self.changed is None:
            return  # run() has not started; it reads the selection when it starts
        self.changed.set()
        if self._ws is not None and not self._ws.closed:
            asyncio.ensure_future(self._ws.close())

    async def run(self):
        self.changed = asyncio.Event()
        delay = 1
        while True:
            self.changed.clear()
            ids = sorted(self.selection.entities)
            if not ids:
                log.info("No entities selected yet; not subscribing")
                await self.changed.wait()
                continue
            try:
                await self._session(ids)
                delay = 1
            except Exception as err:  # keep retrying whatever went wrong
                log.warning("Home Assistant connection failed: %s", err)
                delay = min(delay * 2, 60)
            if not self.changed.is_set():
                await asyncio.sleep(delay)

    async def _session(self, ids):
        async with ClientSession() as http:
            async with http.ws_connect(self.ws_url, heartbeat=30) as ws:
                self._ws = ws
                try:
                    await ws.receive_json()  # auth_required
                    await ws.send_json({"type": "auth", "access_token": self.token})
                    reply = await ws.receive_json()
                    if reply.get("type") != "auth_ok":
                        raise RuntimeError("Home Assistant did not accept the supervisor token")
                    self.connected = True
                    log.info("Subscribed to %d entities", len(ids))
                    await ws.send_json({"id": 1, "type": "subscribe_entities", "entity_ids": ids})
                    async for msg in ws:
                        if self.changed.is_set():
                            break
                        if msg.type != WSMsgType.TEXT:
                            continue
                        data = msg.json()
                        if data.get("id") != 1 or data.get("type") != "event":
                            continue
                        for entity_id in apply_event(self.states, data.get("event") or {}):
                            if entity_id in self.selection.entities:
                                view = public_view(entity_id, self.states.get(entity_id))
                                await self.on_state(entity_id, view)
                finally:
                    self.connected = False
                    self._ws = None
