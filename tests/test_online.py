# 在线模式端到端：真起 BFF（文件存储 + 开发态短信），浏览器走 登录 -> 对局 -> 全网榜
import json, os, socket, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("GD_BASE", "http://127.0.0.1:5173")
PORT = int(os.environ.get("GD_API_PORT", "8799"))
API = "http://127.0.0.1:%d" % PORT
DB = ROOT / "tests" / "_online_db.json"
if DB.exists():
    DB.unlink()
NODE = shutil_ = sys.executable  # placeholder to keep linters quiet
from playwright.sync_api import sync_playwright

env = dict(os.environ, PORT=str(PORT), HOST="127.0.0.1", GD_DB=str(DB), SMS_PROVIDER="dev", GD_JWT_SECRET="e2e")
proc = subprocess.Popen(["node", str(ROOT / "server/src/server.js")], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            urllib.request.urlopen(API + "/v1/health", timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise SystemExit("BFF 未能在 20s 内就绪")

    def get(path):
        return json.loads(urllib.request.urlopen(API + path, timeout=10).read())

    fails = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page(viewport={"width": 1280, "height": 860})
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        Q = "?api=%s&online=1" % API

        # —— 登录 ——
        page.goto(BASE + Q + "/#")
        page.wait_for_selector("#online-row", timeout=15000)
        page.fill("#login-phone", "13800001111")
        page.click("#btn-code")
        page.wait_for_function("() => /开发环境验证码：\\d{6}/.test(document.getElementById('login-tip').textContent)", timeout=8000)
        code = page.evaluate("() => document.getElementById('login-tip').textContent.slice(-6)")
        page.fill("#login-code", code)
        page.fill("#nick-input", "E2E侦探")
        page.click("#btn-login")
        page.wait_for_selector(".or-on", timeout=8000)
        print("[登录] 开发态验证码登录成功，行内显示", page.locator(".or-on").inner_text())

        # —— 全网榜 tab ——
        page.click("#scope-global")
        page.wait_for_timeout(600)
        print("[榜单] 空榜文案:", page.locator("#board-list li").first.inner_text())

        # —— 对局 ——
        page.goto(BASE + Q + "/#/game/china")
        page.wait_for_selector("#q-name", timeout=30000)
        page.wait_for_function("() => window.__gdDebug", timeout=10000)
        q0 = page.evaluate("() => window.__gdDebug.stages[0].questions[0]")
        if "lat" in q0 or "lng" in q0:
            fails.append("在线题目泄漏坐标: %s" % q0)
        print("[出题] 服务端下发题目不含坐标:", sorted(q0.keys()))

        box = page.locator("#map-holder").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        for i in range(8):
            page.mouse.click(cx, cy)
            page.wait_for_selector("#confirm-pop:not(.hidden)", timeout=8000)
            page.click("#btn-confirm")
            page.wait_for_selector("#settle-pop:not(.hidden)", timeout=8000)
            detail = page.locator("#settle-detail").inner_text()
            if i == 0:
                print("[判分] 第 1 题服务端判分:", detail)
            page.click("#btn-next")
            page.wait_for_timeout(250)
            if page.locator(".stage-settle").count():
                break
        page.wait_for_selector(".stage-settle", timeout=10000)
        passed = page.locator(".ss-result").inner_text()
        print("[局结算] 服务端判定:", passed)
        page.click("#btn-stage-next")
        page.wait_for_selector(".result-page", timeout=10000)
        rank_txt = page.locator(".result-rank").inner_text()
        print("[终局] 全网名次:", rank_txt)
        if "第 1 名" not in rank_txt:
            fails.append("首个玩家应为全网第 1 名: %s" % rank_txt)

        # —— 服务端榜单核对 ——
        bd = get("/v1/boards/china?limit=5")
        if not bd["board"] or bd["board"][0]["nickname"] != "E2E侦探":
            fails.append("服务端榜单未写入: %s" % bd)
        print("[服务端] 全网榜第一条:", bd["board"][0])

        # —— 未登录访问在线对局应被拦回 ——
        ctx2 = b.new_context(viewport={"width": 900, "height": 700})
        p2 = ctx2.new_page()
        p2.goto(BASE + Q + "/#/game/china")
        p2.wait_for_selector(".result-stamp", timeout=10000)
        if "需登录" not in p2.locator(".result-stamp").inner_text():
            fails.append("未登录未被拦截")
        print("[拦截] 未登录进入在线对局被引导回登录 ✓")
        p2.close()
        ctx2.close()

        if errs:
            fails.append("页面报错: %s" % errs)
        b.close()
finally:
    proc.terminate()
    proc.wait(timeout=10)
    if DB.exists():
        DB.unlink()

if fails:
    for f in fails:
        print("  ✗", f)
    raise SystemExit(1)
print("在线模式端到端 ✅ 通过")
