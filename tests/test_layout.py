from pathlib import Path
import os
import math
# 结算卡 / 局档案面板不得遮挡地图：改为独立栏位后，卡片与地图包围盒重叠面积必须为 0
# 覆盖 3 种视口 × 中国篇/世界篇 × 结算卡/局档案 = 12 组
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
OUT = ROOT / "tests"


def overlap(a, b):
    if not a or not b:
        return 0
    w = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
    h = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
    return max(0, w) * max(0, h)


def settle_card(page, mode):
    page.goto(f"{BASE}/#/game/{mode}")
    page.wait_for_selector("#q-name", timeout=30000)
    page.wait_for_function("() => window.__gdDebug", timeout=10000)
    page.wait_for_timeout(2000 if mode == "world" else 400)
    box = page.locator("#map-holder").bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    page.click("#btn-confirm")
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
    page.wait_for_timeout(1600)


def stage_panel(page):
    if page.evaluate("() => window.__gdDebug.state.phase") == "settle":
        page.click("#btn-next")
    page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=8000)
    page.evaluate("() => { window.__gdDebug.state.qInStage = 7; window.__gdDebug.state.stageScore = 99999 }")
    box = page.locator("#map-holder").bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    page.click("#btn-confirm")
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
    page.click("#btn-next")
    page.wait_for_selector(".stage-settle", timeout=10000)
    page.wait_for_timeout(600)


fails = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for w, h, tag in [(1280, 800, "desk"), (1440, 900, "wide"), (390, 844, "mob")]:
        page = browser.new_page(viewport={"width": w, "height": h})
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        for mode in ("china", "world"):
            settle_card(page, mode)
            mb = page.locator("#map-holder").bounding_box()
            cb = page.locator("#settle-pop").bounding_box()
            ov = overlap(mb, cb)
            print(f"[{tag} {mode}] 结算卡 vs 地图 重叠 {ov:.0f}px²  卡 {cb['width']:.0f}x{cb['height']:.0f}  地图 {mb['width']:.0f}x{mb['height']:.0f}")
            if ov:
                fails.append(f"{tag}/{mode} 结算卡遮挡地图 {ov:.0f}px²")
            page.screenshot(path=str(OUT / f"layout-{tag}-{mode}-settle.png"))

            stage_panel(page)
            page.locator(".ss-chip").nth(0).hover()
            page.wait_for_timeout(900)
            mb = page.locator("#map-holder").bounding_box()
            pb = page.locator(".stage-settle").bounding_box()
            ov = overlap(mb, pb)
            print(f"[{tag} {mode}] 局档案 vs 地图 重叠 {ov:.0f}px²  面板 {pb['width']:.0f}x{pb['height']:.0f}")
            if ov:
                fails.append(f"{tag}/{mode} 局档案遮挡地图 {ov:.0f}px²")
            # 主操作按钮必须在视口内可见
            btn = page.locator("#btn-stage-next").bounding_box()
            if btn["y"] < 0 or btn["y"] + btn["height"] > h:
                fails.append(f"{tag}/{mode} 局档案主按钮超出视口")
            page.screenshot(path=str(OUT / f"layout-{tag}-{mode}-stage.png"))
            page.goto(f"{BASE}/#/")
            page.wait_for_timeout(300)
        if errs:
            fails.append(f"{tag} 页面报错 {errs}")
        page.close()
    browser.close()

assert not fails, "遮挡回归：\n  " + "\n  ".join(fails)
print("全部通过 ✅")
