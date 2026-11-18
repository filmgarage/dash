"""Home Assistant REST calls, made through the Supervisor."""
from aiohttp import ClientTimeout

from errors import ApiError

TIMEOUT = ClientTimeout(total=15)
MAX_PICTURE_BYTES = 5_000_000
PICTURE_PATHS = ("/api/image_proxy/", "/api/camera_proxy/")
PICTURE_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif")  # SVG is refused: it can contain scripts


def picture_path_allowed(path):
    """True for a relative Home Assistant picture path, such as /api/image_proxy/image.qr?token=..."""
    if not isinstance(path, str) or not path.startswith(PICTURE_PATHS):
        return False
    route = path.split("?", 1)[0]
    # No "." or ".." segments and no percent-encoding: a server would normalise them and reach other endpoints.
    segments = route.split("/")
    return ("." not in segments and ".." not in segments and "%" not in route and "\\" not in path
            and "://" not in path and not path.startswith("//"))


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
        """Fetch a picture from Home Assistant. Only its own image and camera proxy paths are allowed:
        the Supervisor token is never sent to any other address, and redirects are not followed."""
        if not picture_path_allowed(entity_picture):
            raise ApiError("picture path not allowed", 403)
        async with self.session.get(self.base + entity_picture, headers=self._headers(),
                                    timeout=TIMEOUT, allow_redirects=False) as r:
            if r.status != 200:
                raise ApiError(f"Home Assistant answered {r.status}", 502)
            content_type = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type not in PICTURE_TYPES:
                raise ApiError("picture type not allowed", 415)
            if r.content_length and r.content_length > MAX_PICTURE_BYTES:
                raise ApiError("picture is too large", 413)
            data = bytearray()
            async for chunk in r.content.iter_chunked(65536):
                data.extend(chunk)
                if len(data) > MAX_PICTURE_BYTES:
                    raise ApiError("picture is too large", 413)
            return bytes(data), content_type
