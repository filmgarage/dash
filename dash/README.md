# DASH HA App (v0.7.1)

DASH is a Home Assistant app for simple, light web dashboards on screens such as a Fully Kiosk photo frame or a
wall tablet. You design a layout in the DASH editor, publish it, and the screen shows it with live values from
Home Assistant.

## What the HA App does

- **Editor** (Home Assistant sidebar, panel "DASH"): create layouts, folders, skins and published pages.
  Access is controlled by Home Assistant itself; no separate login.
- **Automatic entity selection**: the HA App monitors exactly the entities used by layouts that have a published
  page. Publishing adds entities, unpublishing removes the ones that no other published page uses. Drafts do not
  change anything.
- **Screen server** (port 8092, local network only): serves the published pages and the viewer, gives the viewer the
  states, and pushes live changes over a websocket. Data needs the read token; the pages themselves do not.
- **Files**: layouts are stored in the HA App's data folder. Published pages, the viewer, skins and images are
  stored in the HA App's data folder too, and served by the HA App on port 8092. Home Assistant's `www` folder is
  not used, so nothing is published through Home Assistant's web server.

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**, open the menu (⋮) and choose **Repositories**.
2. Add the URL of the repository (the repository root, the folder that contains `repository.yaml`).
3. Find **DASH** in the store, install it and open its **Configuration** tab.
4. Set a **read token** (see below) and save.
5. Start the HA App. Open **DASH** in the sidebar.

Requirements: Home Assistant OS or Supervised. The HA App uses the Supervisor token that Home Assistant provides;
you do not create a long-lived token. No restart of Home Assistant is needed.

## Safety

This chapter explains what the HA App exposes, where, and how to keep it safe. Read it before you publish anything.

### What is reachable, and from where

| What | Where | What a visitor needs |
|---|---|---|
| Editor (drafts, publishing, read token) | Home Assistant sidebar (Ingress) | a logged-in Home Assistant user |
| Published pages, viewer, skins, images under `/dash/` | port 8092, local network | nothing; they contain no data and no token |
| Data: states, layouts, service calls, pictures, live updates | port 8092, local network | the read token |

The editor is never on a network port of its own. The published pages are **not** served through Home Assistant's
web server (`/local/`), so they are not exposed through Home Assistant's login page or through a reverse proxy in
front of Home Assistant.

### Keep port 8092 on your local network

- Do not forward port 8092 on your router.
- Do not add `/dash/` or port 8092 to a reverse proxy such as Nginx Proxy Manager.
- Check your router and proxy settings after you install the HA App. The HA App cannot check this for you.

### The read token

- The read token gives access to the states of the published layouts and to the services in `read_services` on the
  entities of those layouts. It cannot change layouts, publish pages or read the editor.
- Use a long random value (at least 24 characters from a password generator) and do not reuse it anywhere else.
- The token is in the screen URL. It is visible in the browser history and in the screen's settings.
- To replace it, change `read_token` in the HA App options, then update the URL on every screen.
- Replace the token at once if a screen is lost or sold, or if its URL was seen by someone who should not have it.

### Limit what a screen may do

- Keep `read_services` short. A screen only needs `toggle` and `press` for most dashboards.
- Leave out `lock` and `unlock` if a screen stands in a shared place.
- Keep `allow_domains` to the domains your dashboards use.

### What the HA App does not protect

- Anyone on your local network who can reach port 8092 can open the published pages and skins. They see layout
  names, titles and labels that you wrote into them. Do not put private information in those.
- The HTML of a published page is not checked. It runs in the browser of anyone who opens it on the local network.
  Publish only content you trust.
- Traffic on port 8092 is plain `http`. Use it only on a network you trust.
- The HA App does not replace Home Assistant's own security. Keep Home Assistant behind a login, keep it up to date
  and use strong passwords for its users.

### Checklist

- [ ] Port 8092 is not forwarded on the router.
- [ ] No reverse proxy route points to `/dash/` or to port 8092.
- [ ] The read token is long, random and not used elsewhere.
- [ ] `read_services` contains only the services the screens need.
- [ ] Home Assistant and the HA App are up to date.
- [ ] Only trusted content is published.

## Disclaimer

**Use this HA App at your own risk.**

This HA App is provided "as is", without warranty of any kind, express or implied, including but not limited to
warranties of merchantability, fitness for a particular purpose and non-infringement. The author accepts no liability
for any damage, data loss, security incident, privacy breach or unintended behaviour of devices, including
devices that you control through a dashboard. You are responsible for how you configure, expose and use it.
Test it with non-critical devices first.

## Options

