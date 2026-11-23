# Changelog

## 0.11.0 (contract 10.0)

Changes since 0.10.0: Fully Kiosk tablets in the publish window, and the editor and viewer of editor 2.5 and viewer 33.

### App
- `GET api/fully_devices`: the Fully Kiosk tablets of Home Assistant, with their online state, their DASH screen, their
  layout and their admin address (`http://<host>:2323`). `start` is `false` for now.
- `POST api/fully_show`: sends a published layout to a tablet. The App creates the tablet's screen the first time (named
  after the device, linked by its device id) and keeps its token. It loads the screen address in the tablet, and with
  `start: true` also sets it as start page. Refusals: `400` unpublished layout, `404` unknown device, `502` Home Assistant.
- `docs/CONTRACT.md` section 0l. App version raised to 0.11.0.

### Front end (editor 2.5, viewer 33)
- Skins: per-shape styles. A skin, and its dark, domain and state blocks, can carry `landscape` and `portrait` blocks on
  top of the square default. The skin editor previews each icon as square, landscape and portrait.
- The viewer counts tiles of 1.5 x their height or wider as landscape, and 1.5 x their width or taller as portrait. The
  skin's shape blocks apply on top of the default.
- New layout and new skin: start from Empty, Dash, Classic or Minimal.
- Top bar: a "folder · Layout / Skin" button opens file management. A dropdown lists the saved files, with folders that
  expand and collapse.
- File management: drag layouts and skins into a folder, or back out to the top level.
- Layers: folders. Make a folder from the selection (or an empty one), rename it with a double-click, and drag elements
  between layers and in and out of folders.
- Publish window (replaces the two links at the bottom of the page):
  - Published dashboards: Publish and Publish again per dashboard, open on the screen address, open the preview through
    Ingress, unpublish.
  - Available screens: Fully Kiosk tablets with Show now, Set as start page and a settings button. Other screens with
    Show this page, copy address and delete. "+ New" makes a screen.
- The top bar Publish button reads "Publish…" and is greyed out while the publish window is open.
- Built-in layouts and skins are ordinary, editable files. They are created only when nothing is stored yet. The
  "built in" labels are gone; only the default skin keeps its "default" label.
- Renamed: layout `default-layout-read-only` is now `default`, layout `minimal` is now `squares`, skin
  `default-skin-read-only` is now `modernist`. The editor migrates stored files on connect.
- Fix: the squares (minimal) layout follows the skin's shape blocks, so its layout and icon size no longer drift.

### Breaking
- Published pages that point to `default-layout-read-only` or `minimal` must be published again.

## 0.10.0 (contract 10.0)

Changes since 0.9.1: history and camera data for the viewer.

- `GET history` (screen port, `/dash/...` form) and `GET api/history` (editor): the history of one entity for the
  history graph, for `hours` 1 to 168 and up to `points` 500. Numbers are averaged per time bucket, and a state that is
  not a number is `null`. Uses the Home Assistant recorder.
- `GET camera` (screen port) and `GET api/camera` (editor): the current still image of a `camera.*` entity, without
  caching. A camera that is off or unavailable gives `503`.
- Both follow the same rules as `states`: the screen token and its layout, or Ingress and the HA App options.
- The forecast was already in the `states` answer since 0.8.4; nothing changed for it.
- A skin saved in version 3 (the old model) is refused with a message that names it. The conversion of old skins is removed.
- `docs/CONTRACT.md` is version 10.0 (section 0k).
- App version raised to 0.10.0.

## 0.9.1 (contract 9.1)

Changes since 0.9.0: documentation of the skin format. No change in behaviour.

- The skin format is described in `DASH-FILE-FORMAT.md` (format-version 1): skin background, `show.switch`,
  `show.extras`, and dark mode with `always`, `time` and `until`. Light and dark are the only words for the two modes.
- Skins in the old model (version 3) are accepted until App 0.10.0. The designer converts them once. App 0.10.0 refuses
  them.
- The editor (`index.html`) and the viewer (`viewer.html`) are updated by the designer. The editor still saves the old
  skin model until its conversion is in; the App accepts that.
- `docs/CONTRACT.md` is version 9.1 (section 0j).
- App version raised to 0.9.1.

## 0.9.0 (contract 9.0)

Changes since 0.8.9: the App panel can save its settings.

- `api/settings` saves the App panel settings: `allow_domains`, `allow_entities`, `exclude_domains`,
  `exclude_entities`, `language`, `date_format`, `time_format`, `default_skin` and `warnings`. Every value is checked, and
  a single bad value refuses the whole save with a message that names the key.
- Saved lists are kept in `settings.json` and override the App options for those lists. They apply at once, without a
  restart.
- `api/status` returns the same settings, so the App panel can show the current values.
- App version raised to 0.9.0.
