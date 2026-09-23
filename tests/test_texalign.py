from pathlib import Path
import os
# 探测贴图中城市像素位置 vs 等距圆柱期望位置
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")

# (名称, lng, lat)
CITIES = [
    ("巴黎", 2.35, 48.86),
    ("伦敦", -0.13, 51.51),
    ("纽约", -74.01, 40.71),
    ("东京", 139.69, 35.68),
    ("悉尼", 151.21, -33.87),
    ("里约", -43.17, -22.91),
    ("莫斯科", 37.62, 55.76),
    ("朗伊尔城", 15.63, 78.22),
]

W, H = 2048, 1024

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 800, "height": 600})
    page.goto(f"{BASE}/tests/texcheck.html")
    page.wait_for_function("() => typeof window.__probe === 'function'", timeout=20000)
    print(f"{'城市':<8}{'期望像素':>16}{'实际像素':>16}{'dx':>8}{'dy':>8}{'纬向偏差°':>10}")
    worst = 0
    for name, lng, lat in CITIES:
        px = page.evaluate("([a, b]) => window.__probe(a, b)", [lng, lat])
        exp = [(lng + 180) / 360 * W, (90 - lat) / 180 * H]
        if not isinstance(px, list) or len(px) != 2:
            print(name, "PROBE ERROR", px)
            continue
        dx, dy = px[0] - exp[0], px[1] - exp[1]
        dlat = dy / H * 180  # 像素差换算为纬度差
        dlng = dx / W * 360
        worst = max(worst, abs(dlat), abs(dlng))
        print(f"{name:<8}({exp[0]:7.1f},{exp[1]:7.1f})({px[0]:7.1f},{px[1]:7.1f}){dx:8.1f}{dy:8.1f}{dlat:10.2f}")
    browser.close()
    print(f"\n最大偏差: {worst:.2f}°  {'✅ 对齐' if worst < 1 else '❌ 未对齐'}")
