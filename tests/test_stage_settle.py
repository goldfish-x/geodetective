from pathlib import Path
import os
# 局结算「地名档案」：数据校验 + 面板交互（悬停简介/配图/红点）+ 世界篇地球转向
import json
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
# —— 1. 档案数据校验 ——
for bank_name, desc_name in (("china", "china-desc"), ("world", "world-desc")):
    with open(rf"{ROOT}\web\src\data\{bank_name}.json", encoding="utf-8") as f:
        bank = json.load(f)
    with open(rf"{ROOT}\web\src\data\{desc_name}.json", encoding="utf-8") as f:
        desc = json.load(f)
    all_q = bank["cities"] + bank["scenics"]
    assert len(desc) == 400, f"{desc_name} 条目 {len(desc)} != 400"
    img_cnt = 0
    for q in all_q:
        e = desc.get(q["name"])
        assert e, f"缺少档案: {q['name']}"
        L = len(e["desc"])
        assert 100 <= L <= 200, f"{q['name']} 简介 {L} 字"
        if q["difficulty"] <= 2:
            assert e.get("img"), f"{q['name']}（难度{q['difficulty']}）缺少配图 prompt"
            img_cnt += 1
        else:
            assert not e.get("img"), f"{q['name']}（难度{q['difficulty']}）不应有配图"
    print(f"[档案] {desc_name}: 400 条 · 配图 {img_cnt} 条 ✓")

with open(rf"{ROOT}\web\src\data\china-desc.json", encoding="utf-8") as f:
    CDESC = json.load(f)

def play_stage(page, cx, cy):
    """快速答完当前局 8 题（中心点击 → 确认 → 点「下一题」）"""
    for _ in range(8):
        page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=10000)
        page.mouse.click(cx, cy)
        page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
        page.click("#btn-confirm")
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
        page.click("#btn-next")  # 结算后由玩家点击推进（已取消自动跳题）

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # —— 2. 中国篇：通关 → 档案面板 ——
    page.goto(f"{BASE}/#/game/china")
    page.wait_for_selector("#q-name", timeout=20000)
    page.wait_for_function("() => window.__gdDebug", timeout=10000)
    page.evaluate("() => { window.__gdDebug.state.stageScore = 99999 }")
    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    play_stage(page, cx, cy)

    page.wait_for_selector(".stage-settle", timeout=10000)
    stage_names = page.evaluate("() => window.__gdDebug.stages[0].questions.map(q => q.name)")
    chips = page.locator(".ss-chip")
    assert chips.count() == 8, f"档案面板地名 {chips.count()} != 8"
    for i, n in enumerate(stage_names):
        assert n in chips.nth(i).inner_text(), f"第{i+1}个地名不符"
    assert "通 关" in page.locator(".ss-result").inner_text()
    print(f"[面板] 8 地名列出: {'、'.join(stage_names[:3])}… ✓")

    # 悬停第 1 个地名：简介 + 坐标 + 配图（难度1 → 必有配图）+ 红点
    chips.nth(0).hover()
    page.wait_for_timeout(600)
    name0 = stage_names[0]
    assert name0 in page.locator(".ss-name").inner_text()
    assert page.locator(".ss-desc").inner_text().strip() == CDESC[name0]["desc"].strip(), "简介内容与数据不符"
    assert page.locator(".ss-geo").inner_text().startswith("华北地区") or "°" in page.locator(".ss-geo").inner_text()
    imgs = page.locator(".ss-img")
    assert imgs.count() == 1, "著名地点缺少配图"
    src = imgs.get_attribute("src")
    assert src and (src.startswith('/images/') or src.startswith('/geodetective/images/') or src.startswith('data:image/')), src
    print(f"[悬停] 「{name0}」简介/坐标/配图 ✓")

    # 红点视觉验证截图
    page.screenshot(path=str(ROOT / "tests" / "gd_ss_china.png"))

    # 悬停第 2 个地名：档案切换
    chips.nth(1).hover()
    page.wait_for_timeout(400)
    assert stage_names[1] in page.locator(".ss-name").inner_text()
    print("[悬停] 档案切换 ✓")

    # 进入第 2 局
    page.click("#btn-stage-next")
    page.wait_for_function(
        "() => window.__gdDebug.state.stageIndex === 1 && window.__gdDebug.state.phase === 'answering'",
        timeout=10000)
    print("[流程] 面板继续 → 第2局 ✓")

    # —— 3. 世界篇：地球转向红点 ——
    page.goto(f"{BASE}/#/")
    page.wait_for_selector(".mode-card", timeout=10000)
    page.goto(f"{BASE}/#/game/world")
    page.wait_for_selector("#q-name", timeout=30000)
    page.wait_for_function("() => window.__gdDebug", timeout=10000)
    page.evaluate("() => { window.__gdDebug.state.stageScore = 99999 }")
    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    play_stage(page, cx, cy)

    page.wait_for_selector(".stage-settle", timeout=10000)
    page.locator(".ss-chip").first.hover()
    page.wait_for_timeout(1800)  # 等地球转向动画
    page.screenshot(path=str(ROOT / "tests" / "gd_ss_world.png"))
    assert page.locator(".ss-desc").inner_text().strip(), "世界篇档案简介为空"
    page.click("#btn-stage-next")
    page.wait_for_function(
        "() => window.__gdDebug.state.stageIndex === 1 && window.__gdDebug.state.phase === 'answering'",
        timeout=10000)
    print("[世界篇] 档案面板 + 地球转向红点截图 ✓")

    browser.close()
    assert not errors, f"页面 JS 报错: {errors}"

print("全部通过 ✅")
