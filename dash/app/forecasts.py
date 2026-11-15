"""Weather forecasts (contract 8.4, section 12.2). Home Assistant no longer puts them in the attributes,
so the HA App asks the weather service and adds the result to the attributes it sends to screens."""
import asyncio
import logging

from ha_bridge import public_view

log = logging.getLogger("dash.forecast")
REFRESH_SECONDS = 30 * 60
DEBOUNCE_SECONDS = 2
DAILY_MAX, HOURLY_MAX = 7, 24
FEATURE_DAILY, FEATURE_HOURLY = 1, 2  # Home Assistant WeatherEntityFeature bits


def forecast_entries(raw, limit):
    """Keeps the fields of section 12.2 and drops entries without a datetime."""
    out = []
    for item in (raw or [])[:limit]:
        if not isinstance(item, dict) or not item.get("datetime"):
            continue
        entry = {"datetime": str(item["datetime"]), "condition": item.get("condition"),
                 "temperature": item.get("temperature")}
        for key in ("templow", "precipitation_probability"):
            if item.get(key) is not None:
                entry[key] = item[key]
        out.append(entry)
    return out


def wanted_kinds(attrs):
    """The forecast types an entity supports, as (service type, attribute name, maximum entries)."""
    features = int(attrs.get("supported_features") or 0)
    kinds = []
    if features & FEATURE_DAILY:
        kinds.append(("daily", "forecast_daily", DAILY_MAX))
    if features & FEATURE_HOURLY:
        kinds.append(("hourly", "forecast_hourly", HOURLY_MAX))
    return kinds


class Forecasts:
    def __init__(self, ha, states, active, publish):
        self.ha = ha
        self.states = states      # the bridge's state table
        self.active = active      # the ActiveSet
        self.publish = publish    # async callable(entity_id, view)
        self._tasks = {}

    def schedule(self, entity_id):
        """Called on every state change; refreshes a weather entity once, a few seconds later."""
        if not entity_id.startswith("weather.") or entity_id not in self.active.entities:
            return
        task = self._tasks.get(entity_id)
        if task is None or task.done():
            self._tasks[entity_id] = asyncio.ensure_future(self._later(entity_id))

    async def _later(self, entity_id):
        await asyncio.sleep(DEBOUNCE_SECONDS)
        await self.refresh(entity_id)

    async def refresh(self, entity_id):
        state = self.states.get(entity_id)
        if state is None:
            return False
        changed = False
        for kind, key, limit in wanted_kinds(state.get("a") or {}):
            try:
                raw = await self.ha.forecast(entity_id, kind)
            except Exception as err:  # a failed forecast must not stop the entity
                log.warning("Forecast %s for %s failed: %s", kind, entity_id, err)
                continue
            entries = forecast_entries(raw, limit)
            state = self.states.get(entity_id)
            if state is None:
                return False
            if state["a"].get(key) != entries:
                state["a"][key] = entries
                changed = True
        if changed:
            await self.publish(entity_id, public_view(entity_id, self.states[entity_id]))
        return changed

    async def run(self):
        """Refreshes every active weather entity every 30 minutes."""
        while True:
            await asyncio.sleep(REFRESH_SECONDS)
            for entity_id in sorted(self.active.entities):
                if entity_id.startswith("weather."):
                    await self.refresh(entity_id)
