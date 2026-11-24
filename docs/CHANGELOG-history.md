# DASH changelog history

Older release notes. The App's own changelog (dash/CHANGELOG.md) holds only the latest release.

## 0.12.2 (contract 10.0)

Changes since 0.12.1: editor 2.7 and viewer 37 from the designer, with the fonts delinked.

### App
- Editor 2.7 and viewer 37 are installed. The editor and the viewer load their fonts from `assets/fonts/` in the App. No
  external font or script links remain; the React libraries of the editor are inside the editor file.
- The editor no longer writes `allow_domains` or `allow_entities`. Access is set in the App configuration. A list saved
  by an earlier editor still overrides the configuration until it is removed from the saved App settings.
- `docs/CONTRACT.md` is unchanged (contract 10.0). App version raised to 0.12.2.

### Editor (designer changes, see the designer changelog)
- Code view: a dropdown switches between Layout JSON and Page HTML.
- App settings: a read-only list of the access settings from the App configuration.
- "Files" is now "File Manager"; "HTML" is now "Code".
- File Manager: touch drag picks up a file after a short hold; the list no longer scrolls while dragging.
- Files and folders sort alphabetically, ignoring capitals, with numbers in number order.
- Media player: artwork and volume show again on narrow tiles.

## 0.12.1 (contract 10.0)

Changes since 0.12.0: cameras and media players work in the App.

### App
- `camera` is in the default `allowed_domains`. Camera entities were not listed before. Installs with their own list
  add `camera` in the App options.
- Media players send the track title, the artist, the album, the app name, the volume, the mute state, the position, the
  duration, the source, shuffle, repeat and the sound mode. Before, the viewer got none of these, so no title and no
  volume bar.
- The artwork of a media player or camera is loaded through the App. The screen no longer receives the picture URL,
  which holds a token; it gets a marker that changes with the picture.
- Fonts: Roboto (viewer) and Archivo (editor) are included as variable WOFF2 files in `app/ui/assets/fonts`, with their
  SIL Open Font License texts. The screen port serves the viewer's assets under `/dash/assets/`, so the viewer gets the
  same fonts on every device.
- `docs/CONTRACT.md` section 0m. App version raised to 0.12.1.

## 0.12.0 (contract 10.0)

Changes since 0.11.0: screen rename, `sun` in the default allowed domains, and the editor 2.6 and viewer 36 front end.

### App
- `POST api/screen_rename?from=<name>&to=<name>`: renames a screen. Its token, layout and address stay the same, and its
  open push channels stay connected. `404` unknown screen, `409` name already in use, `400` invalid name. The screen
  sensor moves to the new name.
- `sun` is in the default `allowed_domains`, so dark mode in skins can follow `sun.sun`. Installs that still have the old
  default list in their options: add `sun` there.
- `docs/CONTRACT.md` section 0m. App version raised to 0.12.0.

### Front end (editor 2.6, viewer 36)
- Publish window: Published dashboards (Publish and Publish again per dashboard, open direct or through Ingress,
  unpublish), and Available screens (Fully Kiosk tablets with Show now, Set as start page and settings; general screens
  with show, rename, copy address and delete; "+ New").
- Top bar: Files button, and "Layout:" and "with skin" dropdowns that open downward with folders expanded.
- Group selection shows X/Y (editable) and W/H (read-only). The align buttons are gone.
- Dark mode on Entity tiles works for any entity, also one typed by hand.
- `sun` is in the default domains, with a warning when it is removed.
- Brightness bars can be tapped to set the brightness.
- Portrait tiles: rotated clock, vertical history graph with labels on the left, vertical slider, vertical brightness bar,
  stacked cover and alarm buttons, and media with the artwork on top.
