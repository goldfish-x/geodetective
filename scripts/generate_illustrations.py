"""为「Commons 上找不到合规真拍」的地点绘制旅行海报式插画配图（纯 PIL，离线、确定性）。

用法:
  python scripts/generate_illustrations.py            # 只补缺失的插画位
  python scripts/generate_illustrations.py --force    # 全部重绘
  python scripts/generate_illustrations.py --only 大海道,阿什哈巴德

设计约束：
  - 场景原型与配色写在 scripts/illustration-scenes.json，逐地点人工指定（图文必须对应）
  - 同一个地名每次重绘结果完全一致（种子 = 地名 md5）
  - 900px 超采样后缩到 300x300 WebP，与其余配图同规格
  - 不画文字：结算卡片只有 100 CSS px，地名由 UI 自己显示
"""
import hashlib
import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "scripts/illustration-scenes.json"
EDGE = 300
SS = 3                      # 超采样倍数
W = EDGE * SS
FORCE = "--force" in sys.argv
ONLY = [x for x in (sys.argv[sys.argv.index("--only") + 1].split(",")
        if "--only" in sys.argv else []) if x]


# ---------- 颜色工具 ----------
def hx(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    a, b = hx(a) if isinstance(a, str) else a, hx(b) if isinstance(b, str) else b
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rgb(c):
    return hx(c) if isinstance(c, str) else c


def darken(c, t):
    return mix(c, "#000000", t)


def sky_gradient(stops):
    """stops: 自上而下的颜色列表 -> 900x900 渐变底图"""
    grad = Image.new("RGB", (1, W))
    n = len(stops)
    px = grad.load()
    for y in range(W):
        f = (y / (W - 1)) * (n - 1)
        i = min(int(f), n - 2)
        px[0, y] = mix(stops[i], stops[i + 1], f - i)
    return grad.resize((W, W), Image.BILINEAR)


# ---------- 地形 ----------
def ridge_points(seed, base_y, amp, rough, n=129, peaky=0.0):
    """中点位移生成一条山脊线（返回 n 个 (x, y)）"""
    rnd = random.Random(seed)
    h = [0.0] * n
    step, size = 1, amp
    h[0], h[n - 1] = rnd.uniform(-0.3, 0.3) * amp, rnd.uniform(-0.3, 0.3) * amp
    while step < n - 1:
        for i in range(0, n - 1, step * 2 if step else 1):
            j = min(i + step * 2, n - 1)
            h[(i + j) // 2] = (h[i] + h[j]) / 2 + rnd.uniform(-size, size)
        step *= 2
        size *= rough
    if peaky:                      # 抬出几座尖峰（雪山/石林用）
        for _ in range(int(peaky)):
            c = rnd.randrange(n)
            wdt = rnd.randrange(6, 22)
            for i in range(max(0, c - wdt), min(n, c + wdt)):
                h[i] += (1 - abs(i - c) / wdt) ** 2 * amp * rnd.uniform(0.7, 1.5)
    sm = [sum(h[max(0, i - 2):i + 3]) / len(h[max(0, i - 2):i + 3]) for i in range(n)]
    return [(i * W / (n - 1), base_y - sm[i]) for i in range(n)]


def fill_poly(img, pts, color, y0=None):
    d = ImageDraw.Draw(img)
    body = pts + [(W, W), (0, W)] if y0 is None else pts + [(W, y0), (0, y0)]
    d.polygon(body, fill=color)


def draw_cones(img, seed, base_y, count, hmin, hmax, color, spread=1.0):
    """喀斯特峰丛：一堆独立圆锥"""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    for _ in range(count):
        x = rnd.uniform(-0.05, 1.05) * W
        h = rnd.uniform(hmin, hmax)
        w = h * rnd.uniform(0.42, 0.72) * spread
        d.polygon([(x - w, base_y + 4), (x - w * rnd.uniform(0.1, 0.3), base_y - h),
                   (x + w * rnd.uniform(0.1, 0.3), base_y - h), (x + w, base_y + 4)],
                  fill=color)


def draw_pillars(img, seed, base_y, count, hmin, hmax, color, tilt=0.06):
    """雅丹土墩 / 花岗岩石林：宽窄不一、略微倾斜、顶面平或圆"""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    for _ in range(count):
        x = rnd.uniform(-0.02, 1.02) * W
        h = rnd.uniform(hmin, hmax)
        w = h * rnd.uniform(0.16, 0.42)
        sk = rnd.uniform(-tilt, tilt) * h
        top = base_y - h
        d.polygon([(x - w, base_y + 6), (x - w * 0.72 + sk, top), (x + w * 0.72 + sk, top),
                   (x + w, base_y + 6)], fill=color)
        if rnd.random() < 0.45:                       # 顶帽
            d.ellipse([x + sk - w * 0.95, top - w * 0.5, x + sk + w * 0.95, top + w * 0.45],
                      fill=color)
        for k in range(1, 3):                         # 风蚀层理
            yy = top + h * k / 3.0
            d.line([(x - w * (1 - 0.12 * k), yy), (x + w * (1 - 0.12 * k), yy)],
                   fill=mix(color, "#000000", 0.18), width=max(1, SS))


def draw_dunes(img, seed, base_y, amp, color, n=90):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    for _ in range(14):
        x = rnd.uniform(0, W)
        r = rnd.uniform(0.08, 0.22) * W
        d.chord([x - r, base_y - r * rnd.uniform(0.28, 0.5), x + r, base_y + r],
                180, 360, fill=color)


def draw_terraces(img, top_y, bot_y, bands, fill_a, fill_b, rim):
    """水田梯田：一层层宽带 + 田埂，避免碎线糊成噪声"""
    d = ImageDraw.Draw(img)
    step = (bot_y - top_y) / bands
    for i in range(bands):
        y0 = top_y + i * step
        y1 = y0 + step * 1.02
        amp = step * 0.30
        f = 1.1 + (i % 3) * 0.35
        ph = i * 1.7
        xs = list(range(-20, W + 21, 16))
        up = [(x, y0 + amp * math.sin(x / W * math.pi * f + ph)) for x in xs]
        dn = [(x, y1 + amp * math.sin(x / W * math.pi * f + ph)) for x in xs]
        d.polygon(up + list(reversed(dn)),
                  fill=mix(fill_a, fill_b, i / max(1, bands - 1)))
        d.line(dn, fill=rim, width=max(2, int(step * 0.14)))


def draw_water(img, seed, y0, sky_bottom, sun_x=None, ripples=26):
    """水面：渐变 + 横向波光 + 太阳倒影"""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    deep, shallow = darken(sky_bottom, 0.55), mix(sky_bottom, "#ffffff", 0.15)
    for y in range(int(y0), W, 2):
        t = (y - y0) / max(1, W - y0)
        d.line([(0, y), (W, y)], fill=mix(deep, shallow, 0.15 + t * 0.6))
    if sun_x is not None:
        for y in range(int(y0), W, 3):
            t = (y - y0) / max(1, W - y0)
            w = (10 + 70 * t) * SS * 0.5
            d.line([(sun_x - w / 2, y), (sun_x + w / 2, y)],
                   fill=mix(shallow, "#fff3d8", 0.75 - t * 0.45), width=2)
    for _ in range(ripples):
        y = rnd.uniform(y0 + 6, W - 2)
        x = rnd.uniform(-0.1, 0.95) * W
        ln = rnd.uniform(0.04, 0.22) * W
        t = (y - y0) / max(1, W - y0)
        d.line([(x, y), (x + ln, y)], fill=mix(shallow, "#ffffff", 0.4 + 0.35 * t),
               width=max(1, int(1.2 * SS * (0.4 + t))))


def draw_grid_pans(img, seed, y0, color, water, cell=6):
    """盐田/鱼塘方格网（透视收缩）"""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    rows = 9
    for r in range(rows):
        t = r / rows
        y = y0 + (W - y0) * (t ** 1.7)
        h = (W - y0) / rows * (1 + 2.4 * t)
        cols = max(3, int(9 - r))
        for c in range(cols + 1):
            x = (c + rnd.uniform(-0.06, 0.06)) / (cols + 1) * W
            w = W / (cols + 1) * 0.42
            d.polygon([(x - w, y), (x + w, y), (x + w * 1.5, y + h * 0.5),
                       (x - w * 1.5, y + h * 0.5)],
                      fill=water if (r + c) % 2 == 0 else color)


# ---------- 人造物 / 植被母题（全部剪影） ----------
def roofs(img, x0, y, count, step, color, style="hui", rnd=None):
    """一排民居。style: hui=徽派马头墙, tibet=藏寨碉房, drum=侗族吊脚"""
    rnd = rnd or random.Random(0)
    d = ImageDraw.Draw(img)
    for i in range(count):
        x = x0 + i * step + rnd.uniform(-step * 0.12, step * 0.12)
        w = step * rnd.uniform(0.62, 0.92)
        h = w * rnd.uniform(0.5, 0.8)
        if style == "hui":
            d.rectangle([x - w / 2, y - h, x + w / 2, y], fill=color)
            d.polygon([(x - w / 2, y - h), (x - w / 2, y - h * 1.35), (x - w * 0.1, y - h * 1.35),
                       (x - w * 0.1, y - h)], fill=color)          # 马头墙
            d.polygon([(x - w * 0.62, y - h), (x, y - h * 1.5), (x + w * 0.62, y - h)], fill=color)
        elif style == "tibet":
            d.rectangle([x - w / 2, y - h, x + w / 2, y], fill=color)
            d.polygon([(x - w * 0.42, y - h), (x - w * 0.3, y - h * 1.28),
                       (x + w * 0.3, y - h * 1.28), (x + w * 0.42, y - h)], fill=color)
        else:
            d.rectangle([x - w / 2, y - h * 0.7, x + w / 2, y], fill=color)
            d.polygon([(x - w * 0.62, y - h * 0.7), (x, y - h * 1.45), (x + w * 0.62, y - h * 0.7)],
                      fill=color)


def pagoda(img, x, y, h, color, tiers=5):
    d = ImageDraw.Draw(img)
    for i in range(tiers):
        t = i / tiers
        w = h * (0.42 - 0.055 * i)
        yy = y - h * (0.16 + 0.16 * i)
        d.polygon([(x - w, yy), (x + w, yy), (x + w * 0.62, yy - h * 0.11),
                   (x - w * 0.62, yy - h * 0.11)], fill=color)
        d.polygon([(x - w * 1.18, yy), (x, yy - h * 0.075), (x + w * 1.18, yy)], fill=color)
    d.polygon([(x - h * 0.06, y - h * 0.92), (x, y - h * 1.12), (x + h * 0.06, y - h * 0.92)],
              fill=color)


def drum_tower(img, x, y, h, color):
    """侗族鼓楼：密檐但檐口平缓外挑，带基座与宝顶"""
    d = ImageDraw.Draw(img)
    d.rectangle([x - h * 0.34, y - h * 0.1, x + h * 0.34, y], fill=color)          # 基座
    for i in range(6):
        w = h * (0.40 - 0.052 * i)
        yy = y - h * (0.14 + 0.13 * i)
        d.rectangle([x - w * 0.42, yy - h * 0.075, x + w * 0.42, yy], fill=color)  # 塔身
        d.polygon([(x - w, yy), (x - w * 0.5, yy - h * 0.055), (x, yy - h * 0.075),
                   (x + w * 0.5, yy - h * 0.055), (x + w, yy), (x, yy + h * 0.02)],
                  fill=color)                                                      # 平缓出檐
    d.line([(x, y - h * 0.92), (x, y - h * 1.08)], fill=color, width=max(2, int(1.6 * SS)))
    d.ellipse([x - h * 0.03, y - h * 1.13, x + h * 0.03, y - h * 1.06], fill=color)


def bridge(img, y, color, arches=7):
    """铁路/公路桥：连续拱 + 桥面"""
    d = ImageDraw.Draw(img)
    deck = y - 0.055 * W
    d.rectangle([0, deck, W, deck + 0.02 * W], fill=color)
    aw = W / arches
    for i in range(arches):
        x = i * aw + aw / 2
        d.pieslice([x - aw * 0.36, y - aw * 0.5, x + aw * 0.36, y + aw * 0.5], 180, 360, fill=color)
        d.rectangle([x - aw * 0.36, y - aw * 0.02, x + aw * 0.36, y], fill=color)


def train(img, x, y, sc, color):
    """电力机车剪影（株洲：动力机械之城）"""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x - sc * 1.9, y - sc * 0.75, x + sc * 1.9, y - sc * 0.1], radius=sc * 0.16,
                        fill=color)
    d.rectangle([x - sc * 1.55, y - sc * 1.12, x - sc * 0.35, y - sc * 0.75], fill=color)
    d.line([(x - sc * 0.95, y - sc * 1.12), (x - sc * 0.6, y - sc * 1.55)], fill=color, width=max(2, SS))
    d.line([(x - sc * 1.2, y - sc * 1.55), (x - sc * 0.35, y - sc * 1.55)], fill=color, width=max(2, SS))
    for i in (-1.35, -0.45, 0.45, 1.35):
        d.ellipse([x + i * sc - sc * 0.2, y - sc * 0.3, x + i * sc + sc * 0.2, y + 0.02 * sc], fill=color)


