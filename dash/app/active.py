"""The entities the add-on monitors: the entities used by layouts that have a published page."""
import json
import logging
from pathlib import Path

log = logging.getLogger("dash.active")


class ActiveSet:
    def __init__(self, path):
        self.path = Path(path)
        self.pages = {}
        self.listeners = []  # callables(added, removed), called when the monitored set changes
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))["pages"]
                self.pages = {page: sorted(ents) for page, ents in raw.items()}
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                log.error("Could not read %s; starting with an empty set", self.path)

    @property
    def entities(self):
        return {e for ents in self.pages.values() for e in ents}

    def reasons(self):
        """Entity id mapped to the layouts that use it."""
        out = {}
        for page, ents in self.pages.items():
            for entity_id in ents:
                out.setdefault(entity_id, []).append(page)
        return {entity_id: sorted(pages) for entity_id, pages in out.items()}

    def set_page(self, page, entities):
        before = self.entities
        self.pages[page] = sorted(set(entities))
        return self._commit(before)

    def remove_page(self, page):
        before = self.entities
        self.pages.pop(page, None)
        return self._commit(before)

    def _commit(self, before):
        self._save()
        after = self.entities
        added, removed = sorted(after - before), sorted(before - after)
        if added or removed:
            for listener in self.listeners:
                listener(added, removed)
        return added, removed

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"pages": self.pages}, indent=2), encoding="utf-8")
        tmp.replace(self.path)
