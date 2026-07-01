"""Scheduled price monitoring with threshold alerts."""

from __future__ import annotations

from datetime import datetime
from typing import List

from apscheduler.schedulers.blocking import BlockingScheduler

from .compare import compare
from .config import MonitorConfig, Watch
from .models import PriceObservation
from .notify import Notifier
from .providers import build_providers
from .storage import PriceStore


class Monitor:
    def __init__(self, config: MonitorConfig, db_path: str = "flightprice.db") -> None:
        self.config = config
        self.providers = build_providers()
        self.store = PriceStore(db_path)
        self.notifier = Notifier()

    def check_once(self) -> None:
        """Run every watch a single time (used by the scheduler and by tests)."""
        for watch in self.config.watches:
            self._check_watch(watch)

    def _check_watch(self, watch: Watch) -> None:
        result = compare(watch.query, self.providers)
        cheapest = result.cheapest
        if cheapest is None:
            errs = "; ".join(result.errors) or "no offers found"
            print(f"[{_now()}] {watch.name}: no results ({errs})")
            return

        slug = watch.query.slug()
        prev = self.store.previous_price(slug)
        low = self.store.lowest_ever(slug)

        self.store.record(
            PriceObservation(
                query_slug=slug,
                provider=cheapest.provider,
                price=cheapest.price,
                currency=cheapest.currency,
                observed_at=datetime.now(),
            )
        )

        trend = ""
        if prev is not None:
            delta = cheapest.price - prev
            arrow = "↓" if delta < 0 else ("↑" if delta > 0 else "→")
            trend = f"  {arrow} {abs(delta):.0f} vs last"
        print(
            f"[{_now()}] {watch.name}: cheapest "
            f"{cheapest.price:.0f} {cheapest.currency} "
            f"({','.join(cheapest.carriers)}){trend}"
        )

        if cheapest.price <= watch.max_price:
            self._alert(watch, cheapest, low)

    def _alert(self, watch: Watch, offer, previous_low) -> None:
        record = ""
        if previous_low is None or offer.price <= previous_low:
            record = "  🎉 lowest price on record!"
        subject = (
            f"✈️ 機票降價 {watch.name}: {offer.price:.0f} {offer.currency}"
        )
        body = (
            f"路線: {watch.query.origin} → {watch.query.destination}\n"
            f"去程: {watch.query.depart_date}"
            + (f"  回程: {watch.query.return_date}\n" if watch.query.return_date else "\n")
            + f"人數: {watch.query.adults}\n"
            f"目標價: {watch.max_price:.0f} {offer.currency}\n"
            f"現價: {offer.price:.0f} {offer.currency}{record}\n"
            f"航空: {', '.join(offer.carriers)}\n"
            + (f"訂票: {offer.booking_url}\n" if offer.booking_url else "")
        )
        self.notifier.send(subject, body)

    def run_forever(self) -> None:
        """Start the blocking scheduler. Runs an immediate check, then repeats."""
        interval = max(self.config.check_interval_minutes, 1)
        print(
            f"Monitoring {len(self.config.watches)} watch(es) "
            f"every {interval} min. Providers: "
            f"{', '.join(p.name for p in self.providers)}. Ctrl-C to stop."
        )
        self.check_once()
        scheduler = BlockingScheduler()
        scheduler.add_job(self.check_once, "interval", minutes=interval)
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("\nStopped.")
        finally:
            self.store.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
