from pathlib import Path
import os
# 回归验证：300 题题库 + 10 局关卡结构 + 局门槛中止/晋级路径
import json
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
# ———— 1. 题库静态校验 ————
CHINA_HINTS = {"华北地区", "东北地区", "华东地区", "华中地区", "华南地区", "西南地区", "西北地区"}
WORLD_HINTS = {"亚洲", "欧洲", "非洲", "北美洲", "南美洲", "大洋洲"}

for bank_name, hints in (("china", CHINA_HINTS), ("world", WORLD_HINTS)):
    with open(rf"{ROOT}\src\data\{bank_name}.json", encoding="utf-8") as f:
        bank = json.load(f)
    for kind in ("cities", "scenics"):
        items = bank[kind]
        names = [q["name"] for q in items]
        assert len(items) == 150, f"{bank_name}.{kind} 数量 {len(items)} != 150"
        assert len(set(names)) == 150, f"{bank_name}.{kind} 存在重复题目"
        for lv in range(1, 6):
            cnt = sum(1 for q in items if q["difficulty"] == lv)
            assert cnt == 30, f"{bank_name}.{kind} 难度{lv} 数量 {cnt} != 30"
        for q in items:
            assert q["hint"] in hints, f"{bank_name}.{kind} 非法 hint: {q['hint']}"
            assert isinstance(q["lat"], (int, float)) and -90 <= q["lat"] <= 90
            assert isinstance(q["lng"], (int, float)) and -180 <= q["lng"] <= 180
    print(f"[题库] {bank_name}: 共 {len(bank['cities']) + len(bank['scenics'])} 题 ✓")

