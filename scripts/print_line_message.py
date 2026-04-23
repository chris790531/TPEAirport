from __future__ import annotations

import json
from pathlib import Path

from tpeairport.flightforecast import HourlyForecast
from tpeairport.line_format import format_forecast_message


def main() -> int:
    p = Path("data/flightforecast_latest.json")
    obj = json.loads(p.read_text(encoding="utf-8"))
    items = [HourlyForecast(**i) for i in obj["items"]]
    print(format_forecast_message(items, obj["fetched_at_utc"], top_n=3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