def skyline(img, y, color, seed, maxh=0.3):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    x = -0.02 * W
    while x < W:
        w = rnd.uniform(0.03, 0.09) * W
        h = rnd.uniform(0.06, maxh) * W
        d.rectangle([x, y - h, x + w, y], fill=color)
        if rnd.random() < 0.3:
            d.line([(x + w / 2, y - h), (x + w / 2, y - h - 0.03 * W)], fill=color, width=max(2, SS))
        x += w + rnd.uniform(0.002, 0.012) * W


def trees(img, seed, y, count, hmin, hmax, color, kind="pine"):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    for _ in range(count):
        x = rnd.uniform(-0.03, 1.03) * W
        h = rnd.uniform(hmin, hmax)
        if kind == "pine":
            w = h * 0.34
            for k in range(3):
                yy = y - h * (0.25 + 0.26 * k)
                d.polygon([(x - w * (1 - k * 0.25), yy), (x, yy - h * 0.42),
                           (x + w * (1 - k * 0.25), yy)], fill=color)
            d.rectangle([x - h * 0.035, y - h * 0.3, x + h * 0.035, y], fill=color)
        elif kind == "birch":
            d.line([(x, y), (x, y - h)], fill=color, width=max(2, int(0.008 * W)))
            for k in range(4):
                yy = y - h * (0.45 + 0.16 * k)
                d.ellipse([x - h * 0.16, yy - h * 0.12, x + h * 0.16, yy + h * 0.1], fill=color)
        elif kind == "mangrove":
            w = h * 0.34
            d.line([(x, y), (x, y - h * 0.62)], fill=color, width=max(2, int(0.012 * W)))
            for k in range(4):                                  # 支柱根
                a = -0.9 + k * 0.6
                d.line([(x, y - h * 0.3), (x + math.sin(a) * w * 0.9, y)], fill=color,
                       width=max(2, int(0.008 * W)))
            for k in range(3):                                  # 分层树冠
                cw = w * (1.05 - 0.22 * k)
                cy = y - h * (0.72 + 0.16 * k)
                d.ellipse([x - cw, cy - cw * 0.55, x + cw, cy + cw * 0.5], fill=color)
        else:                                   # reed 芦苇
            for k in range(3):
                a = -0.5 + k * 0.5
                d.line([(x, y), (x + math.sin(a) * h * 0.3, y - h)], fill=color,
                       width=max(1, int(0.006 * W)))


