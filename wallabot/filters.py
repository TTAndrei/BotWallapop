"""Motor de filtrado: decide qué anuncios son interesantes y por qué se descartan los demás.

Todo el texto (anuncios y reglas) se normaliza igual antes de comparar:
minúsculas, sin tildes, sin signos de puntuación, letras y números separados
("rtx3060ti" -> "rtx 3060 ti") y las capacidades unificadas
("12 GB", "12GB", "12G", "12 gigas" -> "12gb").
Así basta con escribir "12gb" una vez en la regla.

Un término se busca como palabra/frase completa: "ti" encuentra "3060 Ti"
pero no "tienda". Si empieza por "re:" se trata como expresión regular sobre
el texto ya normalizado.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .models import Item

_UNIT = re.compile(r"\b(\d+) (?:gb|g|gigas?|gigabytes?)\b")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", text)
    text = _UNIT.sub(r"\1gb", text)
    return f" {' '.join(text.split())} "


class Term:
    def __init__(self, source: str):
        self.source = source
        if source.startswith("re:"):
            self._regex = re.compile(source[3:])
            self._phrase = None
        else:
            self._regex = None
            self._phrase = normalize(source)
            if self._phrase.strip() == "":
                raise ValueError(f"Término vacío: {source!r}")

    def found_in(self, normalized_text: str) -> bool:
        if self._regex is not None:
            return bool(self._regex.search(normalized_text))
        return self._phrase in normalized_text

    def __repr__(self) -> str:
        return self.source


@dataclass
class Rules:
    # Cada grupo es una lista de alternativas: tiene que aparecer al menos una
    # de cada grupo. Ej: [["3060"], ["12gb"]] -> debe contener 3060 Y 12gb.
    # require mira solo el título; require_any, título + descripción.
    require: list[list[str]] = field(default_factory=list)
    require_any: list[list[str]] = field(default_factory=list)
    # Si aparece cualquiera de estos en el TÍTULO, se descarta.
    exclude_title: list[str] = field(default_factory=list)
    # Si aparece cualquiera de estos en el título O la descripción, se descarta.
    exclude_any: list[str] = field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    include_reserved: bool = False
    shipping_only: bool = False
    max_age_days: float | None = None


class ItemFilter:
    def __init__(self, rules: Rules):
        self.rules = rules
        self._require = [[Term(t) for t in group] for group in rules.require]
        self._require_any = [[Term(t) for t in group] for group in rules.require_any]
        self._exclude_title = [Term(t) for t in rules.exclude_title]
        self._exclude_any = [Term(t) for t in rules.exclude_any]

    def rejection_reason(self, item: Item, now: datetime | None = None) -> str | None:
        """None si el anuncio pasa el filtro; si no, el motivo del descarte."""
        r = self.rules
        if item.price is not None:
            if r.min_price is not None and item.price < r.min_price:
                return f"precio bajo (< {r.min_price:g} €)"
            if r.max_price is not None and item.price > r.max_price:
                return f"precio alto (> {r.max_price:g} €)"
        if item.reserved and not r.include_reserved:
            return "reservado"
        if r.shipping_only and not item.shipping:
            return "sin envío"
        if r.max_age_days is not None and item.created_at is not None:
            now = now or datetime.now(timezone.utc)
            if now - item.created_at > timedelta(days=r.max_age_days):
                return f"antiguo (> {r.max_age_days:g} días)"

        title = normalize(item.title)
        everything = normalize(f"{item.title} {item.description}")

        for term in self._exclude_title:
            if term.found_in(title):
                return f"título contiene «{term}»"
        for term in self._exclude_any:
            if term.found_in(everything):
                return f"contiene «{term}»"

        for groups, haystack, where in ((self._require, title, " en el título"), (self._require_any, everything, "")):
            for group in groups:
                if not any(term.found_in(haystack) for term in group):
                    return f"falta «{' / '.join(map(str, group))}»{where}"
        return None

    def accepts(self, item: Item) -> bool:
        return self.rejection_reason(item) is None
