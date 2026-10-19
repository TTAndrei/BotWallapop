from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import datetime

from .api import WallapopClient, WallapopError
from .config import Search, load_searches
from .filters import ItemFilter
from .notify import TelegramNotifier
from .report import SearchResult, item_line, print_result, write_html
from .storage import SeenStore


def run_search(client: WallapopClient, search: Search) -> SearchResult:
    rules = search.rules
    item_filter = ItemFilter(rules)
    result = SearchResult(search)
    items = client.search(
        search.query,
        search.latitude,
        search.longitude,
        distance_km=search.distance_km,
        # Los límites de precio también se mandan a Wallapop: así las cajas de 10 €
        # ni siquiera llegan y las páginas se aprovechan para anuncios de verdad.
        min_price=rules.min_price,
        max_price=rules.max_price,
        category_id=search.category_id,
        order_by=search.order_by,
        max_pages=search.max_pages,
    )
    for item in items:
        reason = item_filter.rejection_reason(item)
        if reason is None:
            result.accepted.append(item)
        else:
            result.rejected.append((item, reason))
    return result


def select(searches: list[Search], names: list[str] | None) -> list[Search]:
    if not names:
        return searches
    wanted = {n.lower() for n in names}
    chosen = [s for s in searches if s.name.lower() in wanted]
    if not chosen:
        sys.exit(f"No hay búsquedas con ese nombre. Disponibles: {', '.join(s.name for s in searches)}")
    return chosen


def cmd_search(args: argparse.Namespace) -> None:
    searches = select(load_searches(args.config), args.nombre)
    client = WallapopClient()
    results = []
    for search in searches:
        try:
            result = run_search(client, search)
        except WallapopError as exc:
            print(f"\n[{search.name}] {exc}", file=sys.stderr)
            continue
        result.sort(args.orden)
        print_result(result, show_rejected=args.descartados)
        results.append(result)
    if args.html and results:
        write_html(results, args.html)
        print(f"\nPágina con fotos guardada en {args.html}")


def cmd_watch(args: argparse.Namespace) -> None:
    searches = select(load_searches(args.config), args.nombre)
    client = WallapopClient()
    store = SeenStore(args.estado)
    notifier = TelegramNotifier.from_env()
    print(f"Vigilando {len(searches)} búsqueda(s) cada {args.intervalo} min. "
          f"Telegram: {'activado' if notifier else 'desactivado'}. Ctrl+C para salir.")

    while True:
        for search in searches:
            try:
                result = run_search(client, search)
            except WallapopError as exc:
                print(f"[{search.name}] {exc}", file=sys.stderr)
                continue
            first_time = store.is_new_search(search.name)
            new_ids = set(store.filter_new(search.name, [i.id for i in result.accepted]))
            new_items = [i for i in result.accepted if i.id in new_ids]
            store.add(search.name, [i.id for i in new_items])

            stamp = datetime.now().strftime("%H:%M")
            if first_time and not args.avisar_existentes:
                print(f"[{stamp}] {search.name}: {len(new_items)} anuncios actuales guardados; "
                      "a partir de ahora solo aviso de los nuevos.")
                continue
            for item in new_items:
                print(f"[{stamp}] NUEVO en {search.name}:\n{item_line(item, result.is_deal(item))}")
                if notifier:
                    try:
                        notifier.send_item(search.name, item)
                    except Exception as exc:  # un fallo de Telegram no debe parar el bot
                        print(f"  (no se pudo avisar por Telegram: {exc})", file=sys.stderr)
            if not new_items:
                print(f"[{stamp}] {search.name}: nada nuevo")
        store.save()
        if args.una_vez:
            return
        # Un poco de aleatoriedad para no hacer peticiones con un patrón fijo.
        time.sleep(args.intervalo * 60 * random.uniform(0.85, 1.15))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="wallabot",
        description="Busca en Wallapop y filtra la morralla (cajas, otros modelos, PCs enteros...).",
    )
    parser.add_argument("-c", "--config", default="busquedas.toml", help="fichero de búsquedas (por defecto busquedas.toml)")
    parser.add_argument("-n", "--nombre", action="append", help="ejecuta solo la búsqueda con este nombre (repetible)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("buscar", help="busca una vez y muestra lo interesante")
    p_search.add_argument("--orden", choices=("precio", "fecha"), default="precio")
    p_search.add_argument("--descartados", action="store_true", help="lista también lo descartado y el motivo")
    p_search.add_argument("--html", metavar="FICHERO", help="guarda una página con fotos de los resultados")
    p_search.set_defaults(func=cmd_search)

    p_watch = sub.add_parser("vigilar", help="repite la búsqueda y avisa solo de anuncios nuevos")
    p_watch.add_argument("-i", "--intervalo", type=float, default=10, help="minutos entre búsquedas (por defecto 10)")
    p_watch.add_argument("--estado", default="vistos.json", help="dónde guardar los anuncios ya vistos")
    p_watch.add_argument("--avisar-existentes", action="store_true", help="en la primera pasada avisa también de lo que ya había")
    p_watch.add_argument("--una-vez", action="store_true", help="una sola pasada (útil con cron)")
    p_watch.set_defaults(func=cmd_watch)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except FileNotFoundError as exc:
        sys.exit(f"No encuentro {exc.filename}. Copia busquedas.example.toml a busquedas.toml y edítalo.")
    except ValueError as exc:
        sys.exit(f"Error en la configuración: {exc}")
    except KeyboardInterrupt:
        pass
