# DASH changelog

## 0.12.3 (contract 10.0)

Changes since 0.12.2: editor 3.0 and viewer 39 from the designer, italic fonts, and the new logo and favicon.

### App
- New App icon (`icon.png`, 512×512) and favicon (`app/ui/assets/favicon.png`, 64×64).
- Italic variable fonts are included in `app/ui/assets/fonts`: `Roboto-Italic-Variable.woff2` and
  `Archivo-Italic-Variable.woff2`, served on the screen port and through Ingress like the other fonts. The OFL texts are
  unchanged.
- The tests cover the italic font files on both ports.
- App version raised to 0.12.3. `docs/CONTRACT.md` is unchanged (contract 10.0).

### Editor 3.0 and viewer 39 (designer changes)
- The fonts load from `assets/fonts/` instead of being embedded, so the editor file is about 1.5 MB smaller.
- The `.ttf` fonts from editor 2.9 are removed.
- File Manager drag shows a label with the file name and the layout or skin icon next to the cursor.
- Example tiles in the preview always look online and can be switched on and off locally.
- Example entities end in `_placeholder`. The built-in layouts `default` and `squares` are migrated when opened; your
  own layouts are left alone.
- File Manager drag works on touch screens inside Home Assistant, for layouts and skins.
- Example scene, script and button tiles respond in the preview even when their domain is not allowed.
