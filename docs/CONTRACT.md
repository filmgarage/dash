# Contract: DASH

**Version:** 8.7 (adds 0f, sections 3.7 and 4.3; changes sections 3, 4, 4.1, 6.1, 6.2, 12.4; section 0e and 3.6 remain from 8.6)

This contract describes how the designer (the editor front end) works with the DASH HA App. The HA App serves the
editor through Home Assistant Ingress and serves the screens on port 8092 of the Home Assistant host.

Everything not mentioned here is unchanged from version 7.1: the layout format (sections 3 and 3a), layout paths
(4.8), skins (11), default icons (13), image naming and limits (14, 8) and the error table (5).

## 0f. Changes in version 8.7 (polling, ETag and pictures)

- Every state answer carries an `ETag`. A poll that finds nothing new gets `304` without a body (section 4.3).
- New editor endpoint `api/image` (section 3.7): the picture of an allowed image entity as binary data, for `<img src>`.
- Polling is reduced: the screen polls `states` every 5 minutes while the push channel is open (was 60 seconds),
  and every 2 seconds only while it is closed.
- Pictures are not polled any more. A picture is loaded once with `v=<last_changed>` and loaded again only when the
  `last_changed` of its entity changes (section 4.3). The 10-second picture poll is removed.
- `api/states` returns the live state table with the same fields as `states` (section 12.4), not one Home Assistant
  request per entity.
- **For the designer and the viewer:** the requirements are in section 4.3, marked **Required**.

## 0e. Changes in version 8.6 (skin in the layout)

- A layout may name the skin it uses (section 3.6). The editor shows that skin, uses it when it publishes the layout,
  and adds it to the screen URL.
- The built-in layouts are `dash`, `minimal` and `empty`; the editor creates missing ones on first connect (section 12.5).

## 0d. Changes in version 8.5 (screen address, options, thermostat and weather in the HA App)

- The screen address is known to the HA App. `api/status` returns `screen_host` (section 3.1). The designer uses it
  for screen URLs instead of `location.hostname` when `screen_address_mode` is `ip`. The HA App detects the address
  when it starts, or the designer asks for it once and saves it with `api/settings` (section 3.5).
- New HA App options: `screen_address_mode`, `screen_ip`, and the allow and exclude lists (section 7). Locks and alarm
  panels are excluded by default (section 7.2).
- The HA App needs `hassio_api: true` to read the network address from the Supervisor (section 7.1).
- The HA App sends the attributes of section 12.1 for climate and weather entities. The unit of both is the temperature unit.
- The HA App fetches the forecast with `weather.get_forecasts` (section 12.2). It refreshes every 30 minutes and after a
  state change, and sends the result as a `state` push message.
- The thermostat services of section 12.3 are in the default `read_services`, together with `set_preset_mode`.
- Publishing a page with an entity that the options do not allow is refused with `400` (section 7.2).

## 0c. Changes in version 8.4 (thermostat, weather, text sensors, built-in files)

- `states`, `api/states` and push messages carry more attributes for `climate` and `weather` (section 12.1).
- The HA App fetches the weather forecast with `weather.get_forecasts` and sends it as attributes (section 12.2).
- `set_temperature`, `set_hvac_mode` and `set_preset_mode` and their data keys are allowed; the first two are in the
  default `read_services` (section 12.3).
- Tiles change only after the HA App reports the new state. The HA App sends it without delay (section 12.4).
- The editor creates the built-in layout `dash` and the built-in skins `dash` and `minimal` when they are missing
  (section 12.5).

## 0. Changes in version 8.2 (location of published files, security)

- Published pages, the viewer, skins and images are served by the HA App itself, on the screen port `8092`, under the
  prefix `/dash/`. Home Assistant's `www` folder and the `/local/` path are no longer used.
- Published files are therefore not reachable through Home Assistant's web server, and Home Assistant's login is not
  involved. They are reachable only on the network where port 8092 is reachable (section 11).
- `api/status` returns the real version and `publish_url_prefix: "/dash/"`. The screen URL is built from the screen
  host, the `screen_port` and the prefix (section 3.1).
- New editor endpoint `api/file` to preview published files, for example layout images (section 3.3).
- The viewer and its API share one origin. The CORS headers from 8.1 are removed (section 4.2).
- The HA App no longer maps Home Assistant's configuration folder (section 7.1).
- Pages published before 8.2 are not served. Publish every layout again.

Sections of 8.1 that conflict with this section are superseded by it.

## 0b. Changes in version 8.3 (viewer)

- The viewer is no longer part of the editor. It is a separate page, `app/ui/viewer.html`, delivered with the HA App.
  The editor does not publish it, does not embed it and does not check its version.
