# 荣誉榜奖牌 + 榜首庆祝回归守卫
#   1. 前三名有 1st/2nd/3rd 奖牌前缀，且三行背景板颜色各不相同、第四名起无奖牌
#   2. 本次成绩登顶 → 庆祝画面（champion 卡片 + 王冠行 + 金粉雨 + 第 1 名徽章）
#   3. 未登顶 → 不出现任何庆祝元素
#   4. 用户偏好减少动效时，金粉雨与王冠动画必须关闭
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
KEY = "gd_leaderboard"
fails = []


def seed(page, entries):
    page.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [KEY, {"china": entries}])


def finish_run(page, total):
    """直接推进到终局结算：注入第 8 题已结算 + 本局未达标的状态"""
    # 先回首页再进游戏：上一局结束时地址栏已经是 #/game/china，
    # 同一 hash 再 goto 不会触发路由重渲染，会卡在终局页拿不到 #q-name
    page.goto(f"{BASE}/#/")
    page.wait_for_selector(".mode-card", timeout=10000)
    page.goto(f"{BASE}/#/game/china")
    page.wait_for_selector("#q-name", timeout=30000)
    page.wait_for_function("() => window.__gdDebug", timeout=10000)
    page.evaluate("t => { const d = window.__gdDebug; "
                  "d.state.qInStage = 7; d.state.stageScore = 0; d.state.total = t; "
                  "d.state.phase = 'settle' }", total)
    page.evaluate("() => document.getElementById('btn-next').click()")
    page.wait_for_selector(".stage-settle", timeout=10000)
    page.click("#btn-stage-next")
    page.wait_for_selector(".result-page", timeout=10000)
    page.wait_for_timeout(700)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 860})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append("[console] " + m.text) if m.type == "error" else None)

    # ————— 1. 排行榜奖牌与背景板 —————
    page.goto(BASE)
    page.wait_for_selector(".board-list", timeout=10000)
    seed(page, [{"score": s, "date": "2026-09-%02d" % i} for i, s in
                enumerate([9800, 8600, 7400, 6100, 5200], start=1)])
    page.reload()
    page.wait_for_selector(".board-list li.top3", timeout=10000)
    rows = page.evaluate("""() => [...document.querySelectorAll('.board-list li')].map(li => {
      const m = li.querySelector('.bl-medal'), cs = getComputedStyle(li)
      return { cls: li.className, medal: m ? m.textContent : null,
               bg: cs.backgroundImage === 'none' ? null : cs.backgroundImage,
               idx: li.querySelector('.bl-idx').textContent.trim() }
    })""")
    medals = [r["medal"] for r in rows[:3]]
    if medals != ["1st", "2nd", "3rd"]:
        fails.append(f"前三名奖牌应为 1st/2nd/3rd，实际 {medals}")
    bgs = {r["bg"] for r in rows[:3]}
    if len(bgs) != 3 or None in bgs:
        fails.append(f"前三名背景板颜色未区分开：{bgs}")
    if [r["idx"] for r in rows[:3]] != ["1st", "2nd", "3rd"]:
        fails.append(f"前三名序号位被奖牌占用后文本异常：{[r['idx'] for r in rows[:3]]}")
    for r in rows[3:]:
        if r["medal"] or r["bg"] or r["cls"]:
            fails.append(f"第四名起不应有奖牌/背景板：{r}")
    print(f"[排行榜] 奖牌 {medals} · 三种背景板互不相同 · 第 4 名起 {len(rows) - 3} 行无奖牌 ✓")

    # ————— 2. 登顶：庆祝画面 —————
    seed(page, [])
    finish_run(page, 99999)
    champ = page.evaluate("""() => ({
      card: !!document.querySelector('.result-card.champion'),
      crown: document.querySelector('.result-crown') ? document.querySelector('.result-crown').textContent : null,
      rank: document.querySelector('.result-rank').className + '|' + document.querySelector('.result-rank').textContent.trim(),
      bits: document.querySelectorAll('.confetti i').length,
      anim: document.querySelector('.confetti i') ? getComputedStyle(document.querySelector('.confetti i')).animationName : null,
      score: document.querySelector('.result-score em').textContent
    })""")
    if not champ["card"]:
        fails.append("登顶时 .result-card 缺少 champion 类")
    if not champ["crown"] or "独占榜首" not in champ["crown"]:
        fails.append(f"缺少王冠行：{champ['crown']}")
    if "first" not in champ["rank"] or "第 1 名" not in champ["rank"]:
        fails.append(f"排名徽章未切到榜首态：{champ['rank']}")
    if champ["bits"] != 36:
        fails.append(f"金粉雨应为 36 片，实际 {champ['bits']}")
    if champ["anim"] != "confettiFall":
        fails.append(f"金粉雨动画未启用：{champ['anim']}")
    top = page.evaluate("k => JSON.parse(localStorage.getItem(k)).china[0].score", KEY)
    if top != 99999:
        fails.append(f"榜首成绩未写入：{top}")
    page.screenshot(path=str(ROOT / "tests" / "gd_champion.png"))
    print(f"[庆祝] 总分 {champ['score']} → champion 卡片 + 王冠 + 36 片金粉雨 + 第 1 名徽章 ✓")

    # ————— 3. 回到首页：这次的成绩应排在第一并带 1st 奖牌 —————
    page.goto(f"{BASE}/#/")
    page.wait_for_selector(".board-list li.top1", timeout=10000)
    if page.locator(".board-list li.top1 .bl-medal").inner_text() != "1st":
        fails.append("刚登顶的成绩在荣誉榜上没有 1st 奖牌")
    print("[闭环] 返回首页后该记录位于榜首并挂 1st 奖牌 ✓")

    # ————— 4. 未登顶：不得出现庆祝元素 —————
    seed(page, [{"score": 100000, "date": "2026-09-01"}])
    finish_run(page, 99999)
    plain = page.evaluate("""() => ({
      card: !!document.querySelector('.result-card.champion'),
      crown: !!document.querySelector('.result-crown'),
      bits: document.querySelectorAll('.confetti i').length,
      rank: document.querySelector('.result-rank').textContent.trim()
    })""")
    if plain["card"] or plain["crown"] or plain["bits"]:
        fails.append(f"未登顶却出现庆祝元素：{plain}")
    if "第 2 名" not in plain["rank"]:
        fails.append(f"排名文案应为第 2 名：{plain['rank']}")
    print(f"[非榜首] 无庆祝画面，文案「{plain['rank']}」✓")

    # ————— 5. 窄屏：王冠行不得压住右上角印章 —————
    page.emulate_media(reduced_motion=None)
    m = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True)
    m.on("pageerror", lambda e: errs.append(str(e)))
    finish_run(m, 77777)
    boxes = m.evaluate("""() => {
      const r = el => { const b = el.getBoundingClientRect()
        return { l: b.left, t: b.top, r: b.right, b: b.bottom } }
      return { crown: r(document.querySelector('.result-crown')),
               stamp: r(document.querySelector('.result-stamp')) }
    }""")
    c, st = boxes["crown"], boxes["stamp"]
    ox = max(0, min(c["r"], st["r"]) - max(c["l"], st["l"]))
    gap = c["t"] - st["b"]          # 王冠顶边到印章底边的净空（>0 即完全分开）
    if ox > 1 and gap < 2:
        fails.append(f"390px 下王冠行与印章挤在一起（横向交叠 {ox:.0f}px · 净空 {gap:.1f}px）：{boxes}")
    m.screenshot(path=str(ROOT / "tests" / "gd_champion_mob.png"))
    print(f"[窄屏] 王冠行让到印章下方（横向交叠 {ox:.0f}px · 净空 {gap:.1f}px）✓")
    m.close()

    # ————— 6. 减少动效偏好 —————
    page.emulate_media(reduced_motion="reduce")
    seed(page, [])   # 上一步是未登顶局、页面上没有金粉雨，重开一局登顶再检查
    finish_run(page, 88888)
    rm = page.evaluate("""() => ({
      confetti: getComputedStyle(document.querySelector('.confetti i')).animationName,
      crown: getComputedStyle(document.querySelector('.result-crown')).animationName
    })""")
    if rm["confetti"] != "none" or rm["crown"] != "none":
        fails.append(f"prefers-reduced-motion 下动画未关闭：{rm}")
    print(f"[无障碍] 减少动效偏好下 confetti={rm['confetti']} crown={rm['crown']} ✓")

    browser.close()
    assert not errs, f"页面报错: {errs}"

if fails:
    for m in fails:
        print("  ✗", m)
    raise SystemExit(1)
print("荣誉榜与榜首庆祝守卫 ✅ 通过")
