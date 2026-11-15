# Contract: DASH

**Version:** 8.2 (replaces 8.1)

This contract describes how the designer (the editor front end) works with the DASH HA App. The HA App serves the
editor through Home Assistant Ingress and serves the screens on port 8092 of the Home Assistant host.

Everything not mentioned here is unchanged from version 7.1: the layout format (sections 3 and 3a), layout paths
(4.8), skins (11), default icons (13), image naming and limits (14, 8) and the error table (5).

## 0. Changes in version 8.2 (location of published files, security)

- Published pages, the viewer, skins and images are served by the HA App itself, on the screen port `8092`, under the
  prefix `/dash/`. Home Assistant's `www` folder and the `/local/` path are no longer used.
- Published files are therefore not reachable through Home Assistant's web server, and Home Assistant's login is not
  involved. They are reachable only on the network where port 8092 is reachable (section 11).
- `api/status` returns the real version and `publish_url_prefix: "/dash/"`. The editor builds a screen URL from the host
  name it is loaded from, the `screen_port` and the prefix (section 3.1).
- New editor endpoint `api/file` to preview published files, for example layout images (section 3.3).
- The viewer and its API share one origin. The CORS headers from 8.1 are removed (section 4.2).
- The HA App no longer maps Home Assistant's configuration folder (section 7.1).
- Pages published before 8.2 are not served. Publish every layout again.

Sections of 8.1 that conflict with this section are superseded by it.

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

The editor does not need to know the host name or port of the HA App. Its requests are relative to the page it is
loaded from. The editor URL must end with `/`.

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
  viewer.html                     the viewer (section 6)
  kitchen/
    morning.html                  published page of kitchen/morning
    morning/
      photo-garden.jpg            images of layout kitchen/morning
  skins/
    _default.json                 pointer to the default skin (section 11.3 of 7.1)
    night.json                    skin night
    night/
      stars.jpg                   background images of skin night

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
| GET | `api/states` | `ids` | - | current states of **any allowed entity**, not only monitored ones (7.1 section 2.1a) |
| GET | `api/imagedata` | `entity`, `hash` (optional) | - | picture of **any allowed** image entity, for the editor preview (7.1 section 2.3) |
| GET | `api/service` | `entity_id`, `service` | - | run an action for the editor preview (7.1 section 2.4) |
| GET | `api/file` | `path` | - | a published file, for previews (3.3) |
| GET | `api/layouts` | - | - | tree of layouts and folders (7.1 section 4.1) |
| GET | `api/layout_load` | `path` | - | load a draft layout (7.1 section 4.2) |
| POST | `api/layout_save` | `path`, `if_saved` (optional) | layout | save a draft layout (7.1 section 4.3) |
| POST | `api/layout_move` | `from`, `to` | - | move an unpublished layout (7.1 section 4.4) |
| POST | `api/layout_delete` | `path` | - | delete an unpublished layout (7.1 section 4.5) |
| POST | `api/folder_create` | `path` | - | create a folder (7.1 section 4.6) |
| POST | `api/folder_delete` | `path` | - | delete an empty folder (7.1 section 4.7) |
| POST | `api/publish_save` | `path`, `type` (optional) | `{"html": "..."}` or `{"json": {...}}` | publish a page or skin (sections 5 and 6) |
| POST | `api/publish_delete` | `path`, `type` (optional) | - | unpublish a page or delete a skin (section 5) |
| GET | `api/publish_list` | - | - | all published pages and skins (7.1 section 6.3) |
| POST | `api/image_upload` | `layout` or `skin`, `name` | `{"data_url": "..."}` | store an image (7.1 section 14.1) |
| GET | `api/image_list` | `layout` or `skin` | - | images (7.1 section 14.2) |
| POST | `api/image_delete` | `layout` or `skin`, `name` | `{}` | delete an image (7.1 section 14.3) |
| GET | `api/active` | - | - | entities currently monitored, with the layouts that use them (section 5) |

### 3.1 `api/status`

```json
{"version": "0.3.1", "state": "running", "read_token": "<read token>", "screen_port": 8092,
 "publish_url_prefix": "/dash/", "ha_connected": true, "active_entities": 3}
```

- `read_token`: the read token from the HA App options, or `""` when none is set. The editor uses it to build viewer
  URLs. This is safe: Ingress only lets logged-in Home Assistant users reach `api/status`.
- `screen_port`: the port of the screen server (section 4).
- `publish_url_prefix`: where published files are served on the screen port. A screen URL is
  `http://<host>:<screen_port><publish_url_prefix><path>`, where `<host>` is the host name the editor is loaded from
  (`location.hostname`).
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

### 3.3 `api/file`

`GET api/file?path=kitchen/morning/photo-garden.jpg` returns the published file with its content type.

- The editor uses it to preview images of a layout, so the browser never has to load them from the screen port.
- Only files inside the publish folder. A path with `..`, a leading `/` or a backslash: `400 invalid path`.
  A missing file: `404 file not found`.

## 4. Screen server (port 8092)

Two kinds of access:

| Method | Path | Query | Auth | Purpose |
|---|---|---|---|---|
| GET | `/dash/<path>` | - | none | published pages, `viewer.html`, skins and images (section 2). No directory listing: `403` or `404` for a folder. |
| GET | `states` | `ids`, `token` | read token | states of **monitored** entities only (others are left out, not an error) |
| GET | `layout_load` | `path`, `token` | read token | the **published version** of a layout (`404` if not published) |
| GET | `service` | `entity_id`, `service`, `layout`, `token` | read token | run an action; the entity must be on the named published layout (7.1 section 1.2) |
| GET | `imagedata` | `entity`, `hash` (optional), `token` | read token | picture of a monitored image entity (7.1 section 2.3) |
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
2. A change of one entity:
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