- The same file is served in two places: on the screen server for Fully Kiosk and the wall tablets (section 6.1), and
  on Ingress for a preview that the designer opens in a separate tab (section 6.2).
- New editor endpoint `api/published_layout` (section 3.4). The Ingress viewer loads the published copy of a layout with
  it, never the draft.
- The editor never embeds the viewer in an `<iframe>` (section 4.2).

## 0a. Changes from version 7.1

- The designer API is part of the HA App. The AppDaemon endpoints (`/api/appdaemon/...`) are retired.
- The editor runs through Home Assistant Ingress. It needs **no token**. All API paths are **relative**
  (`api/layouts`, not `/api/appdaemon/layouts`), because Ingress adds a path prefix.
- The main token and the write token are removed. Only the **read token** remains, for the screens.
- Entities are **selected automatically**: the HA App monitors exactly the entities used by published layouts (section 5).
- Layouts are stored in the HA App's data folder.
- The screens use the HA App's own API on port 8092, with push updates instead of polling.
- Allowed domains and services are set in the HA App options.
- `layout_delete` and `layout_move` of a published layout are refused (`409 layout is published`).

## 1. Architecture

| Surface | Where | Who uses it | Auth |
|---|---|---|---|
| Editor | Home Assistant Ingress (the DASH panel) | the designer in the browser | none; Ingress only lets logged-in Home Assistant users in |
| Screen server | port `8092` on the Home Assistant host, local network only | viewer, Fully Kiosk | none for the pages under `/dash/`; read token for all data |
| Viewer preview | Home Assistant Ingress (`viewer`), opened in a separate tab | the designer, to see a layout | Ingress only; no token |

The editor does not need to know the port of the HA App. Its requests are relative to the page it is loaded from.
The editor URL must end with `/`. The editor needs the screen host and port from `api/status` to build screen URLs.

## 2. Folder structure

```text
/data/layouts/                    drafts, inside the HA App, not public
  kitchen/
    morning.json                  layout kitchen/morning
  test.json                       layout test

/data/published/                  the published version of each layout, not public
  kitchen/
    morning.json                  copy of layout kitchen/morning at its last publish

/data/www/dash/                   published files, served on port 8092 at /dash/
  kitchen/
    morning.html                  published page of kitchen/morning
    morning/
      photo-garden.jpg            images of layout kitchen/morning
  skins/
    _default.json                 pointer to the default skin (section 11.3 of 7.1)
    night.json                    skin night
    night/
      stars.jpg                   background images of skin night

/data/settings.json               the screen address saved by the designer (section 3.5), if any
/data/active.json                 monitored entities and the layouts that use them
```

- `/data` is kept across updates and included in backups.
- `skins` is reserved: no layout or folder path may start with it (section 4.8 of 7.1).
- The editor reads the URL prefix from `api/status` (`publish_url_prefix`). `dash` is the only supported name.

## 3. Editor endpoints (Ingress)

All paths are relative to the editor page. No token. Same parameters and response formats as 7.1, except where stated.

| Method | Path | Query | Body | Purpose |
|---|---|---|---|---|
| GET | `api/status` | - | - | version, state and the values the editor needs for screen URLs (3.1) |
| GET | `api/entities` | - | - | allowed entities with names, icons and attributes (7.1 section 2.2a) |
| GET | `api/states` | `ids` | - | current states of **any allowed entity**, not only monitored ones, from the live state table (12.4); `ETag` and `304` (4.3) |
| GET | `api/image` | `entity` | - | picture of **any allowed** image entity as binary data, for `<img src>` (3.7) |
| GET | `api/imagedata` | `entity`, `hash` (optional) | - | picture of **any allowed** image entity as base64, for the editor preview (7.1 section 2.3) |
| GET | `api/service` | `entity_id`, `service` | - | run an action for the editor preview (7.1 section 2.4) |
| GET | `api/file` | `path` | - | a published file, for previews (3.3) |
| GET | `api/layouts` | - | - | tree of layouts and folders (7.1 section 4.1) |
| GET | `api/layout_load` | `path` | - | load a draft layout (7.1 section 4.2) |
| POST | `api/layout_save` | `path`, `if_saved` (optional) | layout | save a draft layout (7.1 section 4.3) |
| POST | `api/layout_move` | `from`, `to` | - | move an unpublished layout (7.1 section 4.4) |
| POST | `api/layout_delete` | `path` | - | delete an unpublished layout (7.1 section 4.5) |
| POST | `api/folder_create` | `path` | - | create a folder (7.1 section 4.6) |
| POST | `api/folder_delete` | `path` | - | delete an empty folder (7.1 section 4.7) |
| POST | `api/publish_save` | `path`, `type` (optional) | `{"html": "..."}` or `{"json": {...}}` | publish a page or skin (sections 5 and 6); `400` for a refused entity (7.2) |
| POST | `api/publish_delete` | `path`, `type` (optional) | - | unpublish a page or delete a skin (section 5) |
| GET | `api/publish_list` | - | - | all published pages and skins (7.1 section 6.3) |
| POST | `api/image_upload` | `layout` or `skin`, `name` | `{"data_url": "..."}` | store an image (7.1 section 14.1) |
| GET | `api/image_list` | `layout` or `skin` | - | images (7.1 section 14.2) |
| POST | `api/image_delete` | `layout` or `skin`, `name` | `{}` | delete an image (7.1 section 14.3) |
| GET | `api/active` | - | - | entities currently monitored, with the layouts that use them (section 5) |
| POST | `api/settings` | - | `{"screen_ip": "192.168.1.10"}` | save the screen address when the HA App does not know it (3.5) |
| GET | `api/published_layout` | `path` | - | the published copy of a layout, for the Ingress viewer (3.4) |

