"""Skyscanner flight offers via the "Sky Scrapper" RapidAPI proxy.

Skyscanner's own API is partner-only; Sky Scrapper scrapes Skyscanner's
public search results and re-exposes them through RapidAPI.

Docs: https://rapidapi.com/apiheya/api/sky-scrapper
Free tier: 20 requests/month.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import requests

from ..models import FlightOffer, SearchQuery, Segment
from .base import FlightProvider, ProviderError

_DEFAULT_HOST = "sky-scrapper.p.rapidapi.com"


class SkyscannerProvider(FlightProvider):
    name = "skyscanner"

    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        timeout: int = 20,
    ) -> None:
        self._api_key = api_key or os.getenv("SKYSCANNER_RAPIDAPI_KEY", "")
        self._host = host or os.getenv("SKYSCANNER_RAPIDAPI_HOST", _DEFAULT_HOST)
        self._timeout = timeout
        if not self._api_key:
            raise ProviderError("Skyscanner (RapidAPI) credentials are not configured")

    @property
    def _headers(self) -> Dict[str, str]:
        return {"x-rapidapi-host": self._host, "x-rapidapi-key": self._api_key}

    # -- airport resolution -------------------------------------------------
    def _resolve_entity_id(self, iata_code: str) -> str:
        # searchFlights needs an entityId per airport, which only the
        # airport-search endpoint returns; the IATA code alone isn't enough.
        resp = requests.get(
            f"https://{self._host}/api/v1/flights/searchAirport",
            headers=self._headers,
            params={"query": iata_code, "locale": "en-US"},
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise ProviderError(
                f"Skyscanner airport lookup failed: {resp.status_code} {resp.text}"
            )
        for item in resp.json().get("data", []):
            params = item.get("navigation", {}).get("relevantFlightParams", {})
            if params.get("flightPlaceType") == "AIRPORT" and params.get("skyId") == iata_code:
                return params["entityId"]
        raise ProviderError(f"Skyscanner: no airport entity found for '{iata_code}'")

    # -- search ---------------------------------------------------------------
    def search(self, query: SearchQuery) -> List[FlightOffer]:
        origin_entity_id = self._resolve_entity_id(query.origin)
        destination_entity_id = self._resolve_entity_id(query.destination)

        params = {
            "originSkyId": query.origin,
            "destinationSkyId": query.destination,
            "originEntityId": origin_entity_id,
            "destinationEntityId": destination_entity_id,
            "date": query.depart_date,
            "adults": query.adults,
            "currency": query.currency,
            "sortBy": "best",
            "market": "en-US",
            "countryCode": "US",
        }
        if query.return_date:
            params["returnDate"] = query.return_date

        resp = requests.get(
            f"https://{self._host}/api/v2/flights/searchFlights",
            headers=self._headers,
            params=params,
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise ProviderError(f"Skyscanner search failed: {resp.status_code} {resp.text}")
        return self._parse(resp.json(), query.currency)

    def _parse(self, body: dict, currency: str) -> List[FlightOffer]:
        itineraries = (body.get("data") or {}).get("itineraries") or []
        offers: List[FlightOffer] = []
        for itin in itineraries:
            price = (itin.get("price") or {}).get("raw")
            if price is None:
                continue
            segments: List[Segment] = []
            for leg in itin.get("legs", []):
                for seg in leg.get("segments", []):
                    carrier = seg.get("marketingCarrier", {})
                    segments.append(
                        Segment(
                            carrier=carrier.get("name", ""),
                            flight_number=f"{carrier.get('alternateId', '')}{seg.get('flightNumber', '')}",
                            origin=seg.get("origin", {}).get("displayCode", ""),
                            destination=seg.get("destination", {}).get("displayCode", ""),
                            departure=seg.get("departure", ""),
                            arrival=seg.get("arrival", ""),
                        )
                    )
            offers.append(
                FlightOffer(
                    provider=self.name,
                    price=float(price),
                    currency=currency,
                    segments=segments,
                )
            )
        return offers
