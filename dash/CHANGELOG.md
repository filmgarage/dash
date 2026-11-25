# DASH changelog

## 0.12.4 (contract 10.0)

Changes since 0.12.3: editor 3.2 and viewer 40 from the designer.

### App
- Editor 3.2 and viewer 40 are installed.
- Skins are stored flat in `skins/`. Skin names cannot contain `/`, and the Skins column has no folders. Layout folders
  are unchanged.
- Italic text uses the italic fonts that the App already serves (`Roboto-Italic-Variable.woff2` and
  `Archivo-Italic-Variable.woff2`), instead of a synthesised slant.
- App version raised to 0.12.4. `docs/CONTRACT.md` is unchanged (contract 10.0).

### Editor 3.2 and viewer 40 (designer changes)
- Example layouts use the `_placeholder` entities again. The renamed demo entities (`light.demo_…`) are no longer shown
  as offline Home Assistant entities.
- Skin examples use a placeholder entity for every tile and never pick a real Home Assistant entity.
- Built-in layouts loaded from the App replace any entity that is not a known placeholder with a placeholder of the same
  domain.