### 3.1 `api/status`

```json
{"version": "0.7.1", "state": "running", "read_token": "<read token>", "screen_port": 8092,
 "publish_url_prefix": "/dash/", "ha_connected": true, "active_entities": 3,
 "allowed_domains": ["light", "sensor", "switch"], "excluded_domains": ["alarm_control_panel", "lock"],
 "screen_address_mode": "ip", "screen_host": "192.168.69.248", "screen_host_source": "detected"}
```

- `read_token`: the read token from the HA App options, or `""` when none is set. The editor uses it to build viewer
  URLs. This is safe: Ingress only lets logged-in Home Assistant users reach `api/status`.
- `screen_port`: the port of the screen server (section 4).
- `screen_address_mode`: `ip` or `url` (option `screen_address_mode`).
- `screen_host`: the address screens use, or `null` when the HA App does not know it. `screen_host_source` is `option`
  (the option `screen_ip`), `saved` (section 3.5), `detected` (found at start), or `null`.
- `allowed_domains`: the domains the HA App allows, minus the excluded ones. The designer must use this list to show
  which entities can be picked. It must not keep its own list.
- `excluded_domains`: the domains that are never used, even when allowed by `allow_domains`.
- `publish_url_prefix`: where published files are served on the screen port. A screen URL is
  `http://<host>:<screen_port><publish_url_prefix><path>`, where `<host>` is `screen_host` when `screen_address_mode`
  is `ip`, and the host name the editor is loaded from (`location.hostname`) when it is `url`.
- The editor uses a successful `api/status` to detect that it runs inside the HA App.

### 3.2 `api/publish_save`

```json
{"ok": true, "path": "kitchen/morning", "url": "/dash/kitchen/morning.html",
 "entities": ["light.kitchen", "sensor.temp"],
 "added": ["sensor.temp"], "removed": []}
```

- `url`: the path on the screen server. Prefix it with `http://<host>:<screen_port>` to get the full URL.
- `entities`: every entity used by the published version of this layout.
- `added` / `removed`: the change in the monitored set caused by this publish.
- Publishing stores a copy of the layout as it is at that moment. Screens show that copy (section 5).
- `400 not allowed by the HA App options: <entity ids>` when a layout uses an entity that the options do not allow (7.2).

### 3.3 `api/file`

`GET api/file?path=kitchen/morning/photo-garden.jpg` returns the published file with its content type.

- The editor uses it to preview images of a layout, so the browser never has to load them from the screen port.
- Only files inside the publish folder. A path with `..`, a leading `/` or a backslash: `400 invalid path`.
  A missing file: `404 file not found`.

### 3.4 `api/published_layout`

`GET api/published_layout?path=kitchen/morning` returns the **published** copy of a layout, the same JSON that
`layout_load` returns on port 8092. It is used by the Ingress viewer (section 6.2).

- `404 layout is not published` if the layout has no published copy.
- The draft is never returned here.

### 3.5 `api/settings`

`POST api/settings` with `{"screen_ip": "192.168.1.10"}` saves the screen address that the designer asks for. It is
used only when the option `screen_ip` is empty, and only after the address found at start (section 3.1, order:
option, saved, detected).

- The answer is the status fields of 3.1.
- `400 screen_ip must be an IPv4 address such as 192.168.1.10` when the value is not an IPv4 address.
- The designer asks only when `screen_host` is `null` and `screen_address_mode` is `ip`.

### 3.6 Layout field `skin`

`skin` (optional): de naam van de skin die de editor bij deze layout toont en bij publiceren gebruikt

- The HA App stores the field as part of the layout. It does not check the value; the editor checks that it names an
  existing skin.
