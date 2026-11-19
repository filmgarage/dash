"""Screen tokens (contract 9.0): one token per screen, bound to one published layout.

Every token starts with TOKEN_PREFIX. There is no master token: a request without a screen token is refused.
"""
import json
import os
import re
import secrets
from pathlib import Path

TOKEN_PREFIX = "autotoken_"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}$")


def new_token():
    return TOKEN_PREFIX + secrets.token_urlsafe(24)


class ScreenStore:
    def __init__(self, path):
        self.path = Path(path)
        self.screens = self._load()

    def _load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        items = raw.get("screens") if isinstance(raw, dict) else None
        return [s for s in (items or []) if isinstance(s, dict) and isinstance(s.get("name"), str)
                and isinstance(s.get("layout"), str) and isinstance(s.get("token"), str)]

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        # Tokens are secrets: the file is readable by its owner only (P11).
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"screens": self.screens}, indent=2))
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def list(self):
        return [dict(s) for s in self.screens]

    def get(self, name):
        for s in self.screens:
            if s["name"] == name:
                return dict(s)
        return None

    def find_by_token(self, given):
        """The screen that owns the token, or None. Compares every token in constant time."""
        found = None
        for s in self.screens:
            if secrets.compare_digest(given.encode(), s["token"].encode()):
                found = s
        return dict(found) if found else None

    def save_screen(self, name, layout):
        if not NAME_RE.match(name or ""):
            raise ValueError("screen name: letters, digits, space, dot, dash or underscore, up to 40 characters")
        for s in self.screens:
            if s["name"] == name:
                s["layout"] = layout
                self._save()
                return dict(s)
        screen = {"name": name, "layout": layout, "token": new_token()}
        self.screens.append(screen)
        self._save()
        return dict(screen)

    def rotate(self, name):
        for s in self.screens:
            if s["name"] == name:
                s["token"] = new_token()
                self._save()
                return dict(s)
        return None

    def delete(self, name):
        before = len(self.screens)
        self.screens = [s for s in self.screens if s["name"] != name]
        if len(self.screens) != before:
            self._save()
            return True
        return False
