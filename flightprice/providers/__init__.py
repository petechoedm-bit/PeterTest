"""Flight search providers.

A provider knows how to turn a :class:`~flightprice.models.SearchQuery` into a
list of :class:`~flightprice.models.FlightOffer`. Add new sources (Skyscanner,
Kiwi, …) by subclassing :class:`~flightprice.providers.base.FlightProvider`.
"""

from __future__ import annotations

import os
from typing import List

from .base import FlightProvider
from .amadeus import AmadeusProvider
from .demo import DemoProvider


def build_providers() -> List[FlightProvider]:
    """Return the providers usable with the current environment.

    Uses Amadeus when credentials are present, otherwise falls back to the
    offline Demo provider so the tool always returns something runnable.
    """

    providers: List[FlightProvider] = []
    if os.getenv("AMADEUS_CLIENT_ID") and os.getenv("AMADEUS_CLIENT_SECRET"):
        providers.append(AmadeusProvider())
    if not providers:
        providers.append(DemoProvider())
    return providers


__all__ = [
    "FlightProvider",
    "AmadeusProvider",
    "DemoProvider",
    "build_providers",
]
