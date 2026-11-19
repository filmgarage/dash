"""Layouts (App data folder) and published files (Home Assistant www folder)."""
import base64
import binascii
import json
import os
import re
import threading
import time

from errors import ApiError

SEG_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ENTITY_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
NAME_UNSAFE_RE = re.compile(r"[^a-z0-9_-]")
IMAGE_NAME_RE = re.compile(r"^[a-z0-9_.-]{1,64}$")
SKIN_DEFAULT = "_default"
MAX_DEPTH = 4
MAX_TILES = 200
MAX_ENTITIES = 100  # different entities in one layout; the same limit applies to state requests and subscriptions
MAX_HTML_BYTES = 2_000_000
MAX_SKIN_BYTES = 256_000
MAX_IMAGE_BYTES = 700_000
MAX_IMAGE_NAME = 64
# SVG is refused: an SVG file can contain scripts.
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
IMAGE_EXTS = set(IMAGE_TYPES.values())


def parse_path(raw):
    """'kitchen/morning' becomes ['kitchen', 'morning']. None when the path is invalid."""
    if not raw:
        return None
    parts = raw.split("/")
    if not 1 <= len(parts) <= MAX_DEPTH or not all(SEG_RE.match(p) for p in parts):
        return None
    return parts


def checked(parts):
    """Layouts and pages may not live under 'skins'. Raises for invalid paths."""
    if parts is None or parts[0] == "skins":
        raise ApiError("invalid path", 400)
    return parts


def skin_parts(parts):
    if not parts or len(parts) != 2 or parts[0] != "skins":
        raise ApiError("json is only allowed for skins (path skins/<name>)", 400)
    return parts


def validate_layout(body):
    tiles = body.get("tiles")
    if not isinstance(tiles, list) or len(tiles) > MAX_TILES:
        return f"tiles must be a list (maximum {MAX_TILES})"
    for tile in tiles:
        if not isinstance(tile, dict):
            return "each tile must be an object"
        entity = tile.get("entity")
        if entity and not ENTITY_RE.match(str(entity)):
            return f"invalid entity: {entity}"
        for key in ("x", "y", "w", "h"):
            if not isinstance(tile.get(key, 0), int):
                return f"{key} must be an integer"
    if len({str(tile.get("entity")) for tile in tiles if isinstance(tile, dict) and tile.get("entity")}) > MAX_ENTITIES:
        return f"a layout may use at most {MAX_ENTITIES} different entities"
    return None


def read_json(path):
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)