- The viewer does not read the field: a screen gets its skin from the `skin` parameter of its URL (section 6.1).
- The screen URL that the editor builds (sections 3.1 and 6.1) carries the layout's skin as `&skin=<name>`. A layout
  without `skin` gets a URL without the parameter, and the viewer then uses the default skin (section 12.5).
- Example: `http://192.168.69.248:8092/dash/viewer.html?layout=kitchen/morning&skin=night&token=<read token>`.

### 3.7 `api/image`

- Query: `entity`, an `image.` entity that is allowed (section 7.2). No token. Not limited to monitored entities.
- Response: the picture bytes with their content type (`image/png`, `image/jpeg`, `image/webp` or `image/gif`).
- Headers: `ETag` (a hash of the bytes), `Cache-Control: no-cache`, `X-Content-Type-Options: nosniff`.
- With `If-None-Match` equal to the current `ETag`: `304` without a body.
- Errors: `403` for an entity that is not an allowed image; `502` when Home Assistant cannot be reached (section 8).
- Use it as `api/image?entity=image.qr` in `<img src>`. Add `v=<last_changed>` as described in section 4.3.

## 4. Screen server (port 8092)

Two kinds of access:

| Method | Path | Query | Auth | Purpose |
|---|---|---|---|---|
| GET | `/dash/<path>` | - | none | published pages, `viewer.html`, skins and images (section 2). No directory listing: `403` or `404` for a folder. |
| GET | `states` | `ids`, `token` | read token | states of **monitored** entities only (others are left out, not an error); `ETag` and `304` (4.3) |
| GET | `layout_load` | `path`, `token` | read token | the **published version** of a layout (`404` if not published) |
| GET | `service` | `entity_id`, `service`, `layout`, `token` | read token | run an action; the entity must be on the named published layout (7.1 section 1.2) |
| GET | `image` | `entity`, `token` | read token | picture of a monitored image entity as binary data, with `ETag` and `304` (4.3) |
| GET | `imagedata` | `entity`, `hash` (optional), `token` | read token | picture of a monitored image entity as base64 (7.1 section 2.3); not used for pictures on a screen in 8.7 |
| WS | `ws` | `token` | read token | push updates (section 4.1) |

The read token is given as `?token=<read token>` or as `Authorization: Bearer <read token>`.
Without a token or with a wrong one: `401`. No token configured in the HA App: `503`.
Editor endpoints (`api/...`) are not available on port 8092: `404`.

### 4.1 Push channel (`ws`)

- Connect to `ws://<host>:8092/ws?token=<read token>`. A wrong or missing token closes the connection with code `4401`.
- The server sends a ping every 30 seconds. The client may close and reconnect at any time.

**Client → server** (optional; may be sent again at any time, for example after the layout changed):

```json
{"type": "subscribe", "entities": ["light.kitchen", "sensor.temp"]}
```

Without `subscribe` the client receives all monitored entities. Entities that are not monitored are ignored.

**Server → client**, one JSON object per message:

1. Snapshot, right after connecting and after every `subscribe`:
   ```json
   {"type": "states", "states": {"light.kitchen": {"state": "on", "unit": "", "name": "Kitchen", "icon": "", "device_class": "", "last_changed": 1794521264123, "attributes": {"brightness": 204}}}}
   ```
   Each value has the same fields as `states` (7.1 section 2.1a).
2. A change of one entity, including a change of the forecast (section 12.2):
   ```json
   {"type": "state", "entity_id": "light.kitchen", "state": {"state": "off", "unit": "", "name": "Kitchen", "icon": "", "device_class": "", "last_changed": 1794521300000, "attributes": {}}}
   ```
   `state` is the **complete** new state, not a difference.
3. An entity that is no longer monitored, or no longer exists:
   ```json
   {"type": "removed", "entity_id": "light.kitchen"}
   ```
4. The published layout changed (publish or unpublish):
   ```json
   {"type": "layout", "path": "kitchen/morning", "saved": 1794521300123}
   ```
   The viewer then reloads the layout with `layout_load`. On unpublish, `saved` is `null`.

- `attributes` holds the keys of section 12.1 that apply to the entity. The viewer uses `brightness` for the light bar.
- The viewer uses `states` once at start, then the push channel. It polls `states` every 2 seconds only while
  the push channel is closed, and every 5 minutes as a safety check while it is open (section 4.3).

### 4.2 Same origin

The viewer is served on the same origin as the API (`http://<host>:8092`). The browser therefore needs no CORS
headers, and **8.2 sends none**. A web page on another origin, open in a browser on the network, cannot read the
responses. Scripts and tools that call the API directly still need the token (section 11).

**Rules for the editor (designer):**

