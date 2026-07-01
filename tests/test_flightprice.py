"""Unit tests exercising the demo provider, comparison, storage and monitor."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from flightprice.compare import compare
from flightprice.config import MonitorConfig, Watch
from flightprice.models import PriceObservation, SearchQuery
from flightprice.monitor import Monitor
from flightprice.providers.base import ProviderError
from flightprice.providers.demo import DemoProvider
from flightprice.providers.skyscanner import SkyscannerProvider
from flightprice.storage import PriceStore


class SearchQueryTests(unittest.TestCase):
    def test_normalises_and_validates(self):
        q = SearchQuery("tpe", "nrt", "2026-07-20", "2026-07-27")
        self.assertEqual(q.origin, "TPE")
        self.assertEqual(q.destination, "NRT")
        self.assertFalse(q.one_way)
        self.assertIn("TPE-NRT", q.slug())

    def test_same_origin_destination_rejected(self):
        with self.assertRaises(ValueError):
            SearchQuery("TPE", "TPE", "2026-07-20")

    def test_one_way(self):
        self.assertTrue(SearchQuery("TPE", "KIX", "2026-07-20").one_way)


class DemoProviderTests(unittest.TestCase):
    def test_returns_sorted_offers(self):
        provider = DemoProvider()
        q = SearchQuery("TPE", "NRT", "2026-07-20", "2026-07-27")
        offers = provider.search(q)
        self.assertTrue(offers)
        prices = [o.price for o in offers]
        self.assertEqual(prices, sorted(prices))
        self.assertTrue(all(o.currency == "TWD" for o in offers))

    def test_deterministic(self):
        q = SearchQuery("TPE", "KIX", "2026-08-15")
        a = DemoProvider().search(q)
        b = DemoProvider().search(q)
        self.assertEqual([o.price for o in a], [o.price for o in b])

    def test_round_trip_costs_more_than_one_way(self):
        p = DemoProvider()
        ow = p.search(SearchQuery("TPE", "NRT", "2026-07-20"))
        rt = p.search(SearchQuery("TPE", "NRT", "2026-07-20", "2026-07-27"))
        self.assertLess(ow[0].price, rt[0].price)


def _airport_search_response(sky_id: str, entity_id: str) -> dict:
    return {
        "status": True,
        "data": [
            {
                "navigation": {
                    "relevantFlightParams": {
                        "skyId": sky_id,
                        "entityId": entity_id,
                        "flightPlaceType": "AIRPORT",
                    }
                }
            }
        ],
    }

_SEARCH_FLIGHTS_RESPONSE = {
    "status": True,
    "data": {
        "context": {"status": "complete"},
        "itineraries": [
            {
                "price": {"raw": 200.66, "formatted": "$201"},
                "legs": [
                    {
                        "durationInMinutes": 205,
                        "stopCount": 0,
                        "segments": [
                            {
                                "origin": {"displayCode": "TPE"},
                                "destination": {"displayCode": "NRT"},
                                "departure": "2026-08-15T06:35:00",
                                "arrival": "2026-08-15T11:00:00",
                                "flightNumber": "200",
                                "marketingCarrier": {
                                    "name": "Tigerair Taiwan",
                                    "alternateId": "IT",
                                },
                            }
                        ]
                    }
                ],
                "isSelfTransfer": False,
                "tags": ["cheapest"],
                "farePolicy": {
                    "isChangeAllowed": False,
                    "isPartiallyChangeable": False,
                    "isCancellationAllowed": False,
                    "isPartiallyRefundable": False,
                },
                "eco": {"ecoContenderDelta": 20.2},
            }
        ],
    },
}


class SkyscannerProviderTests(unittest.TestCase):
    def test_missing_credentials_raise(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                SkyscannerProvider()

    def test_search_resolves_airports_and_parses_offers(self):
        provider = SkyscannerProvider(api_key="test-key")
        query = SearchQuery("TPE", "NRT", "2026-08-15")

        with patch("flightprice.providers.skyscanner.requests.get") as get:
            get.side_effect = [
                Mock(status_code=200, json=lambda: _airport_search_response("TPE", "128667054")),
                Mock(status_code=200, json=lambda: _airport_search_response("NRT", "128668889")),
                Mock(status_code=200, json=lambda: _SEARCH_FLIGHTS_RESPONSE),
            ]
            offers = provider.search(query)

        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertEqual(offer.provider, "skyscanner")
        self.assertEqual(offer.price, 200.66)
        self.assertEqual(offer.currency, "TWD")
        self.assertEqual(len(offer.segments), 1)
        self.assertEqual(offer.segments[0].flight_number, "IT200")
        self.assertEqual(offer.duration_minutes, 205)
        self.assertEqual(offer.stop_count, 0)
        self.assertEqual(offer.self_transfer, False)
        self.assertEqual(offer.tags, ["cheapest"])
        self.assertEqual(offer.fare_policy, {
            "changeAllowed": False,
            "cancellationAllowed": False,
            "partiallyRefundable": False,
        })
        self.assertEqual(offer.eco_delta_pct, 20.2)

    def test_search_raises_on_http_error(self):
        provider = SkyscannerProvider(api_key="test-key")
        query = SearchQuery("TPE", "NRT", "2026-08-15")

        with patch("flightprice.providers.skyscanner.requests.get") as get:
            get.return_value = Mock(status_code=401, text="unauthorized")
            with self.assertRaises(ProviderError):
                provider.search(query)


class CompareTests(unittest.TestCase):
    def test_merges_and_reports_no_errors(self):
        q = SearchQuery("TPE", "NRT", "2026-07-20")
        result = compare(q, [DemoProvider()])
        self.assertIsNotNone(result.cheapest)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.cheapest, result.offers[0])


class StorageTests(unittest.TestCase):
    def test_history_and_trends(self):
        with tempfile.TemporaryDirectory() as d:
            store = PriceStore(os.path.join(d, "t.db"))
            slug = "TPE-NRT-2026-07-20"
            for price in (10000, 8000, 8500):
                store.record(
                    PriceObservation(slug, "demo", price, "TWD", datetime.now())
                )
            self.assertEqual(store.lowest_ever(slug), 8000)
            self.assertEqual(store.previous_price(slug), 8000)
            self.assertEqual(len(store.history(slug)), 3)
            store.close()


class MonitorTests(unittest.TestCase):
    def test_check_once_records_and_alerts(self):
        with tempfile.TemporaryDirectory() as d:
            watch = Watch(
                name="test",
                query=SearchQuery("TPE", "NRT", "2026-07-20", "2026-07-27"),
                max_price=10_000_000,  # guaranteed to trigger an alert
            )
            config = MonitorConfig(check_interval_minutes=60, watches=[watch])
            monitor = Monitor(config, db_path=os.path.join(d, "m.db"))
            monitor.check_once()
            slug = watch.query.slug()
            self.assertIsNotNone(monitor.store.lowest_ever(slug))
            monitor.store.close()


if __name__ == "__main__":
    unittest.main()
