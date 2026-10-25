# -*- coding: utf-8 -*-
"""校验待出图提示词：不得串到其他事件、长度合规、必须能对上本事件（防序号错位）"""
import json,sys,os,re
sys.stdout.reconfigure(encoding="utf-8")
import pathlib
R=str(pathlib.Path(__file__).resolve().parents[1])
P=json.load(open(os.path.join(R,"scripts/history-image-prompts.json"),encoding="utf-8"))
TODO=json.load(open(os.path.join(R,"scripts/history-image-todo.json"),encoding="utf-8"))
rows={}
for m in ("china","world"):
    d=json.load(open(os.path.join(R,"web/src/data/%s.json"%m),encoding="utf-8"))
    de=json.load(open(os.path.join(R,"web/src/data/%s-desc.json"%m),encoding="utf-8"))
    for x in d["history"]: rows[m+"|"+x["name"]]=de[x["name"]]["desc"]
ALL=[x["mode"]+"|"+x["name"] for s in ("A","B") for x in TODO[s]]
def core(n):
    return re.sub(r"(之战|之役|之变|之会|之盟|出生|签署|起义|事变|会议|政变|大捷|战役|惨案|屠杀|革命|改革|变法|改制|"
     r"会盟|会战|战争|陷落|灭亡|独立|条约|和约|运动|开凿|建成|出土|发现|爆发|遇刺|撤退|登陆|爆炸|获释|成立|航行|"
     r"入藏|会师|谈判|谈判|出塞|从军|作画|平定|起兵|兵变|叛乱|围城|迁都|东渡|西行|开工|国有化|长征|被刺|被焚|改新|来航|遇害|战死)$","",n)
fail=[]
for k in ALL:
    pr=P.get(k)
    if not pr: fail.append((k,"缺提示词")); continue
    if not (35<=len(pr)<=120): fail.append((k,"长度 %d"%len(pr)))
    n=k.split("|",1)[1]; c=core(n)
    for k2 in ALL:
        if k2==k: continue
        n2=k2.split("|",1)[1]; c2=core(n2)
        if len(c2)>=3 and c2 in pr and c2!=c: fail.append((k,"串台→%s"%n2))
    # 本事件可辨识性：提示词应含事件名核心、地名核心或梗概里的人名/关键词
    sig={n[:2],c}
    place=next((x["place"] for s in ("A","B") for x in TODO[s] if x["mode"]+"|"+x["name"]==k),"")
    if place: sig.add(place[:2]); sig.add(re.sub(r"(省|市|区|县|自治区|旗|州)$","",place)[:3])
    desc=rows.get(k,"")
    sig|={w for w in re.findall(r"[\u4e00-\u9fa5]{2,4}",desc[:120])}
    if not any(t and t in pr for t in sig): fail.append((k,"无法对应本事件"))

BAN={"塑像","铜像","石像","雕像","雕塑","幼年","少年","神童"}
ANC={"china"}
for k,v in P.items():
    m=k.split("|",1)[0]
    if m in ANC:
        hit=[w for w in BAN if w in v]
        if hit: fail.append((k,"古代事件提示词含"+ "/".join(hit)))

print("检查 %d 条，问题 %d 条"%(len(ALL),len(set(f[0] for f in fail))))
for k,w in sorted(set(fail))[:30]: print("  ✗",k.split("|",1)[1],w)
sys.exit(1 if fail else 0)
