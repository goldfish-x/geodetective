# -*- coding: utf-8 -*-
"""生成 web/public/gallery.html：历史线 480 张配图总览，可筛选/标记/导出
（历史版 6 档难度，星级条按 6 档渲染；不能用 5 档写死，否则 repeat(-1) 会整页报错）"""
import os,json,sys
sys.stdout.reconfigure(encoding="utf-8")
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(p):
    fp=os.path.join(R,p)
    return json.load(open(fp,encoding="utf-8")) if os.path.exists(fp) else {}
bank={m:rd("web/src/data/%s.json"%m) for m in ("china","world")}
co={m:rd("web/src/data/%s-coords.json"%m) for m in ("china","world")}
desc={m:rd("web/src/data/%s-desc.json"%m) for m in ("china","world")}
prov={}
for m in ("china","world"):
    for kind in ("commons","user","web","provenance","geo-provenance","alias-provenance"):
        for k,v in rd("scripts/%s-image-%s-provenance.json"%(m,kind)).items():
            if not isinstance(v,dict): continue
            p=m+"|"+k
            subj=v.get("subject","")
            src=v.get("source","")
            if subj=="event":
                badge = "自备生成图" if src=="generated" else ("用户提供" if src=="user" else "事件图")
            elif kind=="commons": badge="Commons 实景"
            elif kind=="web": badge="网络检索"
            else: badge="Commons 实景"
            prov.setdefault(p,{"badge":badge,"title":(v.get("title") or v.get("url") or "")[:90],
                               "license":(v.get("license") or "")[:40]})
RECHECK=set(json.load(open(os.path.join(R,"scripts/history-image-recheck-prompts.json"),encoding="utf-8"))) if os.path.exists(os.path.join(R,"scripts/history-image-recheck-prompts.json")) else set()
ITEM=[]
for m in ("china","world"):
    for x in bank[m]["history"]:
        n=x["name"]; p=m+"|"+n
        f=os.path.exists(os.path.join(R,"web/public/images/%s/%s.webp"%(m,n)))
        pv=prov.get(p,{})
        ill=set(json.load(open(os.path.join(R,"scripts/illustration-scenes.json"),encoding="utf-8"))) if os.path.exists(os.path.join(R,"scripts/illustration-scenes.json")) else set()
        badge=pv.get("badge") or ("代码插画" if n in ill else ("自备生成图" if desc[m].get(n,{}).get("img") else "自备素材"))
        ITEM.append({"m":m,"n":n,"t":x["difficulty"],"a":co[m][n][2],"hint":x["hint"],
                     "f":f,"b":badge,"ttl":pv.get("title",""),"lic":pv.get("license",""),
                     "r":1 if (m+"|"+n) in RECHECK else 0})
