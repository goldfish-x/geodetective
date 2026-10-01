from pathlib import Path
import os
# 地理大侦探 · 原型流程验证脚本
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.on('console', lambda m: errors.append('[console] ' + m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append('[pageerror] ' + str(e)))

    # —— 首页 ——
    page.goto(BASE)
    page.wait_for_load_state('networkidle')
    page.screenshot(path='tests/home.png')
    print('home title:', page.text_content('.home-title'))

    # —— 中国篇 ——
    page.click('.mode-card.china')
    page.wait_for_timeout(3000)
    print('china question:', page.text_content('#q-name'))
    page.screenshot(path='tests/game-china.png')

    box = page.locator('#map-holder').bounding_box()
    page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.wait_for_timeout(600)
    print('confirm visible:', page.locator('#confirm-pop').is_visible())
    page.screenshot(path='tests/china-picked.png')

    page.click('#btn-confirm')
    page.wait_for_timeout(600)
    print('settle visible:', page.locator('#settle-pop').is_visible())
    print('settle title:', page.text_content('#settle-title'))
    print('settle detail:', page.text_content('#settle-detail'))
    page.screenshot(path='tests/china-settle.png')

    # 测试道具：下一题后用线索；加时属付费预留内容，当前应完全隐藏
    page.click('#btn-next')
    page.wait_for_timeout(600)
    assert page.locator('#prop-time').count() == 0, '加时道具未隐藏（应为后续付费内容）'
    page.click('#prop-hint')
    page.wait_for_timeout(400)
    print('hint banner:', page.text_content('#hint-banner'))
    print('props: 加时已屏蔽，仅线索可用')
    page.screenshot(path='tests/china-props.png')

    # —— 世界篇 ——
    page.click('#btn-back')
    page.wait_for_timeout(1000)
    page.click('.mode-card.world')
    page.wait_for_timeout(5000)
    print('world question:', page.text_content('#q-name'))
    page.screenshot(path='tests/game-world.png')

    wb = page.locator('#map-holder').bounding_box()
    page.mouse.click(wb['x'] + wb['width'] / 2, wb['y'] + wb['height'] / 2)
    page.wait_for_timeout(1000)
    print('world confirm visible:', page.locator('#confirm-pop').is_visible())
    page.screenshot(path='tests/world-picked.png')

    if page.locator('#confirm-pop').is_visible():
        page.click('#btn-confirm')
        page.wait_for_timeout(600)
        print('world settle:', page.text_content('#settle-title'), '|', page.text_content('#settle-detail'))
        page.screenshot(path='tests/world-settle.png')

    browser.close()

print('console errors:', len(errors))
for e in errors:
    print(' ', e[:300])
