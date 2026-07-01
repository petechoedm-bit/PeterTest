"""Load monitoring config (watches) from YAML and .env files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

from .models import SearchQuery


@dataclass
class Watch:
    name: str
    query: SearchQuery
    max_price: float


@dataclass
class MonitorConfig:
    check_interval_minutes: int
    watches: List[Watch]


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no external dependency).

    Only sets keys that are not already present in the environment.
    """
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_watches(path: str) -> MonitorConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    interval = int(data.get("check_interval_minutes", 60))
    watches: List[Watch] = []
    for raw in data.get("watches", []):
        query = SearchQuery(
            origin=raw["origin"],
            destination=raw["destination"],
            depart_date=str(raw["depart_date"]),
            return_date=(str(raw["return_date"]) if raw.get("return_date") else None),
            adults=int(raw.get("adults", 1)),
            currency=raw.get("currency", "TWD"),
            non_stop=bool(raw.get("non_stop", False)),
        )
        watches.append(
            Watch(
                name=raw.get("name", query.slug()),
                query=query,
                max_price=float(raw["max_price"]),
            )
        )
    return MonitorConfig(check_interval_minutes=interval, watches=watches)
