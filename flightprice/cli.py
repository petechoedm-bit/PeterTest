"""Command-line interface for real-time search and scheduled monitoring."""

from __future__ import annotations

import argparse
import sys
from typing import List

from .compare import compare
from .config import load_dotenv, load_watches
from .models import SearchQuery
from .monitor import Monitor
from .providers import build_providers


def _add_search_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("origin", help="Origin IATA code, e.g. TPE")
    p.add_argument("destination", help="Destination IATA code, e.g. NRT")
    p.add_argument("depart_date", help="Departure date YYYY-MM-DD")
    p.add_argument("return_date", nargs="?", default=None, help="Return date (optional)")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--currency", default="TWD")
    p.add_argument("--non-stop", action="store_true", help="Direct flights only")
    p.add_argument("--top", type=int, default=10, help="How many results to show")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flightprice",
        description="Compare and monitor flight prices across providers.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="One-off price comparison")
    _add_search_args(search)

    monitor = sub.add_parser("monitor", help="Run scheduled price watches")
    monitor.add_argument(
        "--config", default="watches.yaml", help="Path to watches YAML"
    )
    monitor.add_argument("--db", default="flightprice.db", help="History DB path")
    monitor.add_argument(
        "--once", action="store_true", help="Run one check and exit"
    )
    return parser


def _run_search(args: argparse.Namespace) -> int:
    query = SearchQuery(
        origin=args.origin,
        destination=args.destination,
        depart_date=args.depart_date,
        return_date=args.return_date,
        adults=args.adults,
        currency=args.currency,
        non_stop=args.non_stop,
    )
    providers = build_providers()
    print(f"Searching via: {', '.join(p.name for p in providers)}\n")
    result = compare(query, providers)

    if not result.offers:
        print("No offers found.")
        for err in result.errors:
            print(f"  ! {err}")
        return 1

    trip = "one-way" if query.one_way else "round-trip"
    print(
        f"{query.origin} → {query.destination}  {query.depart_date}"
        + (f" / {query.return_date}" if query.return_date else "")
        + f"  ({trip}, {query.adults} pax)\n"
    )
    for i, offer in enumerate(result.top(args.top), 1):
        marker = "⭐" if i == 1 else "  "
        print(f"{marker} {i:>2}. {offer.summary}")
    cheapest = result.cheapest
    print(f"\nCheapest: {cheapest.price:.0f} {cheapest.currency} "
          f"via {cheapest.provider} ({', '.join(cheapest.carriers)})")
    for err in result.errors:
        print(f"  ! {err}")
    return 0


def _run_monitor(args: argparse.Namespace) -> int:
    config = load_watches(args.config)
    if not config.watches:
        print(f"No watches defined in {args.config}.")
        return 1
    monitor = Monitor(config, db_path=args.db)
    if args.once:
        monitor.check_once()
        monitor.store.close()
    else:
        monitor.run_forever()
    return 0


def main(argv: List[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    if args.command == "search":
        return _run_search(args)
    if args.command == "monitor":
        return _run_monitor(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
