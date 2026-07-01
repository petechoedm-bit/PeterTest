"""Search aggregation and comparison across providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .models import FlightOffer, SearchQuery
from .providers.base import FlightProvider, ProviderError


@dataclass
class ComparisonResult:
    query: SearchQuery
    offers: List[FlightOffer]
    errors: List[str]

    @property
    def cheapest(self) -> FlightOffer | None:
        return self.offers[0] if self.offers else None

    def top(self, n: int) -> List[FlightOffer]:
        return self.offers[:n]


def compare(
    query: SearchQuery, providers: List[FlightProvider]
) -> ComparisonResult:
    """Run ``query`` against every provider and merge results, cheapest first.

    Provider failures are collected rather than raised so one bad source does
    not sink the whole comparison.
    """

    all_offers: List[FlightOffer] = []
    errors: List[str] = []
    for provider in providers:
        try:
            all_offers.extend(provider.search(query))
        except ProviderError as exc:
            errors.append(f"{provider.name}: {exc}")
        except Exception as exc:  # defensive: never let one provider crash all
            errors.append(f"{provider.name}: unexpected error: {exc}")

    all_offers.sort(key=lambda o: (o.price, o.stops))
    return ComparisonResult(query=query, offers=all_offers, errors=errors)
