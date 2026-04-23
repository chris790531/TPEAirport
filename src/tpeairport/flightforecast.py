"""Fetch Taoyuan Airport hourly passenger forecast (T1/T2).

The public page is a SPA, but it exposes downloadable Excel files (``.xls``)
per day. We:
- Render the page once to discover the latest ``.xls`` URL
- Download the ``.xls``
- Parse hourly totals for T1/T2 from the sheet
"""

from __future__ import annotations

import csv
import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from playwright.sync_api import sync_playwright
from python_calamine import CalamineWorkbook


LOGGER = logging.getLogger(__name__)

FORECAST_URL = "https://www.taoyuanairport.com.tw/flightforecast"

Terminal = Literal["T1", "T2"]


@dataclass(frozen=True)
class HourlyForecast:
    terminal: Terminal
    hour: int
    people: int


@dataclass(frozen=True)
class ForecastSnapshot:
    fetched_at_utc: str
    source_url: str
    source_xls_url: str
    items: list[HourlyForecast]


_RE_INT = re.compile(r"\d+")
_RE_FILE = re.compile(r"/uploads/fos/(?P<date>\d{4}_\d{2}_\d{2})(?P<update>_update)?\.xls$", re.I)
_RE_TIME = re.compile(r"^(?P<h>\d{2}):00\s*~\s*(?P=h):59$")


class ForecastSourceNotFoundError(RuntimeError):
    """Raised when no forecast xls link can be discovered."""


class ForecastDownloadError(RuntimeError):
    """Raised when the forecast xls cannot be downloaded."""


class ForecastFormatChangedError(RuntimeError):
    """Raised when the xls format is unexpected or cannot be parsed reliably."""


def _parse_int(text: str) -> int:
    """Parse an integer from a string containing digits/commas/etc."""
    m = _RE_INT.findall(text.replace(",", ""))
    if not m:
        raise ValueError(f"Cannot parse int from: {text!r}")
    return int("".join(m))


def _ensure_hour(value: int) -> int:
    if not 0 <= value <= 23:
        raise ValueError(f"hour out of range: {value}")
    return value


def discover_latest_xls_url(headless: bool = True) -> str:
    """Discover the latest forecast ``.xls`` download URL.

    Prefer plain HTTP parsing (no browser dependency). Fallback to Playwright
    rendering if the site changes and the xls links are not present in HTML.
    """
    LOGGER.info("stage=discover headless=%s url=%s", headless, FORECAST_URL)
    try:
        return discover_latest_xls_url_http()
    except Exception as e:  # noqa: BLE001 - intentional fallback path
        LOGGER.info("stage=discover http_failed; falling back to Playwright: %s", e)
        return discover_latest_xls_url_playwright(headless=headless)


def _iter_xls_candidates(hrefs: Iterable[str]) -> list[tuple[str, str, bool]]:
    candidates: list[tuple[str, str, bool]] = []
    for href in hrefs:
        m = _RE_FILE.search(href)
        if not m:
            continue
        date = m.group("date")
        is_update = m.group("update") is not None
        candidates.append((date, href, is_update))
    return candidates


def _pick_latest_candidate(candidates: list[tuple[str, str, bool]]) -> str:
    if not candidates:
        raise ForecastSourceNotFoundError("No .xls links found for flightforecast")

    # Sort by date, then prefer *_update on same day.
    candidates.sort(key=lambda t: (t[0], t[2]))
    date, href, is_update = candidates[-1]
    LOGGER.info("stage=discover result_date=%s update=%s href=%s", date, is_update, href)
    return href


