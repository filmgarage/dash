# Changelog

## 0.8.7: viewer 20, designer 1.3 (contract 9.0)

Security and reliability review. No change for the designer or the viewer; the contract is unchanged. The screens
now accept only POST for service calls, so any client that sent a GET to `service` must use POST.

- Service calls are POST only, on the screen server and in the editor API. A GET is refused.
- Scenes, scripts, buttons and input buttons are excluded by default. To use them, remove them from `exclude_domains`.
- If `allow_domains` is filled in, only those domains are active. An empty list uses the defaults. Single entities can still be added with `allow_entities`.
- A layout change closes the open live connections of the screens that show it. Their tokens get the new layout.
- Live updates: a failed connection is cleaned up and no longer leaves a connection behind.
- Picture cache has a byte limit (32 MiB) and removes the least recently used pictures first.
- Background tasks are tracked and their errors are logged. Startup and shutdown clean up their resources.
- Fallback state reads for the editor run with a limit on concurrency and a deadline.
- Internal errors return a generic message with a reference; the details are only in the log.
- Screen token file (`screens.json`) is written with owner-only permissions.
- Documentation: screen tokens replace the read token everywhere; backup and storage guidance is added.
- App version raised to 0.8.7.
