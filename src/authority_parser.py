"""
src/authority_parser.py
Parses tei/authority.xml (TEI <listPerson>, <listPlace>, and
<list type="ethnonym|fauna|flora">) into Python dataclasses.
Consumed by build.py → build_authority() → templates/authority.html

The page mirrors Imnaishvili's five indexes (საძიებლები):
  I. persons   II. places   III. ethnonyms   IV. animals   V. plants
Persons are sub-grouped by @type; the other sections are flat, Georgian-sorted.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from lxml import etree

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# Person @type → Georgian sub-section label, in display order.
PERSON_TYPE_LABELS: dict[str, str] = {
    "divinity":   "ღვთაება",
    "theotokos":  "ღვთისმშობელი",
    "archangel":  "მთავარანგელოზები",
    "apostle":    "მოციქულები",
    "prophet":    "წინასწარმეტყველები",
    "patriarch":  "მამამთავრები",
    "bishop":     "ეპისკოპოსები",
    "priest":     "მღვდელმსახურები",
    "martyr":     "მოწამენი",
    "monastic":   "მონაზვნები",
    "ruler":      "მეფეები და მმართველები",
    "biblical":   "ბიბლიური პირები",
    "character":  "თხზულებათა პერსონაჟები",
    "":           "სხვა",
}
PERSON_TYPE_ORDER = list(PERSON_TYPE_LABELS.keys())


@dataclass
class NameEntry:
    xml_id:      str
    name:        str                      # main form (Georgian)
    variants:    list[str] = field(default_factory=list)
    type:        str = ""
    desc:        str = ""                 # note[@type="description"]
    attestation: str = ""                 # verbatim Shanidze page/line string
    seealso:     str = ""                 # note[@type="seeAlso"]
    viaf:        str = ""
    name_la:     str = ""
    name_en:     str = ""
    lex_id:      str = ""   # linked lexicon entry (fauna/flora/ethnonym → common noun)


@dataclass
class TypeGroup:
    type:    str
    label:   str
    entries: list[NameEntry] = field(default_factory=list)


@dataclass
class Section:
    key:     str                          # anchor id: persons|places|ethnonyms|animals|plants
    label:   str                          # Georgian heading
    count:   int = 0
    groups:  list[TypeGroup] = field(default_factory=list)   # persons only
    entries: list[NameEntry] = field(default_factory=list)   # flat sections


@dataclass
class AuthorityData:
    sections: list[Section] = field(default_factory=list)
    total:    int = 0


def _text(el, xpath: str) -> str:
    node = el.find(xpath, NS)
    return (node.text or "").strip() if node is not None and node.text else ""


def _sort_key(e: NameEntry) -> str:
    return e.name


def _display_variants(variants: list[str]) -> list[str]:
    """Keep only genuine name-forms for display, dropping inflections.

    Groups forms by stem: a form that starts with a shorter form already kept
    is treated as an inflection (same stem + case ending) and hidden. Distinct
    names / spellings (ქრისტე vs ქრისტჱ, ელისაბედ vs ელისაბეთ) survive because
    neither is a prefix of the other. The full variant set stays in the XML for
    text tagging — this only filters what the page shows.
    """
    roots: list[str] = []
    for v in sorted(dict.fromkeys(v.strip() for v in variants if v and v.strip()),
                    key=len):
        if not any(v.startswith(r) for r in roots):
            roots.append(v)
    return roots


class AuthorityParser:
    def __init__(self, path: Path):
        self.path = path

    # ── entry builders ────────────────────────────────
    def _person(self, el) -> NameEntry:
        mains = [n for n in el.findall("tei:persName", NS)
                 if n.get("type") in (None, "main")]
        main_ka = next((n.text.strip() for n in mains
                        if n.get(XML_LANG) == "ka" and n.text), "")
        if not main_ka and mains and mains[0].text:
            main_ka = mains[0].text.strip()
        variants = [n.text.strip() for n in el.findall("tei:persName", NS)
                    if n.get("type") == "variant" and n.text]
        return NameEntry(
            xml_id=el.get(XML_ID, ""),
            name=main_ka,
            variants=_display_variants(variants),
            type=el.get("type", "") or "",
            desc=_text(el, "tei:note[@type='description']"),
            attestation=_text(el, "tei:bibl[@type='attestation']/tei:citedRange"),
            seealso=_text(el, "tei:note[@type='seeAlso']"),
            viaf=_text(el, "tei:idno[@type='VIAF']"),
            name_la=next((n.text.strip() for n in mains
                          if n.get(XML_LANG) == "la" and n.text), ""),
            name_en=next((n.text.strip() for n in mains
                          if n.get(XML_LANG) == "en" and n.text), ""),
        )

    def _place(self, el) -> NameEntry:
        mains = [n for n in el.findall("tei:placeName", NS)
                 if n.get("type") in (None, "main")]
        main_ka = next((n.text.strip() for n in mains
                        if n.get(XML_LANG) == "ka" and n.text), "")
        if not main_ka and mains and mains[0].text:
            main_ka = mains[0].text.strip()
        variants = [n.text.strip() for n in el.findall("tei:placeName", NS)
                    if n.get("type") == "variant" and n.text]
        return NameEntry(
            xml_id=el.get(XML_ID, ""),
            name=main_ka,
            variants=_display_variants(variants),
            type=el.get("type", "") or "",
            desc=_text(el, "tei:note[@type='description']"),
            attestation=_text(el, "tei:bibl[@type='attestation']/tei:citedRange"),
            seealso=_text(el, "tei:note[@type='seeAlso']"),
            viaf=_text(el, "tei:idno[@type='VIAF']"),
            name_la=next((n.text.strip() for n in mains
                          if n.get(XML_LANG) == "la" and n.text), ""),
            name_en=next((n.text.strip() for n in mains
                          if n.get(XML_LANG) == "en" and n.text), ""),
        )

    def _item(self, el) -> NameEntry:
        terms = el.findall("tei:term", NS)
        main = next((t.text.strip() for t in terms
                     if t.get("type") in (None,) and t.text), "")
        if not main and terms and terms[0].text:
            main = terms[0].text.strip()
        variants = [t.text.strip() for t in terms
                    if t.get("type") == "variant" and t.text]
        return NameEntry(
            xml_id=el.get(XML_ID, ""),
            name=main,
            variants=_display_variants(variants),
            desc=_text(el, "tei:note[@type='description']"),
            attestation=_text(el, "tei:bibl[@type='attestation']/tei:citedRange"),
            seealso=_text(el, "tei:note[@type='seeAlso']"),
            lex_id=el.get("corresp", "").lstrip("#"),
        )

    # ── main ──────────────────────────────────────────
    def parse(self) -> AuthorityData:
        tree = etree.parse(str(self.path))
        root = tree.getroot()
        data = AuthorityData()

        # I. persons — grouped by @type
        persons = [self._person(p) for p in root.findall(".//tei:person", NS)]
        by_type: dict[str, list[NameEntry]] = {}
        for p in persons:
            by_type.setdefault(p.type or "", []).append(p)
        groups = []
        for ty in PERSON_TYPE_ORDER:
            if by_type.get(ty):
                groups.append(TypeGroup(
                    type=ty,
                    label=PERSON_TYPE_LABELS[ty],
                    entries=sorted(by_type[ty], key=_sort_key),
                ))
        # any unexpected types not in the map
        for ty, items in by_type.items():
            if ty not in PERSON_TYPE_LABELS:
                groups.append(TypeGroup(type=ty, label=ty,
                                        entries=sorted(items, key=_sort_key)))
        data.sections.append(Section(
            key="persons", label="პირთა სახელები",
            count=len(persons), groups=groups))

        # II. places — flat
        places = sorted((self._place(p) for p in root.findall(".//tei:place", NS)),
                        key=_sort_key)
        data.sections.append(Section(
            key="places", label="გეოგრაფიული სახელები",
            count=len(places), entries=places))

        # III–V. ethnonyms / animals / plants — flat <list type="…">
        for ltype, key, label in [
            ("ethnonym", "ethnonyms", "ხალხთა და ტომთა სახელები"),
            ("fauna",    "animals",   "ცხოველთა სახელები"),
            ("flora",    "plants",    "მცენარეთა სახელები"),
        ]:
            items = sorted(
                (self._item(it) for it in
                 root.findall(f".//tei:list[@type='{ltype}']/tei:item", NS)),
                key=_sort_key)
            data.sections.append(Section(
                key=key, label=label, count=len(items), entries=items))

        data.total = sum(s.count for s in data.sections)
        return data