- Alarm tiles show their mode buttons again (icons only when narrow). Cover tiles show open, stop and close again.
- Media tiles leave out the artwork when the tile is too small for it.
- Built-in layouts use their own demo entities instead of yours.
- Landscape tiles stack icon and text; tiles under 120 px high keep them side by side.
- The Light / Dark / Now switch sits next to the live banner. "Screens" is now "Active screens". The Skin section in the
  properties is gone.
- File drag in file management uses pointer events, so it works inside Home Assistant.
- Fixes: the popup slider fill is visible on older Fully browsers; weather, sensor, gauge, history, camera and image tiles
  no longer take the "on" colours; slider tiles have their thumb block again; brightness bars are thin again.

### Breaking
- This release needs the HA App endpoints `api/fully_devices`, `api/fully_show` and `api/screen_rename`, and `sun` in the
  allowed domains (see API-REQUEST-fully.md).

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
## 0.8.9: viewer 20, designer 1.3 (contract 9.0)

Changes since 0.8.8: placeholder and page sensors.

- The placeholder page is `/dash/placeholder.html`. Its logo is clickable: one click turns the logo 180 degrees and
  shows "You can now publish your first DASH", the next click restores the first text. The change is immediate.
- A page sensor (`sensor.dash_<page>`) gets the token of a screen that shows that layout, as `#token=`. Without such a
  screen, or while the layout is unpublished, the state is the placeholder URL.
- Page sensors have readable friendly names, such as `thuis / woonkamer`.
- Publishing in the editor still works when Home Assistant is unreachable. A failed sensor update does not fail the save.
- App version raised to 0.8.9.


## 0.8.8: viewer 20, designer 1.3 (contract 9.0)

Pages and screens are in Home Assistant. The App writes them as text sensors.

- Each published page has a sensor `sensor.dash_<page>`. Its state is the page URL with the token of a screen that shows that layout (`#token=`). Without such a screen, or while the layout is unpublished, the state is the placeholder URL. Its friendly name is the page path with spaces, for example `thuis / woonkamer`.
- Each screen has a sensor `sensor.dash_screen_<name>`. Its state is the complete viewer URL of the screen, with the
  screen token after `#`. An automation can give this URL to a display as its start URL.
- Screen sensors contain the token. Home Assistant stores their history in its recorder. Exclude them there if that
  is not wanted.
- A screen whose layout is not published gets a placeholder (logo and "Add a DASH of magic") as its sensor state, at `/dash/placeholder.html`. It switches to the viewer URL when the layout is published.
- Sensors are written at startup and when a page or screen is saved, rotated or deleted. A deleted page or screen
  gets the state `removed` until Home Assistant restarts.
- Service calls are POST only, on the screen server and in the editor API. A GET is refused.
- Scenes, scripts, buttons and input buttons are excluded by default. To use them, remove them from `exclude_domains`.
- If `allow_domains` is filled in, only those domains are active. An empty list uses the defaults. Single entities can
  still be added with `allow_entities`.
- A layout change closes the open live connections of the screens that show it.
- The picture cache has a byte limit (32 MiB) and removes the least recently used pictures first.
- Background tasks are tracked and their errors are logged. Startup and shutdown clean up their resources.
- Internal errors return a generic message with a reference; the details are only in the log.
- The screen token file (`screens.json`) is written with owner-only permissions.
- App version raised to 0.8.8.

## 0.8.7: viewer 20, designer 1.3 (contract 9.0)

Security and reliability review. No change for the designer or the viewer; the contract is unchanged. The screens
now accept only POST for service calls, so any client that sent a GET to `service` must use POST.