def boat(img, x, y, sc, color, mast=False, raft=False):
    d = ImageDraw.Draw(img)
    if raft:
        d.rounded_rectangle([x - sc * 1.5, y - sc * 0.12, x + sc * 1.5, y + sc * 0.12],
                            radius=sc * 0.1, fill=color)
        d.line([(x + sc * 0.9, y), (x + sc * 1.25, y - sc * 1.5)], fill=color, width=max(2, SS))
        return
    d.polygon([(x - sc * 1.4, y), (x + sc * 1.4, y), (x + sc * 0.95, y + sc * 0.42),
               (x - sc * 0.95, y + sc * 0.42)], fill=color)
    if mast:
        d.polygon([(x, y - sc * 1.9), (x + sc * 0.85, y - sc * 0.15), (x, y - sc * 0.15)], fill=color)
        d.line([(x, y), (x, y - sc * 1.95)], fill=color, width=max(2, SS))


def birds(img, x, y, sc, color, n=7):
    rnd = random.Random(int(x) + int(y))
    d = ImageDraw.Draw(img)
    for _ in range(n):
        bx = x + rnd.uniform(-sc * 3, sc * 3)
        by = y + rnd.uniform(-sc * 1.4, sc * 1.4)
        w = rnd.uniform(0.5, 1.2) * sc
        d.arc([bx - w, by - w * 0.6, bx, by + w * 0.5], 200, 340, fill=color, width=max(1, SS))
        d.arc([bx, by - w * 0.6, bx + w, by + w * 0.5], 200, 340, fill=color, width=max(1, SS))


def ger(img, x, y, sc, color):
    d = ImageDraw.Draw(img)
    d.pieslice([x - sc, y - sc * 0.9, x + sc, y + sc * 0.5], 180, 360, fill=color)
    d.rectangle([x - sc, y - sc * 0.2, x + sc, y + sc * 0.05], fill=color)


def camel(img, x, y, sc, color):
    d = ImageDraw.Draw(img)
    d.ellipse([x - sc, y - sc * 0.75, x + sc, y], fill=color)
    for cx in (-0.45, 0.4):
        d.ellipse([x + cx * sc - sc * 0.3, y - sc * 1.2, x + cx * sc + sc * 0.3, y - sc * 0.5],
                  fill=color)
    d.line([(x + sc * 0.9, y - sc * 0.55), (x + sc * 1.25, y - sc * 1.25)], fill=color,
           width=max(2, int(1.6 * SS)))
    d.ellipse([x + sc * 1.15, y - sc * 1.4, x + sc * 1.5, y - sc * 1.1], fill=color)
    for lx in (-0.7, -0.25, 0.3, 0.75):
        d.line([(x + lx * sc, y - sc * 0.1), (x + lx * sc, y + sc * 0.75)], fill=color,
               width=max(2, int(1.6 * SS)))


def road(img, y0, color, curve=0.25):
    """沙漠公路：透视梯形 + 中线"""
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(25):
        t = i / 24
        y = y0 + (W - y0) * t
        half = W * (0.006 + 0.16 * t ** 1.6)
        cx = W * (0.5 + curve * math.sin(t * 2.2))
        pts.append((y, cx, half))
    left = [(cx - half, y) for y, cx, half in pts]
    right = [(cx + half, y) for y, cx, half in reversed(pts)]
    d.polygon(left + right, fill=color)
    for y, cx, half in pts[::2]:
        d.line([(cx - half * 0.03, y), (cx + half * 0.03, y + 3)],
               fill=mix(color, "#ffffff", 0.6), width=max(2, SS))


