# DASH changelog

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
