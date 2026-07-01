"""Abstract base class for flight search providers."""

from __future__ import annotations

import abc
from typing import List

from ..models import FlightOffer, SearchQuery


class ProviderError(RuntimeError):
    """Raised when a provider cannot fulfil a search."""


class FlightProvider(abc.ABC):
    """Interface every flight data source must implement."""

    #: Short, stable identifier shown in results and stored in history.
    name: str = "base"

    @abc.abstractmethod
    def search(self, query: SearchQuery) -> List[FlightOffer]:
        """Return priced offers for ``query`` (may be empty, never ``None``)."""
        raise NotImplementedError