def write_bytes(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def write_text(path, text):
    write_bytes(path, text.encode("utf8"))


def image_files(folder):
    if not os.path.isdir(folder):
        return []
    return [name for name in sorted(os.listdir(folder))
            if os.path.isfile(os.path.join(folder, name)) and os.path.splitext(name)[1] in IMAGE_EXTS]


def remove_folder_if_empty(folder):
    if os.path.isdir(folder) and not os.listdir(folder):
        os.rmdir(folder)


def remove_images(folder):
    """Deletes the image files of one folder. Sub-folders belong to other layouts and stay."""
    for name in image_files(folder):
        os.remove(os.path.join(folder, name))
    remove_folder_if_empty(folder)


def replace_prefix(value, old, new):
    """Rewrites every image URL that starts with old, anywhere in a layout."""
    if isinstance(value, str):
        return new + value[len(old):] if value.startswith(old) else value
    if isinstance(value, dict):
        return {k: replace_prefix(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_prefix(v, old, new) for v in value]
    return value


def decode_image(data_url):
    if not isinstance(data_url, str) or not data_url.startswith("data:") or ";base64," not in data_url:
        raise ApiError('no image in body (expected {"data_url": "data:image/...;base64,..."})', 400)
    header, payload = data_url[5:].split(";base64,", 1)
    ext = IMAGE_TYPES.get(header.lower())
    if not ext:
        raise ApiError("image type not allowed (png, jpeg, webp or gif)", 415)
    if len(payload) > MAX_IMAGE_BYTES * 4 // 3 + 8:
        raise ApiError("image is too large (maximum 700 KB)", 413)
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise ApiError("invalid base64", 400)
    if not data:
        raise ApiError("image is empty (no data after base64 decoding)", 400)
    if len(data) > MAX_IMAGE_BYTES:
        raise ApiError("image is too large (maximum 700 KB)", 413)
    return ext, data


def clean_image_base(raw):
    """'Photo Garden.JPG' becomes 'photo-garden'. Only a-z, 0-9, '-' and '_' are kept."""
    base = os.path.splitext(raw)[0].lower().replace(".", "-")
    base = re.sub(r"\s+", "-", base)
    base = NAME_UNSAFE_RE.sub("", base)
    base = re.sub(r"-+", "-", base).strip("-_")
    return base[:MAX_IMAGE_NAME - 5] or "image"


def unique_image_name(folder, base, ext):
    name, n = base + ext, 2
    while os.path.exists(os.path.join(folder, name)):
        name = f"{base}-{n}{ext}"
        n += 1
    return name


class Store:
    def __init__(self, layout_dir, publish_dir, publish_url, published_dir):
        self.layout_dir = os.path.realpath(str(layout_dir))
        self.publish_dir = os.path.realpath(str(publish_dir))
        self.published_dir = os.path.realpath(str(published_dir))
        self.publish_url = publish_url.rstrip("/")
        self.lock = threading.Lock()
        os.makedirs(self.layout_dir, exist_ok=True)
        os.makedirs(os.path.join(self.publish_dir, "skins"), exist_ok=True)
        os.makedirs(self.published_dir, exist_ok=True)

    @staticmethod
    def _under(root, parts, suffix=""):
        target = os.path.realpath(os.path.join(root, *parts) + suffix)
        if not target.startswith(root + os.sep):
            raise ApiError("invalid path", 400)
        return target

    def layout_file(self, parts):
        return self._under(self.layout_dir, parts, ".json")

    def page_file(self, parts):
        return self._under(self.publish_dir, parts, ".html")

    def file_path(self, relative):
        """Path of a published file, for the editor preview. Refuses anything outside the publish folder."""
        if not relative or relative.startswith("/") or "\\" in relative or ".." in relative.split("/"):
            raise ApiError("invalid path", 400)
        target = os.path.realpath(os.path.join(self.publish_dir, relative))
        if not target.startswith(self.publish_dir + os.sep) or not os.path.isfile(target):
            raise ApiError("file not found", 404)
        return target

    def publish_folder(self, parts):
        return self._under(self.publish_dir, parts)

    def url(self, parts, ext=""):
        return f"{self.publish_url}/" + "/".join(parts) + ext

    def has_layout(self, parts):
        return bool(parts) and os.path.isfile(self.layout_file(parts))

    def is_published(self, parts):
        return bool(parts) and os.path.isfile(self.page_file(parts))

    def published_file(self, parts):
        return self._under(self.published_dir, parts, ".json")

    def load_published(self, parts):
        """The published version of a layout: a copy taken when the page was published."""
        target = self.published_file(checked(parts))
        if not os.path.isfile(target):
            raise ApiError("layout is not published", 404)
        return read_json(target)

    def published_entities(self, parts):
        """Entity ids used by the published version of a layout. Empty when it is not published."""
        if not parts or not os.path.isfile(self.published_file(parts)):
            return set()
        try:
            tiles = read_json(self.published_file(parts)).get("tiles", [])
        except (OSError, ValueError, AttributeError):
            return set()
        return {t["entity"] for t in tiles if isinstance(t, dict) and t.get("entity")}

    def snapshot_layout(self, parts):
        """Stores a copy of the current layout as its published version. Returns its saved value."""
        with self.lock:
            src = self.layout_file(checked(parts))
            if not os.path.isfile(src):
                raise ApiError("layout not found", 404)
            data = read_json(src)
            target = self.published_file(parts)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            write_text(target, json.dumps(data, indent=2, ensure_ascii=False))
        return data.get("saved")

    # ----- layouts and folders -----

    def _meta(self, path, fallback):
        try:
            data = read_json(path)
            return data.get("title") or fallback, data.get("saved")
        except (OSError, ValueError, AttributeError):
            return fallback, None

    def _tree(self, rel, depth):
        base = os.path.join(self.layout_dir, *rel) if rel else self.layout_dir
        folders, layouts = [], []
        for name in sorted(os.listdir(base)):
            full = os.path.join(base, name)
            if os.path.isdir(full) and SEG_RE.match(name):
                children = self._tree(rel + [name], depth + 1) if depth < MAX_DEPTH else []
                folders.append({"type": "folder", "path": "/".join(rel + [name]), "children": children})
            elif name.endswith(".json") and SEG_RE.match(name[:-5]) and os.path.isfile(full):
                title, saved = self._meta(full, name[:-5])
                layouts.append({"type": "layout", "path": "/".join(rel + [name[:-5]]),
                                "title": title, "saved": saved})
        return folders + layouts

    def tree(self):
        return self._tree([], 1)

    def names(self):
        return sorted(f[:-5] for f in os.listdir(self.layout_dir)
                      if f.endswith(".json") and SEG_RE.match(f[:-5]))

    def load_layout(self, parts):
        target = self.layout_file(checked(parts))
        if not os.path.isfile(target):
            raise ApiError("layout not found", 404)
        return read_json(target)

    def save_layout(self, parts, body, if_saved):
        checked(parts)
        problem = validate_layout(body)
        if problem:
            raise ApiError(problem, 400)
        target = self.layout_file(parts)
        with self.lock:
            if if_saved and os.path.isfile(target) and str(self._meta(target, None)[1]) != if_saved:
                raise ApiError("layout was modified in the meantime", 409)
            if os.path.isdir(target[:-5]):
                raise ApiError("a folder with this name already exists", 409)
            saved = int(time.time() * 1000)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            write_text(target, json.dumps(dict(body, version=1, saved=saved),
                                          indent=2, ensure_ascii=False))
        return saved

    def move_layout(self, src_parts, dst_parts):
        checked(src_parts)
        checked(dst_parts)
        src = self.layout_file(src_parts)
        dst = self.layout_file(dst_parts)
        if not os.path.isfile(src):
            raise ApiError("layout not found", 404)
        if self.is_published(src_parts):
            raise ApiError("layout is published; unpublish it first", 409)
        if os.path.exists(dst) or os.path.isdir(dst[:-5]) or self.is_published(dst_parts):
            raise ApiError("already exists", 409)
        src_folder = self.publish_folder(src_parts)
        dst_folder = self.publish_folder(dst_parts)
        images = image_files(src_folder)
        if any(os.path.exists(os.path.join(dst_folder, name)) for name in images):
            raise ApiError("an image with this name already exists at the destination", 409)
        data = replace_prefix(read_json(src), self.url(src_parts) + "/", self.url(dst_parts) + "/")
        with self.lock:
            if images:
                os.makedirs(dst_folder, exist_ok=True)
                for name in images:
                    os.replace(os.path.join(src_folder, name), os.path.join(dst_folder, name))
                remove_folder_if_empty(src_folder)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            write_text(dst, json.dumps(data, indent=2, ensure_ascii=False))
            os.remove(src)

    def delete_layout(self, parts):
        checked(parts)
        target = self.layout_file(parts)
        with self.lock:
            if not os.path.isfile(target):
                raise ApiError("layout not found", 404)
            if self.is_published(parts):
                raise ApiError("layout is published; unpublish it first", 409)
            os.remove(target)
            remove_images(self.publish_folder(parts))

    def create_folder(self, parts):
        checked(parts)
        folder = self._under(self.layout_dir, parts)
        if os.path.isfile(folder + ".json"):
            raise ApiError("already exists as a layout", 409)
        os.makedirs(folder, exist_ok=True)

    def delete_folder(self, parts):
        checked(parts)
        folder = self._under(self.layout_dir, parts)
        if not os.path.isdir(folder):
            raise ApiError("folder not found", 404)
        if os.listdir(folder):
            raise ApiError("folder is not empty", 409)
        os.rmdir(folder)

    # ----- publishing -----

    def publish_html(self, parts, html):
        checked(parts)
        if len(html.encode("utf8")) > MAX_HTML_BYTES:
            raise ApiError("html is too large", 413)
        target = self.page_file(parts)
        with self.lock:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            write_text(target, html)
        return self.url(parts, ".html")

    def publish_skin(self, parts, body):
        skin_parts(parts)
        if parts[1] == SKIN_DEFAULT:
            pointer = body.get("skin")
            if set(body) != {"skin"} or not isinstance(pointer, str) \
                    or not SEG_RE.match(pointer) or pointer == SKIN_DEFAULT:
                raise ApiError('the default pointer must be {"skin": "<name>"}', 400)
            if not os.path.isfile(self._under(self.publish_dir, ["skins", pointer], ".json")):
                raise ApiError("the default pointer must name an existing skin", 400)
        content = json.dumps(body, indent=2, ensure_ascii=False)
        if len(content.encode("utf8")) > MAX_SKIN_BYTES:
            raise ApiError("skin is too large (maximum 256 KB)", 413)
        target = self._under(self.publish_dir, parts, ".json")
        with self.lock:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            write_text(target, content)
        return self.url(parts, ".json")

    def delete_page(self, parts):
        checked(parts)
        target = self.page_file(parts)
        with self.lock:
            if not os.path.isfile(target):
                raise ApiError("page not found", 404)
            os.remove(target)
            if os.path.isfile(self.published_file(parts)):
                os.remove(self.published_file(parts))

    def delete_skin(self, parts):
        skin_parts(parts)
        target = self._under(self.publish_dir, parts, ".json")
        with self.lock:
            if not os.path.isfile(target):
                raise ApiError("page not found", 404)
            os.remove(target)
            remove_images(self.publish_folder(parts))

    def publish_list(self):
        pages = []
        for root, _dirs, files in os.walk(self.publish_dir):
            for name in files:
                if not name.endswith((".html", ".json")):
                    continue
                kind = "json" if name.endswith(".json") else "html"
                rel = os.path.relpath(os.path.join(root, name), self.publish_dir)
                parts = rel[:-5].split(os.sep)
                if kind == "json" and not (len(parts) == 2 and parts[0] == "skins"):
                    continue
                if kind == "html" and parts[0] == "skins":
                    continue
                pages.append({"path": "/".join(parts), "type": kind, "url": self.url(parts, "." + kind)})
        pages.sort(key=lambda p: (p["type"], p["path"]))
        return pages

    # ----- images -----

    def image_folder(self, owner):
        kind, value = owner
        if kind == "layout":
            parts = checked(value)
        else:
            if not value or not SEG_RE.match(value) or value == SKIN_DEFAULT:
                raise ApiError("invalid skin name", 400)
            parts = ["skins", value]
        return parts, self.publish_folder(parts)

    def upload_image(self, owner, raw_name, data_url):
        parts, folder = self.image_folder(owner)
        ext, data = decode_image(data_url)
        if not raw_name or ".." in raw_name or "/" in raw_name or "\\" in raw_name:
            raise ApiError("invalid name", 400)
        base = clean_image_base(raw_name)
        with self.lock:
            os.makedirs(folder, exist_ok=True)
            name = unique_image_name(folder, base, ext)
            write_bytes(os.path.join(folder, name), data)
        return {"ok": True, "name": name, "url": self.url(parts + [name]), "size": len(data)}

    def list_images(self, owner):
        parts, folder = self.image_folder(owner)
        images = []
        for name in image_files(folder):
            st = os.stat(os.path.join(folder, name))
            images.append({"name": name, "url": self.url(parts + [name]),
                           "size": st.st_size, "modified": int(st.st_mtime * 1000)})
        return {"images": images}

    def delete_image(self, owner, name):
        _parts, folder = self.image_folder(owner)
        if not name or not IMAGE_NAME_RE.match(name) or os.path.splitext(name)[1] not in IMAGE_EXTS:
            raise ApiError("invalid name", 400)
        target = os.path.join(folder, name)
        with self.lock:
            if not os.path.isfile(target):
                raise ApiError("image not found", 404)
            os.remove(target)
