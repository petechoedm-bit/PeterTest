"""SQLite-backed price history.

Records the cheapest offer per (query, provider) at each check so the monitor
can report trends ("↓ NT$1,200 vs. yesterday") and you can chart prices later.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import PriceObservation

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    query_slug  TEXT NOT NULL,
    provider    TEXT NOT NULL,
    price       REAL NOT NULL,
    currency    TEXT NOT NULL,
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_slug
    ON price_history (query_slug, observed_at);
"""


class PriceStore:
    def __init__(self, path: str = "flightprice.db") -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(self, obs: PriceObservation) -> None:
        self._conn.execute(
            "INSERT INTO price_history "
            "(query_slug, provider, price, currency, observed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                obs.query_slug,
                obs.provider,
                obs.price,
                obs.currency,
                obs.observed_at.isoformat(),
            ),
        )
        self._conn.commit()

    def lowest_ever(self, query_slug: str) -> Optional[float]:
        row = self._conn.execute(
            "SELECT MIN(price) AS p FROM price_history WHERE query_slug = ?",
            (query_slug,),
        ).fetchone()
        return row["p"] if row and row["p"] is not None else None

    def previous_price(self, query_slug: str) -> Optional[float]:
        """The most recent recorded price before the latest one."""
        rows = self._conn.execute(
            "SELECT price FROM price_history WHERE query_slug = ? "
            "ORDER BY observed_at DESC LIMIT 2",
            (query_slug,),
        ).fetchall()
        return rows[1]["price"] if len(rows) == 2 else None

    def history(self, query_slug: str, limit: int = 50) -> List[PriceObservation]:
        rows = self._conn.execute(
            "SELECT * FROM price_history WHERE query_slug = ? "
            "ORDER BY observed_at DESC LIMIT ?",
            (query_slug, limit),
        ).fetchall()
        return [
            PriceObservation(
                query_slug=r["query_slug"],
                provider=r["provider"],
                price=r["price"],
                currency=r["currency"],
                observed_at=datetime.fromisoformat(r["observed_at"]),
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