ITEM.sort(key=lambda x:(x["m"],x["t"],x["n"]))
from collections import Counter
cnt=Counter((i["m"],i["b"]) for i in ITEM)
print("items",len(ITEM)); [print("   ",k,v) for k,v in sorted(cnt.items())]
HTML="""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>历史配图总览 · 地理大侦探</title>
<style>
:root{--bg:#0f1419;--card:#171e26;--line:#243040;--fg:#e6edf3;--dim:#93a4b8;--acc:#ffb454;--bad:#ff5c5c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;z-index:9;background:rgba(15,20,25,.96);border-bottom:1px solid var(--line);padding:12px 16px}
h1{font-size:16px;margin:0 0 8px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:6px}
button{background:#1f2937;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:5px 10px;cursor:pointer;font-size:13px}
button.on{background:var(--acc);color:#111;border-color:var(--acc);font-weight:600}
input[type=search]{background:#0b1015;border:1px solid var(--line);color:var(--fg);border-radius:6px;padding:6px 10px;min-width:220px}
.stat{color:var(--dim);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;padding:14px 16px 120px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;cursor:pointer;position:relative}
.card img{display:block;width:100%;aspect-ratio:1/1;object-fit:cover;background:#0b1015}
.card .meta{padding:7px 9px}
.card .nm{font-size:13px;font-weight:600;line-height:1.3}
.card .sub{font-size:11px;color:var(--dim);margin-top:2px}
.card .bd{position:absolute;top:6px;left:6px;background:rgba(0,0,0,.66);border:1px solid var(--line);border-radius:5px;padding:2px 6px;font-size:10px;color:#cfe3ff}
.card.mark{border-color:var(--bad);box-shadow:0 0 0 2px var(--bad) inset}
.card.mark::after{content:"待换";position:absolute;top:6px;right:6px;background:var(--bad);color:#fff;font-size:10px;padding:2px 6px;border-radius:5px;font-weight:700}
.card.mute{opacity:.28}
footer{position:fixed;left:0;right:0;bottom:0;background:rgba(15,20,25,.98);border-top:1px solid var(--line);padding:8px 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
textarea{flex:1;min-height:52px;background:#0b1015;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px;font-size:12px;font-family:ui-monospace,Consolas,monospace}
.tip{color:var(--dim);font-size:12px}
</style></head><body>
<header>
  <h1>历史配图总览 · 中国篇 / 世界篇 480 张（六档）<span class="stat" id="stat"></span></h1>
  <div class="row">
    <span class="tip">篇章</span>
    <button data-f="m" data-v="" class="on">全部</button>
    <button data-f="m" data-v="china">中国篇</button>
    <button data-f="m" data-v="world">世界篇</button>
    <span class="tip">星级</span>
    <button data-f="t" data-v="" class="on">全部</button>
    <button data-f="t" data-v="1">1★</button><button data-f="t" data-v="2">2★</button>
    <button data-f="t" data-v="3">3★</button><button data-f="t" data-v="4">4★</button>
    <button data-f="t" data-v="5">5★</button><button data-f="t" data-v="6">6★</button>
    <button data-f="mark" data-v="">全部</button><button data-f="mark" data-v="1">只看待换</button>
    <input id="q" type="search" placeholder="搜事件名 / 省份国家（如 西安、洛阳）">
  </div>
  <div class="row tip">点卡片 = 标记「待换」（再点取消）。标记存在本机浏览器；标完把下面文本框内容发我即可。</div>
</header>
<div class="grid" id="grid"></div>
<footer>
  <button id="exp">导出待换名单</button><button id="clr">清空标记</button>
  <textarea id="out" placeholder="点「导出待换名单」后，这里会出现事件名清单，直接复制发我"></textarea>
</footer>
<script>
const DATA=__DATA__;
const KEY="gd_review_hist_v1";
let mark=new Set(JSON.parse(localStorage.getItem(KEY)||"null")||DATA.filter(d=>d.r).map(d=>d.m+"|"+d.n));
const st={m:"",t:"",mark:"",q:""};
const MAX_T=6;   // 历史版 6 档难度；星级条按 6 格渲染，避免 repeat(-1)
const grid=document.getElementById("grid");
function save(){localStorage.setItem(KEY,JSON.stringify([...mark]))}
function render(){
  const q=st.q.trim().toLowerCase();
  let shown=0;
  grid.innerHTML=DATA.filter(d=>{
    if(st.m&&d.m!==st.m)return false;
    if(st.t&&String(d.t)!==st.t)return false;
    if(st.mark==="1"&&!mark.has(d.m+"|"+d.n))return false;
    if(q&&!(d.n.toLowerCase().includes(q)||(d.a||"").toLowerCase().includes(q)||(d.hint||"").includes(q)))return false;
    return true;
  }).map((d,i)=>{
    shown++;
    const k=d.m+"|"+d.n, on=mark.has(k);
    return `<div class="card${on?" mark":""}" data-k="${k}">
      ${d.f?`<img loading="lazy" src="images/${d.m}/${encodeURIComponent(d.n)}.webp" alt="${d.n}">`
           :`<div class="meta" style="aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;color:#5b6b7d">缺图</div>`}
      <span class="bd">${d.b}</span>
      <div class="meta"><div class="nm">${d.n}</div>
      <div class="sub">${d.m==="china"?"中国篇":"世界篇"} · ${"★".repeat(Math.min(d.t,MAX_T))}${"☆".repeat(Math.max(0,MAX_T-d.t))} · ${d.a||"—"}</div></div></div>`;
  }).join("");
  document.getElementById("stat").textContent=`共 ${DATA.length} 张 · 当前 ${shown} · 待换 ${mark.size}`;
}
grid.addEventListener("click",e=>{
  const c=e.target.closest(".card"); if(!c)return;
  const k=c.dataset.k;
  if(mark.has(k))mark.delete(k); else mark.add(k);
  save(); render();
});
document.querySelectorAll("[data-f]").forEach(b=>b.addEventListener("click",()=>{
  const f=b.dataset.f;
  st[f]=b.dataset.v;
  document.querySelectorAll(`[data-f="${f}"]`).forEach(x=>x.classList.toggle("on",x===b));
  render();
}));
document.getElementById("q").addEventListener("input",e=>{st.q=e.target.value;render()});
document.getElementById("clr").addEventListener("click",()=>{
  if(confirm("清空所有「待换」标记？")){mark.clear();save();render()}
});
document.getElementById("exp").addEventListener("click",()=>{
  const list=DATA.filter(d=>mark.has(d.m+"|"+d.n)).map(d=>`${d.m==="china"?"中国篇":"世界篇"} ${d.n}`);
  document.getElementById("out").value=list.join("\\n");
  document.getElementById("out").select();
});
render();
</script></body></html>"""
HTML=HTML.replace("__DATA__",json.dumps(ITEM,ensure_ascii=False,separators=(",",":")))
out=os.path.join(R,"web/public/gallery.html")
open(out,"w",encoding="utf-8").write(HTML)
print("written",out,os.path.getsize(out)//1024,"KB")
