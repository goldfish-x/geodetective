from pathlib import Path
import os
# 回归验证：题库 + 两条赛道（地理版 10 局 / 历史版 12 局）关卡结构 + 局门槛中止/晋级路径
import json
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
# ———— 1. 题库静态校验 ————
CHINA_HINTS = {"华北地区", "东北地区", "华东地区", "华中地区", "华南地区", "西南地区", "西北地区", "蒙古高原"}
WORLD_HINTS = {"亚洲", "欧洲", "非洲", "北美洲", "南美洲", "大洋洲"}
# 地理版两线仍是 5 档；历史版扩到 6 档
LEVELS_OF_KIND = {"cities": 5, "scenics": 5, "history": 6}

for bank_name, hints in (("china", CHINA_HINTS), ("world", WORLD_HINTS)):
    with open(rf"{ROOT}\web\src\data\{bank_name}.json", encoding="utf-8") as f:
        bank = json.load(f)
    for kind in ("cities", "scenics", "history"):
        items = bank[kind]
        names = [q["name"] for q in items]
        assert len(items) >= 200, f"{bank_name}.{kind} 数量 {len(items)} < 200"
        assert len(set(names)) == len(items), f"{bank_name}.{kind} 存在重复题目"
        lvls = LEVELS_OF_KIND[kind]
        for lv in range(1, lvls + 1):
            cnt = sum(1 for q in items if q["difficulty"] == lv)
            assert cnt >= 40, f"{bank_name}.{kind} 难度{lv} 数量 {cnt} < 40"
        assert not any(q["difficulty"] > lvls for q in items), f"{bank_name}.{kind} 存在超出 {lvls} 档的难度"
        with open(rf"{ROOT}\web\src\data\{bank_name}-coords.json", encoding="utf-8") as f:
            coords = json.load(f)
        for q in items:
            assert q["hint"] in hints, f"{bank_name}.{kind} 非法 hint: {q['hint']}"
            assert "lat" not in q and "lng" not in q, f"{bank_name}.{kind} 题库不应内嵌坐标: {q['name']}"
            c = coords.get(q["name"])
            assert isinstance(c, list) and len(c) == 3, f"{q['name']} 缺坐标/归属"
            assert -90 <= c[0] <= 90 and -180 <= c[1] <= 180, f"{q['name']} 坐标越界: {c}"
    print(f"[题库] {bank_name}: 共 {sum(len(v) for v in bank.values())} 题"
          f"（城市 {len(bank['cities'])} / 景点 {len(bank['scenics'])} / 历史 {len(bank['history'])}） ✓")

