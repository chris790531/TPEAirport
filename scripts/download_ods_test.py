from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    url = "https://www.taoyuan-airport.com/uploads/fos/2026_04_24.ods"
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = b.new_context(
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.goto("https://www.taoyuanairport.com.tw/flightforecast", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        resp = page.request.get(url)
        print("status:", resp.status)
        print("content-type:", resp.headers.get("content-type"))
        out = Path("data") / "sample_pw.ods"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(resp.body())
        print("wrote:", out, "bytes:", out.stat().st_size)

        ctx.close()
        b.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

