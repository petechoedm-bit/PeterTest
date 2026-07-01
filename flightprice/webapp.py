"""Minimal local web UI for one-off searches.

Run with ``python -m flightprice web`` and open http://127.0.0.1:5000/.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .compare import compare
from .config import load_dotenv
from .models import SearchQuery
from .providers import build_providers

app = Flask(__name__)

_DATA_DIR = Path(__file__).parent / "data"
_AIRPORTS = json.loads((_DATA_DIR / "airports.json").read_text(encoding="utf-8"))
_CITY_ALIASES_ZH = json.loads((_DATA_DIR / "city_aliases_zh.json").read_text(encoding="utf-8"))


@app.route("/airports.json")
def airports_json():
    # Offline airport lookup for the origin/destination autocomplete — no
    # RapidAPI calls, so it doesn't touch the Skyscanner free-tier quota.
    return jsonify({"airports": _AIRPORTS, "aliases_zh": _CITY_ALIASES_ZH})


_TAG_LABELS_ZH = {
    "cheapest": "最便宜",
    "second_cheapest": "次便宜",
    "third_cheapest": "第三便宜",
    "fastest": "最快",
    "shortest": "飛行時間最短",
    "second_shortest": "次短",
    "third_shortest": "第三短",
}


def _duration_fmt(minutes):
    if not minutes:
        return "—"
    hours, mins = divmod(int(minutes), 60)
    return f"{hours}小時{mins}分" if mins else f"{hours}小時"


def _time_fmt(iso_str):
    # "2026-08-15T06:35:00" -> "06:35"
    return iso_str[11:16] if iso_str and len(iso_str) >= 16 else (iso_str or "—")


def _tag_fmt(tag):
    return _TAG_LABELS_ZH.get(tag, tag)


app.jinja_env.filters["duration_fmt"] = _duration_fmt
app.jinja_env.filters["time_fmt"] = _time_fmt
app.jinja_env.filters["tag_fmt"] = _tag_fmt


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method != "POST":
        return render_template("index.html")

    try:
        query = SearchQuery(
            origin=request.form["origin"],
            destination=request.form["destination"],
            depart_date=request.form["depart_date"],
            return_date=request.form.get("return_date") or None,
            adults=int(request.form.get("adults") or 1),
            currency=request.form.get("currency") or "TWD",
            non_stop=bool(request.form.get("non_stop")),
        )
    except ValueError as exc:
        return render_template("index.html", error=str(exc))

    providers = build_providers()
    result = compare(query, providers)
    return render_template(
        "results.html",
        query=query,
        offers=result.top(20),
        cheapest=result.cheapest,
        errors=result.errors,
        provider_names=", ".join(p.name for p in providers),
    )


def main() -> None:
    load_dotenv()
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
