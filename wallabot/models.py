from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Item:
    """Un anuncio de Wallapop, ya normalizado."""

    id: str
    title: str
    description: str = ""
    price: float | None = None
    currency: str = "EUR"
    url: str = ""
    city: str = ""
    reserved: bool = False
    shipping: bool = False
    image: str = ""
    created_at: datetime | None = None
    raw: dict = field(default_factory=dict, repr=False)

    def price_str(self) -> str:
        if self.price is None:
            return "¿?"
        value = f"{self.price:.0f}" if self.price == int(self.price) else f"{self.price:.2f}"
        return f"{value} €" if self.currency == "EUR" else f"{value} {self.currency}"
