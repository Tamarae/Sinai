"""
src/lexicon_parser.py
Parses tei/lexicon.xml into LexiconData consumed by build.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib     import Path
from typing      import List, Dict, Optional
import xml.etree.ElementTree as ET
from collections import defaultdict

NS = {"tei": "http://www.tei-c.org/ns/1.0",
      "xml": "http://www.w3.org/XML/1998/namespace",
      }

def _t(el, xpath: str) -> str:
    node = el.find(xpath, NS)
    return (node.text or "").strip() if node is not None else ""

def _attr(el, attrib: str, default: str = "") -> str:
    return el.get(attrib, default)

def _xml_id(el) -> str:
    return el.get("{http://www.w3.org/XML/1998/namespace}id", "")

def _xml_lang(el) -> str:
    return el.get("{http://www.w3.org/XML/1998/namespace}lang", "")


@dataclass
class POS:
    id:         str    # "noun", "verb", …
    abbr:       str    # "სახ.", "ზმნ.", …
    label:      str    # same as abbr for filter button
    label_full: str    # "საზოგადო სახელი"

@dataclass
class CitationData:
    text:   str
    author: str
    title:  str
    locus:  str

@dataclass
class SenseData:
    def_ka: str
    note:   str = ""

@dataclass
class SeeAlso:
    xml_id: str
    lemma:  str

@dataclass
class SourceRef:
    text_id: str
    label:   str

@dataclass
class EntryData:
    xml_id:        str
    lemma:         str
    pos:           str    # pos id
    pos_label:     str
    gender:        str
    greek:         str
    greek_alt:     str
    greek_logeion: str    # form used for Logeion URL
    senses:        List[SenseData] = field(default_factory=list)
    citation:      Optional[CitationData] = None
    see_also:      List[SeeAlso] = field(default_factory=list)
    sources:       List[SourceRef] = field(default_factory=list)
    sources_more:  int = 0
    bog_id:        str = ""
    olia_uri:      str = ""


@dataclass
class LexiconData:
    entries:          List[EntryData]
    entries_by_letter: Dict[str, List[EntryData]]
    alphabet:         List[str]
    pos_list:         List[POS]


# ── Georgian alphabet order ────────────────────────────
GEO_ALPHA = list("აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ")

def geo_sort_key(entry: EntryData) -> list:
    return [GEO_ALPHA.index(c) if c in GEO_ALPHA else 999 for c in entry.lemma]


# ── Parser ─────────────────────────────────────────────

class LexiconParser:

    POS_TABLE = [
        POS("noun",    "სახ.", "სახ.", "საზოგადო სახელი"),
        POS("verb",    "ზმნ.", "ზმნ.", "ზმნა"),
        POS("adj",     "ზედ.", "ზედ.", "ზედსართავი"),
        POS("adv",     "ზმნზ.","ზმნზ.","ზმნიზედა"),
        POS("pron",    "ნაც.", "ნაც.", "ნაცვალსახელი"),
        POS("conj",    "კვ.",  "კვ.",  "კავშირი"),
        POS("prep",    "თ-ს.","თ-ს.","თანდებული"),
        POS("part",    "ნაწ.", "ნაწ.", "ნაწილაკი"),
        POS("other",   "სხვ.", "სხვ.", "სხვა"),
    ]

    POS_NORM = {
        "noun": "noun", "verb": "verb",
        "adjective": "adj", "adj": "adj",
        "adverb": "adv", "adv": "adv",
        "pronoun": "pron",
        "conjunction": "conj",
        "preposition": "prep",
        "particle": "part",
    }

    GENDER_MAP = {"m": "m.", "f": "f.", "n": "n.", "m/n": "m./n.", "f/n": "f./n."}

    def __init__(self, path: Path):
        self.path = path

    def parse(self) -> LexiconData:
        tree = ET.parse(self.path)
        root = tree.getroot()

        entries: List[EntryData] = []

        for entry_el in root.findall(".//tei:entry", NS):
            e = self._parse_entry(entry_el)
            if e:
                entries.append(e)

        # Sort Georgian alphabetically
        entries.sort(key=geo_sort_key)

        # Group by first letter
        by_letter: Dict[str, List[EntryData]] = defaultdict(list)
        for e in entries:
            first = e.lemma[0] if e.lemma else "?"
            by_letter[first].append(e)

        alphabet = [l for l in GEO_ALPHA if l in by_letter]

        return LexiconData(
            entries=entries,
            entries_by_letter=dict(by_letter),
            alphabet=alphabet,
            pos_list=self.POS_TABLE,
        )

    def _parse_entry(self, el: ET.Element) -> Optional[EntryData]:
        xml_id  = _xml_id(el)
        corresp = _attr(el, "corresp", "")        # e.g. "bog:angelozi"
        bog_id  = corresp.replace("bog:", "") if corresp.startswith("bog:") else ""

        # Lemma
        form_el = el.find("tei:form[@type='lemma']/tei:orth", NS)
        lemma   = (form_el.text or "").strip() if form_el is not None else ""
        if not lemma:
            return None

        # POS + gender
        gram_el = el.find("tei:gramGrp", NS)
        pos_raw = _t(gram_el, "tei:pos") if gram_el is not None else ""
        gender  = _t(gram_el, "tei:gen") if gram_el is not None else ""
        pos_id  = self.POS_NORM.get(pos_raw.lower(), "other")
        pos_rec = next((p for p in self.POS_TABLE if p.id == pos_id), self.POS_TABLE[-1])

        # Greek equivalents
        greek = greek_alt = greek_logeion = ""
        cit_els = el.findall(".//tei:cit[@type='translation']", NS)
        for i, cit_el in enumerate(cit_els):
            q = _t(cit_el, "tei:quote")
            if i == 0:
                greek          = q
                greek_logeion  = q
            else:
                greek_alt = q

        # OLiA
        olia_el = el.find(".//tei:xr[@type='lod']/tei:ref", NS)
        olia_uri = _attr(olia_el, "target") if olia_el is not None else ""

        # Senses
        senses: List[SenseData] = []
        for sense_el in el.findall("tei:sense", NS):
            def_ka = _t(sense_el, "tei:def[@xml:lang='ka']") or _t(sense_el, "tei:def")
            note   = _t(sense_el, "tei:note")
            if def_ka:
                senses.append(SenseData(def_ka=def_ka, note=note))

        # Citation (first <cit type="example"> or <q>)
        citation = None
        ex_el = el.find(".//tei:cit[@type='example']", NS)
        if ex_el is not None:
            q_text  = _t(ex_el, "tei:quote")
            bibl_el = ex_el.find("tei:bibl", NS)
            cit_author= _t(bibl_el, "tei:author") if bibl_el is not None else ""
            cit_title = _t(bibl_el, "tei:title")  if bibl_el is not None else ""
            cit_locus = _t(bibl_el, "tei:ref")    if bibl_el is not None else ""
            if q_text:
                citation = CitationData(text=q_text, author=cit_author,
                                        title=cit_title, locus=cit_locus)

        # See also
        see_also: List[SeeAlso] = []
        for xr_el in el.findall("tei:xr[@type='cf']", NS):
            ref_el = xr_el.find("tei:ref", NS)
            if ref_el is not None:
                target = _attr(ref_el, "target", "").lstrip("#")
                label  = (ref_el.text or target).strip()
                see_also.append(SeeAlso(xml_id=target, lemma=label))

        # Source text references  <xr type="source">
        sources: List[SourceRef] = []
        MAX_DISPLAYED = 4
        for xr_el in el.findall("tei:xr[@type='source']", NS):
            for ref_el in xr_el.findall("tei:ref", NS):
                target = _attr(ref_el, "target", "").lstrip("#")
                label  = (ref_el.text or target).strip()
                sources.append(SourceRef(text_id=target, label=label))

        sources_more = max(0, len(sources) - MAX_DISPLAYED)
        sources      = sources[:MAX_DISPLAYED]

        return EntryData(
            xml_id=xml_id, lemma=lemma, pos=pos_id, pos_label=pos_rec.abbr,
            gender=self.GENDER_MAP.get(gender, gender),
            greek=greek, greek_alt=greek_alt, greek_logeion=greek_logeion,
            senses=senses, citation=citation, see_also=see_also,
            sources=sources, sources_more=sources_more,
            bog_id=bog_id, olia_uri=olia_uri,
        )
