"""CLI to fetch and persist TPE flightforecast hourly people estimates."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from tpeairport.flightforecast import (
    ForecastDownloadError,
    ForecastFormatChangedError,
    ForecastSourceNotFoundError,
    fetch_snapshot,
    write_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[1] / "data"),
        help="Output directory (default: ./data)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (for debugging).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    try:
        snapshot = fetch_snapshot(headless=not args.headed)
        json_path, csv_path = write_snapshot(snapshot, Path(args.out))
        logging.info("Wrote %s", json_path)
        logging.info("Wrote %s", csv_path)
        return 0
    except ForecastSourceNotFoundError as e:
        logging.error("找不到最新的 xls 連結：%s", e)
        return 2
    except ForecastDownloadError as e:
        logging.error("下載 xls 失敗：%s", e)
        return 3
    except ForecastFormatChangedError as e:
        logging.error("xls 格式疑似改版，解析失敗：%s", e)
        return 4
    except Exception:
        logging.exception("未知錯誤")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

