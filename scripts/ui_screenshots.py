import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
WIDTHS = (375, 768, 1280)
BANNED = [
    "decision trace",
    "why the ai",
    "sources used",
    "strategy",
    "model evaluation",
    "confidence",
    "probability",
    "misconception",
]


def settle(page: Page, ms: int = 1800) -> None:
    page.wait_for_timeout(ms)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60000)
    page.wait_for_timeout(400)


def click(page: Page, label: str) -> None:
    page.get_by_role("button", name=label, exact=True).first.click()
    settle(page)


def measure(page: Page) -> dict:
    return page.evaluate(
        "() => {"
        "const visible = b => b.offsetParent !== null && b.innerText.trim();"
        "const buttons = [...document.querySelectorAll('button')].filter(visible);"
        "const size = b => ({t: b.innerText.trim().slice(0, 40), h: Math.round(b.getBoundingClientRect().height)});"
        "const small = buttons.map(size).filter(x => x.h < 44);"
        "const scroll = document.documentElement.scrollWidth > window.innerWidth;"
        "return {horizontal_scroll: scroll, small_buttons: small, text: document.body.innerText};"
        "}"
    )


def shot(page: Page, name: str, width: int, report: dict) -> None:
    folder = OUT / f"w{width}"
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / f"{name}.png"), full_page=True)
    m = measure(page)
    text = m.pop("text").lower()
    m["banned"] = [b for b in BANNED if b in text]
    report.setdefault(str(width), {})[name] = m


def run(base: str) -> dict:
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in WIDTHS:
            page = browser.new_page(viewport={"width": width, "height": 900}, color_scheme="dark")
            page.goto(base)
            page.get_by_role("button", name="Start guided demo").wait_for(timeout=120000)
            settle(page)
            shot(page, "01_landing", width, report)
            click(page, "Start guided demo")
            shot(page, "02_question", width, report)
            click(page, "Next step")
            shot(page, "03_quick_check", width, report)
            click(page, "Next step")
            shot(page, "04_incorrect_hint", width, report)
            click(page, "Next step")
            click(page, "Next step")
            shot(page, "05_second_hint", width, report)
            click(page, "Next step")
            shot(page, "06_revealed", width, report)
            click(page, "Next step")
            click(page, "Next step")
            shot(page, "07_correct", width, report)
            click(page, "Next step")
            shot(page, "08_lock_in", width, report)
            click(page, "Exit demo")
            click(page, "Continue learning")
            shot(page, "09_live_lesson", width, report)
            page.goto(base + "?view=insights")
            page.get_by_text("Re:Learn Insights").first.wait_for(timeout=60000)
            settle(page)
            folder = OUT / f"w{width}"
            page.screenshot(path=str(folder / "10_insights.png"), full_page=True)
            page.close()
        browser.close()
    return report


if __name__ == "__main__":
    result = run(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501/")
    (OUT / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for width, states in result.items():
        for name, m in states.items():
            print(
                width,
                name,
                "hscroll" if m["horizontal_scroll"] else "ok",
                "small:",
                m["small_buttons"],
                "banned:",
                m["banned"],
            )
