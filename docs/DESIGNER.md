# Designer guide: building the DASH editor

This guide is for the developer who builds the DASH editor (the designer). The editor is one HTML file. The viewer is a separate file. It runs inside
Home Assistant through Ingress and talks only to the HA App's editor API. The full rules are in
[CONTRACT.md](CONTRACT.md). This guide is the short version with the checklist.

## What you deliver

- **One file:** `dash/app/ui/index.html`. It is a self-contained page: CSS and JavaScript inline, no build step at
  install time.
- **No other files,** unless you really need them. If you do, put them in `dash/app/ui/assets/` and reference them
  with relative paths (`assets/logo.png`), never with absolute paths.
- **The whole file** on every delivery. Not a diff, not a fragment.
- **First line:** a comment with your version and the contract version, for example
  `<!-- DASH designer 1.0, contract 8.2 -->`.
- **Language:** English for all text in the file, including comments. Remove old comments and debug code before you
  deliver.

## How the editor reaches the HA App

- Every request goes to a relative path under `api/`, for example `api/layouts`. Ingress adds the prefix; do not
  build it yourself.
- Read the URL prefix and the screen port from `api/status` (`publish_url_prefix`, `screen_port`). Build screen URLs
  from the host name the editor is loaded from, the screen port and the prefix. Do not hard-code the port.
- Which domains the user may pick come from `api/status` (`allowed_domains`). Do not keep a fixed list of domains in the
  editor. The server refuses a layout with a refused entity when it is published.
- The editor needs **no token** for its own calls. Its requests have no `token` parameter.
- The read token from `api/status` (`read_token`) is only used to build the screen URL that the user copies.

## Endpoints the editor uses

| Method | Path | Purpose |
|---|---|---|
| GET | `api/status` | version, prefix, screen port, read token, connection state |
| GET | `api/entities`, `api/states` | entities and their states for the editor |
| GET | `api/service` | run an action for the editor preview |
| GET | `api/layouts`, `api/layout_load` | list layouts, load a draft |
| POST | `api/layout_save`, `api/layout_move`, `api/layout_delete` | save, move or delete a draft |
| POST | `api/folder_create`, `api/folder_delete` | manage folders |
| POST | `api/publish_save`, `api/publish_delete` | publish or unpublish a layout or skin |
| GET | `api/publish_list`, `api/active` | what is published, which entities are monitored |
| GET | `api/image_list`, `api/imagedata` | images for the editor |
| POST | `api/image_upload`, `api/image_delete` | manage images |
| GET | `api/file` | a published file, for previews |
| GET | `api/published_layout` | the published copy of a layout (used by the Ingress viewer, not the editor) |

Anything else is not available to the editor.

## What the file must not contain

Each rule is checked by `tests/test_ui.py`. Run that test before you deliver.

- **Port 8092** anywhere in the file. The editor never calls the screen server, not even to check it. Use `api/file`
  and `api/imagedata` for previews.
- **Absolute URLs and external hosts:** no `https://`, `http://`, `ws://`, no CDN (`unpkg`, `jsdelivr`, `cdnjs`) and no
  Google Fonts. React, icons and fonts must be part of the file or of `assets/`.
- **Absolute paths** such as `/api/...`, `/local/...` or `/dash/...`. They break under Ingress and the `/local/` path is
  no longer used.
- **AppDaemon** in any form: no `/api/appdaemon/`, no `appdaemon` in code, comments or exported scripts.
- **WebSocket, EventSource or XMLHttpRequest** in the editor. Use `fetch` on `api/` paths.
- **An `<iframe>`** in the editor. The viewer is a separate page (contract 6).
- **A read token in the editor's own requests.** Do not add `token=` to an `api/` call.
- **A token written into exported code.** Exported scripts must not contain `const TOKEN = ...`.

## Exported code

If the editor exports code (for example a script for a screen or a template), that code is part of the file and is
checked too. Exported code must use relative paths and the same rules as above. It must not contain AppDaemon routes,
absolute `/api/` paths, the read token, or the screen port as a fixed value.

## Icon in the browser tab

- The editor page uses `<link rel="icon" href="favicon.png">`. The HA App serves `favicon.png` next to `index.html`.
- Published pages on the screen server use `<link rel="icon" href="/dash/favicon.png">`.
- The file is `app/ui/assets/favicon.png`. Replace it to change the icon.

## Previews

- Images in the editor: `api/file?path=...` for published files, `api/imagedata` for monitored image entities.
- The viewer is **not** part of the editor. Do not embed it, and do not embed any page in an `<iframe>`. To show a
  layout, open the viewer in a new tab: the Ingress viewer at `viewer` (contract 6.2), or a screen URL (contract 3.1).
  Both are routes of the HA App.

## Checklist before you deliver

- [ ] One file, `app/ui/index.html`, with the version comment on the first line.
- [ ] All text in English, no old comments, no debug code.
- [ ] Every request uses a relative `api/` path listed above.
- [ ] No port 8092, no absolute URL, no external host, no CDN, no Google Fonts.
- [ ] No AppDaemon code or path, in the editor or in exported code.
- [ ] No WebSocket, EventSource or XHR; no token in editor requests; no token in exported code.
- [ ] `python3 -m unittest discover -s tests -p "test_*.py"` passes in the `dash` folder.
- [ ] Tested in Home Assistant with the editor opened from the sidebar, and with a published layout on a screen.

## Delivery

Send the complete `index.html`. The HA App maintainer replaces the placeholder in `dash/app/ui/index.html`, runs the
tests and bumps the HA App version.
