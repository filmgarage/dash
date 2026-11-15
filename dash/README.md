# DASH add-on (v0.1.4)

First base of the DASH add-on for Home Assistant. It replaces AppDaemon for the screens.

## What it does now

- **Interface (sidebar, Ingress):** choose which entities the screens may see. Changes save automatically.
- **Live connection:** one websocket to Home Assistant, subscribed only to the selected entities. Home Assistant
  sends only changes, so nothing is polled.
- **Screen API (port 8092):** snapshot, live updates, and service calls, all limited to the selection.

Layouts, skins and publishing come in a later version.

## Install (local add-on)

1. Copy the `dash` folder to the `addons` share of Home Assistant (Samba or SSH).
2. Settings > Add-ons > Add-on store > menu > Check for updates. DASH appears under "Local add-ons". Install it.
3. Configuration tab: set `read_token` to a long random string. This is the token for the screens.
4. Start the add-on and open DASH from the sidebar. Select the entities.

If port 8092 is taken on your system, change it in `config.yaml` (`ports`) and in the screen URLs.

## Screen protocol (port 8092)

All requests need the token: `?token=<read_token>` or `Authorization: Bearer <read_token>`.

- `GET /health` (no token): `{"ok": true}`
- `GET /api/states?ids=light.kitchen,...`: `{"states": {"light.kitchen": {state, name, unit, icon, device_class, last_changed, attributes}}}`
  Entities that are not selected are left out.
- `POST /api/service` with `{"entity_id": "light.kitchen", "service": "toggle", "data": {}}`:
  the entity must be selected and the service must be in the allowed list.
- `GET /ws?token=...` (websocket). Send `{"type": "subscribe", "entities": ["light.kitchen"]}`. The server replies with
  `{"type": "snapshot", "states": {...}}` and then `{"type": "state", "entity_id": ..., "data": {...}}` for each change,
  or `{"type": "removed", "entity_id": ...}`. Only entities in the selection are ever sent.

## Security

- The interface only answers requests that carry the Ingress header, so it cannot be reached on the network.
- Screens need the read token. Without a token set, all screen requests return `503`.
- The screen port only offers the screen API, never the interface.

## Known limits (v0.1.4)

- Not yet tested against a live Home Assistant. Test the websocket and the service calls first.
- The screen token is a single shared secret. A per-screen token comes later.
- Base image tags in `build.yaml` must match your Home Assistant version.
