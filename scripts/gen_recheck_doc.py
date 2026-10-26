# -*- coding: utf-8 -*-
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
    rows.append((0 if m=="china" else 1,v["tier"],n,a,v["problem"],desc,v["prompt"]))
rows.sort()
tot=len(rows); ch=sum(1 for r in rows if r[0]==0)
def cnt(mo,t): return sum(1 for r in rows if r[0]==mo and r[1]==t)
GAL="https://goldfish-x.github.io/geodetective/gallery.html"
lines=[]
lines.append("# 历史配图自查表（2026-10-26）")
lines.append("")
lines.append("我把 400 张历史配图逐张看过一遍（20 张联络表 × 20），下面 **{} 条明显与史实/地点不对**（中国篇 {}、世界篇 {}）。".format(tot,ch,tot-ch))
lines.append("每行给了：现在这张错在哪、该事件的文字简介（你顺带核一下）、以及按「近代=档案老照片 / 古代=历史画·版画·壁画 / 人物=传世画像（不用塑像、不画幼年）」口径写的重生成提示词。")
lines.append("")
lines.append("处理方式：在表上划掉不需要换的；剩下的按提示词重生成，或你用自己的模型生成后丢回 `web/public/images/<篇章>/<事件名>.webp`，我来裁切查重入库。")
lines.append("也能在画布 {} 里看（这 {} 张已预先标红），标完点「导出待换名单」。".format(GAL,tot))
lines.append("")
lines.append("统计：中国篇 1★{} 2★{} 3★{} 4★{} 5★{}；世界篇 1★{} 2★{} 3★{} 4★{} 5★{}".format(
    cnt(0,1),cnt(0,2),cnt(0,3),cnt(0,4),cnt(0,5),cnt(1,1),cnt(1,2),cnt(1,3),cnt(1,4),cnt(1,5)))
lines.append("")
lines.append("| # | 篇章 | 星级 | 事件 | 发生地（今） | 现在这张的问题 | 文字简介 | 建议重生成提示词 |")
lines.append("|---|---|---|---|---|---|---|---|")
for i,(mo,t,n,a,prob,desc,pr) in enumerate(rows,1):
    lines.append("| {} | {} | {}★ | {} | {} | {} | {} | {} |".format(
        i,"中国篇" if mo==0 else "世界篇",t,n,a,prob,desc,pr))
lines.append("")
open(os.path.join(R,"docs/配图复核表.md"),"w",encoding="utf-8").write("\n".join(lines))
print("rows",tot,"china",ch)
