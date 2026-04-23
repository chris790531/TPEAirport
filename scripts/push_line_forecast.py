"""Fetch forecast and push as a LINE message.

Environment variables required:
- LINE_CHANNEL_ACCESS_TOKEN
- LINE_TARGET_ID (userId / groupId / roomId)
"""

from __future__ import annotations

import argparse
import logging
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from tpeairport.flightforecast import fetch_snapshot
from tpeairport.line_format import format_forecast_message


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Run browser headed (debug).")
    parser.add_argument("--top", type=int, default=6, help="Top N busiest hours per terminal.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    target = os.environ.get("LINE_TARGET_ID", "").strip()
    if not token:
        logging.error("缺少環境變數 LINE_CHANNEL_ACCESS_TOKEN")
        return 2
    if not target:
        logging.error("缺少環境變數 LINE_TARGET_ID（userId/groupId/roomId）")
        return 2

    snapshot = fetch_snapshot(headless=not args.headed)
    text = format_forecast_message(snapshot.items, snapshot.fetched_at_utc, top_n=args.top)

    config = Configuration(access_token=token)
    with ApiClient(config) as api_client:
        api = MessagingApi(api_client)
        api.push_message(
            PushMessageRequest(
                to=target,
                messages=[TextMessage(text=text)],
            )
        )

    logging.info("已推播到 LINE target=%s", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

