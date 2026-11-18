"""Connected screens and the entities each one listens to."""
import asyncio
import logging

from ha_bridge import public_view

log = logging.getLogger("dash.hub")
SEND_TIMEOUT = 5  # seconds a screen may take to accept one message


class Hub:
    def __init__(self, active, bridge):
        self.active = active
        self.bridge = bridge
        self.clients = {}  # websocket -> set of entity ids, or None for every active entity
        self.owners = {}  # websocket -> screen token

    def add(self, ws, token):
        self.clients[ws] = None
        self.owners[ws] = token  # the screen token

    async def close_for_token(self, token):
        """Closes the push channels that use a token, for example after the token was rotated or the screen deleted."""
        for ws, owner in list(self.owners.items()):
            if owner == token:
                self.remove(ws)
                try:
                    await ws.close(code=4401)
                except Exception:  # already gone
                    pass

    def remove(self, ws):
        self.clients.pop(ws, None)
        self.owners.pop(ws, None)

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
        targets = [ws for ws, wanted in list(self.clients.items())
                   if entity_id is None or wanted is None or entity_id in wanted]
        await asyncio.gather(*(self._send_one(ws, message) for ws in targets))

    async def _send_one(self, ws, message):
        try:
            await asyncio.wait_for(ws.send_json(message), SEND_TIMEOUT)
        except Exception:  # gone, or too slow: drop it so the other screens are not held up
            log.debug("A screen went away or is too slow; dropping it")
            self.remove(ws)
