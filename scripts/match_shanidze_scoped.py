import re, glob, json
from lxml import etree
from collections import defaultdict
TEI="http://www.tei-c.org/ns/1.0"; NS={"tei":TEI,"xml":"http://www.w3.org/XML/1998/namespace"}
NSB="{"+TEI+"}"; XID="{http://www.w3.org/XML/1998/namespace}id"
GEO=re.compile(r'[Ⴀ-ჿⴀ-⴯Ა-Ჿ]+')
def clean(s): return re.sub(r'[҃\s\-]','',s or '')
def norm(s): return clean(s).replace('ჱ','ე').replace('ჲ','ი').replace('ჳ','ვ')
ENDINGS=sorted(['ი','ჲ','ის','ისა','ისი','ს','სა','თა','ითა','ით','მან','მა','ე','ესა','ეს',
                'ად','ო','ოჲ','ნი','ნ','თ','სი','ებ','ება','ებს','ებისა','მდე','გან','ისგან'],
               key=len,reverse=True)
def stem_of(lc):
    for e in ('ი','ჲ'):
        if lc.endswith(e) and len(lc)-len(e)>=3: return lc[:-len(e)]
    return lc
def stem_match(tc, lc):
    if len(lc)<4: return tc==lc
    st=stem_of(lc)
    if tc==lc or tc==st: return True
    if tc.startswith(st) and len(st)>=3:
        rem=tc[len(st):]
        return rem in ENDINGS
    return False

# page -> text
cat=etree.parse("tei/catalog.xml"); page2text={}
for ev in cat.findall(".//tei:event",NS):
    cr=ev.find("tei:bibl[@type='edition']/tei:citedRange",NS)
    if cr is None: continue
    fr=cr.get("from"); to=cr.get("to") or fr
    if fr and to:
        for p in range(int(fr),int(to)+1): page2text.setdefault(p,ev.get(XID))

# entries: forms + target texts
lex=etree.parse("tei/lexicon.xml")
text2entries=defaultdict(list)
for e in lex.findall(".//tei:entry",NS):
    xid=e.get(XID)
    lemma=(e.findtext("tei:form[@type='lemma']/tei:orth",default="",namespaces=NS)).strip()
    if not lemma: continue
    forms=[lemma]+[ (o.text or "").strip() for o in e.findall("tei:form[@type='variant']/tei:orth",NS) if o.text]
    forms+=[ (h.text or "").strip() for h in e.findall(".//tei:cit[@type='example']//tei:hi[@rend='letterspaced']",NS) if h.text]
    forms_c={clean(f) for f in forms if f}
    forms_n={norm(f) for f in forms if f}
    pages=[int(c.text) for c in e.findall(".//tei:bibl[@type='attestation']/tei:citedRange[@unit='page']",NS) if c.text and c.text.isdigit()]
    texts={page2text[p] for p in pages if p in page2text}
    rec=(xid, clean(lemma), forms_c, forms_n)
    for t in texts: text2entries[t].append(rec)

SKIP={NSB+t for t in ("rdg","note","bibl","citedRange","teiHeader","fw","head","title","abbr")}
def taggable(el):
    p=el
    while p is not None:
        if p.tag in SKIP: return False
        if p.tag==NSB+"hi" and p.get("rend")=="initial": return False
        p=p.getparent()
    return True

# carryover (global)
surf2new=json.load(open("/tmp/surf2new.json"))
bytext={}; disc_tokens=0; covered=set()
for f in sorted(glob.glob("tei/texts/*.xml")):
    tid=f.split("/")[-1][:-4]
    tmap=dict(surf2new)   # carryover applies everywhere
    ents=text2entries.get(tid,[])
    if ents:
        t=etree.parse(f)
        for el in t.iter():
            if el.tag==NSB+"rdg": continue
            for textval,ist in ((el.text,1),(el.tail,0)):
                host=el if ist else el.getparent()
                if host is None or not taggable(host): continue
                for m in GEO.finditer(textval or ""):
                    w=m.group(0)
                    if w in tmap: continue
                    tc=clean(w); tn=norm(w); hit=None
                    for (xid,lc,fc,fn) in ents:          # exact
                        if tc in fc: hit=xid; break
                    if not hit:
                        for (xid,lc,fc,fn) in ents:       # normalized
                            if tn in fn: hit=xid; break
                    if not hit:
                        for (xid,lc,fc,fn) in ents:       # scoped stem
                            if stem_match(tc,lc): hit=xid; break
                    if hit:
                        tmap[w]=hit; disc_tokens+=1; covered.add(hit)
    bytext[tid]=tmap
json.dump(bytext,open("/tmp/tagmap_bytext.json","w"),ensure_ascii=False)
# coverage estimate: entries now reachable (carryover + discovered)
carry_ids=set(surf2new.values())
print(f"scoped discoveries (new surface tokens): {disc_tokens}")
print(f"entries newly covered by scoping: {len(covered)}")
print(f"entries covered total (carryover ∪ scoped): ~{len(carry_ids|covered)}")