- The editor requests data only from the editor API (`api/...`) on its own Ingress address. It never sends a request
  to port `8092`: not with `fetch`, `XMLHttpRequest`, a WebSocket, `EventSource` or an image or script URL.
  Use `api/imagedata`, `api/file` and `api/service` instead of the screen endpoints.
- The port is never written into the code. The editor takes `screen_port` from `api/status` (section 3.1). A fallback
  value such as `|| 8092` is not allowed.
- A **link** to a published page is allowed (section 3.2). The editor may show the screen URL as text, and may give a
  link (`<a href="http://<host>:<screen_port>/dash/...?token=..." target="_blank">`) that opens the page in a new tab.
  Opening a link is a navigation made by the user, not a request made by the editor, so it is not blocked by the
  browser and is not a violation of this rule. The `http://` text in such a link is allowed.
- If Home Assistant is opened over `https://`, the browser blocks any request from the editor to `http://<host>:8092`
  as mixed content. The rule above avoids this problem. A link that the user clicks is not blocked.
- The editor never embeds a page in an `<iframe>`. The viewer (section 6) is not part of the editor. The designer
  opens it in a new tab, either the Ingress viewer (section 6.2) or a screen URL (section 3.1).
- The editor never uses a read token for its own requests. The token appears only in the screen URL that the editor
  builds for a link.

### 4.3 Polling, ETag and pictures

**Required** for the designer (editor and Ingress viewer) and for the viewer on the screen server.

**ETag on state answers.** `states` (screen server) and `api/states` (Ingress) send an `ETag`. Send the last `ETag` back
as `If-None-Match`. When nothing has changed, the answer is `304` without a body. A browser does this by itself when
the request uses the default cache mode. Do **not** use `cache: "no-store"` for these requests, because that removes
the `ETag` check.

**Polling intervals.**

| Place | Push channel | Request | Interval |
|---|---|---|---|
| Screen server | open | `states` | every 5 minutes (safety check only; changes come from push) |
| Screen server | closed | `states` | every 2 seconds |
| Ingress | none (no push across origins, section 4.2) | `api/states` | every 2 seconds, with `If-None-Match` |

**Pictures are loaded once.** A picture is not polled. The `src` of an image tile carries the `last_changed` of its
entity as `v`:

- Screen server: `/image?entity=image.qr&token=<read token>&v=<last_changed>`
- Ingress: `api/image?entity=image.qr&v=<last_changed>`

- The picture loads when the tile is shown.
- It loads again **only when the `last_changed` of that entity changes**. The new value comes from the push channel
  (a `state` message) on the screen server, or from the next `api/states` answer when push is closed or on Ingress.
- Do not reload pictures on a timer. The 10-second picture poll of 8.6 is removed.
- The state of a Home Assistant image entity is the time of its last picture update, so `last_changed` changes when the
  picture changes.
- `imagedata` (base64, with `hash`) is not needed for tiles in 8.7. The editor may still use it for its own previews.

## 5. Monitored entities (automatic selection)

- **Monitored set** = all entities used by the **published version** of each layout that has a published page,
  minus the entities that the options do not allow (section 7.2).
- `publish_save` of a page stores a copy of the layout as it is at that moment. The screens show that copy.
- Saving a draft changes neither the set nor what screens show. Publishing again does both.
  A screen never shows a tile whose entity is not monitored.
- `layout_move` and `layout_delete` of a published layout: `409 layout is published`. Unpublish first.
- `publish_save` adds the entities of the new page. Unpublishing (`publish_delete` of a page) removes the entities that
  no other published layout uses.
- An entity that does not exist in Home Assistant stays in the set and is reported with `"missing": true` in `api/active`.
- `api/active` returns the set and where each entity comes from:

```json
{"active": [
  {"entity_id": "light.kitchen", "layouts": ["kitchen/morning"], "missing": false},
  {"entity_id": "sensor.temp", "layouts": ["kitchen/morning", "test"], "missing": false}
]}
```

- The HA App keeps the set and its reasons in `/data`, so it survives restarts.

## 6. Viewer

### 6.1 One file, two places

- The viewer is one file: `app/ui/viewer.html`, part of the HA App. It is not published by the editor and it is not
  part of `app/ui/index.html`.
- It is served in two places, and it picks its transport from the place it is loaded from:

| Place | URL | Transport | Token | Used for |
|---|---|---|---|---|
| Screen server | `http://<host>:8092/dash/viewer.html?layout=kitchen/morning&skin=night&token=<read token>` | push (`ws`), `layout_load`, `states`, `service`, `image` on port 8092 | read token in the URL | Fully Kiosk and wall tablets |
| Ingress | `<ingress URL>/viewer?layout=kitchen/morning&skin=night` | polling of the editor API (section 6.2) | none | the designer, in a separate tab |

