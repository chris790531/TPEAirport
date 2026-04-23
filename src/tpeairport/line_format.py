"""Format flightforecast snapshot for LINE messages."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable

from tpeairport.flightforecast import HourlyForecast


def _fmt_hour(h: int) -> str:
    return f"{h:02d}:00"


def format_forecast_message(
    items: Iterable[HourlyForecast],
    fetched_at_utc: str,
    *,
    top_n: int = 6,
) -> str:
    """Format T1/T2 hourly forecast as a compact LINE-friendly message.

    - top_n: show top N busiest hours for each terminal (sorted by people desc)
    """
    by_terminal: dict[str, list[HourlyForecast]] = defaultdict(list)
    for it in items:
        by_terminal[it.terminal].append(it)

    # Normalize order
    for t in by_terminal:
        by_terminal[t] = sorted(by_terminal[t], key=lambda x: x.hour)

    # Parse timestamp to a friendlier string if possible
    fetched = fetched_at_utc
    try:
        fetched = datetime.fromisoformat(fetched_at_utc.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass

    lines: list[str] = []
    lines.append("桃園機場 整點人數預估")
    lines.append(f"更新時間：{fetched}")

    for terminal in ("T1", "T2"):
        items_t = by_terminal.get(terminal, [])
        if not items_t:
            lines.append(f"{terminal}：無資料")
            continue

        total = sum(i.people for i in items_t)
        busiest = sorted(items_t, key=lambda x: x.people, reverse=True)[:top_n]

        lines.append("")
        lines.append(f"{terminal}（當日合計 {total:,}）")
        for b in busiest:
            lines.append(f"- {_fmt_hour(b.hour)} {b.people:,}")

    return "\n".join(lines).strip()

