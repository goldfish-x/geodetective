from pathlib import Path
import os
# 世界篇冒烟：进入游戏 → 点击球面 → 确认 → 结算，无 JS 报错
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/#/game/world")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("#q-name", timeout=30000)
    print("[题目]", page.locator("#q-name").inner_text(), page.locator("#q-diff").inner_text())

    # 点击地球中心区域（应弹确认框）
    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.click(cx, cy)
    page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    page.click("#btn-confirm")
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
    detail = page.locator("#settle-detail").inner_text()
    print("[结算]", detail)
    assert "距离实际位置" in detail, "结算未给出距离"
    page.screenshot(path=str(ROOT / "tests" / "gd_world.png"))
    browser.close()
    assert not errors, f"JS 报错: {errors}"
    print("世界篇冒烟 ✅ 通过")
