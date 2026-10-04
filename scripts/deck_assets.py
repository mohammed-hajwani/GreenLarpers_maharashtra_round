from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from relearn.multimodal.diagrams import diagram_svg
from relearn.multimodal.simulations import simulation_html

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "deck" / "assets"
BASE = "http://localhost:8501/"
CROPS = {
    "landing": (500, 60, 2060, 1720),
    "hint": (500, 0, 2060, 1720),
    "reveal_diagram": (500, 0, 2060, 1720),
    "explain_back": (500, 0, 2060, 1720),
    "insights_trace": (740, 100, 2440, 1720),
    "insights_map": (740, 0, 2440, 1720),
}


def settle(page, ms: int = 1500) -> None:
    page.wait_for_timeout(ms)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=90000)
    page.wait_for_timeout(400)


def next_step(page, times: int = 1) -> None:
    for _ in range(times):
        page.get_by_role("button", name="Next step").click()
        settle(page, 1200)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 860}, color_scheme="dark", device_scale_factor=2)
        page.goto(BASE + "?view=learn")
        page.get_by_role("button", name="Start guided demo").wait_for(timeout=120000)
        settle(page)
        page.screenshot(path=str(OUT / "landing.png"))
        page.get_by_role("button", name="Start guided demo").click()
        settle(page)
        next_step(page, 2)
        page.locator(".st-key-rl-feedback-card").first.scroll_into_view_if_needed()
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "hint.png"))
        next_step(page, 3)
        page.locator(".rl-visual").first.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "reveal_diagram.png"))
        next_step(page, 11)
        page.locator(".st-key-rl-question-card").first.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / "explain_back.png"))
        page.goto(BASE + "?view=insights&learner=guided-demo")
        page.get_by_text("Class misconception map").first.wait_for(timeout=90000)
        settle(page)
        page.screenshot(path=str(OUT / "insights_map.png"))
        page.get_by_text("Student decisions").first.click()
        settle(page)
        page.get_by_text("AI Decision Trace").first.click()
        settle(page, 800)
        page.get_by_text("Why did the AI make this prediction?").first.click()
        settle(page, 800)
        page.screenshot(path=str(OUT / "insights_trace.png"), full_page=False)
        sim = browser.new_page(device_scale_factor=2)
        sim.set_viewport_size({"width": 680, "height": 470})
        sim.set_content(simulation_html("M01"))
        sim.get_by_role("button", name="Push once").click()
        sim.wait_for_timeout(1300)
        sim.screenshot(path=str(OUT / "simulation_m01.png"))
        sheet = browser.new_page(device_scale_factor=2)
        sheet.set_viewport_size({"width": 920, "height": 600})
        style = "margin:0;background:#181526;padding:20px"
        sheet.set_content(f'<html><body style="{style}">{diagram_svg("M01")}</body></html>')
        sheet.screenshot(path=str(OUT / "diagram_m01.png"))
        browser.close()
    crop()
    print(sorted(x.name for x in (OUT / "crops").iterdir()))


def crop() -> None:
    (OUT / "crops").mkdir(exist_ok=True)
    for shot in OUT.glob("*.png"):
        image = Image.open(shot)
        box = CROPS.get(shot.stem)
        (image.crop(box) if box else image).save(OUT / "crops" / shot.name)


if __name__ == "__main__":
    main()
