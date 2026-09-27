from pathlib import Path
import os
import math
# 世界篇结算镜头：答案在球背面时必须转到答案正面；答案已可见时不许动；且不许「自动回位」
# 历史坑：用 viewControl.alpha/beta 下发目标会被 echarts-gl 每帧的相机角度回写覆盖，
# 玩家刚拖拽完地球时结算转向会全部失效（实测 0/6），所以这里全部走真实结算流程断言。
from playwright.sync_api import sync_playwright

BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")


def u(x):
    a, b = math.radians(90 - x[1]), math.radians(x[0])
    return (math.sin(a) * math.cos(b), math.cos(a), math.sin(a) * math.sin(b))


def ang(p, q):
    a, b = u(p), u(q)
    return math.degrees(math.acos(max(-1, min(1, sum(x * y for x, y in zip(a, b))))))


def moved(a, b):
    """两帧视角的球面夹角（经度要按 360° 取模，否则 -179 与 181 会算出 360°）"""
    return ang([a[0], a[1]], [b[0], b[1]])


def answer_of(page):
    return page.evaluate(
        "() => { const s = window.__gdDebug.stages[0];"
        " const q = s.questions[window.__gdDebug.state.qInStage]; return [q.name, q.lng, q.lat] }")


def play_one(browser):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{BASE}/#/game/world")
    page.wait_for_selector("#q-name", timeout=30000)
    page.wait_for_function("() => window.__gdDebug && window.__gdDebug.map.getView", timeout=20000)
    page.wait_for_timeout(2000)
    return page


def settle_at(page, fx, fy=0.5):
    box = page.locator("#map-holder").bounding_box()
    page.mouse.click(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
    page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=5000)
    page.click("#btn-confirm")
    page.wait_for_selector("#settle-pop:not(.hidden)", timeout=5000)
    page.wait_for_timeout(2200)
    return page.evaluate("() => window.__gdDebug.map.getView()")


def drag(page, fx0, dfx, dfy):
    box = page.locator("#map-holder").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
    page.mouse.down()
    for i in range(12):
        page.mouse.move(box["x"] + box["width"] * (0.5 + dfx * i), box["y"] + box["height"] * (0.5 + dfy * i))
    page.mouse.up()
    page.wait_for_timeout(900)


fails = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # A. 答案在球背面（从对跖点起视）→ 结算后必须正对答案
    for i in range(3):
        page = play_one(browser)
        q = answer_of(page)
        A = [q[1], q[2]]
        anti = [(A[0] + 180 + 540) % 360 - 180, -A[1]]
        page.evaluate("([lng, lat]) => window.__gdDebug.map.showSpot(lng, lat)", anti)
        page.wait_for_timeout(1500)
        v = settle_at(page, 0.5)
        d = ang(v, A)
        print(f"  A{i+1} {q[0]:<8} 结算后距答案 {d:5.2f}°")
        if d >= 3:
            fails.append(f"答案在球背面时未转向：{q[0]} 偏差 {d:.1f}°")
        page.close()

    # B. 答案本来就在正面、落点也几乎重合 → 不许动镜头（保持玩家视角）
    page = play_one(browser)
    q = answer_of(page)
    A = [q[1], q[2]]
    page.evaluate("([lng, lat]) => window.__gdDebug.map.showSpot(lng, lat)", A)
    page.wait_for_timeout(1800)
    page.evaluate("() => window.__gdDebug.map.clearSpot()")
    page.wait_for_timeout(400)
    v0 = page.evaluate("() => window.__gdDebug.map.getView()")
    v1 = settle_at(page, 0.5)
    d = moved(v0, v1)
    print(f"  B {q[0]:<8} 可见时镜头位移 {d:.2f}°")
    if d > 2:
        fails.append(f"答案已可见却动了镜头：{d:.1f}°")

    # C. 拖拽后进入下一题 → 不许回位
    drag(page, 0.02, 0.02, 0.0)
    vd = page.evaluate("() => window.__gdDebug.map.getView()")
    page.click("#btn-next")
    page.wait_for_timeout(2500)
    v2 = page.evaluate("() => window.__gdDebug.map.getView()")
    d = moved(vd, v2)
    print(f"  C 下一题后回位量 {d:.2f}°")
    if d > 2:
        fails.append(f"进入下一题时地球自动回位：{d:.1f}°")

    # D. 结算转向完成后玩家再拖拽 → 回位锚点不许抢镜头
    page.wait_for_selector("#q-name")
    v3 = settle_at(page, 0.62, 0.42)
    drag(page, -0.02, 0.0, 0.008)
    vt = page.evaluate("() => window.__gdDebug.map.getView()")
    d = moved(v3, vt)
    print(f"  D 结算后拖拽生效量 {d:.2f}°")
    if d < 5:
        fails.append(f"结算后拖拽被回位锚点抢走镜头：仅 {d:.1f}°")
    page.close()
    browser.close()

assert not fails, "镜头回归失败：\n  " + "\n  ".join(fails)
print("全部通过 ✅")

