# 结算推进节奏回归：单题结算后不再自动跳题，必须由玩家点击/回车推进；
# 世界篇结算时地球保持玩家视角（仅在答案转到背面时才转向）。
import math
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('GD_BASE', 'http://127.0.0.1:5173')


def state(page):
    return page.evaluate('() => { const d = window.__gdDebug.state; '
                         'return { phase: d.phase, q: d.qInStage, stage: d.stageIndex } }')


def ang(p, q):
    '''两点球面大圆夹角（度）'''
    a1, b1 = math.radians(90 - p[1]), math.radians(p[0])
    a2, b2 = math.radians(90 - q[1]), math.radians(q[0])
    d = (math.sin(a1) * math.sin(a2) * math.cos(b1 - b2) + math.cos(a1) * math.cos(a2))
    return math.degrees(math.acos(max(-1.0, min(1.0, d))))


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

    # ————— 2. 世界篇：结算不改变玩家视角 —————
    page.goto(f'{BASE}/#/')
    page.wait_for_selector('.mode-card.world', timeout=10000)
    page.click('.mode-card.world')
    page.wait_for_selector('#q-name', timeout=30000)
    page.wait_for_function('() => window.__gdDebug && typeof window.__gdDebug.map.getView === "function"',
                           timeout=20000)
    page.wait_for_timeout(2500)  # 等地球首帧与初始视角稳定
    v0 = page.evaluate('() => window.__gdDebug.map.getView()')

    box = page.locator('#map-holder').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    # 落点选在视角正前方：答案与落点都可见，视角应当纹丝不动
    page.mouse.click(cx, cy)
    page.wait_for_selector('#confirm-pop:not(.hidden)', timeout=5000)
    page.evaluate('() => { const d = window.__gdDebug; const [lng, lat] = d.map.getView(); '
                  'd.state.guess = { lng: lng + 6, lat } }')
    page.click('#btn-confirm')
    page.wait_for_selector('#settle-pop:not(.hidden)', timeout=5000)
    page.wait_for_timeout(2500)
    v1 = page.evaluate('() => window.__gdDebug.map.getView()')
    assert ang(v0, v1) < 1.5, f'结算导致地球回位/转向: {v0} -> {v1}'
    print(f'[视角] 答案可见时视角保持不动（偏移 {ang(v0, v1):.2f}°）✓')

    # 落点选到球背面：应转向，让答案与落点都进入可见半球
    page.click('#btn-next')
    page.wait_for_function('() => window.__gdDebug.state.phase === "answering"', timeout=5000)
    q1 = page.evaluate('() => window.__gdDebug.stages[0].questions[1]')
    page.mouse.click(cx, cy)
    page.wait_for_selector('#confirm-pop:not(.hidden)', timeout=5000)
    page.evaluate('() => { window.__gdDebug.state.guess = { lng: -75, lat: 8 } }')
    page.click('#btn-confirm')
    page.wait_for_selector('#settle-pop:not(.hidden)', timeout=5000)
    page.wait_for_timeout(2500)
    v2 = page.evaluate('() => window.__gdDebug.map.getView()')
    assert ang(v1, v2) > 20, f'答案在背面却没有转向: {v1} -> {v2}'
    far = max(ang(v2, [q1['lng'], q1['lat']]), ang(v2, [-75, 8]))
    assert far <= 80, f'转向后答案/落点仍不可见，最远 {far:.1f}°'
    print(f'[转向] 答案在背面时朝两点中点旋转，最远点距视线 {far:.1f}° ✓')
    page.screenshot(path=str(ROOT / 'tests' / 'gd_world_settle_view.png'))

    browser.close()
    assert not errors, f'页面报错: {errors}'

print('结算推进节奏回归 ✅ 通过')
