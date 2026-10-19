"""Recuerda qué anuncios ya se han visto, para que el modo vigilar solo avise de los nuevos."""

from __future__ import annotations

import json
from pathlib import Path

MAX_IDS_PER_SEARCH = 5000


class SeenStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        try:
            self._data: dict[str, list[str]] = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def is_new_search(self, search: str) -> bool:
        return search not in self._data

    def filter_new(self, search: str, ids: list[str]) -> list[str]:
        known = set(self._data.get(search, []))
        return [i for i in ids if i not in known]

    def add(self, search: str, ids: list[str]) -> None:
        current = self._data.setdefault(search, [])
        known = set(current)
        current.extend(i for i in ids if i not in known)
        del current[:-MAX_IDS_PER_SEARCH]

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data))
        tmp.replace(self.path)