def discover_latest_xls_url_http() -> str:
    """Discover latest xls URL by fetching HTML and scanning for uploads links."""
    import urllib.request

    LOGGER.info("stage=discover method=http url=%s", FORECAST_URL)
    req = urllib.request.Request(
        FORECAST_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    # The site often embeds absolute/relative uploads links in the HTML payload.
    hrefs = set()
    for m in re.finditer(r'["\'](?P<h>/uploads/fos/\d{4}_\d{2}_\d{2}(?:_update)?\.xls)["\']', html, re.I):
        hrefs.add("https://www.taoyuanairport.com.tw" + m.group("h"))

    candidates = _iter_xls_candidates(sorted(hrefs))
    return _pick_latest_candidate(candidates)


def discover_latest_xls_url_playwright(headless: bool = True) -> str:
    """Discover the latest forecast ``.xls`` download URL by rendering the SPA."""
    LOGGER.info("stage=discover method=playwright headless=%s url=%s", headless, FORECAST_URL)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            page.goto(FORECAST_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            hrefs: list[str] = page.eval_on_selector_all(
                "a",
                "() => Array.from(document.querySelectorAll('a')).map(a => a.href).filter(Boolean)",
            )
        finally:
            context.close()
            browser.close()

    candidates = _iter_xls_candidates(hrefs)
    return _pick_latest_candidate(candidates)


def download_xls(url: str, dest: Path) -> Path:
    """Download the xls to dest (overwrite)."""
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("stage=download url=%s dest=%s", url, dest)

    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": FORECAST_URL,
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                status = getattr(resp, "status", 200)
                if status >= 400:
                    raise ForecastDownloadError(f"HTTP {status} downloading xls")
                data = resp.read()
            if len(data) < 1024:
                raise ForecastDownloadError(f"Downloaded xls too small: {len(data)} bytes")
            dest.write_bytes(data)
            LOGGER.info("stage=download ok bytes=%s dest=%s", len(data), dest)
            return dest
        except Exception as e:  # noqa: BLE001 - retry loop
            last_err = e
            LOGGER.warning("stage=download failed attempt=%s/3 err=%s", attempt, e)
            time.sleep(1.5 * attempt)

    raise ForecastDownloadError(f"Failed to download xls after retries: {last_err}")


def parse_xls_hourly_totals(path: Path) -> list[HourlyForecast]:
    """Parse hourly totals for T1/T2 from the downloaded xls.

    The first sheet has three blocks side-by-side:
    - Total
    - Terminal 1
    - Terminal 2

    Each block has: time_range + 5 numeric columns. We sum those 5 columns as
    the "整點人數預估" for that hour.
    """
    LOGGER.info("stage=parse path=%s", path)
    wb = CalamineWorkbook.from_path(str(path))
    sheet = wb.get_sheet_by_index(0)
    rows = sheet.to_python()

    def sum_block(row: list[object], time_col: int) -> int:
        # Immediately to the right of a time cell there are 5 numeric columns.
        total = 0
        for c in range(time_col + 1, time_col + 6):
            v = row[c] if c < len(row) else 0
            if v is None:
                continue
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                total += int(v)
            elif isinstance(v, str) and v.strip():
                total += _parse_int(v)
        return int(total)

    # Build per-terminal mapping to enforce 0..23 exactly once.
    by_terminal_hour: dict[Terminal, dict[int, int]] = {"T1": {}, "T2": {}}

    for row in rows:
        if not row:
            continue

        time_cols: list[tuple[int, int]] = []
        for idx, cell in enumerate(row):
            if not isinstance(cell, str):
                continue
            tm = _RE_TIME.match(cell.strip())
            if not tm:
                continue
            hour = _ensure_hour(int(tm.group("h")))
            time_cols.append((idx, hour))

        if len(time_cols) < 2:
            continue

        time_cols.sort(key=lambda t: t[0])

        # Expected layouts seen:
        # - [TotalBlockTime, T1Time, T2Time] (3 blocks)
        # - [T1Time, T2Time] (2 blocks, total omitted)
        if len(time_cols) >= 3:
            t1_time_col, t1_hour = time_cols[1]
            t2_time_col, t2_hour = time_cols[2]
        else:
            t1_time_col, t1_hour = time_cols[0]
            t2_time_col, t2_hour = time_cols[1]

        if t1_hour != t2_hour:
            # A format change or a merged-cell artifact; skip to avoid corrupt data.
            continue

        people_t1 = sum_block(row, t1_time_col)
        people_t2 = sum_block(row, t2_time_col)

        by_terminal_hour["T1"][t1_hour] = people_t1
        by_terminal_hour["T2"][t2_hour] = people_t2

    missing = {
        t: [h for h in range(24) if h not in hours]
        for t, hours in by_terminal_hour.items()
    }
    if any(missing[t] for t in ("T1", "T2")):
        raise ForecastFormatChangedError(
            "Parsed hours are incomplete; likely xls format changed. "
            f"Missing T1={missing['T1']} T2={missing['T2']}"
        )

    out: list[HourlyForecast] = []
    for terminal in ("T1", "T2"):
        for hour in range(24):
            out.append(
                HourlyForecast(
                    terminal=terminal, hour=hour, people=int(by_terminal_hour[terminal][hour])
                )
            )

    LOGGER.info("stage=parse ok items=%s", len(out))
    return out


def fetch_snapshot(headless: bool = True) -> ForecastSnapshot:
    """Fetch a snapshot of hourly passenger forecasts for T1 and T2."""
    fetched_at = datetime.now(tz=timezone.utc).isoformat()

    try:
        xls_url = discover_latest_xls_url(headless=headless)
    except Exception:
        LOGGER.exception("stage=discover failed")
        raise

    tmp_path = Path.cwd() / "data" / "_latest_forecast.xls"
    try:
        download_xls(xls_url, tmp_path)
    except Exception:
        LOGGER.exception("stage=download failed url=%s dest=%s", xls_url, tmp_path)
        raise

    try:
        items = parse_xls_hourly_totals(tmp_path)
    except Exception:
        LOGGER.exception("stage=parse failed path=%s", tmp_path)
        raise

    items = sorted(items, key=lambda i: (i.terminal, i.hour))

    return ForecastSnapshot(
        fetched_at_utc=fetched_at,
        source_url=FORECAST_URL,
        source_xls_url=xls_url,
        items=items,
    )


def write_snapshot(snapshot: ForecastSnapshot, out_dir: Path) -> tuple[Path, Path]:
    """Write snapshot as JSON + CSV (atomic writes)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("stage=write out_dir=%s items=%s", out_dir, len(snapshot.items))

    json_path = out_dir / "flightforecast_latest.json"
    csv_path = out_dir / "flightforecast_latest.csv"

    tmp_json = json_path.with_suffix(".json.tmp")
    tmp_csv = csv_path.with_suffix(".csv.tmp")

    payload = {
        "fetched_at_utc": snapshot.fetched_at_utc,
        "source_url": snapshot.source_url,
        "source_xls_url": snapshot.source_xls_url,
        "items": [asdict(i) for i in snapshot.items],
    }
    tmp_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_json.replace(json_path)

    with tmp_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["terminal", "hour", "people"])
        w.writeheader()
        for item in snapshot.items:
            w.writerow(asdict(item))
    tmp_csv.replace(csv_path)

    LOGGER.info("stage=write ok json=%s csv=%s", json_path, csv_path)
    return json_path, csv_path

