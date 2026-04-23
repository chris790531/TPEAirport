from __future__ import annotations

from collections import Counter
from pathlib import Path

from tpeairport.flightforecast import parse_xls_hourly_totals


def test_parse_sample_xls_has_48_rows_and_full_hours() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = repo_root / "data" / "sample.xls"

    items = parse_xls_hourly_totals(fixture)

    assert len(items) == 48  # 24 hours * 2 terminals

    counts = Counter((i.terminal, i.hour) for i in items)
    for hour in range(24):
        assert counts[("T1", hour)] == 1
        assert counts[("T2", hour)] == 1

    assert all(i.people >= 0 for i in items)