def waterfall(img, x, y0, y1, w, color):
    """瀑布：上窄下宽的水帘（低对比多股 + 落点水雾）"""
    ov = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    col = rgb(color)
    d.polygon([(x - w * 0.45, y0), (x + w * 0.45, y0), (x + w * 1.5, y1), (x - w * 1.5, y1)],
              fill=col + (105,))
    d.polygon([(x - w * 0.30, y0), (x + w * 0.30, y0), (x + w * 0.95, y1), (x - w * 0.95, y1)],
              fill=col + (85,))
    for i in range(6):
        xx = x - w * 0.75 + i * w * 0.30
        d.line([(xx, y0 + 4), (xx - w * 0.20, y1 - w * 0.2)],
               fill=(255, 255, 255, 80), width=max(1, SS))
    d.ellipse([x - w * 2.0, y1 - w * 0.4, x + w * 2.0, y1 + w * 1.1],
              fill=(255, 255, 255, 62))
    img.alpha_composite(ov.filter(ImageFilter.GaussianBlur(w * 0.62)))

def rock_art(img, color, seed, panel=(0.18, 0.62, 0.82, 0.98)):
    """贺兰山岩画：岩面 + 人面/射手/动物刻痕"""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = [v * W for v in panel]
    d.rounded_rectangle([x0, y0, x1, y1], radius=0.02 * W, fill=color)
    ink = mix(color, "#f0e0bc", 0.85)
    for _ in range(9):
        cx = rnd.uniform(x0 + 24, x1 - 24)
        cy = rnd.uniform(y0 + 24, y1 - 28)
        sc = rnd.uniform(0.012, 0.028) * W
        kind = rnd.random()
        if kind < 0.4:
            d.ellipse([cx - sc, cy - sc, cx + sc, cy + sc], outline=ink, width=max(2, SS))
            d.line([(cx - sc * 0.4, cy - sc * 0.2), (cx - sc * 0.15, cy - sc * 0.2)], fill=ink, width=SS)
            d.line([(cx + sc * 0.15, cy - sc * 0.2), (cx + sc * 0.4, cy - sc * 0.2)], fill=ink, width=SS)
            d.line([(cx - sc * 0.4, cy + sc * 0.4), (cx + sc * 0.4, cy + sc * 0.4)], fill=ink, width=SS)
        elif kind < 0.7:
            d.line([(cx, cy + sc), (cx, cy - sc)], fill=ink, width=max(2, SS))
            d.line([(cx - sc, cy - sc * 1.4), (cx, cy - sc * 0.4)], fill=ink, width=max(2, SS))
            d.line([(cx + sc, cy - sc * 1.4), (cx, cy - sc * 0.4)], fill=ink, width=max(2, SS))
            d.arc([cx - sc * 1.4, cy - sc, cx + sc * 1.4, cy + sc * 1.6], 200, 340, fill=ink, width=SS)
        else:
            d.ellipse([cx - sc, cy - sc * 0.6, cx + sc, cy + sc * 0.4], outline=ink, width=max(2, SS))
            d.line([(cx + sc * 0.7, cy - sc * 0.4), (cx + sc * 1.3, cy - sc)], fill=ink, width=max(2, SS))


def stars(img, seed, y_max, n=150):
    ov = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.uniform(0, W), rnd.uniform(0, y_max)
        r = rnd.choice([1, 1, 1, 2]) * SS * 0.5
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 245, rnd.randint(90, 255)))
    img.alpha_composite(ov)


def sun(img, x, y, r, color, glow=1.8):
    ov = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    c = rgb(color)
    d.ellipse([x - r * glow * 2.4, y - r * glow * 2.4, x + r * glow * 2.4, y + r * glow * 2.4],
              fill=c + (44,))
    d.ellipse([x - r * glow, y - r * glow, x + r * glow, y + r * glow], fill=c + (95,))
    d.ellipse([x - r, y - r, x + r, y + r], fill=c + (235,))
    img.alpha_composite(ov.filter(ImageFilter.GaussianBlur(r * 0.5)))


def mist(img, y, h, alpha=70, tint="#ffffff"):
    ov = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(ov).rectangle([0, y - h / 2, W, y + h / 2], fill=rgb(tint) + (alpha,))
    img.alpha_composite(ov.filter(ImageFilter.GaussianBlur(h * 0.9)))

# ---------- 配色 ----------
PALETTES = {
    "dawn":    dict(sky=["#1d2a4d", "#7c5a80", "#f3bd85"], haze="#f7dcbc", ink="#241a2b",
                    water="#8e6f86", ground="#3a2b3c"),
    "dayblue": dict(sky=["#1c4f7c", "#6ba9cd", "#e2f1f8"], haze="#dcecf4", ink="#1d3143",
                    water="#3f7fa6", ground="#2f4d3a"),
    "emerald": dict(sky=["#0f3f3d", "#33836d", "#d3e9d4"], haze="#cfe6d6", ink="#123028",
                    water="#1f6f5c", ground="#22493a"),
    "golden":  dict(sky=["#3b2a17", "#a76f2d", "#f8dc9f"], haze="#f6e0b0", ink="#3a2415",
                    water="#8a6a3a", ground="#5a4324"),
    "dusk":    dict(sky=["#101a33", "#4c3d6d", "#e58f63"], haze="#c99f8a", ink="#181425",
                    water="#4a3f63", ground="#2a2334"),
    "night":   dict(sky=["#04060e", "#0f1c38", "#33456b"], haze="#2b3a5c", ink="#0a0f1c",
                    water="#16233f", ground="#111726"),
    "snow":    dict(sky=["#2a4a66", "#84abcd", "#eef6fa"], haze="#e8f2f8", ink="#22313f",
                    water="#5d8bab", ground="#3d4f5c"),
    "ochre":   dict(sky=["#4a3a22", "#b08a50", "#f2e0bb"], haze="#efdcbc", ink="#4a3418",
                    water="#9c8149", ground="#6d5326"),
    "redrock": dict(sky=["#3a2130", "#a4493d", "#f3ac7c"], haze="#f0c39a", ink="#3a1b18",
                    water="#8c4a3c", ground="#5c2a22"),
    "tealsea": dict(sky=["#0d3b52", "#4399aa", "#e9f6f3"], haze="#dcefec", ink="#12333c",
                    water="#2f8497", ground="#2b4f4a"),
}


