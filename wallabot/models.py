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
    province: str = ""
    postal_code: str = ""
    country: str = "ES"
    reserved: bool = False
    shipping: bool = False
    image: str = ""
    created_at: datetime | None = None
    raw: dict = field(default_factory=dict, repr=False)

    def place(self) -> str:
        """Ciudad (provincia), y el país si no es España."""
        place = self.city
        if self.province and self.province != self.city:
            place += f" ({self.province})"
        if self.country and self.country != "ES":
            place += f", {self.country}"
        return place

    def price_str(self) -> str:
        if self.price is None:
            return "¿?"
        value = f"{self.price:.0f}" if self.price == int(self.price) else f"{self.price:.2f}"
        return f"{value} €" if self.currency == "EUR" else f"{value} {self.currency}"
