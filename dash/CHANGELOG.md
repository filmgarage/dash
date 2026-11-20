# Changelog

## 0.8.8: viewer 20, designer 1.3 (contract 9.0)

Pages and screens are in Home Assistant. The App writes them as text sensors.

- Each published page has a sensor `sensor.dash_<page>`. Its state is the page URL (no token).
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
