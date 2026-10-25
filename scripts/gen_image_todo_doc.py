# -*- coding: utf-8 -*-
"""由 tracked 资产生成 docs/历史事件待出图清单.md（不要手改文档，改这三份 JSON）"""
import os,json,re,sys,glob
sys.stdout.reconfigure(encoding="utf-8")
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(p): return json.load(open(os.path.join(R,p),encoding="utf-8"))
TODO=rd("scripts/history-image-todo.json"); P=rd("scripts/history-image-prompts.json")
Q=rd("scripts/history-image-queries.json")
INFO={}; FILED={}
for m in ("china","world"):
    d=rd("web/src/data/%s.json"%m); co=rd("web/src/data/%s-coords.json"%m)
    for x in d["history"]:
        INFO[m+"|"+x["name"]]=(x["difficulty"],co[x["name"]][2])
        FILED[m+"|"+x["name"]]=os.path.exists(os.path.join(R,"web/public/images/%s/%s.webp"%(m,x["name"])))
EVENT=set()
for m in ("china","world"):
    for fn in ("commons","web","user"):
        p="scripts/%s-image-%s-provenance.json"%(m,fn)
        if not os.path.exists(os.path.join(R,p)): continue
        for k,v in rd(p).items():
            if isinstance(v,dict) and v.get("subject")=="event": EVENT.add(m+"|"+k)
NEED=set(x["mode"]+"|"+x["name"] for s in ("A","B") for x in TODO[s])
A=[x for x in TODO["A"]]; B=[x for x in TODO["B"]]; E=[x for x in TODO.get("regen",[])]
C=[k for k in INFO if FILED[k] and k not in EVENT and k not in NEED]
D=[k for k in EVENT if FILED[k]]
def lab(m): return "中国篇" if m=="china" else "世界篇"
def cnt(rows): return sum(1 for r in rows if (r["mode"] if isinstance(r,dict) else r.split("|")[0])=="china")
A.sort(key=lambda x:(x["mode"],x["tier"],x["name"])); B.sort(key=lambda x:(x["mode"],x["tier"],x["name"]))
L=["# 历史事件线待出图清单","",
"> **配图口径**：历史事件优先用「事件本身的图」——1840 年后用当年黑白/泛黄档案老照片或历史海报；",
"> 更早的用中西方教科书与百科常见的历史油画、国画、版画、壁画，人物用历代传世肖像画或水墨工笔设色画像",
"> （中国古代没有塑像习俗，不用铜像石像；人物出生类事件直接用成年画像，不画幼年神童场景）。",
"> 只有遗址保存完整的（元上都、汉长安城夯土、石窟、长城关隘、古城墙一类）才用遗址实景，纪念馆/纪念碑次选。",
"> 地图、政区图、战役形势图、文字展板、卡通动画、电视剧剧照、复制园景、车站厂房一律不收。","",
"> **本文档由脚本生成**：`python scripts/gen_image_todo_doc.py`，数据源是",
"> `scripts/history-image-todo.json`、`scripts/history-image-prompts.json` 与各 provenance 文件；",
"> 提示词一致性（防序号串台、防塑像/幼年）由 `scripts/check_image_prompts.py` 把关，已接入 CI。","",
"## 统计","","| 档 | 含义 | 中国篇 | 世界篇 | 合计 |","|---|---|---|---|---|"]
for tag,rows,mean in (("A",A,"完全无图（当前走确定性占位图）"),("B",B,"有图但只是城市风貌/无法指认地点，需换成事件图"),
                      ("C",C,"已有可指认地点的遗址·纪念馆·地标实景（达标）"),("D",D,"已是事件画 / 老照片 / 肖像 / 传世画像（达标）"),
                      ("E",E,"已有图但提示词已修订，建议按新提示词重生成")):
    n=len(rows); c=cnt(rows); L.append("| %s | %s | %d | %d | %d |"%(tag,mean,c,n-c,n))
L+=["**待生成 {} 张**（A {} + B {}）。原图建议 600×600 以上正方形，文件名用事件名原文，放进 `web/public/images/<篇章>/` 后由我裁成 300×300 WebP、查重并登记来源。".format(len(A)+len(B),len(A),len(B)),""]
for tag,rows,title in (("A",A,"A 档：完全无图"),("B",B,"B 档：需把城市风貌照换成事件图"),("E",E,"E 档：已配图，但提示词已修订、建议重生成")):
    L+=["## %s（%d 条）"%(title,len(rows)),"","| 篇章 | 难度 | 事件 | 发生地（今） | 建议出图提示词 |","|---|---|---|---|---|"]
    for x in rows:
        k=x["mode"]+"|"+x["name"]
        L.append("| %s | %d | %s | %s | %s |"%(lab(x["mode"]),x["tier"],x["name"],x["place"] or INFO[k][1],P.get(k,"（待生成）")))
    L+=["","文件名对照：","","```text"]+["web/public/images/%s/%s.webp"%(x["mode"],x["name"]) for x in rows]+["```",""]
L+=["## 附：已入库的事件图（%d 张，可抽查图文是否对应）"%len(D),"",
 "| 篇章 | 难度 | 事件 | 来源标题 | 许可 |","|---|---|---|---|---|"]
PRV={}
for m in ("china","world"):
    for fn in ("commons","web","user"):
        p="scripts/%s-image-%s-provenance.json"%(m,fn)
        if not os.path.exists(os.path.join(R,p)): continue
        for k,v in rd(p).items():
            if isinstance(v,dict) and v.get("subject")=="event": PRV[m+"|"+k]=v
for k in sorted(D,key=lambda k:(k.split("|")[0],INFO[k][0],k)):
    v=PRV.get(k,{})
    L.append("| %s | %d | %s | %s | %s |"%("中国篇" if k.startswith("china") else "世界篇",INFO[k][0],
        k.split("|",1)[1],(v.get("title") or "")[:56],(v.get("license") or "")[:22]))
L.append("")
open(os.path.join(R,"docs/历史事件待出图清单.md"),"w",encoding="utf-8").write("\n".join(L))
print("A",len(A),"B",len(B),"C",len(C),"D",len(D))
