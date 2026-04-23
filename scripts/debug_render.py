from __future__ import annotations

from playwright.sync_api import sync_playwright


def main() -> int:
    url = "https://www.taoyuanairport.com.tw/flightforecast"
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = b.new_context(
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        def on_failed(req):
            print("request_failed:", req.url, req.failure)

        page.on("requestfailed", on_failed)

        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        html = page.content()
        inner = page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
        print("title:", page.title())
        print("html_len:", len(html))
        print("inner_len:", len(inner))
        safe = (
            inner[:500]
            .replace("\n", "\\n")
            .encode("cp950", "backslashreplace")
            .decode("cp950")
        )
        print("inner_head:", safe)
        context.close()
        b.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

