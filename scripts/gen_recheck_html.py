# -*- coding: utf-8 -*-
"""由 recheck-prompts.json 生成 web/public/recheck.html（可读表格页，挂 Pages）"""
import os,json,sys
sys.stdout.reconfigure(encoding="utf-8")
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(p):
    fp=os.path.join(R,p); return json.load(open(fp,encoding="utf-8")) if os.path.exists(fp) else {}
BR=rd("scripts/history-image-recheck-prompts.json")
INFO={}
for m in ("china","world"):
    d=rd("web/src/data/%s.json"%m); co=rd("web/src/data/%s-coords.json"%m); de=rd("web/src/data/%s-desc.json"%m)
    for x in d["history"]: INFO[m+"|"+x["name"]]=(co[x["name"]][2],de[x["name"]]["desc"])
rows=[]
for k,v in BR.items():
    m,n=k.split("|",1); a,desc=INFO[k]
    rows.append({"m":"中国篇" if m=="china" else "世界篇","t":v["tier"],"n":n,"a":a,"p":v["problem"],"d":desc,"q":v["prompt"]})
rows.sort(key=lambda r:(r["m"]!="中国篇",r["t"],r["n"]))
HTML="""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>历史配图自查表 · 地理大侦探</title>
<style>
:root{--bg:#0f1419;--line:#243040;--fg:#e6edf3;--dim:#93a4b8;--acc:#ffb454}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;background:rgba(15,20,25,.97);border-bottom:1px solid var(--line);padding:10px 16px;z-index:5}
h1{font-size:16px;margin:0 0 6px}.dim{color:var(--dim);font-size:12px}
input{background:#0b1015;border:1px solid var(--line);color:var(--fg);border-radius:6px;padding:6px 10px;min-width:260px;margin-top:6px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:8px 10px;vertical-align:top;text-align:left}
th{position:sticky;top:74px;background:#131a22;font-weight:600;z-index:4}
td.n{font-weight:600;white-space:nowrap}
td.p{color:#ffb4b4;min-width:150px}td.d{color:#c8d4e2;max-width:330px}td.q{color:#b8e6c8;min-width:300px}
tr:hover td{background:#141c25}
a{color:var(--acc)}
</style></head><body>
<header><h1>历史配图自查表 · __N__ 条待换（中国篇 __C__ / 世界篇 __W__）</h1>
<div class="dim">逐张看完 400 张后的结果。这里给了：现图问题、文字简介（顺带核一下）、按新口径写的重生成提示词。也可以在 <a href="./gallery.html">配图画布</a> 里看这 __N__ 张（已标红）。</div>
<input id="q" placeholder="搜事件名 / 省份国家 / 提示词关键词"></header>
<table><thead><tr><th>篇章</th><th>星</th><th>事件</th><th>发生地（今）</th><th>现在这张的问题</th><th>文字简介</th><th>建议重生成提示词</th></tr></thead>
<tbody id="tb"></tbody></table>
<script>
const D=__DATA__;
const tb=document.getElementById("tb");
function render(f){
  const q=(f||"").trim().toLowerCase();
  tb.innerHTML=D.filter(d=>!q||d.n.toLowerCase().includes(q)||(d.a||"").toLowerCase().includes(q)||d.q.toLowerCase().includes(q)||d.d.toLowerCase().includes(q))
   .map(d=>`<tr><td>${d.m}</td><td>${d.t}★</td><td class="n">${d.n}</td><td>${d.a||"—"}</td>
   <td class="p">${d.p}</td><td class="d">${d.d}</td><td class="q">${d.q}</td></tr>`).join("");
}
document.getElementById("q").addEventListener("input",e=>render(e.target.value));
render("");
</script></body></html>"""
n=len(rows); c=sum(1 for r in rows if r["m"]=="中国篇")
HTML=(HTML.replace("__DATA__",json.dumps(rows,ensure_ascii=False,separators=(",",":")))
          .replace("__N__",str(n)).replace("__C__",str(c)).replace("__W__",str(n-c)))
open(os.path.join(R,"web/public/recheck.html"),"w",encoding="utf-8").write(HTML)
print("written",n,c)