def ctx_of(name, pal, seed):
    return dict(name=name, seed=seed, p=PALETTES[pal], rnd=random.Random(seed))


def layer(img, c, base, amp, rough, depth, peaky=0.0, n=129):
    """一层山脊。depth 0=最远（几乎融进天空），1=最近（接近墨色）"""
    col = mix(mix(c["p"]["sky"][-1], c["p"]["haze"], 0.5), c["p"]["ink"], depth)
    pts = ridge_points(c["seed"] + int(base * 1000), base * W, amp * W, rough, n=n, peaky=peaky)
    fill_poly(img, pts, col)
    return col


def flat(img, y0, col):
    ImageDraw.Draw(img).rectangle([0, y0, W, W], fill=col)


def depth_col(c, depth):
    return mix(mix(c["p"]["sky"][-1], c["p"]["haze"], 0.45), c["p"]["ink"], depth)


def finish(img, vignette=0.32, grain=14):
    """统一做旧：胶片颗粒 + 轻微暗角，让整套插画风格一致"""
    img = img.convert("RGB")
    if grain:
        noise = Image.effect_noise((W, W), grain).convert("L")
        ov = ImageChops.overlay(img, Image.merge("RGB", (noise, noise, noise)))
        img = Image.blend(img, ov, 0.16)
    if vignette:
        mask = Image.new("L", (W, W), 0)
        ImageDraw.Draw(mask).ellipse([-W * 0.22, -W * 0.22, W * 1.22, W * 1.22], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(W * 0.15))
        shade = Image.new("RGBA", (W, W), (8, 10, 18, 0))
        shade.putalpha(mask.point(lambda v: int((255 - v) * vignette)))
        img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    return img

# ---------- 场景配方 ----------
def base(img, c, sun=None, star=False, clouds=0):
    img.paste(sky_gradient(c["p"]["sky"]), (0, 0))
    if star:
        stars(img, c["seed"], W * 0.5)
    if sun:
        sun_disc(img, sun[0] * W, sun[1] * W, sun[2] * W,
                 mix(c["p"]["sky"][-1], "#fff4dc", 0.72))
    rnd = c["rnd"]
    for _ in range(clouds):
        y = rnd.uniform(0.12, 0.42) * W
        w = rnd.uniform(0.25, 0.6) * W
        x = rnd.uniform(-0.1, 0.9) * W
        mist(img, y, w * 0.12, alpha=rnd.randint(18, 34), tint=c["p"]["haze"])


def sun_disc(img, x, y, r, color, glow=1.5):
    """日/月光斑：小而柔，避免盖过地形主体"""
    ov = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    col = rgb(color)
    d.ellipse([x - r * glow * 2.1, y - r * glow * 2.1, x + r * glow * 2.1, y + r * glow * 2.1],
              fill=col + (26,))
    d.ellipse([x - r * glow, y - r * glow, x + r * glow, y + r * glow], fill=col + (64,))
    d.ellipse([x - r, y - r, x + r, y + r], fill=col + (215,))
    img.alpha_composite(ov.filter(ImageFilter.GaussianBlur(r * 0.9)))


def band(img, pts, w0, w1, color):
    """沿中心线画一条宽度渐变的带子（河流/栈道/公路）"""
    d = ImageDraw.Draw(img)
    n = len(pts)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        px, py = pts[max(0, i - 1)]
        nx2, ny2 = pts[min(n - 1, i + 1)]
        dx, dy = nx2 - px, ny2 - py
        ln = math.hypot(dx, dy) or 1.0
        ox, oy = -dy / ln, dx / ln
        t = i / (n - 1)
        hw = (w0 + (w1 - w0) * t) / 2.0
        left.append((x + ox * hw, y + oy * hw))
        right.append((x - ox * hw, y - oy * hw))
    d.polygon(left + list(reversed(right)), fill=color)


def karst_lake(img, c):
    layer(img, c, 0.60, 0.05, 0.5, 0.25)
    draw_cones(img, c["seed"], 0.63 * W, 9, 0.10 * W, 0.24 * W, depth_col(c, 0.5))
    draw_cones(img, c["seed"] + 7, 0.68 * W, 7, 0.14 * W, 0.30 * W, depth_col(c, 0.75))
    draw_water(img, c["seed"] + 3, 0.68 * W, c["p"]["water"])
    boat(img, 0.68 * W, 0.84 * W, 0.035 * W, c["p"]["ink"], mast=True)
    trees(img, c["seed"] + 11, 0.70 * W, 5, 0.05 * W, 0.09 * W, c["p"]["ink"], kind="reed")


def karst_paddy(img, c):
    layer(img, c, 0.52, 0.06, 0.55, 0.3)
    draw_cones(img, c["seed"], 0.58 * W, 10, 0.12 * W, 0.28 * W, depth_col(c, 0.55))
    flat(img, 0.60 * W, mix(c["p"]["ground"], c["p"]["haze"], 0.25))
    draw_terraces(img, 0.62 * W, W, 9, mix(c["p"]["ground"], c["p"]["water"], 0.75),
                  mix(c["p"]["ground"], c["p"]["haze"], 0.1), c["p"]["ink"])
    roofs(img, 0.72 * W, 0.66 * W, 3, 0.05 * W, c["p"]["ink"], style="hui", rnd=c["rnd"])
    boat(img, 0.3 * W, 0.9 * W, 0.04 * W, c["p"]["ink"], raft=True)


def stone_wall(img, c):
    """扎尕那：环形石壁（整面平顶陡崖）+ 谷底藏寨"""
    d = ImageDraw.Draw(img)
    wall = [(x, 0.30 * W + 0.055 * W * math.sin(x / W * math.pi * 2.6) +
             0.02 * W * math.sin(x / W * math.pi * 7.3)) for x in range(0, W + 1, 20)]
    d.polygon(wall + [(W, W), (0, W)], fill=depth_col(c, 0.42))
    inner = [(x, y + 0.055 * W) for x, y in wall]
    d.polygon(inner + [(W, W), (0, W)], fill=depth_col(c, 0.6))
    mist(img, 0.52 * W, 0.05 * W, alpha=64, tint=c["p"]["haze"])
    flat(img, 0.72 * W, mix(c["p"]["ground"], c["p"]["ink"], 0.25))
    d.polygon([(0.05 * W, 0.72 * W), (0.30 * W, 0.5 * W), (0.34 * W, 0.72 * W)],
              fill=depth_col(c, 0.75))
    d.polygon([(0.66 * W, 0.72 * W), (0.82 * W, 0.46 * W), (0.9 * W, 0.72 * W)],
              fill=depth_col(c, 0.7))
    roofs(img, 0.28 * W, 0.87 * W, 6, 0.075 * W, c["p"]["ink"], style="tibet", rnd=c["rnd"])
    trees(img, c["seed"] + 2, 0.99 * W, 10, 0.07 * W, 0.13 * W, c["p"]["ink"], kind="pine")


