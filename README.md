# DASH HA App (v0.8.2)

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

Read the full guide in [docs/NETWORK-SECURITY.md](../docs/NETWORK-SECURITY.md) before you publish anything. The
short version:

- The editor is only in the Home Assistant sidebar (Ingress). It has no port of its own.
- The screens use port 8092 on your local network. Do not forward that port on your router, and do not add `/dash/`
  or port 8092 to a reverse proxy.
- The published pages, skins and images under `/dash/` need no token. They contain no data, but anyone on your
  local network who can reach port 8092 can open them. Do not put private information in layout names, titles or labels.
- Every screen has its own token (`autotoken_…`), created in the designer. A screen token reaches only the layout it
  was made for. There is no shared token. The token is part of the screen URL, so treat that URL as a secret, and
  rotate the token if a screen is lost.
- Keep `read_services` short. Leave out `lock`, `unlock` and the alarm services on shared screens.
- A screen can start any script, button or scene it is allowed to use, and a script can do more than its name says.
  A script that switches a light can also switch a lock or an alarm. Before you put a script or a button on a layout,
  read what it does in Home Assistant. Do not put on a screen a control that you would not want anyone in the room to press.
- The traffic on port 8092 is plain `http`. Use it only on a network you trust.
- **Accepted risk:** the HA App does not check what a script or a button does. A screen can run a script or a button
  that is allowed, and that script can unlock a door or switch an alarm, even though the HA App blocks `lock.unlock`
  itself. The owner has accepted this risk. The allow and exclude lists limit which entities a screen sees, not what
  those entities do inside Home Assistant. Leave `script`, `button` and `input_button` out of the allow lists unless
  you need them, and check every script before you put it on a screen.

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

The HA App reads the screen address from the entity `sensor.local_ip`. That entity comes from the Local IP Address
integration: add it under Settings > Devices & services. Without it, set the address with the `screen_ip` option or
in the designer. The address is read when the HA App starts; restart the HA App after you add the integration.
The HA App uses it only to build screen URLs and changes no network setting.

## Setting up a screen

A screen needs no login. Its start URL contains everything it needs. Replace `HA_IP` with the local address of
Home Assistant:

```text
http://HA_IP:8092/dash/viewer.html?layout=kitchen/morning&skin=night#token=YOUR_SCREEN_TOKEN
```

The token is in the part after `#`, so it is not sent to the server in the request line. Create the screen and its token
in the designer.

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
- Each screen has its own token (`autotoken_…`). There is no shared token.
