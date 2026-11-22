# Changelog

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
