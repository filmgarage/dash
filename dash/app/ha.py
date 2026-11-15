"""Home Assistant REST calls, made through the Supervisor."""
from aiohttp import ClientTimeout

from errors import ApiError

TIMEOUT = ClientTimeout(total=15)


class Supervisor:
    def __init__(self, base_url, token, session):
        self.base = base_url.rstrip("/") + "/core"
        self.token = token
        self.session = session

    def require_token(self):
        if not self.token:
            raise ApiError("no Supervisor token: homeassistant_api is not active; rebuild the add-on", 503)

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    async def states(self):
        async with self.session.get(f"{self.base}/api/states", headers=self._headers(),
                                    timeout=TIMEOUT) as r:
            if r.status != 200:
                raise ApiError(f"Home Assistant answered {r.status}", 502)
            return await r.json()

    async def state(self, entity_id):
        async with self.session.get(f"{self.base}/api/states/{entity_id}", headers=self._headers(),
                                    timeout=TIMEOUT) as r:
            if r.status == 404:
                return None
            if r.status != 200:
                raise ApiError(f"Home Assistant answered {r.status}", 502)
            return await r.json()

    async def call_service(self, entity_id, service, data):
        domain = entity_id.split(".", 1)[0]
        payload = {**data, "entity_id": entity_id}
        async with self.session.post(f"{self.base}/api/services/{domain}/{service}", json=payload,
                                     headers=self._headers(), timeout=TIMEOUT) as r:
            if r.status >= 300:
                raise ApiError(f"Home Assistant answered {r.status}", 502)

    async def forecast(self, entity_id, kind):
        """Calls weather.get_forecasts and returns the list for the entity (kind: daily or hourly)."""
        url = f"{self.base}/api/services/weather/get_forecasts?return_response"
        async with self.session.post(url, json={"entity_id": entity_id, "type": kind},
                                     headers=self._headers(), timeout=TIMEOUT) as r:
            if r.status >= 300:
                raise ApiError(f"Home Assistant answered {r.status}", 502)
            data = await r.json()
        answer = (data.get("service_response") or {}).get(entity_id) or {}
        return answer.get("forecast") or []

    async def picture(self, entity_picture):
        url = entity_picture if entity_picture.startswith("http") else self.base + entity_picture
        async with self.session.get(url, headers=self._headers(), timeout=TIMEOUT) as r:
            if r.status != 200:
                raise ApiError(f"Home Assistant answered {r.status}", 502)
            content_type = r.headers.get("Content-Type", "image/png").split(";")[0].strip()
            return await r.read(), content_type
