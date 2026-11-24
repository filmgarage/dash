# DASH changelog

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
