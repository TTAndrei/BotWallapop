"""Salida de resultados: consola y página HTML para elegir ofertas y contactar."""

from __future__ import annotations

import base64
import json
import statistics
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .api import HEADERS
from .config import Messages, Search
from .models import Item

TEMPLATE = Path(__file__).with_name("seleccion.html")

# Un anuncio se marca como chollo si cuesta al menos un 15 % menos que la mediana.
DEAL_RATIO = 0.85
MIN_ITEMS_FOR_DEALS = 5


@dataclass
class SearchResult:
    search: Search
    accepted: list[Item] = field(default_factory=list)
    rejected: list[tuple[Item, str]] = field(default_factory=list)

    @property
    def median_price(self) -> float | None:
        prices = [i.price for i in self.accepted if i.price is not None]
        return statistics.median(prices) if len(prices) >= MIN_ITEMS_FOR_DEALS else None

    def is_deal(self, item: Item) -> bool:
        median = self.median_price
        return median is not None and item.price is not None and item.price <= median * DEAL_RATIO

    def sort(self, order: str) -> None:
        if order == "precio":
            self.accepted.sort(key=lambda i: (i.price is None, i.price or 0))
        else:
            self.accepted.sort(key=lambda i: i.created_at.timestamp() if i.created_at else 0, reverse=True)


def item_line(item: Item, deal: bool = False) -> str:
    extras = " · ".join(x for x in (item.place(), "envío" if item.shipping else "") if x)
    flag = "🔥 " if deal else ""
    return f"  {item.price_str():>9}  {flag}{item.title}" + (f"  ({extras})" if extras else "") + f"\n             {item.url}"


def print_result(result: SearchResult, show_rejected: bool = False) -> None:
    s = result.search
    total = len(result.accepted) + len(result.rejected)
    print(f"\n═══ {s.name} — «{s.query}» ═══")
    print(f"Revisados {total} · interesantes {len(result.accepted)} · descartados {len(result.rejected)}")
    for reason, count in Counter(r for _, r in result.rejected).most_common():
        print(f"   - {reason}: {count}")
    if result.median_price is not None:
        print(f"Precio mediano de lo interesante: {result.median_price:.0f} €  (🔥 = ≥15 % más barato)")
    print()
    if not result.accepted:
        print("  (nada interesante esta vez)")
    for item in result.accepted:
        print(item_line(item, result.is_deal(item)))
    if show_rejected and result.rejected:
        print("\n  Descartados:")
        for item, reason in result.rejected:
            print(f"  {item.price_str():>9}  {item.title}  ← {reason}")


def write_html(
    results: list[SearchResult],
    path: str,
    messages: Messages,
    *,
    standalone: bool = True,
    embed_images: bool = False,
) -> None:
    """Página para elegir ofertas y contactar: copia el mensaje y abre el anuncio.

    standalone=False omite <!doctype>/<head> (para incrustarla en otra página).
    embed_images=True mete las fotos dentro del HTML para que se vea sin conexión.
    """
    data = {
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "messages": {"local": messages.local, "fuera": messages.fuera},
        "searches": [
            {
                "name": r.search.name,
                "median": r.median_price,
                "rejected": len(r.rejected),
                "items": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "price": item.price_str(),
                        "url": item.url,
                        "image": _image_src(item, embed_images),
                        "place": item.place(),
                        "local": messages.is_local(item),
                        "shipping": item.shipping,
                        "deal": r.is_deal(item),
                    }
                    for item in r.accepted
                ],
            }
            for r in results
        ],
    }
    # "</" escapado para que ningún título pueda cerrar el <script>.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    if standalone:
        page = (
            '<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f"</head><body>\n{page}\n</body></html>"
        )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)


def _image_src(item: Item, embed: bool) -> str:
    if not embed or not item.image:
        return item.image
    url = item.image.replace("pictureSize=W640", "pictureSize=W320")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
        with urllib.request.urlopen(request, timeout=15) as response:
            kind = response.headers.get_content_type() or "image/jpeg"
            return f"data:{kind};base64,{base64.b64encode(response.read()).decode()}"
    except OSError:
        return ""