def steppe(img, c):
    """草原：低缓丘陵 + 大片天空 + 蒙古包与白桦"""
    d = ImageDraw.Draw(img)
    layer(img, c, 0.68, 0.05, 0.45, 0.2)
    for i, (yy, amp, depth) in enumerate(((0.74, 0.030, 0.42), (0.82, 0.026, 0.6), (0.93, 0.02, 0.8))):
        pts = [(x, yy * W - amp * W * math.sin(x / W * math.pi * (1.3 + 0.6 * i) + i * 2.1))
               for x in range(0, W + 1, 20)]
        d.polygon(pts + [(W, W), (0, W)], fill=depth_col(c, depth))
    for i, (fx, fy, sc) in enumerate(((0.30, 0.80, 0.9), (0.62, 0.86, 1.15), (0.44, 0.94, 1.4))):
        ger(img, fx * W, fy * W, 0.030 * W * sc, c["p"]["ink"])
    trees(img, c["seed"] + 4, 0.78 * W, 3, 0.045 * W, 0.065 * W, c["p"]["ink"], kind="birch")


def steppe_lake(img, c):
    layer(img, c, 0.58, 0.07, 0.5, 0.3)
    draw_water(img, c["seed"] + 3, 0.62 * W, c["p"]["water"])
    trees(img, c["seed"] + 9, 0.98 * W, 26, 0.10 * W, 0.22 * W, c["p"]["ink"], kind="reed")
    birds(img, 0.55 * W, 0.3 * W, 0.02 * W, c["p"]["ink"])


def pine_at(d, x, y, h, col):
    """在指定位置画一棵小针叶树（树脚在 y）"""
    w = h * 0.36
    for k in range(3):
        yy = y - h * (0.22 + 0.26 * k)
        d.polygon([(x - w * (1 - k * 0.26), yy), (x, yy - h * 0.42),
                   (x + w * (1 - k * 0.26), yy)], fill=col)
    d.rectangle([x - h * 0.04, y - h * 0.28, x + h * 0.04, y], fill=col)


def gorge_bend(img, c, waterfall=False, boat_it=True):
    """峡谷：两侧陡壁夹一条向观者蜿蜒展开的河道（怒江第一湾/安集海/关门山/屏山）"""
    rnd = c["rnd"]
    d = ImageDraw.Draw(img)
    layer(img, c, 0.62, 0.08, 0.5, 0.3)                           # 远处山脊
    river = mix(c["p"]["water"], c["p"]["haze"], 0.45)
    y_top, top_l, top_r, bot_l, bot_r = 0.66, 0.40, 0.58, 0.06, 0.94
    phase = (0.0, 2.4)

    def shore(side, t):
        """岸线：从远处河道口斜插到观者，带一点蜿蜒"""
        k = 0 if side == "L" else 1
        x0, x1 = (top_l, bot_l) if side == "L" else (top_r, bot_r)
        wob = math.sin(t * math.pi * 1.5 + phase[k]) * 0.030 + math.sin(t * 7.3 + k * 2.0) * 0.008
        return ((x0 + (x1 - x0) * t + wob) * W, (y_top + (1.0 - y_top) * t) * W)

    # 两侧谷壁：锯齿顶，内缘就是蛇形岸线
    walls = {}
    for side, depth in (("L", 0.72), ("R", 0.9)):
        edge, steps = [], 16
        for i in range(steps + 1):
            t = i / steps
            if side == "L":
                x, y = t * top_l * W, (0.14 + 0.52 * t ** 1.5) * W
            else:
                x, y = W - t * (1.0 - top_r) * W, (0.10 + 0.56 * t ** 1.5) * W
            edge.append((x, y - (0.05 + 0.05 * (1 - t)) * W * abs(math.sin(t * 9 + (0 if side == "L" else 2)))))
        tail = [shore(side, i / 10.0) for i in range(1, 11)]
        tail += [(0, W), (0, 0)] if side == "L" else [(W, W), (W, 0)]
        col = depth_col(c, depth)
        d.polygon(edge + tail, fill=col)
        walls[side] = (edge, col)

    # 崖壁层理：从顶缘拐点向下拉竖向条带（伸出河道的部分稍后被水面盖住）
    for side, (edge, col) in walls.items():
        dark, light = mix(col, c["p"]["ink"], 0.24), mix(col, "#ffffff", 0.11)
        for i, (ex, ey) in enumerate(edge):
            if i % 2 or ex < 0.02 * W or ex > 0.98 * W:
                continue
            lean = 0.014 * W if side == "L" else -0.014 * W
            d.line([(ex, ey + 0.015 * W), (ex + lean, W)],
                   fill=dark if i % 4 == 0 else light, width=max(1, int(0.013 * W)))

    # 河面
    L = [shore("L", i / 20.0) for i in range(21)]
    R = [shore("R", i / 20.0) for i in range(21)]
    d.polygon(L + list(reversed(R)), fill=river)

    def span(y):
        t = min(1.0, max(0.0, (y - y_top * W) / ((1.0 - y_top) * W)))
        return shore("L", t)[0], shore("R", t)[0], t

    for _ in range(150):                                           # 打散的高光碎波（避免等距"车道线"）
        y = (y_top + (1.0 - y_top) * rnd.random() ** 0.75) * W
        x0, x1, t = span(y)
        ln = rnd.uniform(0.012, 0.055) * (0.45 + t) * W
        a = rnd.uniform(x0 + 2, max(x0 + 3, x1 - ln - 2))
        d.line([(a, y), (a + ln, y)], fill=mix(river, "#ffffff", rnd.uniform(0.14, 0.34)),
               width=max(1, int((0.6 + 1.4 * t) * SS)))
    for i in range(7):                                             # 远处水面反光带（宽而淡，非中线）
        t = i / 7
        y = (y_top + 0.02 + (0.30 - 0.26 * t) * (1.0 - y_top)) * W
        x0, x1, _ = span(y)
        a = rnd.uniform(x0, x1)
        b = min(x1, a + rnd.uniform(0.10, 0.26) * W)
        d.line([(a, y), (b, y)], fill=mix(river, "#fff6e2", 0.30 - 0.03 * i),
               width=max(1, int((1.0 + 2.0 * t) * SS)))
    for pts in (L, R):                                             # 岸线亮边
        d.line(pts, fill=mix(river, c["p"]["haze"], 0.55), width=max(1, int(1.6 * SS)))

    if waterfall:
        waterfall_draw(img, 0.82 * W, 0.32 * W, 0.84 * W, 0.030 * W,
                       mix(c["p"]["haze"], "#ffffff", 0.50))
    if boat_it:
        boat(img, 0.5 * W, 0.93 * W, 0.03 * W, c["p"]["ink"], raft=True)
    mist(img, (y_top - 0.012) * W, 0.04 * W, alpha=44, tint=c["p"]["haze"])
    for side, (edge, _col) in walls.items():                       # 崖顶针叶林贴着顶缘
        for i, (ex, ey) in enumerate(edge[:-1]):
            if i % 3 or ex < 0.03 * W or ex > 0.97 * W or ey > (y_top - 0.07) * W:
                continue
            h = (0.026 + 0.020 * ((i * 7919 + len(side)) % 11) / 11.0) * W
            pine_at(d, ex, ey + 0.005 * W, h, c["p"]["ink"])