- The screen server serves the file at `/dash/viewer.html`. Ingress serves it at `viewer`. Both are routes of the HA App.
- The viewer contains **no token**. On a screen the token is in the URL, so anyone who can read the URL can read the
  token. Keep `read_services` short (section 7).
- Tiles not on the layout cannot be switched (7.1 section 1.2).
- Image entities: loaded once per `last_changed` with `image` (screen server) or `api/image` (Ingress), not polled
  (section 4.3).

### 6.2 The Ingress viewer

- Loads the **published** copy: `api/published_layout`, not the draft (section 3.4).
- Loads the skin from `api/file?path=skins/<name>.json`, and images through `api/file` and `api/image`.
- Uses `api/states` for the states of the layout, polled every 2 seconds with `If-None-Match` (section 4.3). It does
  not use the push channel: a WebSocket to port 8092 from the Ingress origin is not allowed by section 4.2.
- Loads pictures with `api/image` and reloads them only when the `last_changed` of the entity changes (section 4.3).
- Switching a tile uses `api/service` with the same rules as the editor preview (7.1 section 1.2).
- Has no `api` parameter and no token. The base is the relative `api/` path of the page it is loaded from.

### 6.3 Both places

- The viewer loads the layout with `layout_load` (screen server) or `api/published_layout` (Ingress), the skin from
  `/dash/skins/` (screen server) or `api/file` (Ingress), then uses `states` and the push channel (screen server) or
  polling (Ingress).
- After a layout is published again, a screen gets a `layout` message on the push channel and reloads it. Without push
  it notices the new `saved` within 30 seconds. The Ingress viewer notices it on its next poll.
- Everything on the screen server is plain `http` on one host and port. Browsers do not block the connection as mixed
  content.

## 7. Configuration (HA App options)

```yaml
read_token: "<read-only token>"    # for the screen server, port 8092
log_level: info
screen_address_mode: ip            # ip (screen_host from api/status) or url (the host the editor was opened with)
screen_ip: ""                      # empty: detected at start, or asked by the designer (3.5)
allow_domains: [...]               # empty: built-in list (section 7.2)
allow_entities: []
exclude_domains: [lock, alarm_control_panel]
exclude_entities: []
services: [...]                    # services the editor may call (7.1 section 2.4)
allow_services: []
exclude_services: [lock, unlock, open, alarm_*]   # see 7.2
read_services: [...]               # services the read token may call (7.1 section 2.4); default includes
                                   # set_temperature, set_hvac_mode and set_preset_mode (section 12.3)
allow_read_services: []
exclude_read_services: [lock, unlock, open, alarm_*]
```

The HA App uses the Supervisor token that Home Assistant provides. Nothing is entered for Home Assistant itself.

### 7.1 HA App `config.yaml` (relevant parts)

```yaml
ingress: true
ingress_port: 8099            # editor, only reachable through Ingress
ports:
  8092/tcp: 8092              # screen server, local network
homeassistant_api: true       # Supervisor token for states, services and forecasts
hassio_api: true              # Supervisor network information, to find the screen address (3.1)
```

- The HA App has no folder mapping. Everything it writes is in `/data`.
- Published files are in `/data/www/dash/` and served on port 8092 at `/dash/`. Home Assistant's `www` folder is not used.
- Port 8099 (the editor) is not exposed to the network. Only Ingress reaches it.

### 7.2 Allow and exclude rules

- An entity is allowed when its domain is in `allow_domains` or it is in `allow_entities`, and it is not excluded.
  Exclusion (`exclude_domains`, `exclude_entities`) always wins.
- A missing option uses its default. An empty exclude list excludes nothing.
- `publish_save` of an html page with a refused entity: `400 not allowed by the HA App options: <entity ids>`.
- A screen may call a service only if it is in `read_services` and not in `exclude_read_services`. The editor preview
  uses `services` and `exclude_services` in the same way.
- By default `lock` and `alarm_control_panel` are excluded, with their services (`lock`, `unlock`, `open` and the
  `alarm_*` services). A lock or alarm tile cannot be published, and no screen can unlock or disarm.
- Changes take effect after the HA App restarts.

## 8. Errors

Same as 7.1 section 5, with these changes:

| Code | Meaning in 8.5 |
|---|---|
| 400 | `invalid path`; `screen_ip must be an IPv4 address`; `not allowed by the HA App options: <entity ids>` (publishing) |
| 401 | screen server: missing or wrong read token. On the WebSocket, the connection is closed with code `4401`. |
| 403 | service or entity not allowed; for the screen server also: entity not on the named published layout |
| 404 | not found; `layout is not published` for `layout_load` and `service` on the screen server |
| 409 | `layout is published` (`layout_delete` or `layout_move` of a published layout); `already exists` |
| 503 | screen server: `read token not configured` |

