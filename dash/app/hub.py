"""Connected screens and the entities each one listens to."""
import logging

from ha_bridge import public_view

log = logging.getLogger("dash.hub")


class Hub:
    def __init__(self, active, bridge):
        self.active = active
        self.bridge = bridge
        self.clients = {}  # websocket -> set of entity ids, or None for every active entity

    def add(self, ws):
        self.clients[ws] = None

    def remove(self, ws):
        self.clients.pop(ws, None)

    def subscribe(self, ws, entities):
        self.clients[ws] = set(entities)

    def snapshot(self, entities=None):
        ids = self.active.entities if entities is None else entities
        return {e: public_view(e, self.bridge.states[e])
                for e in sorted(ids) if e in self.active.entities and e in self.bridge.states}

    async def broadcast(self, entity_id, view):
        if entity_id not in self.active.entities:
            return
        if view is None:
            message = {"type": "removed", "entity_id": entity_id}
        else:
            message = {"type": "state", "entity_id": entity_id, "state": view}
        await self._send(entity_id, message)

    async def broadcast_layout(self, path, saved):
        """Tells every screen that a published layout changed. saved is None when it was unpublished."""
        await self._send(None, {"type": "layout", "path": path, "saved": saved})

    async def announce_removed(self, entities):
        for entity_id in entities:
            await self._send(entity_id, {"type": "removed", "entity_id": entity_id})

    async def _send(self, entity_id, message):
        for ws, wanted in list(self.clients.items()):
            if entity_id is not None and wanted is not None and entity_id not in wanted:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                log.debug("A screen went away; dropping it")
                self.clients.pop(ws, None)
