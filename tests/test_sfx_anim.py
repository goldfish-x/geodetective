from pathlib import Path
import os
# 回归验证：音效模块无异常 + 动画反馈（判级标签/倒计时脉冲/局过关闪屏/静音开关）
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # —— 静音开关 ——
    page.goto(f"{BASE}/#/game/china")
    page.wait_for_selector("#q-name", timeout=20000)
    assert page.locator("#btn-snd").is_visible(), "静音按钮不存在"
    icon_on = page.locator("#btn-snd").inner_html()
    page.click("#btn-snd")
    icon_off = page.locator("#btn-snd").inner_html()
    assert icon_on != icon_off, "静音切换图标未变化"
    assert page.evaluate("() => localStorage.getItem('gd-muted')") == "1", "静音偏好未持久化"
    page.click("#btn-snd")  # 恢复
    assert page.evaluate("() => localStorage.getItem('gd-muted')") == "0"
    print("[静音] 开关切换 + localStorage 持久化 ✓")

    # —— 题目入场动画 ——
    assert "enter" in page.locator("#q-name").get_attribute("class"), "题目名缺少入场动画类"
    print("[动画] 题目名入场动画类 ✓")

    # —— 第1题：作答 → 判级标签 ——
    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.click(cx, cy)
    page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    page.click("#btn-confirm")
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
    grade = page.locator("#settle-title .grade")
    assert grade.count() == 1, "结算缺少判级标签"
    assert grade.inner_text().strip() in ("精 准", "接 近", "偏 远", "失 手"), grade.inner_text()
    assert "pop" in page.locator("#settle-pop").get_attribute("class"), "结算弹层缺少弹出动画类"
    print(f"[判定] 判级标签「{grade.inner_text().strip()}」+ 弹出动画 ✓")

    # —— 第2题：倒计时告急脉冲，随后自然超时（超时判级） ——
    page.wait_for_function(
        "() => window.__gdDebug.state.qInStage === 1 && window.__gdDebug.state.phase === 'answering'",
        timeout=10000,
    )
    page.wait_for_selector("#timer-text.pulse", timeout=20000)
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=15000)
    assert page.locator("#settle-title .grade").inner_text().strip() == "超 时"
    print("[倒计时] 最后 3 秒脉冲动画 + 超时判级 ✓")

    # —— 第3~8题：快速作答走完第1局（第8题前抬高局分以触发过关） ——
    def answer_and_wait(target_q, target_stage):
        # 等待结算弹层的 2.5s 自动等待期结束、进入答题阶段
        page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=10000)
        page.mouse.click(cx, cy)
        page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
        page.click("#btn-confirm")
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
        page.wait_for_function(
            f"() => window.__gdDebug.state.qInStage === {target_q} && window.__gdDebug.state.stageIndex === {target_stage}",
            timeout=10000,
        )

    for q in range(2, 7):        # 第3~7题（答完 qInStage 2→6）
        if q == 6:
            # 第7题答完后进入第8题前抬高局分
            page.evaluate("() => { window.__gdDebug.state.stageScore = 99999 }")
        answer_and_wait(q + 1, 0)

    # 第8题：作答后 → 局结算档案面板 → 通关 → 闪屏
    page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=10000)
    page.mouse.click(cx, cy)
    page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    page.click("#btn-confirm")
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
    page.wait_for_selector(".stage-settle", timeout=10000)
    page.click("#btn-stage-next")
    page.wait_for_selector(".stage-flash", timeout=3000)
    assert "通过" in page.locator(".stage-flash span").inner_text()
    print("[局过关] 档案面板 → 闪屏动效「第1局 通过」✓")

    # —— 终局：印章 + 进度点（注入未达标状态触发中止） ——
    page.wait_for_function("() => window.__gdDebug.state.phase === 'answering'", timeout=10000)
    page.evaluate("() => { const d = window.__gdDebug; d.state.qInStage = 7; d.state.stageScore = 0; }")
    page.evaluate("() => document.getElementById('btn-next').click()")
    page.wait_for_selector(".stage-settle", timeout=10000)
    page.click("#btn-stage-next")
    page.wait_for_selector(".result-page", timeout=10000)
    assert page.locator(".result-stamp").count() == 1, "缺少印章"
    dots = page.locator(".stage-dot.cleared").count()
    assert dots == 1, f"已通关进度点 {dots} != 1"
    assert page.locator(".result-stamp").inner_text() == "任务中止"
    print(f"[终局] 印章「任务中止」+ 进度点（已通关 {dots} 局）✓")

    browser.close()
    assert not errors, f"页面 JS 报错: {errors}"

print("全部通过 ✅")
