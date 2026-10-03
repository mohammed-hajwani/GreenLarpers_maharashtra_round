import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

CONTRAST_JS = """() => {
  const lum = c => { const v = c.match(/\\d+(\\.\\d+)?/g).slice(0, 3).map(Number).map(x => x / 255)
    .map(x => x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const bg = 'rgb(15, 13, 26)';
  const pick = sel => { const el = document.querySelector(sel); return el ? getComputedStyle(el).color : null; };
  const out = {};
  for (const sel of ['.rl-question', '.rl-subtitle', '.rl-progress-text', '.rl-footer']) {
    const c = pick(sel); if (c) out[sel] = Math.round(ratio(c, bg) * 100) / 100;
  }
  return out;
}"""


def settle(page) -> None:
    page.wait_for_timeout(1500)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60000)
    page.wait_for_timeout(400)


def run(base: str) -> dict:
    result = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, color_scheme="dark")
        page.goto(base)
        page.get_by_role("button", name="Start guided demo").wait_for(timeout=120000)
        settle(page)
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        focused = page.evaluate(
            "() => { const e = document.activeElement; const s = getComputedStyle(e);"
            " return {tag: e.tagName, text: e.innerText.trim().slice(0, 40),"
            " outline: s.outlineStyle + ' ' + s.outlineWidth}; }"
        )
        result["tab_focus"] = focused
        page.get_by_role("button", name="Start: Force vs Motion").click()
        settle(page)
        result["contrast_vs_background"] = page.evaluate(CONTRAST_JS)
        field = page.get_by_label("Your answer")
        if field.get_attribute("type") == "text":
            field.fill("100 N forward")
            page.get_by_label("Your thinking (a sentence helps us help you)").fill("it needs a push to keep moving")
            field.press("Enter")
            settle(page)
            result["enter_submits_answer"] = page.locator('[role="status"][aria-live="polite"]').count() > 0
        else:
            result["enter_submits_answer"] = "question was multiple choice; keyboard path is Tab plus Space then Enter"
        live = page.locator('[role="status"][aria-live="polite"]')
        result["live_region_text"] = live.first.inner_text() if live.count() else ""
        result["icon_plus_text"] = any(ch in result["live_region_text"] for ch in "✓✗→!↺")
        page.close()
        reduced = browser.new_page(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
        reduced.goto(base)
        reduced.get_by_role("button", name="Start guided demo").wait_for(timeout=120000)
        settle(reduced)
        result["reduced_motion_animation"] = reduced.evaluate(
            "() => getComputedStyle(document.querySelector('[class*=\"st-key-rl-card\"]')).animationName"
        )
        reduced.close()
        browser.close()
    return result


if __name__ == "__main__":
    data = run(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501/")
    (ROOT / "docs" / "test_runs" / "a11y_check.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2, ensure_ascii=False))