## 9. Unchanged from 7.1

- Layout format and tile properties (3, 3a)
- Path and name rules (4.8, 14.1)
- Skins: format, default pointer, editor rules, background images (11)
- Default icons and offline icons (13)
- Images per layout and per skin: naming, duplicates, types, limits, deletion (14)
- Limits (8)

## 10. Required before the editor works with the HA App

| Item | Without it |
|---|---|
| `api/publish_save` with `type=json` (skins and the default pointer) | skins cannot be saved; the default skin cannot be set |
| `viewer.html` served by the HA App (6.1) | no viewer on the screen server, so no screen works |
| `api/published_layout` (3.4) | the Ingress viewer cannot show a layout |
| `api/image` (editor) and `image` (screen server) | image entity tiles stay empty |
| `api/file` (editor) | layout images do not show in the editor preview |
| Screen URLs built from `screen_host` (or the host name in mode `url`), `publish_url_prefix` and `screen_port` (3.1) | screen URLs point to the wrong place |
| `read_token` in `api/status` (3.1) | the user types the read token into the editor by hand |
| `api/settings` (3.5) and `screen_host` in `api/status` (3.1) | the designer cannot find the screen address when the HA App does not know it |
| Image folder moves and deletes with layouts (7.1 sections 4.4, 4.5) | orphaned or broken images after a move or delete |
| `layout` push message (4.1) | republished layouts reach the screen only after up to 30 seconds |

## 11. Security

### 11.1 Why 8.2 changed the location of the pages

In 8.1 the published pages were stored in Home Assistant's `www` folder. Home Assistant serves that folder under
`/local/` **without a login**. Every published page, the viewer and every skin was therefore readable by anyone who
could reach the Home Assistant web server, including from the internet if the Home Assistant address is exposed
through a reverse proxy or a port forward. A page could also be used to show or operate a dashboard to anyone who found it.

In 8.2 the pages are served only by the HA App, on port 8092. That port is for the local network. Home Assistant's
login, its web server and any reverse proxy in front of it are no longer part of the path to the pages.

### 11.2 Who can reach what

| What | Where | Needs |
|---|---|---|
| Editor: drafts, layouts, publishing, `read_token` and `screen_host` in `api/status`, service preview | Home Assistant Ingress | a logged-in Home Assistant user |
| Published pages, viewer, skins, images under `/dash/` | port 8092 | nothing (local network only) |
| Data: states, `layout_load`, `service`, `image`, push updates | port 8092 | the read token |

The pages under `/dash/` contain no data and no token. Without the read token a visitor sees the empty layout only.

### 11.3 The read token

- Holds access to the monitored states of the published layouts, and to the services in `read_services` on the
  entities of those layouts. It cannot change layouts, publish, delete or read the editor.
- It is in the screen URL, so it is visible in the browser history and in the screen settings.
- To rotate it: change `read_token` in the HA App options, then update the URL on every screen.
- Use a long random value that is used nowhere else.

### 11.4 Other protections

- **No CORS headers** (4.2): a web page from another origin cannot read the API responses in the browser.
- **Published copy** (5): screens show the published version, so a draft that is not yet published never reaches a screen.
- **Paths**: every path is checked. `..`, absolute paths and folders outside the publish folder are refused, and
  directory listing is off.
- **Limits**: HTML 2 MB, skins 256 KB, images 700 KB. Images may be PNG, JPEG, WebP or GIF. SVG is refused, because
  an SVG file can contain scripts.
- **Service calls**: only domains in `allow_domains` and services in the options (7.2). Locks and alarm panels are
  excluded by default. Service data keys must consist of lowercase letters and underscores, and are checked
  against the list in section 12.3 and 7.1 section 2.4.
- **Editor**: only through Ingress, so only logged-in Home Assistant users reach it.

### 11.5 What is not protected

- Anyone on the local network who can reach port 8092 can open the published pages and the skins. These files contain
  no states and no token, but a title, a label or a skin name is visible to them. Do not put private information in those.
- The read token is in the URL. A proxy log, a browser history or a shared screen can reveal it.
- The HTML of a published page is not checked. It runs in the browser of anyone who opens it on the local network.
  Publish only content you trust.
- Traffic on port 8092 is plain `http`. Use it only on a network you trust. A visitor on that network who reads the
  URL can use the read token, including for the services in `read_services`.

### 11.6 Recommendations

