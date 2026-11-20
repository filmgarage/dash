# DASH changelog history

Older release notes. The App's own changelog (dash/CHANGELOG.md) holds only the latest release.

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