# ———— 2. 浏览器验证 ————
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # —— 2a. 地理版：10 局、城市/景点两线、5 难度 ——
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
        qTypesOk: stages.every(s => s.questions.every(q => q.type === s.type && q.difficulty === s.difficulty)),
        body: document.body.className
      }
    }""")
    assert info["stageCount"] == 10, f"地理版局数 {info['stageCount']} != 10"
    assert all(s == 8 for s in info["sizes"]), f"每局题数异常: {info['sizes']}"
    assert info["types"] == ["city", "scenic"] * 5, f"两线交替异常: {info['types']}"
    assert info["diffs"] == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5], f"难度递增异常: {info['diffs']}"
    assert all(info["mins"][i] < info["mins"][i + 1] for i in range(9)), f"门槛递增异常: {info['mins']}"
    assert info["mins"][0] == 6000 and info["mins"][-1] == 15000, f"门槛区间异常: {info['mins'][0]}~{info['mins'][-1]}"
    assert all(info["mins"][i + 1] - info["mins"][i] == 1000 for i in range(9)), f"门槛涨幅异常: {info['mins']}"
    assert info["unique"], "80 题存在重复"
    assert info["qTypesOk"], "局内题目类型/难度与关卡配置不符"
    assert "trk-history" not in info["body"], "地理版不应挂历史版皮肤"
    print(f"[地理版] 10局×8题 城市/景点交替，门槛 {info['mins'][0]}→{info['mins'][-1]}（每局 +1000） ✓")
    gk = page.evaluate("() => window.__gdDebug.mode.decayK")
    assert gk == 1.7, f"地理版·中国篇衰减指数 {gk} != 1.7"
    print("[计分] 地理版·中国篇衰减 1.7 ✓（历史版·世界篇 1.1 才收严，地理版不受影响）")

    # 使用疆域透镜（三档 1 次）：横幅出现、角标归零、按钮转 used
    assert page.locator('[data-prop="area"] .prop-n').inner_text() == "1"
    page.click('[data-prop="area"]')
    page.wait_for_selector("#hint-banner:not(.hidden)", timeout=3000)
    assert "used" in page.locator('[data-prop="area"]').get_attribute("class"), "道具未标记 used"

    # 快速作答前 7 题（点地图中心 → 确认 → 点「下一题」）
    box = page.locator("#map-holder").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    for i in range(7):
        page.mouse.click(cx, cy)
        page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
        page.click("#btn-confirm")
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
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
    page.click("#btn-next")
    page.wait_for_selector(".stage-settle", timeout=10000)
    assert page.locator(".ss-chip").count() == 8, "档案面板缺少 8 个地名"
    assert "通 关" in page.locator(".ss-result").inner_text()
    page.click("#btn-stage-next")
    page.wait_for_function(
        "() => window.__gdDebug.state.stageIndex === 1 && window.__gdDebug.state.phase === 'answering'",
        timeout=10000,
    )

    assert page.locator("#q-index").inner_text() == "第2局 · 01/08", page.locator("#q-index").inner_text()
    assert page.locator("#q-badge").inner_text() == "景点"
    assert page.locator("#q-diff").inner_text() == "★☆☆☆☆"
    assert page.locator("#q-target").inner_text() == "7,000"
    assert page.locator("#q-stage-score").inner_text() == "0"
    assert "used" in page.locator('[data-prop="area"]').get_attribute("class"), "透镜次数不应跨局恢复"
    assert page.locator('[data-prop="time"] .prop-n').inner_text() == "3", "加时次数不应跨局变化"
    assert "danger" not in page.locator("#q-stage-wrap").get_attribute("class")
    print("[晋级] 第1局达标 → 第2局（景点·简单·门槛7,000），道具为整局计数 ✓")
    page.screenshot(path=str(ROOT / "tests" / "gd_stage2.png"))

    # —— 2b. 历史版：12 局、单线、6 难度、独立门槛、皮肤挂载 ——
    hpage = browser.new_page(viewport={"width": 1280, "height": 800})
    herr = []
    hpage.on("pageerror", lambda e: herr.append(str(e)))
    for mode, cls in (("china", "md-china"), ("world", "md-world")):
        hpage.goto(f"{BASE}/#/history/{mode}")
        hpage.wait_for_selector("#q-name", timeout=20000)
        hpage.wait_for_function("() => window.__gdDebug && window.__gdDebug.stages", timeout=10000)
        hi = hpage.evaluate("""() => {
          const { stages } = window.__gdDebug
          const names = stages.flatMap(s => s.questions.map(q => q.name))
          return {
            n: stages.length,
            sizes: stages.map(s => s.questions.length),
            types: [...new Set(stages.map(s => s.type))],
            diffs: stages.map(s => s.difficulty),
            mins: stages.map(s => s.minScore),
            unique: new Set(names).size === names.length,
            stars: document.querySelector('#q-diff').textContent,
            body: document.body.className,
            bg: getComputedStyle(document.body).backgroundImage,
            k: window.__gdDebug.mode.decayK
          }
        }""")
        assert hi["n"] == 6, f"历史版局数 {hi['n']} != 6"
        assert all(s == 8 for s in hi["sizes"]), f"每局题数异常: {hi['sizes']}"
        assert hi["types"] == ["history"], f"历史版应只有 history 线: {hi['types']}"
        assert hi["diffs"] == [1, 2, 3, 4, 5, 6], f"六档递增异常: {hi['diffs']}"
        assert hi["mins"][0] == 6000 and hi["mins"][-1] == 12000, f"门槛区间异常: {hi['mins'][0]}~{hi['mins'][-1]}"
        assert all(hi["mins"][i + 1] - hi["mins"][i] == 1200 for i in range(5)), f"门槛涨幅异常: {hi['mins']}"
        assert hi["unique"], "48 题存在重复"
        assert hi["stars"] == "★☆☆☆☆☆", f"六档星标异常: {hi['stars']}"
        assert "trk-history" in hi["body"] and cls in hi["body"], f"皮肤类名缺失: {hi['body']}"
        assert "svg" in hi["bg"], f"皮肤纹理未生效: {hi['bg']}"
        # 历史版·世界篇的距离衰减单独收严；中国篇沿用原曲线
        want_k = 1.1 if mode == "world" else 1.7
        assert hi["k"] == want_k, f"历史版·{mode} 衰减指数 {hi['k']} != {want_k}"
        hpage.screenshot(path=str(ROOT / "tests" / f"history_{mode}.png"))
        print(f"[历史版·{mode}] 6局×8题 六档，门槛 {hi['mins'][0]}→{hi['mins'][-1]}，皮肤 {cls} ✓")
    assert not herr, f"历史版页面 JS 报错: {herr}"
    hpage.close()

    # —— 2c. 门槛中止路径（第1局全部超时 → 0 分中止） ——
    page.goto(f"{BASE}/#/")
    page.wait_for_selector(".mode-card", timeout=10000)
    page.goto(f"{BASE}/#/game/china")
    page.wait_for_selector("#q-name", timeout=20000)
    page.wait_for_function("() => window.__gdDebug && window.__gdDebug.stages", timeout=10000)
    for i in range(8):
        page.wait_for_selector("#settle-pop:not(.hidden)", timeout=30000)
        page.click("#btn-next")
        if i < 7:
            page.wait_for_function(
                f"() => window.__gdDebug.state.qInStage === {i + 1} && window.__gdDebug.state.phase === 'answering'",
                timeout=10000,
            )
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
    assert page.locator(".stage-dot").count() == 10, f"地理版进度点 {page.locator('.stage-dot').count()} != 10"
    page.screenshot(path=str(ROOT / "tests" / "gd_gameover.png"))
    print("[中止] 第1局 0 分未达门槛 → 任务中止 · 止步第1局 · 8 行成绩单 · 10 个进度点 ✓")

    browser.close()
    assert not errors, f"页面 JS 报错: {errors}"

print("全部通过 ✅")
