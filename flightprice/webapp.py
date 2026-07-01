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