- Do not forward port 8092 on the router. Do not publish `/dash/` or port 8092 through a reverse proxy.
- Keep the editor only in Home Assistant. Keep Home Assistant itself behind a login and up to date.
- Keep `read_services` short. Leave out `lock`, `unlock` and the alarm services if a screen is in a shared place.
- Change the read token if a screen is lost, sold or if its URL was seen by someone who should not have it.
- Keep the HA App updated.

## 12. Entity data, thermostat and weather (8.4, implemented in 8.5)

### 12.1. Attributes in `states`, `api/states` and push messages

Send these keys when the entity has them (leave a key out, or send `null`, when it does not apply):

| Domain | Attributes |
|---|---|
| `light` | `brightness` |
| `cover` | `current_position` |
| `climate` | `temperature`, `target_temp_low`, `target_temp_high`, `current_temperature`, `hvac_action`, `hvac_modes`, `min_temp`, `max_temp`, `target_temp_step`, `preset_mode`, `preset_modes`, `temperature_unit` |
| `weather` | `temperature`, `temperature_unit`, `humidity`, `wind_speed`, `wind_speed_unit`, `precipitation_unit`, `forecast_daily`, `forecast_hourly` (section 12.2) |
| `sensor` | none; `device_class` (already in 7.1 section 2.1a) tells the viewer how to show the state |

- `state` of a `climate` entity is the HVAC mode (`heat`, `cool`, `heat_cool`, `auto`, `dry`, `fan_only`, `off`).
- `state` of a `weather` entity is the condition (`sunny`, `partlycloudy`, `rainy`, …).
- `unit` of `climate` and `weather` entities: Home Assistant's temperature unit (`°C` or `°F`), taken from
  `temperature_unit` when the entity has no `unit_of_measurement`.
- `state` is always sent **as text, unchanged**. A sensor whose state is not a number (for example `Washing`,
  `2026-11-15T08:00:00+00:00` or `on`) is shown as text by the viewer. Do not convert or drop it.

### 12.2. Weather forecast

Home Assistant no longer puts the forecast in the weather attributes. The HA App fetches it:

- For every monitored `weather` entity, call `weather.get_forecasts` with `type: daily` and `type: hourly`
  (only the types the entity supports, from its `supported_features`) when the entity is added, every 30 minutes, and
  2 seconds after each state change of the entity.
- Put the result in the attributes as `forecast_daily` (max 7 entries) and `forecast_hourly` (max 24 entries).
- Each entry: `{"datetime": "2026-11-16T12:00:00+00:00", "condition": "rainy", "temperature": 9, "templow": 4, "precipitation_probability": 70}`.
  `templow` and `precipitation_probability` may be missing.
- A changed forecast is sent as a `state` push message, like any other change.
- A failed forecast call is logged and leaves the other forecast in place.

### 12.3. Services for the thermostat

Both the editor (`api/service`) and the screens (`service`) send these. The data-key check (section 11.4) must allow them:

| Service | Data keys |
|---|---|
| `set_temperature` | `temperature`, or `target_temp_low` + `target_temp_high` (for `heat_cool`) |
| `set_hvac_mode` | `hvac_mode` |
| `set_preset_mode` | `preset_mode` |

- `set_temperature`, `set_hvac_mode` and `set_preset_mode` are in the default `read_services` and the default `services`,
  so a thermostat works on a screen. An option `read_services` replaces that default.
- Numbers are sent as text in the query (`temperature=21.5`) and converted by the HA App (7.1 section 2.4).

### 12.4. Confirmed state after a service call

A tap does not change the state of a tile. The HA App's state is the only source of the tile's value:

- The viewer and the editor preview show a **pending** indicator after a tap: the tile is dimmed (opacity 0.5) and,
  for a thermostat, the new target temperature or mode is shown while dimmed. The pending indicator clears when the
  new state arrives, or after 8 seconds if it does not.
- The HA App sends the `state` push message as soon as Home Assistant reports the change, and `api/states` and
  `states` return the new state at once, from the live state table, without a cache. An unchanged answer comes back
  as `304` when the request sends the last `ETag` (section 4.3).
- A failed service call clears the pending indicator at once and shows the error (section 8).

### 12.5. Built-in files

- The editor has three built-in layouts: `dash`, `minimal` and `empty`. The layout `empty` has no tiles; it has the
  same canvas as `dash`.
- The editor has two built-in skins: `dash` (default) and `minimal`.
- When it connects and a built-in file is missing, the editor creates it: `layout_save` for each missing layout
  and `publish_save` with `type=json` for each missing skin. When no default skin is set, it sets `dash` as the default.
- The editor never changes, renames or deletes a built-in file afterwards. The HA App needs no special handling, and it
  does not refuse these names.
- The viewer falls back to skin `dash` when `skins/_default.json` is missing.
