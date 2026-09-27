# 结算推进节奏回归：单题结算后不再自动跳题，必须由玩家点击/回车推进；
# 世界篇结算时地球保持玩家视角（仅当答案或落点转到背面时才朝两点中点转向）。
import math
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('GD_BASE', 'http://127.0.0.1:5173')
TURN = 2500  # 等地球转向动画（viewControl animationDurationUpdate ≈ 1s）


def state(page):
    return page.evaluate('() => { const d = window.__gdDebug.state; '
                         'return { phase: d.phase, q: d.qInStage, stage: d.stageIndex } }')


def unit(p):
    a, b = math.radians(90 - p[1]), math.radians(p[0])
    return (math.sin(a) * math.cos(b), math.cos(a), math.sin(a) * math.sin(b))


def from_unit(v):
    n = math.sqrt(sum(x * x for x in v))
    lat = 90 - math.degrees(math.acos(max(-1.0, min(1.0, v[1] / n))))
    lng = math.degrees(math.atan2(v[2], v[0]))
    return [lng, lat]


def ang(p, q):
    '''两点球面大圆夹角（度）'''
    u, v = unit(p), unit(q)
    d = sum(a * b for a, b in zip(u, v))
    return math.degrees(math.acos(max(-1.0, min(1.0, d))))


def rot_away(p, deg):
    '''从 p 沿某条大圆走 deg 度，得到球面上确定距离的另一点'''
    u = unit(p)
    w = (0.0, 1.0, 0.0) if abs(u[1]) < 0.9 else (1.0, 0.0, 0.0)
    dot = sum(a * b for a, b in zip(w, u))
    v = tuple(a - dot * b for a, b in zip(w, u))
    vn = math.sqrt(sum(x * x for x in v))
    v = tuple(x / vn for x in v)
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return from_unit(tuple(ux * c + vx * s for ux, vx in zip(u, v)))


def mid(p, q):
    u, v = unit(p), unit(q)
    return from_unit(tuple(a + b for a, b in zip(u, v)))


