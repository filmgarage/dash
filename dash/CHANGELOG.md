# Changelog

## Viewer 17 (contract 9.0)

Changed `app/ui/viewer.html` from viewer 16 to viewer 17. The contract stays at 9.0.

- Popups for lights, switches and covers: the icon, text and toggle colours now follow the
  tile's own colours (`currentColor` resolves to the tile's text colour in the popup).
- Colour mixing (tints, popup backgrounds) is computed in the viewer as `rgba()` values instead of
  CSS `color-mix()`, so older browser engines, such as the WebView in Fully Kiosk, render them.
- Popup overlay positioned with `top/right/bottom/left` instead of `inset`, for the same reason.
- Pressed tiles show a short grey overlay; the tap highlight of the browser is turned off.
- A passive `touchstart` listener on the document, for quicker touch response.
- The debug line (`?debug=1`) reports `viewer 17`.

Files: `app/ui/viewer.html`.
