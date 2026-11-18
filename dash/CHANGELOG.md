# Changelog

## 0.8.5: viewer 20, designer 1.3 (contract 9.0)

Add-on 0.8.5 ships viewer 20 (`app/ui/viewer.html`, previously viewer 19) and the designer's
editor 1.3 (`app/ui/index.html`, previously 1.2). The contract stays at 9.0.

- Viewer: alarm panels get a popup with arm home, arm away and disarm buttons. The popup works only
  when alarm panels are allowed in the HA App options and the alarm services are allowed.
- Viewer: an alarm code, when the panel requires one, cannot be sent yet. The server does not pass it on.
- Editor: shows a note when the layout is not published, and a note when other screens use the same layout.
- Editor: updated to the designer's 1.3 package. The favicon is not part of the package and is kept.
- Add-on version raised to 0.8.5.
