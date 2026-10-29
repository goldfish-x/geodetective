# 完整流程回归：地理版 10 局 / 历史版 12 局全流程、终局成绩单、排行榜、超时与移动端视口
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
OUT = ROOT / "tests"
# 赛道：geo=地理版（城市+景点，10 局） / history=历史版（历史事件，12 局）
TRACKS = [("geo", "game", "地理版"), ("history", "history", "历史版")]

errors = []


def play_full(browser, route, label, tag):
    """跑完一整条赛道的全部局数，校验终局成绩单与进度点。"""
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append("[console] " + m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append("[%s-pageerror] %s" % (tag, e)))

    page.goto(BASE)
    page.evaluate("() => localStorage.clear()")
    page.fill("#nick-input", "夜行侦探")
    page.goto("%s/#/%s/china" % (BASE, route))
    page.wait_for_selector("#q-name", timeout=30000)
    page.wait_for_function("() => window.__gdDebug && window.__gdDebug.stages", timeout=10000)

    total_stages = page.evaluate("() => window.__gdDebug.stages.length")
    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def answer_question():
        page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=10000)
        page.mouse.click(cx, cy)
        page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
        page.click("#btn-confirm")
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
        page.click("#btn-next")

    for stage_index in range(total_stages):
        page.wait_for_function(
            "() => window.__gdDebug.state.stageIndex === %d && window.__gdDebug.state.qInStage === 0" % stage_index,
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
        assert "通 关" in page.locator(".ss-result").inner_text(), "第%d局未按门槛通过" % (stage_index + 1)
        page.click("#btn-stage-next")

    page.wait_for_selector(".result-page", timeout=10000)
    assert page.locator(".result-stamp").inner_text() == "完美结案"
    rows = page.locator(".result-list li").count()
    assert rows == total_stages * 8, "终局成绩单 %d 行 != %d" % (rows, total_stages * 8)
    cleared = page.locator(".stage-dot.cleared").count()
    assert cleared == total_stages, "终局进度点 %d != %d" % (cleared, total_stages)
    assert ("%d 局全部通关" % total_stages) in page.locator(".result-sub").inner_text()
    print("[完整对局·%s] %d 局 × 8 题 · %d 行成绩单 · 完美结案 ✓" % (label, total_stages, rows))
    print("[总分·%s]" % label, page.locator(".result-score em").inner_text())
    page.screenshot(path=str(OUT / ("%s-result.png" % tag)))

    # —— 返回首页，验证本机 Top 10 ——
    page.click("#btn-home")
    page.wait_for_selector(".board-list li:first-child", timeout=5000)
    print("[排行榜·%s]" % label, page.locator(".board-list li:first-child").inner_text())
    return page


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    geo_page = None
    for track, route, label in TRACKS:
        pg = play_full(browser, route, label, track)
        if track == "geo":
            geo_page = pg
        else:
            pg.close()

    # —— 世界篇：验证超时 0 分结算 ——
    page = geo_page
    page.goto("%s/#/" % BASE)
    page.wait_for_selector(".mode-card.world", timeout=10000)
    page.click(".mode-card.world")
    page.wait_for_selector("#q-name", timeout=30000)
    page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=10000)
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=30000)
    assert page.locator("#settle-title .grade").inner_text().strip() == "超 时"
    page.screenshot(path=str(OUT / "world-timeout.png"))
    print("[超时] 世界篇超时 → 0 分结算 ✓")

    # —— 重新生成单题结算画面截图（中国篇）——
    page.goto("%s/#/" % BASE)
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

    # —— 移动端视口：两个版本首页 + 历史版对局 ——
    mobile = browser.new_page(viewport={"width": 390, "height": 844})
    mobile.on("pageerror", lambda e: errors.append("[m-pageerror] %s" % e))
    for entry, name in (("index.html", "mobile-home.png"), ("history.html", "mobile-history-home.png")):
        mobile.goto("%s/%s" % (BASE, entry))
        mobile.wait_for_selector(".home-title", timeout=10000)
        mobile.screenshot(path=str(OUT / name))
    mobile.goto("%s/#/history/china" % BASE)
    mobile.wait_for_selector("#q-name", timeout=30000)
    mobile.screenshot(path=str(OUT / "mobile-history-game.png"))
    print("[移动端] 两版首页 + 历史版对局 ✓")
    mobile.close()

    browser.close()

if errors:
    for error in errors:
        print(error)
    raise AssertionError("页面错误 %d 个" % len(errors))

print("完整流程回归通过 ✅")
