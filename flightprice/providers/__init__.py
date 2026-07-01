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
from .skyscanner import SkyscannerProvider


def build_providers() -> List[FlightProvider]:
    """Return the providers usable with the current environment.

    Enables every real provider that has credentials configured (so results
    can be compared across sources), falling back to the offline Demo
    provider only when none are configured.
    """

    providers: List[FlightProvider] = []
    if os.getenv("AMADEUS_CLIENT_ID") and os.getenv("AMADEUS_CLIENT_SECRET"):
        providers.append(AmadeusProvider())
    if os.getenv("SKYSCANNER_RAPIDAPI_KEY"):
        providers.append(SkyscannerProvider())
    if not providers:
        providers.append(DemoProvider())
    return providers


__all__ = [
    "FlightProvider",
    "AmadeusProvider",
    "SkyscannerProvider",
    "DemoProvider",
    "build_providers",
]