def waterfall_draw(img, x, y0, y1, w, color):
    waterfall(img, x, y0, y1, w, color)


def terraces(img, c):
    layer(img, c, 0.44, 0.14, 0.6, 0.35)
    flat(img, 0.46 * W, mix(c["p"]["ground"], c["p"]["haze"], 0.3))
    draw_terraces(img, 0.5 * W, W, 10, mix(c["p"]["ground"], c["p"]["water"], 0.72),
                  mix(c["p"]["ground"], c["p"]["haze"], 0.12), c["p"]["ink"])
    roofs(img, 0.7 * W, 0.56 * W, 4, 0.06 * W, c["p"]["ink"], style="tibet", rnd=c["rnd"])
    trees(img, c["seed"] + 1, 0.52 * W, 6, 0.05 * W, 0.1 * W, c["p"]["ink"], kind="pine")


def wave_sandstone(img, c):
    layer(img, c, 0.4, 0.05, 0.5, 0.2)
    d = ImageDraw.Draw(img)
    flat(img, 0.42 * W, mix(c["p"]["ground"], c["p"]["ink"], 0.1))
    for i in range(16):
        t = i / 16
        y = 0.42 * W + (W * 0.62) * t ** 1.25
        col = mix(mix(c["p"]["ground"], "#f6c99a", 0.5 - 0.5 * t), c["p"]["ink"], t * 0.45)
        pts = [(x, y + math.sin(x / W * math.pi * (2.2 + i * 0.35) + i) * (7 + 26 * t) * SS * 0.35)
               for x in range(0, W + 1, 10)]
        d.line(pts, fill=col, width=max(3, int((4 + 12 * t) * SS * 0.5)))


def rock_art_scene(img, c):
    layer(img, c, 0.5, 0.2, 0.62, 0.5, peaky=3)
    flat(img, 0.6 * W, mix(c["p"]["ground"], c["p"]["ink"], 0.35))
    rock_art(img, mix(c["p"]["ground"], "#c9a06a", 0.45), c["seed"] + 4,
             panel=(0.14, 0.6, 0.86, 0.99))


def hui_village(img, c):
    layer(img, c, 0.5, 0.12, 0.55, 0.35)
    flat(img, 0.56 * W, mix(c["p"]["ground"], c["p"]["haze"], 0.25))
    roofs(img, 0.12 * W, 0.66 * W, 7, 0.11 * W, c["p"]["ink"], style="hui", rnd=c["rnd"])
    draw_water(img, c["seed"] + 3, 0.7 * W, c["p"]["water"], ripples=14)
    bridge(img, 0.86 * W, c["p"]["ink"], arches=3)
    trees(img, c["seed"] + 8, 0.62 * W, 5, 0.08 * W, 0.14 * W, c["p"]["ink"], kind="pine")


def yardang(img, c, road_it=False, star=False, city=False):
    flat(img, 0.6 * W, mix(c["p"]["ground"], c["p"]["haze"], 0.35))
    draw_pillars(img, c["seed"], 0.66 * W, 12, 0.10 * W, 0.30 * W, depth_col(c, 0.6))
    draw_pillars(img, c["seed"] + 9, 0.78 * W, 7, 0.12 * W, 0.34 * W, depth_col(c, 0.85))
    if city:
        skyline(img, 0.62 * W, mix(c["p"]["haze"], "#ffffff", 0.55), c["seed"] + 2, maxh=0.2)
    if star:
        stars(img, c["seed"], 0.5 * W)
    if road_it:
        flat(img, 0.8 * W, mix(c["p"]["ground"], c["p"]["ink"], 0.15))
        road(img, 0.8 * W, mix(c["p"]["ink"], "#dcd0c0", 0.35), curve=0.18)
    else:
        draw_dunes(img, c["seed"] + 5, 0.86 * W, 0.1 * W, mix(c["p"]["ground"], c["p"]["ink"], 0.25))


def stone_forest(img, c):
    layer(img, c, 0.55, 0.1, 0.5, 0.35)
    flat(img, 0.6 * W, mix(c["p"]["ground"], c["p"]["haze"], 0.2))
    draw_pillars(img, c["seed"], 0.72 * W, 9, 0.16 * W, 0.34 * W, depth_col(c, 0.7))
    draw_pillars(img, c["seed"] + 3, 0.9 * W, 5, 0.2 * W, 0.42 * W, c["p"]["ink"])
    trees(img, c["seed"] + 6, 0.95 * W, 8, 0.07 * W, 0.13 * W, c["p"]["ink"], kind="pine")


