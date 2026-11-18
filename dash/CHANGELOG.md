# Changelog

## 0.8.3: viewer 18 (contract 9.0)

Add-on 0.8.3 ships viewer 18 (`app/ui/viewer.html`, previously viewer 17) and the designer's latest
editor (`app/ui/index.html`, designer 1.1). The contract stays at 9.0.

- Viewer: popups also for weather and picture tiles (`haimage`), not only for lights, switches and covers.
- Viewer: a tile can opt out of its popup with the `popup` property set to `false`.
- Viewer: a short press animation on tiles with a tap action.
- Viewer: tile construction refactored into one function (`mkTile`).
- Editor: updated to the designer's latest package. The favicon is not part of the package and is kept.

## 0.8.2: viewer 17 (contract 9.0)

Add-on 0.8.2 ships viewer 17 (`app/ui/viewer.html`, previously viewer 16). The contract stays at 9.0.

- Popups for lights, switches and covers: the icon, text and toggle colours now follow the
  tile's own colours (`currentColor` resolves to the tile's text colour in the popup).
- Colour mixing (tints, popup backgrounds) is computed in the viewer as `rgba()` values instead of
  CSS `color-mix()`, so older browser engines, such as the WebView in Fully Kiosk, render them.
- Popup overlay positioned with `top/right/bottom/left` instead of `inset`, for the same reason.
- Pressed tiles show a short grey overlay; the tap highlight of the browser is turned off.
- A passive `touchstart` listener on the document, for quicker touch response.
- The debug line (`?debug=1`) reports `viewer 17`.

Files: `app/ui/viewer.html`.
