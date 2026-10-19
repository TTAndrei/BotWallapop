"""Carga de búsquedas desde un fichero TOML (ver busquedas.example.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from .api import ORDER_BY
from .filters import Rules
from .models import Item

# Madrid, por si no se indica ubicación.
DEFAULT_LATITUDE = 40.4168
DEFAULT_LONGITUDE = -3.7038


@dataclass
class Search:
    name: str
    query: str
    rules: Rules
    latitude: float = DEFAULT_LATITUDE
    longitude: float = DEFAULT_LONGITUDE
    distance_km: float | None = None
    category_id: int | None = None
    order_by: str = "newest"
    max_pages: int = 15


_RULE_KEYS = {f.name for f in fields(Rules)}
_SEARCH_KEYS = {"name", "query", "latitude", "longitude", "distance_km", "category_id", "order_by", "max_pages"}


def load_searches(path: str | Path) -> list[Search]:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)

    defaults = data.get("defaults", {})
    entries = data.get("search", [])
    if not entries:
        raise ValueError(f"{path}: no hay ninguna sección [[search]]")
    return [_build_search({**defaults, **entry}) for entry in entries]


def _build_search(entry: dict) -> Search:
    unknown = set(entry) - _RULE_KEYS - _SEARCH_KEYS
    if unknown:
        raise ValueError(f"Claves desconocidas en la búsqueda {entry.get('name', '?')!r}: {sorted(unknown)}")
    if "query" not in entry:
        raise ValueError("Cada [[search]] necesita 'query'")

    rule_args = {k: v for k, v in entry.items() if k in _RULE_KEYS}
    # Permite escribir require = ["3060", ["12gb", "12 gb"]]: un string suelto es un grupo de uno.
    for key in ("require", "require_any"):
        rule_args[key] = [[g] if isinstance(g, str) else list(g) for g in rule_args.get(key, [])]

    search_args = {k: v for k, v in entry.items() if k in _SEARCH_KEYS}
    search_args.setdefault("name", entry["query"])
    if search_args.get("order_by", "newest") not in ORDER_BY:
        raise ValueError(f"order_by debe ser uno de {ORDER_BY}")
    return Search(rules=Rules(**rule_args), **search_args)


# Prefijos de código postal de Cataluña (Barcelona, Girona, Lleida, Tarragona).
CATALONIA_POSTAL_PREFIXES = ["08", "17", "25", "43"]


@dataclass
class Messages:
    """Mensaje para el vendedor. {titulo} y {precio} se sustituyen por los del anuncio."""

    # Anuncios en tu zona: se puede quedar en mano.
    local: str = "Hola, me interesa la gráfica. Sigue disponible? Gracias"
    # Anuncios fuera de tu zona: se pregunta por el envío.
    fuera: str = (
        "Hola, me interesa la gráfica. Sigue disponible? "
        "Estoy en Cataluña, podrías enviarla por Wallapop? Gracias"
    )
    zona_local: list[str] = field(default_factory=lambda: list(CATALONIA_POSTAL_PREFIXES))

    def is_local(self, item: Item) -> bool:
        return item.country == "ES" and item.postal_code[:2] in self.zona_local

    def for_item(self, item: Item) -> str:
        template = self.local if self.is_local(item) else self.fuera
        return template.replace("{titulo}", item.title).replace("{precio}", item.price_str())


def load_messages(path: str | Path) -> Messages:
    with open(path, "rb") as fh:
        data = tomllib.load(fh).get("mensaje", {})
    unknown = set(data) - {f.name for f in fields(Messages)}
    if unknown:
        raise ValueError(f"Claves desconocidas en [mensaje]: {sorted(unknown)}")
    return Messages(**data)
