# 道具体系回归（离线模式）：图标与次数、悬停说明、加时、回溯、透镜、复活标黄、档位门禁
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
fails = []

def counts(page):
    return page.evaluate("""() => [...document.querySelectorAll('[data-prop]')]
      .map(b => [b.dataset.prop, Number(b.querySelector('.prop-n').textContent), b.className.includes('used')])""")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1280, "height": 860})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))

    # —— 档位门禁：一档全 0，二档无回溯/透镜 ——
    for tier, want in ((1, {"time": 0, "revive": 0, "redo": 0, "area": 0}),
                       (2, {"time": 2, "revive": 2, "redo": 0, "area": 0}),
                       (3, {"time": 3, "revive": 2, "redo": 1, "area": 1})):
        page.goto(BASE + "/#/")
        page.wait_for_selector(".mode-card", timeout=10000)
        page.evaluate("t => localStorage.setItem('gd_tier', String(t))", tier)
        page.goto(BASE + "/#/game/china")
        page.wait_for_selector("#props-bar [data-prop]", timeout=15000)
        got = {k: n for k, n, _ in counts(page)}
        if got != want:
            fails.append(f"档位{tier} 道具次数 {got} != {want}")
    print("[档位] 1/2/3 档次数门禁 ✓")

    # —— 悬停说明 ——
    page.hover('[data-prop="revive"]')
    page.wait_for_selector("#prop-tip.show", timeout=3000)
    tip = page.locator("#prop-tip").inner_text()
    if "复活罗盘" not in tip or "标黄" not in tip:
        fails.append(f"悬停说明异常: {tip}")
    print("[悬停] 道具说明气泡:", tip.replace("\n", " / ")[:46])

    # —— 加时 +12s ——
    before = page.evaluate("() => window.__gdDebug.state.timerRemain")
    page.click('[data-prop="time"]')
    page.wait_for_timeout(300)
    after = page.evaluate("() => window.__gdDebug.state.timerRemain")
    if not (11.0 < after - before < 13.0):
        fails.append(f"加时增量 {after - before:.1f}s 不为 12s")
    print("[加时] 倒计时 +%.1fs ✓" % (after - before))

    # —— 回溯怀表：答两题后回退重做 ——
    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    for _ in range(2):
        page.mouse.click(cx, cy)
        page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
        page.click("#btn-confirm")
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
        page.click("#btn-next")
        page.wait_for_timeout(250)
    rec_before = page.evaluate("() => window.__gdDebug.state.records.length")
    tot_before = page.evaluate("() => window.__gdDebug.state.total")
    page.click('[data-prop="redo"]')
    page.wait_for_function("() => window.__gdDebug.state.qInStage === 0 && window.__gdDebug.state.phase === 'answering'", timeout=8000)
    rec_after = page.evaluate("() => window.__gdDebug.state.records.length")
    tot_after = page.evaluate("() => window.__gdDebug.state.total")
    if rec_after != rec_before - 2 or tot_after != tot_before:
        fails.append(f"回溯后记录 {rec_after}!={rec_before - 2} 或总分变化 {tot_after}!={tot_before}")
    print("[回溯] 回退 2 题，记录 %d→%d，总分不变（中心点 0 分）✓" % (rec_before, rec_after))

    # —— 疆域透镜：横幅 + 省份高亮截图 ——
    page.click('[data-prop="area"]')
    page.wait_for_selector("#hint-banner:not(.hidden)", timeout=3000)
    banner = page.locator("#hint-banner").inner_text()
    if "答案所在" not in banner:
        fails.append(f"透镜横幅异常: {banner}")
    page.screenshot(path=str(ROOT / "tests" / "gd_prop_area.png"))
    print("[透镜] 横幅:", banner)

    # —— 复活罗盘：第 1 局 0 分失败 → 复活进第 2 局 → 第 2 局再失败无复活 → 终局标黄 ——
    page.evaluate("() => { const d = window.__gdDebug; d.state.qInStage = 7; d.state.stageScore = 0; d.state.phase = 'settle' }")
    page.evaluate("() => document.getElementById('btn-next').click()")
    page.wait_for_selector(".stage-settle", timeout=10000)
    if page.locator("#btn-revive").count() != 1:
        fails.append("失败局未出现复活按钮")
    page.click("#btn-revive")
    page.wait_for_function("() => window.__gdDebug.state.stageIndex === 1 && window.__gdDebug.state.phase === 'answering'", timeout=8000)
    print("[复活] 第 1 局复活进入第 2 局 ✓")
    # 三档共 2 枚复活罗盘：第 2 局失败再用掉第 2 枚，第 3 局失败时才应无按钮
    page.evaluate("() => { const d = window.__gdDebug; d.state.qInStage = 7; d.state.stageScore = 0; d.state.phase = 'settle' }")
    page.evaluate("() => document.getElementById('btn-next').click()")
    page.wait_for_selector(".stage-settle", timeout=10000)
    if page.locator("#btn-revive").count() != 1:
        fails.append("第 2 局失败应仍有 1 枚复活罗盘")
    page.click("#btn-revive")
    page.wait_for_function("() => window.__gdDebug.state.stageIndex === 2 && window.__gdDebug.state.phase === 'answering'", timeout=8000)
    page.evaluate("() => { const d = window.__gdDebug; d.state.qInStage = 7; d.state.stageScore = 0; d.state.phase = 'settle' }")
    page.evaluate("() => document.getElementById('btn-next').click()")
    page.wait_for_selector(".stage-settle", timeout=10000)
    if page.locator("#btn-revive").count() != 0:
        fails.append("复活次数用尽后仍显示复活按钮")
    page.click("#btn-stage-next")
    page.wait_for_selector(".result-page", timeout=10000)
    dots = page.evaluate("() => [...document.querySelectorAll('.stage-dot')].map(d => d.className)")
    if "revived" not in dots[0] or "revived" not in dots[1]:
        fails.append(f"终局进度点未标黄: {dots[:3]}")
    note = page.locator(".result-revived-note").inner_text() if page.locator(".result-revived-note").count() else ""
    if "复活罗盘救回" not in note or "1" not in note:
        fails.append(f"复活说明缺失: {note}")
    page.wait_for_timeout(900)
    page.screenshot(path=str(ROOT / "tests" / "gd_prop_revive.png"))
    print("[标黄] 终局进度点与说明:", note)

    b.close()
    if errs:
        fails.append("页面报错: %s" % errs)

if fails:
    for f in fails:
        print("  ✗", f)
    raise SystemExit(1)
print("道具体系回归 ✅ 通过")
