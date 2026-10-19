"""Cliente mínimo de la API de búsqueda de Wallapop (la misma que usa la web)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterator

from .models import Item

SEARCH_URL = "https://api.wallapop.com/api/v3/search"
ITEM_URL = "https://es.wallapop.com/item/{slug}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
    "Origin": "https://es.wallapop.com",
    "Referer": "https://es.wallapop.com/",
    "X-DeviceOS": "0",
}

ORDER_BY = ("newest", "price_low_to_high", "price_high_to_low", "closest", "most_relevance")


class WallapopError(RuntimeError):
    pass


class WallapopClient:
    def __init__(self, timeout: float = 15, delay: float = 1.0, retries: int = 3):
        self.timeout = timeout
        self.delay = delay
        self.retries = retries

    def search(
        self,
        keywords: str,
        latitude: float,
        longitude: float,
        *,
        distance_km: float | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        category_id: int | None = None,
        order_by: str = "newest",
        max_pages: int = 15,
    ) -> Iterator[Item]:
        """Devuelve los anuncios página a página (sin duplicados)."""
        params: dict[str, Any] = {
            "keywords": keywords,
            "latitude": latitude,
            "longitude": longitude,
            "source": "search_box",
            "order_by": order_by,
        }
        if distance_km:
            params["distance"] = int(distance_km * 1000)
        if min_price is not None:
            params["min_sale_price"] = min_price
        if max_price is not None:
            params["max_sale_price"] = max_price
        if category_id:
            params["category_id"] = category_id

        seen: set[str] = set()
        query = params
        for page in range(max_pages):
            data, next_header = self._get(query)
            raw_items = extract_items(data)
            for raw in raw_items:
                item = parse_item(raw)
                if item.id and item.id not in seen:
                    seen.add(item.id)
                    yield item
            # Con filtro de precio Wallapop filtra cada página por separado, así que
            # una página puede venir casi vacía y aun así haber más detrás.
            next_page = (data.get("meta") or {}).get("next_page") or next_header
            if not next_page:
                break
            query = {"next_page": next_page, "source": "search_box"}
            time.sleep(self.delay)

    def _get(self, params: dict[str, Any]) -> tuple[dict, str | None]:
        url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers=HEADERS)
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    return body, response.headers.get("X-NextPage")
            except urllib.error.HTTPError as exc:
                last_error = exc
                # 429 = demasiadas peticiones; 5xx = fallo temporal. Esperamos y reintentamos.
                if exc.code != 429 and exc.code < 500:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
            time.sleep(2 ** (attempt + 1))
        raise WallapopError(f"No se pudo consultar Wallapop: {last_error}")


def extract_items(data: dict) -> list[dict]:
    """La API ha cambiado de formato varias veces; aceptamos los conocidos."""
    payload = ((data.get("data") or {}).get("section") or {}).get("payload") or {}
    for candidate in (payload.get("items"), data.get("search_objects"), data.get("items")):
        if isinstance(candidate, list):
            return candidate
    return []


def parse_item(raw: dict) -> Item:
    price = raw.get("price", raw.get("sale_price"))
    currency = raw.get("currency", "EUR")
    if isinstance(price, dict):
        currency = price.get("currency", currency)
        price = price.get("amount")

    reserved = raw.get("reserved")
    if isinstance(reserved, dict):
        reserved = reserved.get("flag")
    if reserved is None:
        reserved = (raw.get("flags") or {}).get("reserved")

    shipping = raw.get("shipping")
    if isinstance(shipping, dict):
        shipping = shipping.get("user_allows_shipping") or shipping.get("item_is_shippable")
    if shipping is None:
        shipping = raw.get("shipping_allowed")

    image = ""
    images = raw.get("images") or []
    if images and isinstance(images[0], dict):
        first = images[0]
        urls = first.get("urls") or first
        image = urls.get("medium") or urls.get("small") or urls.get("big") or urls.get("original") or ""

    slug = raw.get("web_slug") or raw.get("id", "")
    location = raw.get("location") or {}
    created = raw.get("created_at") or raw.get("modified_at")

    return Item(
        id=str(raw.get("id", "")),
        title=raw.get("title") or "",
        description=raw.get("description") or "",
        price=float(price) if price is not None else None,
        currency=currency or "EUR",
        url=ITEM_URL.format(slug=slug),
        city=location.get("city") or "",
        reserved=bool(reserved),
        shipping=bool(shipping),
        image=image,
        created_at=_parse_timestamp(created),
        raw=raw,
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        # Wallapop usa milisegundos.
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