| Option | Default | Meaning |
|---|---|---|
| `read_token` | empty | Token for screens. Required before any screen can load data. |
| `log_level` | `info` | `debug`, `info`, `warning` or `error`. |
| `screen_address_mode` | `ip` | `ip`: screens use the LAN address of Home Assistant. `url`: screens use the address the editor was opened with, such as a DNS name. |
| `screen_ip` | empty | The LAN address for screens. Empty means the HA App detects it, or the designer asks for it the first time. |
| `allow_domains` | empty (built-in list) | Domains the HA App may use. An empty list means the built-in list. |
| `allow_entities` | empty | Single entities allowed in addition to the domains. |
| `exclude_domains` | `lock`, `alarm_control_panel` | Domains never used, even if allowed above. |
| `exclude_entities` | empty | Single entities never used. |
| `services` | empty (built-in list) | Services the editor may call, for the preview in the editor. |
| `allow_services` | empty | Services added to `services`. |
| `exclude_services` | locks and alarm services | Services removed from `services`. |
| `read_services` | empty (built-in list) | Services a screen may call. Keep this short. |
| `allow_read_services` | empty | Services added to `read_services`. |
| `exclude_read_services` | locks and alarm services | Services removed from `read_services`. |

Rules, in this order:

1. An entity is allowed when its domain is in `allow_domains` or it is in `allow_entities`.
2. An entity is refused when its domain is in `exclude_domains` or it is in `exclude_entities`. Exclusion always wins.
3. A layout that uses a refused entity cannot be published. The editor shows which entity it is.
4. A screen may call a service only if it is in `read_services` and not refused by `exclude_read_services`.

Locks and alarm panels are excluded by default: a lock or alarm tile cannot be published, and no screen can unlock or
disarm. To allow them, remove the domain from `exclude_domains` and the services from `exclude_read_services`. Do this
only for a screen in a place where everyone who can reach port 8092 may open that lock or alarm.

Changes take effect after the HA App restarts. A missing option uses its default; an empty list excludes nothing.

Create the read token with a password generator and use a value that you do not use anywhere else.

The HA App reads the network address of the Home Assistant host from the Supervisor (`hassio_api`). It uses that
only to build screen URLs; it changes no network setting.

## Setting up a screen

A screen needs no login. Its start URL contains everything it needs. Replace `HA_IP` with the local address of
Home Assistant:

```text
http://HA_IP:8092/dash/viewer.html?layout=kitchen/morning&skin=night&token=YOUR_READ_TOKEN
```

| Part | Meaning |
|---|---|
| `viewer.html` | The viewer. The HA App serves it; nothing to publish. |
| `layout=` | The layout to show, as it is named in the editor, for example `kitchen/morning`. The layout must be published. |
| `skin=` | The skin (colours, fonts, tile style). Optional; without it the default skin or the layout's own style is used. |
| `token=` | The read token from the HA App options. |

Steps:

1. Open DASH, design the layout, choose a skin and publish the layout.
2. Build the URL above with the layout path, the skin name and the read token.
3. In Fully Kiosk Browser (or any browser), set this URL as the start page.

The viewer, its API and its live updates all use port 8092 of the same host, over plain `http://`. Nothing goes
through Home Assistant's web server or through a reverse proxy.

The screen shows the **published** version of a layout. Saving a draft changes nothing on screens; publishing
again updates them. The screen reads the layout once when it starts, then receives live changes over the
websocket `ws://HA_IP:8092/ws?token=…`. A wrong token closes the socket with code `4401`. The viewer shows only
the entities of its layout.

## Status page

The status page lists the entities that the HA App monitors, the layouts that use each one, and any entity that is
missing from Home Assistant. Open **DASH** in the sidebar and add `status` to the end of the address in your browser.
The page is only reachable through Home Assistant's login, not on port 8092.

## Files on disk

| Location | Contents |
|---|---|
| `/data/layouts/` | Layouts (drafts and their saved state). |
| `/data/published/` | The published version of each layout, which the screens use. |
| `/data/www/dash/` | Published pages, skins and images. Served on port 8092 at `/dash/`. |
| `/data/active.json` | The monitored entities and the layouts that use them. |

Everything is in the HA App's data folder, so it is kept across updates and included in backups.

## Troubleshooting

- **The editor shows "no Supervisor token"**: the HA App was installed without `homeassistant_api`. Rebuild it from
  the current version.
- **A screen gets 503 "read token not configured"**: set the read token in the HA App options and restart.
- **A screen gets 401 "unauthorized"**: the token in the URL does not match the HA App option.
- **A screen gets 404 "layout is not published"**: publish the layout in the editor.
- **After updating from 0.2.x**: pages published before 0.3.0 were stored in Home Assistant's `www` folder, and they
  are no longer served. Publish every layout again in the editor.
- **An entity shows "(not found)"** in the editor's monitored list: the entity does not exist in Home Assistant
  (anymore). Remove it from the layout.
- For details, set `log_level` to `debug` and read the HA App log.

## Known limits

- The editor's front end is one file, `app/ui/index.html`, checked by `tests/test_ui.py`. Its icon set is
  `app/ui/assets/mdi-icons.txt`, served under `assets/`. The viewer is `app/ui/viewer.html`, checked by `tests/test_viewer.py`.
- The status page (`app/ui/status.html`) lists the monitored entities and the layouts that use them. It stays available
  at `status` in the HA App's panel.
- Entities are monitored for the screens only after publishing. A layout that is only drafted does not show live
  values anywhere.
- The area of an entity is not available.
- The screen API uses one token for all screens.
