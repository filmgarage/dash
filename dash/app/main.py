"""DASH add-on: the editor (Home Assistant Ingress, port 8099) and the screen API (port 8092)."""
import asyncio
import signal
import logging
import os

from aiohttp import ClientSession, web

import editor_api
import screen_api
from active import ActiveSet
from ha import Supervisor
from ha_bridge import HaBridge
from forecasts import Forecasts
from hub import Hub
from settings import (ACTIVE_PATH, APP_VERSION, DATA_DIR, HA_WS_URL, LAYOUT_DIR, PUBLISH_DIR, SETTINGS_PATH,
                      PUBLISH_URL, PUBLISHED_DIR, S6_ENV_DIR, SCREEN_PORT, SUPERVISOR_TOKEN,
                      SUPERVISOR_URL, UI_PORT, load_options, log_level)
from network import detect_lan_ip, load_saved
from store import Store
from web_common import build_app, ingress_only, is_allowed

log = logging.getLogger("dash")


def log_environment():
    log.info("DASH add-on version %s", APP_VERSION)
    log.info("Supervisor environment variables present: %s",
             sorted(k for k in os.environ if "SUPERVISOR" in k or k.startswith("HASS")) or "none")
    log.debug("All environment variable names: %s", sorted(os.environ))
    try:
        log.debug("s6 container environment names: %s", sorted(os.listdir(S6_ENV_DIR)))
    except OSError:
        log.debug("s6 container environment store not found")
    log.info("SUPERVISOR_TOKEN available: %s", bool(SUPERVISOR_TOKEN))
    if not SUPERVISOR_TOKEN:
        log.error("SUPERVISOR_TOKEN is missing; check that homeassistant_api: true is in config.yaml "
                  "and rebuild the add-on")


async def main():
    options = load_options()
    logging.basicConfig(level=log_level(options["log_level"]),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_environment()

    store = Store(LAYOUT_DIR, PUBLISH_DIR, PUBLISH_URL, PUBLISHED_DIR)
    active = ActiveSet(ACTIVE_PATH, allowed=lambda entity_id: is_allowed(options, entity_id))
    for page in list(active.pages):
        parts = page.split("/")
        if store.is_published(parts):
            active.set_page(page, store.published_entities(parts))  # applies the current options
        else:
            active.remove_page(page)

    session = ClientSession()
    detected_ip = await detect_lan_ip(session, SUPERVISOR_URL, SUPERVISOR_TOKEN)
    ha = Supervisor(SUPERVISOR_URL, SUPERVISOR_TOKEN, session)
    bridge = HaBridge(HA_WS_URL, SUPERVISOR_TOKEN, active)
    hub = Hub(active, bridge)
    forecasts = Forecasts(ha, bridge.states, active, hub.broadcast)

    async def on_bridge_state(entity_id, view):
        await hub.broadcast(entity_id, view)
        forecasts.schedule(entity_id)

    bridge.on_state = on_bridge_state
    background = [asyncio.ensure_future(forecasts.run())]

    def on_active_changed(added, removed):
        bridge.active_changed()
        if removed:
            background.append(asyncio.ensure_future(hub.announce_removed(removed)))

    active.listeners.append(on_active_changed)

    state = {"options": options, "store": store, "active": active, "bridge": bridge,
             "hub": hub, "ha": ha, "images": {}, "detected_ip": detected_ip,
             "settings_path": SETTINGS_PATH, "saved": load_saved(SETTINGS_PATH)}
    editor = build_app(editor_api.add_routes, state, [ingress_only])
    screens = build_app(screen_api.add_routes, state)
    runners = []
    for app, port in ((editor, UI_PORT), (screens, SCREEN_PORT)):
        runner = web.AppRunner(app)
        runners.append(runner)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("DASH started: editor on %d, screens on %d", UI_PORT, SCREEN_PORT)

    try:
        if SUPERVISOR_TOKEN:
            await bridge.run()
        else:
            await asyncio.Event().wait()
    finally:
        # Shutdown: stop the background work, then the web servers, then the HTTP session.
        for task in background:
            task.cancel()
        await asyncio.gather(*background, return_exceptions=True)
        for runner in runners:
            await runner.cleanup()
        await session.close()


async def run_until_stopped():
    """Runs main until Ctrl-C or a stop signal from the Supervisor, then lets main shut down cleanly."""
    task = asyncio.ensure_future(main())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, task.cancel)
    try:
        await task
    except asyncio.CancelledError:
        log.info("DASH stopped")


if __name__ == "__main__":
    asyncio.run(run_until_stopped())