# ———— 2. 浏览器验证 ————
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # —— 2a. 关卡结构与晋级路径（中国篇：第1局 → 第2局） ——
    page.goto(f"{BASE}/#/game/china")
    page.wait_for_selector("#q-name", timeout=20000)
    page.wait_for_function("() => window.__gdDebug && window.__gdDebug.stages", timeout=10000)

    info = page.evaluate("""() => {
      const { stages } = window.__gdDebug
      const names = stages.flatMap(s => s.questions.map(q => q.name))
      return {
        stageCount: stages.length,
        sizes: stages.map(s => s.questions.length),
        types: stages.map(s => s.type),
        diffs: stages.map(s => s.difficulty),
        mins: stages.map(s => s.minScore),
        unique: new Set(names).size === names.length,
        qTypesOk: stages.every(s => s.questions.every(q => q.type === s.type && q.difficulty === s.difficulty))
      }
    }""")
    assert info["stageCount"] == 10, f"局数 {info['stageCount']} != 10"
    assert all(s == 8 for s in info["sizes"]), f"每局题数异常: {info['sizes']}"
    assert info["types"] == ["city", "scenic"] * 5, f"类型交替异常: {info['types']}"
    assert info["diffs"] == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5], f"难度递增异常: {info['diffs']}"
    assert all(info["mins"][i] < info["mins"][i + 1] for i in range(9)), f"门槛递增异常: {info['mins']}"
    assert info["unique"], "80 题存在重复"
    assert info["qTypesOk"], "局内题目类型/难度与关卡配置不符"
    print(f"[结构] 10局×8题，门槛 {info['mins']} ✓")

    # 使用线索道具（验证道具可用 + 本局标记 used）
    page.click("#prop-hint")
    page.wait_for_selector("#hint-banner:not(.hidden)", timeout=3000)
    assert "used" in page.locator("#prop-hint").get_attribute("class"), "道具未标记 used"

    # 快速作答前 7 题（点地图中心 → 确认 → 点「下一题」）
    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    for i in range(7):
        page.mouse.click(cx, cy)
        page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
        page.click("#btn-confirm")
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
        # 玩家点击「下一题」才会推进（无自动跳题）
        page.click("#btn-next")
        page.wait_for_function(
            f"() => window.__gdDebug.state.qInStage === {i + 1} && window.__gdDebug.state.phase === 'answering'",
            timeout=10000,
        )

    # 第 8 题前抬高本局分数，验证局门槛晋级逻辑
    page.evaluate("() => { window.__gdDebug.state.stageScore = 99999 }")
    page.mouse.click(cx, cy)
    page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    page.click("#btn-confirm")
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
    page.click("#btn-next")  # 第 8 题结算后点击「查看本局档案」
    # 局结算档案面板出现（通关）
    page.wait_for_selector(".stage-settle", timeout=10000)
    assert page.locator(".ss-chip").count() == 8, "档案面板缺少 8 个地名"
    assert "通 关" in page.locator(".ss-result").inner_text()
    page.click("#btn-stage-next")
    page.wait_for_function(
        "() => window.__gdDebug.state.stageIndex === 1 && window.__gdDebug.state.phase === 'answering'",
        timeout=10000,
    )

    # 第 2 局界面断言
    assert page.locator("#q-index").inner_text() == "第2局 · 01/08", page.locator("#q-index").inner_text()
    assert page.locator("#q-badge").inner_text() == "景点"
    assert page.locator("#q-diff").inner_text() == "★☆☆☆☆"
    assert page.locator("#q-target").inner_text() == "9,000"
    assert page.locator("#q-stage-score").inner_text() == "0"
    assert "used" not in page.locator("#prop-hint").get_attribute("class"), "道具未按局重置"
    assert "danger" not in page.locator("#q-stage-wrap").get_attribute("class")
    print("[晋级] 第1局达标 → 第2局（景点·简单·门槛9000），道具已重置 ✓")
    page.screenshot(path=str(ROOT / "tests" / "gd_stage2.png"))

    # —— 2b. 门槛中止路径（第1局全部超时 → 0 分中止） ——
    # 先回首页再进入，确保 hash 变化触发路由重建游戏状态（goto 相同 hash 不会重载）
    page.goto(f"{BASE}/#/")
    page.wait_for_selector(".mode-card", timeout=10000)
    page.goto(f"{BASE}/#/game/china")
    page.wait_for_selector("#q-name", timeout=20000)
    page.wait_for_function("() => window.__gdDebug && window.__gdDebug.stages", timeout=10000)
    for i in range(8):
        # 超时自动结算（中国篇每题 15 秒）
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=30000)
        page.click("#btn-next")  # 超时结算后同样需要点击推进（第 8 题 → 局结算面板）
        if i < 7:
            page.wait_for_function(
                f"() => window.__gdDebug.state.qInStage === {i + 1} && window.__gdDebug.state.phase === 'answering'",
                timeout=10000,
            )
    # 第 8 题超时结算后 → 局结算档案面板（未达标）→ 结束本局任务
    page.wait_for_selector(".stage-settle", timeout=15000)
    assert "未达标" in page.locator(".ss-result").inner_text()
    assert page.locator("#btn-stage-next").inner_text() == "结束本局任务"
    page.click("#btn-stage-next")
    page.wait_for_selector(".result-page", timeout=15000)

    assert page.locator(".result-stamp").inner_text() == "任务中止"
    sub = page.locator(".result-sub").inner_text()
    assert "止步第1局" in sub, sub
    rows = page.locator(".result-list li").all()
    assert len(rows) == 8, f"成绩单 {len(rows)} 行 != 8"
    assert page.locator(".stage-dot.cleared").count() == 0, "未通关却有已通关标记"
    assert page.locator(".result-score em").inner_text() == "0"
    page.screenshot(path=str(ROOT / "tests" / "gd_gameover.png"))
    print("[中止] 第1局 0 分未达门槛 → 任务中止 · 止步第1局 · 8 行成绩单 ✓")

    browser.close()
    assert not errors, f"页面 JS 报错: {errors}"

print("全部通过 ✅")