- `attributes` may contain `brightness` (0-255), `brightness_pct`, `current_position`, `temperature`,
  `current_temperature` and `hvac_action` when they apply. The viewer uses `brightness` for the light bar.
- The viewer uses `states` once at start, then the push channel. It polls `states` every 2 seconds only while
  the push channel is closed, and once a minute as a safety check while it is open.

### 4.2 Same origin

The viewer is served on the same origin as the API (`http://<host>:8092`). The browser therefore needs no CORS
headers, and **8.2 sends none**. A web page on another origin, open in a browser on the network, cannot read the
responses. Scripts and tools that call the API directly still need the token (section 11).

## 5. Monitored entities (automatic selection)

- **Monitored set** = all entities used by the **published version** of each layout that has a published page.
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

- One page: `/dash/viewer.html`, published once by the editor with `type` `html`.
- URL: `http://<host>:8092/dash/viewer.html?layout=kitchen/morning&skin=night&token=<read token>`
- The viewer uses the host and port it is loaded from. There is no `api` parameter.
- The viewer contains **no token**. The token is in the URL, so anyone who can read the URL can read the token.
  Keep `read_services` short (section 7).
- The viewer loads the layout with `layout_load`, the skin from `/dash/skins/`, then uses `states` and the push channel.
- Tiles not on the layout cannot be switched (7.1 section 1.2).
- After a layout is published again, the viewer gets a `layout` message on the push channel and reloads it.
  Without push it notices the new `saved` within 30 seconds.
- Image entities: `imagedata` on port 8092, polled every 10 seconds with the last `hash`.
- Everything is plain `http` on one host and port. Browsers do not block the connection as mixed content.

## 7. Configuration (HA App options)

```yaml
read_token: "<read-only token>"    # for the screen server, port 8092
log_level: info
allow_domains: [light, switch, input_boolean, scene, script, cover, sensor,
                binary_sensor, weather, climate, image]
services: [...]                    # services the editor may call (7.1 section 2.4)
read_services: [...]               # services the read token may call (7.1 section 2.4)
```

The HA App uses the Supervisor token that Home Assistant provides. Nothing is entered for Home Assistant itself.

### 7.1 HA App `config.yaml` (relevant parts)

```yaml
ingress: true
ingress_port: 8099            # editor, only reachable through Ingress
ports:
  8092/tcp: 8092              # screen server, local network
homeassistant_api: true       # Supervisor token for states and services
```

- The HA App has no folder mapping. Everything it writes is in `/data`.
- Published files are in `/data/www/dash/` and served on port 8092 at `/dash/`. Home Assistant's `www` folder is not used.
- Port 8099 (the editor) is not exposed to the network. Only Ingress reaches it.

## 8. Errors

Same as 7.1 section 5, with these changes:

| Code | Meaning in 8.2 |
|---|---|
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
| `api/publish_save` of `viewer` (html) | no viewer, so no published page works |
| `api/imagedata` (editor) and `imagedata` (screen server) | image entity tiles stay empty |
| `api/file` (editor) | layout images do not show in the editor preview |
| Screen URLs built from `publish_url_prefix` and `screen_port` (3.1) | screen URLs point to the wrong place |
| `read_token` in `api/status` (3.1) | the user types the read token into the editor by hand |
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
| Editor: drafts, layouts, publishing, `read_token` in `api/status`, service preview | Home Assistant Ingress | a logged-in Home Assistant user |
| Published pages, viewer, skins, images under `/dash/` | port 8092 | nothing (local network only) |
| Data: states, `layout_load`, `service`, `imagedata`, push updates | port 8092 | the read token |

The pages under `/dash/` contain no data and no token. Without the read token a visitor sees the empty layout only.

### 11.3 The read token

- Holds access to the monitored states of the published layouts, and to the services in `read_services` on the
  entities of those layouts. It cannot change layouts, publish, delete or read the editor.
- It is in the screen URL, so it is visible in the browser history and in the screen settings.
- To rotate it: change `read_token` in the HA App options, then update the URL on every screen.
- Use a long random value that is used nowhere else.

### 11.4 Other protections in 8.2

- **No CORS headers** (4.2): a web page from another origin cannot read the API responses in the browser.
- **Published copy** (5): screens show the published version, so a draft that is not yet published never reaches a screen.
- **Paths**: every path is checked. `..`, absolute paths and folders outside the publish folder are refused, and
  directory listing is off.
- **Limits**: HTML 2 MB, skins 256 KB, images 700 KB. Images may be PNG, JPEG, WebP or GIF. SVG is refused, because
  an SVG file can contain scripts.
- **Service calls**: only domains in `allow_domains` and services in the options. Service data keys are checked.
- **Editor**: only through Ingress, so only logged-in Home Assistant users reach it.

### 11.5 What 8.2 does not protect

- Anyone on the local network who can reach port 8092 can open the published pages and the skins. These files contain
  no states and no token, but a title, a label or a skin name is visible to them. Do not put private information in those.
- The read token is in the URL. A proxy log, a browser history or a shared screen can reveal it.
- The HTML of a published page is not checked. It runs in the browser of anyone who opens it on the local network.
  Publish only content you trust.
- Traffic on port 8092 is plain `http`. Use it only on a network you trust.

### 11.6 Recommendations

- Do not forward port 8092 on the router. Do not publish `/dash/` or port 8092 through a reverse proxy.
- Keep the editor only in Home Assistant. Keep Home Assistant itself behind a login and up to date.
- Keep `read_services` short. Leave out `lock` and `unlock` if a screen is in a shared place.
- Change the read token if a screen is lost, sold or if its URL was seen by someone who should not have it.
- Keep the HA App updated.
