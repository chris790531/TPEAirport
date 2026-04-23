from __future__ import annotations

from playwright.sync_api import sync_playwright


def main() -> int:
    url = "https://www.taoyuanairport.com.tw/flightforecast"
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
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        links = page.eval_on_selector_all(
            "a",
            "() => Array.from(document.querySelectorAll('a')).map(a => ({text: (a.textContent||'').trim(), href: a.href}))",
        )
        for l in links:
            href = l.get("href", "")
            txt = l.get("text", "")
            if any(href.lower().endswith(ext) for ext in [".xls", ".xlsx", ".ods"]):
                print(txt, href)
        ctx.close()
        b.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

