# -*- coding: utf-8 -*-
"""生成候选池页面 web/public/cand.html：每条事件 1-3 张候选，勾选后导出"""
import os,json,sys
sys.stdout.reconfigure(encoding="utf-8")
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(p):
    fp=os.path.join(R,p); return json.load(open(fp,encoding="utf-8")) if os.path.exists(fp) else {}
CAND=rd("web/public/cand/cand.json"); BR=rd("scripts/history-image-recheck-prompts.json")
INFO={}
for m in ("china","world"):
    d=rd("web/src/data/%s.json"%m); co=rd("web/src/data/%s-coords.json"%m)
    for x in d["history"]: INFO[m+"|"+x["name"]]=(x["difficulty"],co[x["name"]][2])
rows=[]
for k,cs in CAND.items():
    if not cs: continue
    m,n=k.split("|",1); t,a=INFO[k]
    rows.append({"m":m,"n":n,"t":t,"a":a,"c":[{"f":"cand/"+c["f"],"t":c["t"]} for c in cs]})
rows.sort(key=lambda r:(r["m"]!="china",r["t"],r["n"]))
HTML="""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>历史配图候选池 · 地理大侦探</title>
<style>
:root{--bg:#0f1419;--card:#171e26;--line:#243040;--fg:#e6edf3;--dim:#93a4b8;--ok:#2ea043;--acc:#ffb454}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;z-index:9;background:rgba(15,20,25,.97);border-bottom:1px solid var(--line);padding:10px 14px}
h1{font-size:15px;margin:0 0 6px}.dim{color:var(--dim);font-size:12px}
input{background:#0b1015;border:1px solid var(--line);color:var(--fg);border-radius:6px;padding:6px 10px;min-width:240px;margin-top:6px}
.ev{border-bottom:1px solid var(--line);padding:12px 14px}
.ev h3{margin:0 0 8px;font-size:14px}.ev h3 span{color:var(--dim);font-weight:400;font-size:12px;margin-left:8px}
.cands{display:flex;gap:10px;flex-wrap:wrap}
.cand{width:220px;border:2px solid var(--line);border-radius:8px;overflow:hidden;cursor:pointer;background:var(--card)}
.cand img{width:100%;aspect-ratio:1/1;object-fit:cover;display:block}
.cand .t{font-size:11px;color:var(--dim);padding:5px 6px;height:44px;overflow:hidden}
.cand.sel{border-color:var(--ok);box-shadow:0 0 0 2px rgba(46,160,67,.35)}
footer{position:fixed;left:0;right:0;bottom:0;background:rgba(15,20,25,.98);border-top:1px solid var(--line);padding:8px 12px;display:flex;gap:10px;align-items:center}
textarea{flex:1;height:46px;background:#0b1015;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px;font-size:12px}
button{background:#1f2937;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 10px;cursor:pointer}
</style></head><body>
<header><h1>历史配图候选池 · __N__ 条事件 / __C__ 张候选</h1>
<div class="dim">每条事件给了 1–3 张从百度图库检索到的高分辨率候选（标题是来源文章标题）。点选“这张可以用”，没一张合适的就留空。选完点右下「导出我选中的」，把文本发我，我按你选的入库。</div>
<input id="q" placeholder="搜事件名 / 省份国家"></header>
<div id="list"></div>
<footer><button id="exp">导出我选中的</button><textarea id="out" placeholder="点导出后这里出现清单"></textarea></footer>
<script>
const D=__DATA__;const K="gd_cand_pick_v1";
let sel=new Set(JSON.parse(localStorage.getItem(K)||"[]"));
const list=document.getElementById("list");
function draw(f){
  const q=(f||"").trim().toLowerCase();
  list.innerHTML=D.filter(r=>!q||r.n.toLowerCase().includes(q)||(r.a||"").toLowerCase().includes(q)).map(r=>{
    const k=r.m+"|"+r.n;
    return `<div class="ev"><h3>${r.n}<span>${r.m==="china"?"中国篇":"世界篇"} · ${"★".repeat(r.t)} · ${r.a||"—"}</span></h3>
    <div class="cands">`+r.c.map(c=>`<div class="cand${sel.has(k+"|"+c.f)?" sel":""}" data-k="${k}" data-f="${c.f}">
      <img loading="lazy" src="${encodeURI(c.f)}"><div class="t">${c.t}</div></div>`).join("")+`</div></div>`;
  }).join("");
}
list.addEventListener("click",e=>{
  const el=e.target.closest(".cand"); if(!el) return;
  const k=el.dataset.k, f=el.dataset.f;
  [...list.querySelectorAll(`.cand[data-k="${CSS.escape(k)}"]`)].forEach(x=>x.classList.remove("sel"));
  const key=k+"|"+f;
  if(sel.has(key)) sel.delete(key); else { sel.add(key); el.classList.add("sel"); }
  localStorage.setItem(K,JSON.stringify([...sel]));
});
document.getElementById("q").addEventListener("input",e=>draw(e.target.value));
document.getElementById("exp").addEventListener("click",()=>{
  const lines=[...sel].map(k=>{const p=k.split("|");return p[0]==="china"?"中国篇 "+p[1]+" -> "+p.slice(2).join("|"):"世界篇 "+p[1]+" -> "+p.slice(2).join("|")});
  document.getElementById("out").value=lines.join("\\n");document.getElementById("out").select();
});
draw("");
</script></body></html>"""
n=len(rows); c=sum(len(r["c"]) for r in rows)
HTML=(HTML.replace("__DATA__",json.dumps(rows,ensure_ascii=False,separators=(",",":"))).replace("__N__",str(n)).replace("__C__",str(c)))
open(os.path.join(R,"web/public/cand.html"),"w",encoding="utf-8").write(HTML)
print("events",n,"candidates",c)
