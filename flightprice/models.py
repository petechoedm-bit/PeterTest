"""Core data models shared across providers, comparison and storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SearchQuery:
    """A user-customizable flight search request.

    ``origin`` / ``destination`` are IATA airport or city codes (e.g. ``TPE``,
    ``NRT``). ``return_date`` is ``None`` for a one-way search.
    """

    origin: str
    destination: str
    depart_date: str  # ISO date, e.g. "2026-07-20"
    return_date: Optional[str] = None
    adults: int = 1
    currency: str = "TWD"
    non_stop: bool = False
    max_results: int = 20

    def __post_init__(self) -> None:
        if not self.origin or not self.destination:
            raise ValueError("origin and destination are required")
        if self.origin.upper() == self.destination.upper():
            raise ValueError("origin and destination must differ")
        if self.adults < 1:
            raise ValueError("adults must be >= 1")
        # Normalise codes to upper case without mutating a frozen instance.
        object.__setattr__(self, "origin", self.origin.upper())
        object.__setattr__(self, "destination", self.destination.upper())

    @property
    def one_way(self) -> bool:
        return self.return_date is None

    def slug(self) -> str:
        """Stable identifier for storage / dedup."""
        parts = [self.origin, self.destination, self.depart_date]
        if self.return_date:
            parts.append(self.return_date)
        parts.append(f"{self.adults}pax")
        return "-".join(parts)


@dataclass(frozen=True)
class Segment:
    """A single flight leg."""

    carrier: str
    flight_number: str
    origin: str
    destination: str
    departure: str  # ISO datetime
    arrival: str  # ISO datetime


@dataclass(frozen=True)
class FlightOffer:
    """A priced itinerary returned by a provider.

    ``duration_minutes``, ``stop_count``, ``self_transfer``, ``tags``,
    ``fare_policy`` and ``eco_delta_pct`` are itinerary-level extras that not
    every provider can supply (Skyscanner does, Demo/Amadeus don't); they
    default to "unknown" rather than forcing every provider to fake them.
    """

    provider: str
    price: float
    currency: str
    segments: List[Segment] = field(default_factory=list)
    booking_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    stop_count: Optional[int] = None
    self_transfer: Optional[bool] = None
    tags: List[str] = field(default_factory=list)
    fare_policy: Optional[Dict[str, bool]] = None
    eco_delta_pct: Optional[float] = None

    @property
    def carriers(self) -> List[str]:
        seen: List[str] = []
        for seg in self.segments:
            if seg.carrier not in seen:
                seen.append(seg.carrier)
        return seen

    @property
    def stops(self) -> int:
        # Stops on the outbound leg is a rough proxy; segments include return
        # legs too, so this is "total connections across the itinerary".
        return max(len(self.segments) - 1, 0)

    @property
    def summary(self) -> str:
        route = " → ".join(
            [self.segments[0].origin] + [s.destination for s in self.segments]
        ) if self.segments else "?"
        carriers = ",".join(self.carriers) or "?"
        return f"{self.price:.0f} {self.currency}  [{carriers}]  {route}"


@dataclass(frozen=True)
class PriceObservation:
    """A single recorded price point for a query, used for history."""

    query_slug: str
    provider: str
    price: float
    currency: str
    observed_at: datetime