def face(page, lng, lat):
    '''借局结算的 showSpot 把镜头确定性转向某地，随后清掉红点'''
    page.evaluate('([lng, lat]) => { const m = window.__gdDebug.map; '
                  'm.showSpot(lng, lat); m.clearSpot() }', [lng, lat])
    page.wait_for_timeout(TURN)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append('[console] ' + m.text) if m.type == 'error' else None)

    # ————— 1. 中国篇：结算停留 + 键盘推进 + 末题文案 —————
    page.goto(f'{BASE}/#/game/china')
    page.wait_for_selector('#q-name', timeout=30000)
    page.wait_for_function('() => window.__gdDebug', timeout=10000)
    box = page.locator('#map-holder').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2

    page.mouse.click(cx, cy)
    page.wait_for_selector('#confirm-pop:not(.hidden)', timeout=5000)
    page.click('#btn-confirm')
    page.wait_for_selector('#settle-pop:not(.hidden)', timeout=5000)

    assert page.locator('#btn-next').inner_text() == '下一题', page.locator('#btn-next').inner_text()
    assert page.locator('#timer-text').inner_text() == '已结算', page.locator('#timer-text').inner_text()
    assert 'settled' in page.locator('.timer').get_attribute('class'), '倒计时未标记为已结算'
    page.wait_for_timeout(4000)  # 远超旧版 2.5s 自动跳题窗口
    assert state(page) == {'phase': 'settle', 'q': 0, 'stage': 0}, f'结算后仍被自动跳题: {state(page)}'
    print('[节奏] 单题结算 4 秒后停在原地，等待玩家点击 ✓')

    page.keyboard.press('Enter')
    page.wait_for_function(
        '() => window.__gdDebug.state.qInStage === 1 && window.__gdDebug.state.phase === "answering"',
        timeout=5000)
    assert 'settled' not in page.locator('.timer').get_attribute('class'), '新题未解除已结算态'
    print('[键盘] 回车推进到第 2 题，倒计时恢复 ✓')

    page.evaluate('() => { window.__gdDebug.state.qInStage = 7 }')
    page.mouse.click(cx, cy)
    page.wait_for_selector('#confirm-pop:not(.hidden)', timeout=5000)
    page.click('#btn-confirm')
    page.wait_for_selector('#settle-pop:not(.hidden)', timeout=5000)
    assert page.locator('#btn-next').inner_text() == '查看本局档案', page.locator('#btn-next').inner_text()
    page.click('#btn-next')
    page.wait_for_selector('.stage-settle', timeout=10000)
    print('[末题] 第 8 题按钮为「查看本局档案」→ 局结算面板 ✓')

    # ————— 2. 世界篇：答案可见时视角纹丝不动 —————
    page.goto(f'{BASE}/#/')
    page.wait_for_selector('.mode-card.world', timeout=10000)
    page.click('.mode-card.world')
    page.wait_for_selector('#q-name', timeout=30000)
    page.wait_for_function('() => window.__gdDebug && typeof window.__gdDebug.map.getView === "function"',
                           timeout=20000)
    page.wait_for_timeout(TURN)
    box = page.locator('#map-holder').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2

    q0 = page.evaluate('() => window.__gdDebug.stages[0].questions[0]')
    face(page, q0['lng'], q0['lat'])
    v0 = page.evaluate('() => window.__gdDebug.map.getView()')
    assert ang(v0, [q0['lng'], q0['lat']]) < 3, f'预设视角未对准答案: {v0} vs {q0}'

    page.mouse.click(cx, cy)
    page.wait_for_selector('#confirm-pop:not(.hidden)', timeout=5000)
    g0 = rot_away([q0['lng'], q0['lat']], 5)
    page.evaluate('([lng, lat]) => { window.__gdDebug.state.guess = { lng, lat } }', g0)
    page.click('#btn-confirm')
    page.wait_for_selector('#settle-pop:not(.hidden)', timeout=5000)
    page.wait_for_timeout(TURN)
    v1 = page.evaluate('() => window.__gdDebug.map.getView()')
    assert ang(v0, v1) < 1.5, f'答案与落点都可见却转向了: {v0} -> {v1}'
    print(f'[视角] 答案可见时地球保持原位（偏移 {ang(v0, v1):.2f}°）✓')

    # ————— 3. 世界篇：落点转到背面时朝两点中点转向 —————
    page.click('#btn-next')
    page.wait_for_function('() => window.__gdDebug.state.phase === "answering"', timeout=5000)
    q1 = page.evaluate('() => window.__gdDebug.stages[0].questions[1]')
    A1 = [q1['lng'], q1['lat']]
    face(page, A1[0], A1[1])          # 镜头先对准答案 → 答案可见
    v2 = page.evaluate('() => window.__gdDebug.map.getView()')
    G1 = rot_away(A1, 120)            # 落点甩到背面（距答案 120° > 72° 不可见）
    assert ang(G1, v2) > 72, '构造失败：落点仍可见'
    page.mouse.click(cx, cy)
    page.wait_for_selector('#confirm-pop:not(.hidden)', timeout=5000)
    page.evaluate('([lng, lat]) => { window.__gdDebug.state.guess = { lng, lat } }', G1)
    page.click('#btn-confirm')
    page.wait_for_selector('#settle-pop:not(.hidden)', timeout=5000)
    page.wait_for_timeout(TURN)
    v3 = page.evaluate('() => window.__gdDebug.map.getView()')
    want = mid(G1, A1)                # 120° < 150° → 应转向两点球面中点
    assert ang(v2, v3) > 20, f'落点在背面却没有转向: {v2} -> {v3}'
    assert ang(v3, want) < 2, f'转向目标不是两点中点: 实际 {v3} 期望 {want}'
    assert max(ang(v3, A1), ang(v3, G1)) <= 65, '转向后答案/落点仍贴近边缘'
    print(f'[转向] 落点在背面时朝两点中点旋转，两点距视线 '
          f'{max(ang(v3, A1), ang(v3, G1)):.1f}° ✓')
    page.screenshot(path=str(ROOT / 'tests' / 'gd_world_settle_view.png'))

    browser.close()
    assert not errors, f'页面报错: {errors}'

print('结算推进节奏回归 ✅ 通过')
