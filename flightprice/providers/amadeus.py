"""Amadeus Self-Service flight offers provider.

Docs: https://developers.amadeus.com/self-service/category/flights
Free tier gives a generous monthly quota against the ``test`` sandbox.
"""

from __future__ import annotations

import os
import time
from typing import List, Optional

import requests

from ..models import FlightOffer, SearchQuery, Segment
from .base import FlightProvider, ProviderError

_HOSTS = {
    "test": "https://test.api.amadeus.com",
    "production": "https://api.amadeus.com",
}


class AmadeusProvider(FlightProvider):
    name = "amadeus"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        env: Optional[str] = None,
        timeout: int = 20,
    ) -> None:
        self._client_id = client_id or os.getenv("AMADEUS_CLIENT_ID", "")
        self._client_secret = client_secret or os.getenv("AMADEUS_CLIENT_SECRET", "")
        env = (env or os.getenv("AMADEUS_ENV", "test")).lower()
        self._host = _HOSTS.get(env, _HOSTS["test"])
        self._timeout = timeout
        if not self._client_id or not self._client_secret:
            raise ProviderError("Amadeus credentials are not configured")
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    # -- auth -------------------------------------------------------------
    def _access_token(self) -> str:
        # Reuse the token until ~30s before it expires.
        if self._token and time.time() < self._token_expiry - 30:
            return self._token
        resp = requests.post(
            f"{self._host}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise ProviderError(f"Amadeus auth failed: {resp.status_code} {resp.text}")
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expiry = time.time() + float(payload.get("expires_in", 1799))
        return self._token

    # -- search -----------------------------------------------------------
    def search(self, query: SearchQuery) -> List[FlightOffer]:
        params = {
            "originLocationCode": query.origin,
            "destinationLocationCode": query.destination,
            "departureDate": query.depart_date,
            "adults": query.adults,
            "currencyCode": query.currency,
            "nonStop": str(query.non_stop).lower(),
            "max": query.max_results,
        }
        if query.return_date:
            params["returnDate"] = query.return_date

        resp = requests.get(
            f"{self._host}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            params=params,
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise ProviderError(
                f"Amadeus search failed: {resp.status_code} {resp.text}"
            )
        return self._parse(resp.json())

    def _parse(self, body: dict) -> List[FlightOffer]:
        carriers = (body.get("dictionaries") or {}).get("carriers", {})
        offers: List[FlightOffer] = []
        for offer in body.get("data", []):
            price_info = offer.get("price", {})
            try:
                price = float(price_info.get("grandTotal") or price_info["total"])
            except (KeyError, TypeError, ValueError):
                continue
            currency = price_info.get("currency", "")
            segments: List[Segment] = []
            for itin in offer.get("itineraries", []):
                for seg in itin.get("segments", []):
                    dep = seg.get("departure", {})
                    arr = seg.get("arrival", {})
                    code = seg.get("carrierCode", "")
                    segments.append(
                        Segment(
                            carrier=carriers.get(code, code),
                            flight_number=f"{code}{seg.get('number', '')}",
                            origin=dep.get("iataCode", ""),
                            destination=arr.get("iataCode", ""),
                            departure=dep.get("at", ""),
                            arrival=arr.get("at", ""),
                        )
                    )
            offers.append(
                FlightOffer(
                    provider=self.name,
                    price=price,
                    currency=currency,
                    segments=segments,
                )
            )
        return offers
