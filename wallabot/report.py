"""Salida de resultados: consola y página HTML con fotos."""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from html import escape

from .config import Search
from .models import Item

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
    extras = " · ".join(x for x in (item.city, "envío" if item.shipping else "") if x)
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


def write_html(results: list[SearchResult], path: str) -> None:
    sections = []
    for result in results:
        cards = []
        for item in result.accepted:
            deal = ' <span class="deal">🔥 chollo</span>' if result.is_deal(item) else ""
            img = f'<img src="{escape(item.image)}" alt="" loading="lazy">' if item.image else '<div class="noimg"></div>'
            meta = " · ".join(x for x in (item.city, "envío" if item.shipping else "") if x)
            cards.append(
                f'<a class="card" href="{escape(item.url)}" target="_blank" rel="noopener">{img}'
                f'<div class="body"><div class="price">{escape(item.price_str())}{deal}</div>'
                f'<div class="title">{escape(item.title)}</div><div class="meta">{escape(meta)}</div></div></a>'
            )
        sections.append(
            f"<h2>{escape(result.search.name)} <small>{len(result.accepted)} interesantes · "
            f"{len(result.rejected)} descartados</small></h2><div class=\"grid\">{''.join(cards)}</div>"
        )
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resultados Wallapop</title>
<style>
:root {{ --bg:#f6f7f8; --card:#fff; --fg:#1d2327; --muted:#69737b; --accent:#13c1ac; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#15191c; --card:#1f2529; --fg:#e8ecef; --muted:#9aa5ad; }} }}
body {{ margin:0; padding:16px; font-family:system-ui,sans-serif; background:var(--bg); color:var(--fg); }}
h2 small {{ color:var(--muted); font-weight:normal; font-size:.6em; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:12px; }}
.card {{ background:var(--card); border-radius:10px; overflow:hidden; color:inherit; text-decoration:none; }}
.card img, .noimg {{ width:100%; aspect-ratio:1; object-fit:cover; background:var(--muted); display:block; }}
.body {{ padding:8px 10px; }}
.price {{ font-weight:700; color:var(--accent); }}
.deal {{ color:#e8590c; font-size:.85em; }}
.meta {{ color:var(--muted); font-size:.85em; }}
</style></head><body>{''.join(sections)}</body></html>"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
