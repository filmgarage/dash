# Changelog

## 0.8.9: viewer 20, designer 1.3 (contract 9.0)

Changes since 0.8.8: placeholder and page sensors.

- The placeholder page is `/dash/placeholder.html`. Its logo is clickable: one click turns the logo 180 degrees and
  shows "You can now publish your first DASH", the next click restores the first text. The change is immediate.
- A page sensor (`sensor.dash_<page>`) gets the token of a screen that shows that layout, as `#token=`. Without such a
  screen, or while the layout is unpublished, the state is the placeholder URL.
- Page sensors have readable friendly names, such as `thuis / woonkamer`.
- Publishing in the editor still works when Home Assistant is unreachable. A failed sensor update does not fail the save.
- App version raised to 0.8.9.
