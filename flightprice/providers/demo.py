"""Offline demo provider.

Generates deterministic, realistic-looking offers so the whole tool — search,
comparison, history, monitoring, alerts — can be exercised without any API
credentials. Prices vary by route distance, cabin demand and a per-day pseudo
random factor so monitoring actually sees movement over time.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import List

from ..models import FlightOffer, SearchQuery, Segment
from .base import FlightProvider

# A tiny built-in airline pool with plausible price multipliers.
_AIRLINES = [
    ("CI", "China Airlines", 1.00),
    ("BR", "EVA Air", 1.05),
    ("JL", "Japan Airlines", 1.18),
    ("NH", "ANA", 1.20),
    ("IT", "Tigerair Taiwan", 0.72),
    ("JX", "Starlux Airlines", 1.10),
    ("GK", "Jetstar Japan", 0.68),
]


def _seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(digest[:8], 16)


def _rand(seed: int) -> float:
    """Deterministic float in [0, 1) from an integer seed."""
    return ((seed * 1103515245 + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF


class DemoProvider(FlightProvider):
    name = "demo"

    def search(self, query: SearchQuery) -> List[FlightOffer]:
        # Base fare scales with a crude "distance" derived from the codes, and
        # drifts by day so repeated monitoring runs see changing prices.
        route_seed = _seed(query.origin, query.destination)
        base = 4000 + (route_seed % 9000)  # 4000–13000 base one-way
        day_factor = 0.85 + 0.4 * _rand(_seed(query.depart_date, str(datetime.now().date())))

        offers: List[FlightOffer] = []
        for idx, (code, airline, mult) in enumerate(_AIRLINES):
            seed = _seed(query.slug(), code)
            jitter = 0.9 + 0.35 * _rand(seed)
            trip_mult = 1.9 if not query.one_way else 1.0
            price = base * mult * jitter * day_factor * trip_mult * query.adults

            if query.non_stop and idx % 3 == 2:
                # Pretend some airlines only offer connections.
                continue

            segments = self._segments(query, code, airline, idx)
            offers.append(
                FlightOffer(
                    provider=self.name,
                    price=round(price, 0),
                    currency=query.currency,
                    segments=segments,
                    booking_url=f"https://example.com/book/{query.slug()}/{code}",
                )
            )
        offers.sort(key=lambda o: o.price)
        return offers[: query.max_results]

    def _segments(
        self, query: SearchQuery, code: str, airline: str, idx: int
    ) -> List[Segment]:
        dep_dt = datetime.fromisoformat(query.depart_date) + timedelta(
            hours=6 + idx
        )
        arr_dt = dep_dt + timedelta(hours=2 + (idx % 3))
        out = [
            Segment(
                carrier=airline,
                flight_number=f"{code}{100 + idx}",
                origin=query.origin,
                destination=query.destination,
                departure=dep_dt.isoformat(),
                arrival=arr_dt.isoformat(),
            )
        ]
        if not query.return_date:
            return out
        ret_dep = datetime.fromisoformat(query.return_date) + timedelta(
            hours=10 + idx
        )
        ret_arr = ret_dep + timedelta(hours=2 + (idx % 3))
        out.append(
            Segment(
                carrier=airline,
                flight_number=f"{code}{200 + idx}",
                origin=query.destination,
                destination=query.origin,
                departure=ret_dep.isoformat(),
                arrival=ret_arr.isoformat(),
            )
        )
        return out
