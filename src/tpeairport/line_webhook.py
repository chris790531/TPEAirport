"""LINE webhook server (reply mode, not push).

Env:
- LINE_CHANNEL_SECRET
- LINE_CHANNEL_ACCESS_TOKEN
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from tpeairport.flightforecast import fetch_snapshot
from tpeairport.line_format import format_forecast_message


LOGGER = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # Optional dependency; environment variables can still be provided by OS.
    pass


def _get_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


@dataclass
class _Cache:
    ts: float = 0.0
    text: str = ""
    now_text: str = ""


_cache = _Cache()


def _build_reply_text(command: str) -> str:
    cmd = command.strip().lower()

    # Cache to avoid hitting the airport site too often under bursts.
    ttl_sec = 600
    now = time.time()

    if cmd in ("forecast", "f", "help", "?"):
        if _cache.text and (now - _cache.ts) <= ttl_sec:
            return _cache.text
        snapshot = fetch_snapshot(headless=True)
        text = format_forecast_message(snapshot.items, snapshot.fetched_at_utc, top_n=6)
        _cache.ts = now
        _cache.text = text
        return text

    if cmd in ("now", "n", "現在"):
        if _cache.now_text and (now - _cache.ts) <= ttl_sec:
            return _cache.now_text
        snapshot = fetch_snapshot(headless=True)
        items = snapshot.items
        # Find current UTC hour; note: airport data is local, but "hour buckets" are 0-23
        # so we present "現在(台灣時間)" using Asia/Taipei offset (+8).
        tw_hour = (datetime.now(tz=timezone.utc).hour + 8) % 24
        t1 = next((i.people for i in items if i.terminal == "T1" and i.hour == tw_hour), None)
        t2 = next((i.people for i in items if i.terminal == "T2" and i.hour == tw_hour), None)
        text = "\n".join(
            [
                "桃園機場 整點人數預估（現在）",
                f"台灣時間 {tw_hour:02d}:00",
                f"T1：{t1:,}" if t1 is not None else "T1：無資料",
                f"T2：{t2:,}" if t2 is not None else "T2：無資料",
            ]
        )
        _cache.ts = now
        _cache.now_text = text
        return text

    return "\n".join(
        [
            "可用指令：",
            "- forecast：回傳 T1/T2 高峰時段（top6）",
            "- now：回傳目前這個整點（台灣時間）T1/T2",
        ]
    )


def create_app() -> FastAPI:
    secret = _get_env("LINE_CHANNEL_SECRET")
    token = _get_env("LINE_CHANNEL_ACCESS_TOKEN")

    handler = WebhookHandler(secret)
    config = Configuration(access_token=token)

    app = FastAPI()

    @handler.add(MessageEvent, message=TextMessageContent)
    def on_text(event: MessageEvent) -> None:
        text_in = (event.message.text or "").strip()
        reply_text = _build_reply_text(text_in)
        with ApiClient(config) as api_client:
            api = MessagingApi(api_client)
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)],
                )
            )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/callback")
    async def callback(
        request: Request,
        x_line_signature: str | None = Header(default=None, alias="X-Line-Signature"),
    ) -> dict[str, bool]:
        if not x_line_signature:
            raise HTTPException(status_code=400, detail="Missing X-Line-Signature")
        body = await request.body()
        try:
            handler.handle(body.decode("utf-8"), x_line_signature)
        except Exception as e:  # noqa: BLE001
            LOGGER.exception("webhook handle failed: %s", e)
            raise HTTPException(status_code=400, detail="Invalid signature or payload") from e
        return {"ok": True}

    return app

