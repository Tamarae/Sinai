import re, glob, json
from lxml import etree
TEI="http://www.tei-c.org/ns/1.0"; NS="{"+TEI+"}"
bytext=json.load(open("/tmp/tagmap_bytext.json"))
def clean(s): return re.sub(r'[҃]','',s or '')
GEO=re.compile(r'[Ⴀ-ჿⴀ-⴯Ა-Ჿ]+')
SKIP={NS+t for t in ("rdg","note","bibl","citedRange","teiHeader","fw","head","title","abbr","persName","placeName")}
def taggable(el):
    p=el
    while p is not None:
        if p.tag in SKIP: return False
        if p.tag==NS+"hi" and p.get("rend")=="initial": return False
        p=p.getparent()
    return True
tot=0
for f in sorted(glob.glob("tei/texts/*.xml")):
    tid=f.split("/")[-1][:-4]; tagmap=bytext.get(tid,{})
    if not tagmap: continue
    def seg(text):
        if not text: return None
        parts=[(m.group(0),m.start(),m.end()) for m in GEO.finditer(text)]
        ms=[(w,s,e,(tagmap.get(w) or tagmap.get(clean(w)))) for (w,s,e) in parts if (tagmap.get(w) or tagmap.get(clean(w)))]
        if not ms: return None
        lead=text[:ms[0][1]]; segs=[]
        for i,(w,s,e,wid) in enumerate(ms):
            wel=etree.SubElement(etree.Element(NS+"root"),NS+"w"); wel.set("lemma","#"+wid); wel.text=text[s:e]
            wel.tail=text[e: ms[i+1][1] if i+1<len(ms) else len(text)]; segs.append(wel)
        return lead,segs
    def handle(node,which,parent=None):
        text=node.text if which=="text" else node.tail
        r=seg(text)
        if not r: return 0
        lead,segs=r
        if which=="text": node.text=lead; cont=node; base=0
        else: node.tail=lead; cont=parent; base=cont.index(node)+1
        for j,wel in enumerate(segs): cont.insert(base+j,wel)
        return len(segs)
    def process(el):
        if not taggable(el): return 0
        n=0; orig=list(el); n+=handle(el,"text")
        for c in orig:
            n+=process(c); n+=handle(c,"tail",parent=el)
        return n
    t=etree.parse(f); tot+=process(t.getroot())
    t.write(f,encoding="UTF-8",xml_declaration=True)
print("injected",tot,"<w> tags")