- Service calls are POST only, on the screen server and in the editor API. A GET is refused.
- Scenes, scripts, buttons and input buttons are excluded by default. To use them, remove them from `exclude_domains`.
- If `allow_domains` is filled in, only those domains are active. An empty list uses the defaults. Single entities can still be added with `allow_entities`.
- A layout change closes the open live connections of the screens that show it. Their tokens get the new layout.
- Live updates: a failed connection is cleaned up and no longer leaves a connection behind.
- Picture cache has a byte limit (32 MiB) and removes the least recently used pictures first.
- Background tasks are tracked and their errors are logged. Startup and shutdown clean up their resources.
- Fallback state reads for the editor run with a limit on concurrency and a deadline.
- Internal errors return a generic message with a reference; the details are only in the log.
- Screen token file (`screens.json`) is written with owner-only permissions.
- Documentation: screen tokens replace the read token everywhere; backup and storage guidance is added.
- Each published page is a Home Assistant text sensor (`sensor.dash_<page>`). Its state is the page URL. Sensors are written at startup and when a page is saved or deleted.
- App version raised to 0.8.7.

## 0.8.6: viewer 20, designer 1.3 (contract 9.0)

Documentation and naming: the term "App" is used everywhere in the documentation, in code comments and
messages. The viewer and editor are unchanged from 0.8.5.

- Documentation: the former term is replaced by "App" and "Apps", and the store is called "App store".
- Log message and error text use "App".
- App version raised to 0.8.6.

## 0.8.5: viewer 20, designer 1.3 (contract 9.0)

App 0.8.5 ships viewer 20 (`app/ui/viewer.html`, previously viewer 19) and the designer's
editor 1.3 (`app/ui/index.html`, previously 1.2). The contract stays at 9.0.

- Viewer: alarm panels get a popup with arm home, arm away and disarm buttons. The popup works only
  when alarm panels are allowed in the HA App options and the alarm services are allowed.
- Viewer: an alarm code, when the panel requires one, cannot be sent yet. The server does not pass it on.
- Editor: shows a note when the layout is not published, and a note when other screens use the same layout.
- Editor: updated to the designer's 1.3 package. The favicon is not part of the package and is kept.
- App version raised to 0.8.5.

## 0.8.4: viewer 19, designer 1.2 (contract 9.0)

App 0.8.4 ships viewer 19 (`app/ui/viewer.html`, previously viewer 18) and the designer's
editor 1.2 (`app/ui/index.html`, previously 1.1). The contract stays at 9.0.

- Viewer: climate tiles open a popup.
- Viewer: weather tiles have a new layout: name and secondary information on top, icon and
  temperature side by side, forecast below.
- Viewer: climate tile layout adjusted (temperature controls in a column beside the value).
- Editor: updated to the designer's 1.2 package. The favicon is not part of the package and is kept.
- App version raised to 0.8.4.

## 0.8.3: viewer 18 (contract 9.0)

App 0.8.3 ships viewer 18 (`app/ui/viewer.html`, previously viewer 17) and the designer's latest
editor (`app/ui/index.html`, designer 1.1). The contract stays at 9.0.

- Viewer: popups also for weather and picture tiles (`haimage`), not only for lights, switches and covers.
- Viewer: a tile can opt out of its popup with the `popup` property set to `false`.
- Viewer: a short press animation on tiles with a tap action.
- Viewer: tile construction refactored into one function (`mkTile`).
- Editor: updated to the designer's latest package. The favicon is not part of the package and is kept.

## 0.8.2: viewer 17 (contract 9.0)

App 0.8.2 ships viewer 17 (`app/ui/viewer.html`, previously viewer 16). The contract stays at 9.0.

- Popups for lights, switches and covers: the icon, text and toggle colours now follow the
  tile's own colours (`currentColor` resolves to the tile's text colour in the popup).
- Colour mixing (tints, popup backgrounds) is computed in the viewer as `rgba()` values instead of
  CSS `color-mix()`, so older browser engines, such as the WebView in Fully Kiosk, render them.
- Popup overlay positioned with `top/right/bottom/left` instead of `inset`, for the same reason.
- Pressed tiles show a short grey overlay; the tap highlight of the browser is turned off.
- A passive `touchstart` listener on the document, for quicker touch response.
- The debug line (`?debug=1`) reports `viewer 17`.

Files: `app/ui/viewer.html`.
