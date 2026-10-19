import re, glob, json
from lxml import etree
from collections import defaultdict
TEI="http://www.tei-c.org/ns/1.0"; NS={"tei":TEI,"xml":"http://www.w3.org/XML/1998/namespace"}
NSB="{"+TEI+"}"; XID="{http://www.w3.org/XML/1998/namespace}id"
GEO=re.compile(r'[Ⴀ-ჿⴀ-⴯Ა-Ჿ]+')
def clean(s): return re.sub(r'[҃\s\-]','',s or '')
def norm(s): return clean(s).replace('ჱ','ე').replace('ჲ','ი').replace('ჳ','ვ')
ENDINGS=sorted(['ი','ჲ','ის','ისა','ისი','ს','სა','თა','ით','ითა','მან','მა','ე','ესა','ად','ო','ნი','ნ','სი','გან','ისგან','მდე'],key=len,reverse=True)
def stem_of(lc):
    for e in ('ი','ჲ'):
        if lc.endswith(e) and len(lc)-len(e)>=3: return lc[:-len(e)]
    return lc
def stem_match(tc,lc):
    if len(lc)<3: return tc==lc
    st=stem_of(lc)
    if tc==lc or tc==st: return True
    if tc.startswith(st) and len(st)>=3 and tc[len(st):] in ENDINGS: return True
    return False

cat=etree.parse("tei/catalog.xml"); page2text={}
for ev in cat.findall(".//tei:event",NS):
    cr=ev.find("tei:bibl[@type='edition']/tei:citedRange",NS)
    if cr is None: continue
    fr=cr.get("from"); to=cr.get("to") or fr
    if fr and to:
        for p in range(int(fr),int(to)+1): page2text.setdefault(p,ev.get(XID))
def pages_of(e):
    s=" ".join((c.text or "") for c in e.findall(".//tei:bibl[@type='attestation']/tei:citedRange",NS))
    out=[]
    for grp in s.split(';'):
        n=re.findall(r'\d+',grp)
        if n: out.append(int(n[0]))
    return out

auth=etree.parse("tei/authority.xml")
text2names=defaultdict(list)   # tid -> [(tag, id, forms_clean, forms_norm, base_clean)]
for tag,nmt in (("person","persName"),("place","placeName")):
    for e in auth.findall(f".//tei:{tag}",NS):
        xid=e.get(XID)
        forms=[(n.text or "").strip() for n in e.findall(f"tei:{nmt}",NS) if n.text]
        if not forms: continue
        fc={clean(f) for f in forms}; fn={norm(f) for f in forms}
        base=min((clean(f) for f in forms), key=len)
        rec=(nmt, xid, fc, fn, base)
        for p in pages_of(e):
            t=page2text.get(p)
            if t: 
                if rec not in text2names[t]: text2names[t].append(rec)

SKIP={NSB+t for t in ("rdg","note","bibl","citedRange","teiHeader","fw","head","title","abbr","w","persName","placeName")}
def taggable(el):
    p=el
    while p is not None:
        if p.tag in SKIP: return False
        if p.tag==NSB+"hi" and p.get("rend")=="initial": return False
        p=p.getparent()
    return True

tot=0; per_id=defaultdict(int)
for f in sorted(glob.glob("tei/texts/*.xml")):
    tid=f.split("/")[-1][:-4]; names=text2names.get(tid,[])
    if not names: continue
    def match(w):
        tc=clean(w); tn=norm(w)
        for (nmt,xid,fc,fn,base) in names:
            if tc in fc: return nmt,xid
        for (nmt,xid,fc,fn,base) in names:
            if tn in fn: return nmt,xid
        for (nmt,xid,fc,fn,base) in names:
            if stem_match(tc,base): return nmt,xid
        return None
    def seg(text):
        if not text: return None
        res=[]
        for m in GEO.finditer(text):
            hit=match(m.group(0))
            if hit: res.append((m.start(),m.end(),hit))
        if not res: return None
        lead=text[:res[0][0]]; segs=[]
        for i,(s,e,(nmt,xid)) in enumerate(res):
            wel=etree.SubElement(etree.Element(NSB+"root"),NSB+nmt); wel.set("ref","#"+xid); wel.text=text[s:e]
            wel.tail=text[e: res[i+1][0] if i+1<len(res) else len(text)]; segs.append(wel)
        return lead,segs
    def handle(node,which,parent=None):
        text=node.text if which=="text" else node.tail
        r=seg(text)
        if not r: return 0
        lead,segs=r
        if which=="text": node.text=lead; cont=node; base=0
        else: node.tail=lead; cont=parent; base=cont.index(node)+1
        for j,wel in enumerate(segs):
            cont.insert(base+j,wel); per_id[wel.get("ref")[1:]]+=1
        return len(segs)
    def process(el):
        if not taggable(el): return 0
        n=0; orig=list(el); n+=handle(el,"text")
        for c in orig:
            n+=process(c); n+=handle(c,"tail",parent=el)
        return n
    t=etree.parse(f); tot+=process(t.getroot()); t.write(f,encoding="UTF-8",xml_declaration=True)
print(f"injected {tot} name tags | distinct entities tagged: {len(per_id)}")
# split new vs existing
print("newly-tagged example ids:", [k for k in per_id if k.startswith('pers-') and k not in ('pers-iesu-kriste','pers-mariami','pers-davit')][:10])
