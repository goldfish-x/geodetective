# 完整流程回归：10 局 × 8 题、终局成绩单、排行榜、超时与移动端视口
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
OUT = ROOT / "tests"

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # —— 桌面端：中国篇完整 10 局 × 8 题 ——
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append("[console] " + m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append("[pageerror] " + str(e)))

    page.goto(BASE)
    page.evaluate("() => localStorage.clear()")
    page.fill("#nick-input", "夜行侦探")
    page.click(".mode-card.china")
    page.wait_for_selector("#q-name", timeout=30000)
    page.wait_for_function("() => window.__gdDebug && window.__gdDebug.stages", timeout=10000)

    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def answer_question():
        page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=10000)
        page.mouse.click(cx, cy)
        page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
        page.click("#btn-confirm")
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
        page.click("#btn-next")

    for stage_index in range(10):
        page.wait_for_function(
            f"() => window.__gdDebug.state.stageIndex === {stage_index} && window.__gdDebug.state.qInStage === 0",
            timeout=10000,
        )
        # 流程回归关注关卡推进；这里注入门槛分，避免随机题目中心点击导致提前中止。
        page.evaluate(
            "() => { const d = window.__gdDebug; d.state.stageScore = d.stages[d.state.stageIndex].minScore; }"
        )

        for _ in range(8):
            answer_question()

        page.wait_for_selector(".stage-settle", timeout=10000)
        assert page.locator(".ss-chip").count() == 8, "局结算缺少 8 个地名"
        assert "通 关" in page.locator(".ss-result").inner_text(), f"第{stage_index + 1}局未按门槛通过"
        page.click("#btn-stage-next")

    page.wait_for_selector(".result-page", timeout=10000)
    assert page.locator(".result-stamp").inner_text() == "完美结案"
    assert page.locator(".result-list li").count() == 80, "终局成绩单不是 80 行"
    assert page.locator(".stage-dot.cleared").count() == 10, "终局进度点不是 10 个"
    print("[完整对局] 10 局 × 8 题 · 80 行成绩单 · 完美结案 ✓")
    print("[总分]", page.locator(".result-score em").inner_text())
    page.screenshot(path=str(OUT / "china-result.png"))

    # —— 返回首页，验证 Top 10 ——
    page.click("#btn-home")
    page.wait_for_selector(".board-list li:first-child", timeout=5000)
    print("[排行榜]", page.locator(".board-list li:first-child").inner_text())

    # —— 世界篇：验证超时 0 分结算 ——
    page.click(".mode-card.world")
    page.wait_for_selector("#q-name", timeout=30000)
    page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=10000)
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=30000)
    assert page.locator("#settle-title .grade").inner_text().strip() == "超 时"
    page.screenshot(path=str(OUT / "world-timeout.png"))
    print("[超时] 世界篇超时 → 0 分结算 ✓")

    # —— 重新生成单题结算画面截图（中国篇） ——
    page.goto(f"{BASE}/#/")
    page.wait_for_selector(".mode-card.china", timeout=10000)
    page.click(".mode-card.china")
    page.wait_for_selector("#q-name", timeout=30000)
    box = page.locator("#map-holder").bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    page.click("#btn-confirm")
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
    page.screenshot(path=str(OUT / "china-settle.png"))
    print("[结算画面] 精准度刻度 + 新结算卡截图已生成 ✓")
    page.close()

    # —— 移动端视口 ——
    mobile = browser.new_page(viewport={"width": 390, "height": 844})
    mobile.on("pageerror", lambda e: errors.append("[m-pageerror] " + str(e)))
    mobile.goto(BASE)
    mobile.wait_for_selector(".home-title", timeout=10000)
    mobile.screenshot(path=str(OUT / "mobile-home.png"))
    mobile.click(".mode-card.china")
    mobile.wait_for_selector("#q-name", timeout=30000)
    box = mobile.locator("#map-holder").bounding_box()
    mobile.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    mobile.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    mobile.screenshot(path=str(OUT / "mobile-game.png"))
    print("[移动端] 首页与游戏确认流程 ✓")
    mobile.close()

    browser.close()

if errors:
    for error in errors:
        print(error)
    raise AssertionError(f"页面错误 {len(errors)} 个")

print("完整流程回归通过 ✅")