def coast(img, c, pans=False):
    """海岸：远处低丘 + 潮水 + 近处滩涂/盐田"""
    d = ImageDraw.Draw(img)
    layer(img, c, 0.5, 0.05, 0.5, 0.25)
    if pans:
        draw_water(img, c["seed"] + 3, 0.54 * W, c["p"]["water"], ripples=8)
        flat(img, 0.62 * W, mix(c["p"]["water"], c["p"]["haze"], 0.45))
        draw_grid_pans(img, c["seed"], 0.62 * W, mix(c["p"]["haze"], "#ffffff", 0.75),
                       mix(c["p"]["water"], "#ffffff", 0.4))
    else:
        draw_water(img, c["seed"] + 3, 0.54 * W, c["p"]["water"], ripples=16)
        d.polygon([(0, 0.80 * W), (0.25 * W, 0.76 * W), (0.55 * W, 0.80 * W),
                   (0.8 * W, 0.755 * W), (W, 0.79 * W), (W, W), (0, W)],
                  fill=mix(c["p"]["ground"], c["p"]["ink"], 0.35))
        trees(img, c["seed"] + 7, 0.9 * W, 6, 0.10 * W, 0.16 * W, c["p"]["ink"], kind="mangrove")
        birds(img, 0.5 * W, 0.26 * W, 0.016 * W, c["p"]["ink"])


def city_river(img, c):
    layer(img, c, 0.55, 0.06, 0.5, 0.25)
    skyline(img, 0.62 * W, depth_col(c, 0.55), c["seed"], maxh=0.22)
    draw_water(img, c["seed"] + 3, 0.66 * W, c["p"]["water"], ripples=12)
    bridge(img, 0.88 * W, c["p"]["ink"], arches=5)
    train(img, 0.42 * W, 0.805 * W, 0.035 * W, c["p"]["ink"])


def drum_tower_scene(img, c):
    layer(img, c, 0.46, 0.16, 0.62, 0.3, peaky=2)
    mist(img, 0.52 * W, 0.045 * W, alpha=70, tint=c["p"]["haze"])
    layer(img, c, 0.62, 0.14, 0.6, 0.6)
    flat(img, 0.7 * W, mix(c["p"]["ground"], c["p"]["ink"], 0.2))
    drum_tower(img, 0.5 * W, 0.86 * W, 0.34 * W, c["p"]["ink"])
    roofs(img, 0.16 * W, 0.88 * W, 3, 0.08 * W, c["p"]["ink"], style="drum", rnd=c["rnd"])
    roofs(img, 0.68 * W, 0.88 * W, 3, 0.08 * W, c["p"]["ink"], style="drum", rnd=c["rnd"])
    trees(img, c["seed"] + 4, 0.9 * W, 8, 0.07 * W, 0.13 * W, c["p"]["ink"], kind="pine")


def forest_falls(img, c):
    layer(img, c, 0.44, 0.2, 0.6, 0.4, peaky=3)
    layer(img, c, 0.6, 0.18, 0.62, 0.8, peaky=2)
    waterfall_draw(img, 0.3 * W, 0.5 * W, 0.9 * W, 0.05 * W,
                   mix(c["p"]["haze"], "#ffffff", 0.6))
    draw_water(img, c["seed"] + 3, 0.9 * W, c["p"]["water"], ripples=8)
    trees(img, c["seed"] + 2, 0.98 * W, 14, 0.14 * W, 0.3 * W, c["p"]["ink"], kind="pine")
    roofs(img, 0.66 * W, 0.86 * W, 3, 0.09 * W, c["p"]["ink"], style="tibet", rnd=c["rnd"])


def mesa(img, c):
    """黄土台峁 + 远处寺庙白塔（忻州 / 五台山意象）"""
    layer(img, c, 0.52, 0.08, 0.55, 0.3)
    for i, (base_y, amp) in enumerate(((0.62, 0.05), (0.72, 0.045), (0.84, 0.04))):
        d = ImageDraw.Draw(img)
        ph = 1.6 + i * 0.7
        pts = []
        for x in range(0, W + 1, 14):
            wave = 0.5 + 0.5 * math.sin(x / W * math.pi * ph + i)
            pts.append((x, base_y * W - amp * W * wave))
        d.polygon(pts + [(W, W), (0, W)], fill=depth_col(c, 0.35 + 0.25 * i))
    pagoda(img, 0.76 * W, 0.66 * W, 0.2 * W, c["p"]["ink"], tiers=5)
    trees(img, c["seed"] + 3, 0.99 * W, 6, 0.08 * W, 0.14 * W, c["p"]["ink"], kind="pine")


RECIPES = {
    "karst_lake": karst_lake, "karst_paddy": karst_paddy, "stone_wall": stone_wall,
    "steppe": steppe, "steppe_lake": steppe_lake, "gorge_bend": gorge_bend,
    "terraces": terraces, "wave_sandstone": wave_sandstone,
    "rock_art": rock_art_scene,
    "hui_village": hui_village, "yardang": yardang, "stone_forest": stone_forest,
    "coast": coast, "city_river": city_river, "drum_tower": drum_tower_scene,
    "forest_falls": forest_falls, "mesa": mesa,
}

# ---------- 渲染入口 ----------
def render(name, spec):
    c = ctx_of(name, spec.get("pal", "dayblue"), int(hashlib.md5(name.encode()).hexdigest()[:8], 16))
    img = Image.new("RGBA", (W, W), (0, 0, 0, 255))
    base(img, c, sun=spec.get("sun"), star=spec.get("star", False),
         clouds=spec.get("clouds", 0))
    RECIPES[spec["recipe"]](img, c, **spec.get("args", {}))
    return finish(img, vignette=spec.get("vignette", 0.32)).resize((EDGE, EDGE), Image.LANCZOS)


def main():
    scenes = json.loads(SCENES.read_text(encoding="utf-8"))
    made = []
    for mode, items in scenes.items():
        dest_dir = ROOT / "web" / "public" / "images" / mode
        dest_dir.mkdir(parents=True, exist_ok=True)
        for name, spec in items.items():
            if ONLY and name not in ONLY:
                continue
            dest = dest_dir / (name + ".webp")
            if dest.exists() and not FORCE:
                continue
            img = render(name, spec)
            img.save(dest, "WEBP", quality=82, method=6)
            made.append((mode, name, dest.stat().st_size))
            print("[ill] %-6s %-12s %-14s %s" % (
                mode, name, spec["recipe"], str(dest.stat().st_size) + "B"))
    if not made:
        print("没有需要补的插画（都已存在；用 --force 重绘）")
    else:
        print("共生成 %d 张，平均 %.1f KB" % (len(made), sum(m[2] for m in made) / len(made) / 1024))


if __name__ == "__main__":
    raise SystemExit(main())
