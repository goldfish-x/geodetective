# -*- coding: utf-8 -*-
"""抓取 137 条的百度候选图，生成候选池页面 web/public/cand.html 供人工勾选"""
import os,sys,json,re,io,time,urllib.request,urllib.parse,http.cookiejar,html as H
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
os.environ.setdefault("HTTP_PROXY","http://127.0.0.1:7890"); os.environ.setdefault("HTTPS_PROXY","http://127.0.0.1:7890")
R=r"D:\GPTprojects\geodetective"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121 Safari/537.36"
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders=[("User-Agent",UA),("Accept-Language","zh-CN,zh;q=0.9")]
try: op.open("https://image.baidu.com/",timeout=15).read()
except Exception: pass
JUNK=["简谱","试卷","课件","答案","试题","表情包","头像","壁纸","手抄报","简笔画","logo","二维码","截图",
 "拼图","商品","淘宝","京东","价格","门票","招聘","课程","论文","ppt","pdf"]
def core(n):
    return re.sub(r"(之战|之役|之变|之会|之盟|出生|签署|签订|起义|事变|会议|政变|大捷|战役|惨案|屠杀|革命|改革|变法|改制|会盟|会战|战争|陷落|灭亡|独立|条约|和约|运动|开凿|建成|出土|发掘|发现|爆发|遇刺|撤退|登陆|爆炸|获释|成立|航行|入藏|会师|谈判|出塞|从军|作画|平定|起兵|兵变|叛乱|围城|迁都|东渡|西行|国有化|长征|被刺|被焚|改新|来航|遇害|战死|收复|围攻|定都|东征|西征|北伐|南征|之乱|之祸|之围|新政)$","",n)
def bd(q,n=24):
    p={"tn":"resultjson_com","ipn":"rj","word":q,"rn":n,"start":0,"ie":"utf-8","oe":"utf-8","st":1107,"z":0,"hc":1}
    try:
        raw=op.open(urllib.request.Request("https://image.baidu.com/search/acjson?"+urllib.parse.urlencode(p),
            headers={"Referer":"https://image.baidu.com/"}),timeout=20).read().decode("utf-8","ignore").replace("\\'","'")
        j=json.loads(raw,strict=False)
    except Exception: return []
    out=[]
    for it in j.get("data",[]):
        if not isinstance(it,dict): continue
        u=it.get("middleURL") or it.get("thumbURL")
        if u: out.append({"t":re.sub("<[^>]+>","",it.get("pageTitle") or it.get("fromPageTitle") or ""),
                          "u":u,"w":it.get("width") or 0,"h":it.get("height") or 0})
    return out
BR=json.load(open(os.path.join(R,"scripts/history-image-recheck-prompts.json"),encoding="utf-8"))
os.makedirs(os.path.join(R,"web/public/cand"),exist_ok=True)
outfp=os.path.join(R,"web/public/cand/cand.json")
res=json.load(open(outfp,encoding="utf-8")) if os.path.exists(outfp) else {}
print("todo",len([k for k in BR if k not in res]),flush=True)
for k in list(BR):
    if k in res: continue
    m,n=k.split("|",1); c=core(n); person=n[:-2] if n.endswith("出生") else None
    qs=[n+" 油画",n+" 绘画",n+" 复原图"]+([person+" 画像"] if person else [])
    picks=[]
    for q in qs:
        for it in bd(q):
            t=it["t"]
            if any(j in t for j in JUNK): continue
            if not (it["w"] and it["h"] and min(it["w"],it["h"])>=480): continue
            if max(it["w"],it["h"])/min(it["w"],it["h"])>2.2: continue
            if not (c[:2] in t or n[:2] in t or (person and person in t)): continue
            try:
                b=op.open(urllib.request.Request(it["u"],headers={"Referer":"https://image.baidu.com/"}),timeout=20).read()
                im=Image.open(io.BytesIO(b)).convert("RGB")
                if min(im.size)<420: continue
            except Exception: continue
            fn="%s__%s__%d.jpg"%(m,n,len(picks))
            im.save(os.path.join(R,"web/public/cand",fn),"JPEG",quality=88)
            picks.append({"f":fn,"t":t[:80]})
            if len(picks)>=3: break
        if len(picks)>=3: break
    res[k]=picks; json.dump(res,open(outfp,"w",encoding="utf-8"),ensure_ascii=False)
    print(("OK %d "%len(picks))+n,flush=True)
print("done",len(res))
