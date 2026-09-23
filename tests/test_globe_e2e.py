from pathlib import Path
import os
# 端到端验证：球面渲染颜色 vs 贴图颜色（验证球面 UV 与贴图对齐）
import io
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")

# 深入大国腹地的采样点（远离国界，避免边界线混色）
# (名称, lng, lat)
POINTS = [
    ("西伯利亚腹地", 90.0, 62.0),
    ("美国中部", -98.0, 39.0),
    ("澳洲腹地", 134.0, -25.0),
    ("撒哈拉腹地", 10.0, 26.0),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 800, "height": 600})
    page.goto(f"{BASE}/tests/texcheck.html")
    page.wait_for_function("() => typeof window.__lookAt === 'function'", timeout=30000)
    page.wait_for_timeout(3000)  # 等地球首帧渲染

    print(f"{'采样点':<10}{'贴图色RGB':>16}{'球面色RGB':>16}{'色距':>8}")
    ok = True
    for name, lng, lat in POINTS:
        tex_rgb = page.evaluate("([a, b]) => window.__lookAt(a, b)", [lng, lat])
        page.wait_for_timeout(1200)  # 等视角切换与重渲染
        png = page.screenshot(clip={"x": 199, "y": 199, "width": 3, "height": 3})
        img = Image.open(io.BytesIO(png)).convert("RGB")
        # 3x3 区域取平均（抵消纹理过滤的轻微混色）
        gl_rgb = tuple(sum(img.getpixel((x, y))[i] for x in range(3) for y in range(3)) // 9 for i in range(3))
        dist = sum((a - b) ** 2 for a, b in zip(tex_rgb, gl_rgb)) ** 0.5
        status = "✓" if dist < 90 else "✗"
        if dist >= 90:
            ok = False
        print(f"{name:<10}{str(tuple(tex_rgb)):>16}{str(gl_rgb):>16}{dist:8.1f} {status}")
    browser.close()

print("\n球面-贴图对齐:", "✅ 通过" if ok else "❌ 失败")
