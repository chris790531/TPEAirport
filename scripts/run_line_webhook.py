"""Run LINE webhook server locally.

Usage:
  $env:LINE_CHANNEL_SECRET = "..."
  $env:LINE_CHANNEL_ACCESS_TOKEN = "..."
  .\.venv\Scripts\python -m scripts.run_line_webhook --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import logging

import uvicorn

from tpeairport.line_webhook import create_app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

