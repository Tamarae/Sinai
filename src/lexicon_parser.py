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
import html as _html
import re as _re

TEI = "http://www.tei-c.org/ns/1.0"
NS = {"tei": TEI,
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

def _ln(el) -> str:
    return el.tag.split("}", 1)[-1] if isinstance(el.tag, str) else ""

def _inline_html(el) -> str:
    """Serialize mixed content to safe HTML: <hi>→<em>/<strong>,
    <xr>/<ref target> → cross-reference link, text escaped. Children
    like nested <cit> (translations) are skipped — handled separately."""
    out = [_html.escape(el.text or "")]
    for ch in el:
        name = _ln(ch)
        if name == "hi":
            tag = "strong" if ch.get("rend") == "bold" else "em"
            out.append(f"<{tag}>{_inline_html(ch)}</{tag}>")
        elif name == "ref":
            tgt = ch.get("target", "")
            txt = _inline_html(ch)
            out.append(f'<a class="xref" href="{_html.escape(tgt)}">{txt}</a>' if tgt else txt)
        elif name == "xr":
            out.append(_inline_html(ch))            # unwrap (keeps lbl + ref)
        elif name in ("lbl", "seg", "orth", "gloss", "pc"):
            out.append(_inline_html(ch))
        elif name == "cit":
            pass                                    # translations handled elsewhere
        else:
            out.append(_inline_html(ch))
        out.append(_html.escape(ch.tail or ""))
    return _re.sub(r"\s+", " ", "".join(out)).strip()

def _shanidze_ref(bibl_el) -> str:
    """Format <bibl><citedRange unit=page>N</citedRange>,<citedRange unit=line>M</citedRange>…
    as 'N, M; N, M'."""
    if bibl_el is None:
        return ""
    parts, cur = [], []
    for cr in bibl_el.findall("tei:citedRange", NS):
        unit = cr.get("unit"); val = (cr.text or "").strip()
        if unit == "page":
            if cur: parts.append(", ".join(cur)); cur = []
            cur.append(val)
        else:
            cur.append(val)
    if cur: parts.append(", ".join(cur))
    return "; ".join(parts)


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
class ExampleData:
    quote_html:  str = ""   # the Old-Georgian quotation (HTML, hi→em)
    ref:         str = ""   # Shanidze 1959 page/line, e.g. "140, 17"
    translation: str = ""   # modern Georgian rendering

@dataclass
class SenseData:
    def_ka:       str
    note:         str = ""
    def_html:     str = ""   # def with inline cross-reference links
    construction: str = ""   # Imnaishvili gram[@type='construction'] formula
    examples:     List["ExampleData"] = field(default_factory=list)
    refs:         List[str] = field(default_factory=list)   # bare Shanidze attestations

@dataclass
class SeeAlso:
    xml_id: str
    lemma:  str

@dataclass
class SourceRef:
    text_id:       str
    label:         str
    is_dict_source: bool = False  # True = dictionary attribution; False = corpus text link

@dataclass
class SourceInfo:
    """Metadata about a dictionary source — used for filter buttons and entry display."""
    id:          str    # raw source value in XML @source attribute
    group:       str    # filter group id (data-src on filter buttons, data-source on cards)
    label_short: str    # filter button label, e.g. "იმნაიშვილი 1975"
    label_full:  str    # full bibliographic label shown in entries
    pdf_url:     str    # optional PDF link (empty = no link)
    count:       int = 0  # entries from this source (populated at parse time)

@dataclass
class EntryData:
    xml_id:        str
    lemma:         str
    pos:           str    # pos id
    pos_label:     str
    gender:        str
    greek:         str
    greek_alt:     str
    greek_logeion: str
    senses:        List[SenseData] = field(default_factory=list)
    citation:      Optional[CitationData] = None
    see_also:      List[SeeAlso] = field(default_factory=list)
    sources:       List[SourceRef] = field(default_factory=list)
    sources_more:  int = 0
    bog_id:        str = ""
    olia_uri:      str = ""
    source:        str = "corpus"   # raw @source value from XML
    source_label:  str = ""         # human-readable label for src-badge
    source_group:  str = "corpus"   # filter group id for data-source attribute
    pdf_url:       str = ""         # PDF link for the dictionary (may be empty)
    variants:      List[str] = field(default_factory=list)


@dataclass
class LexiconData:
    entries:           List[EntryData]
    entries_by_letter: Dict[str, List[EntryData]]
    alphabet:          List[str]
    pos_list:          List[POS]
    available_sources: List[SourceInfo]   # sources actually present, in display order


def build_popup_lookup(data: LexiconData, geo_slug: dict) -> dict:
    lookup = {}
    for entry in data.entries:
        first = entry.lemma[0] if entry.lemma else ""
        slug = geo_slug.get(first, "a")
        def_text = entry.senses[0].def_ka if entry.senses else ""
        lookup[entry.xml_id] = {
            "lemma": entry.lemma,
            "pos":   entry.pos_label,
            "def":   def_text,
            "slug":  slug,
        }
    return lookup


# ── Georgian alphabet order ────────────────────────────────────────────────────
GEO_ALPHA = list("აბგდევზჱთიკლმნჲოპჟრსტჳუფქღყშჩცძწჭჴხჯჰჵ")

def geo_sort_key(entry: EntryData) -> list:
    return [GEO_ALPHA.index(c) if c in GEO_ALPHA else 999 for c in entry.lemma]


# ── Parser ─────────────────────────────────────────────────────────────────────

class LexiconParser:

    POS_TABLE = [
        POS("noun",    "სახ.", "სახ.", "საზოგადო სახელი"),
        POS("verb",    "ზმნ.", "ზმნ.", "ზმნა"),
        POS("adj",     "ზედ.", "ზედ.", "ზედსართავი"),
        POS("adv",     "ზმნზ.","ზმნზ.","ზმნიზედა"),
        POS("num",     "რცხ.","რცხ.","რიცხვითი"),
        POS("pron",    "ნაც.", "ნაც.", "ნაცვალსახელი"),
        POS("conj",    "კავ.",  "კავ.",  "კავშირი"),
        POS("prep",    "თანდ.","თანდ.","თანდებული"),
        POS("part",    "ნაწ.", "ნაწ.", "ნაწილაკი"),
        POS("vnoun",   "სახ-ზმ.","სახ-ზმ.","სახელზმნა"),
        POS("other",   "სხვ.", "სხვ.", "სხვა"),
    ]

    POS_NORM = {
        "noun": "noun", "verb": "verb",
        "adjective": "adj", "adj": "adj",
        "adverb": "adv", "adv": "adv",
        "numeral": "num", "num": "num",
        "pronoun": "pron",
        "conjunction": "conj",
        "preposition": "prep",
        "postposition": "other",
        "particle": "part",
        "vnoun": "vnoun", "masdar": "vnoun", "სახელზმნა": "vnoun",
        "სახ.": "noun",  "ზმნ.": "verb",  "ზედ.": "adj",
        "ზმნზ.": "adv",  "რცხ.": "num",   "ნაც.": "pron",
        "კავ.": "conj",  "თანდ.": "other", "ნაწ.": "part",
        "სხვ.": "other",
    }

    GENDER_MAP = {"m": "m.", "f": "f.", "n": "n.", "m/n": "m./n.", "f/n": "f./n."}

    # ── Source map ─────────────────────────────────────────────────────────────
    # Keys must match raw @source attribute values used in lexicon.xml.
    # pdf_url: add URL to a scanned PDF when available; leave "" otherwise.
    # group: the data-source value on each card AND the data-src on filter buttons.
    #        Two source IDs can share one group (e.g. "imnaishvili" aliases "imnaishvili-1975").
    SOURCE_MAP: Dict[str, SourceInfo] = {
        "imnaishvili-1975": SourceInfo(
            id="imnaishvili-1975", group="imnaishvili-1975",
            label_short="იმნაიშვილი 1975",
            label_full="ივ. იმნაიშვილი 1975",
            pdf_url="",
        ),
        "imnaishvili": SourceInfo(
            id="imnaishvili", group="imnaishvili-1975",   # same filter group
            label_short="იმნაიშვილი 1975",
            label_full="ივ. იმნაიშვილი",
            pdf_url="",
        ),
        "abuladze1973": SourceInfo(
            id="abuladze1973", group="abuladze1973",
            label_short="აბულაძე 1973",
            label_full="ილ. აბულაძე 1973",
            pdf_url="",
        ),
        "shanidze1971": SourceInfo(
            id="shanidze1971", group="shanidze1971",
            label_short="შანიძე 1971",
            label_full="აკ. შანიძე 1971",
            pdf_url="",
        ),
        "sarjveladze1995": SourceInfo(
            id="sarjveladze1995", group="sarjveladze1995",
            label_short="სარჯველაძე 1995",
            label_full="ზ. სარჯველაძე 1995",
            pdf_url="",
        ),
        "rukhadze-2008": SourceInfo(
            id="rukhadze-2008", group="rukhadze-2008",
            label_short="შეერთებული ლექსიკონი",
            label_full="გ. რუხაძე 2008 — შეერთებული ლექსიკონი",
            pdf_url="",
        ),
        "corpus": SourceInfo(
            id="corpus", group="corpus",
            label_short="კორპუსი",
            label_full="სინური მრავალთავი — კორპუსი",
            pdf_url="",
        ),
        "misc": SourceInfo(
            id="misc", group="misc",
            label_short="სხვა",
            label_full="სხვადასხვა წყარო",
            pdf_url="",
        ),
    }

    _FALLBACK_SOURCE = SourceInfo(
        id="other", group="other",
        label_short="სხვა", label_full="სხვა წყარო", pdf_url="",
    )

    # Set of all known dictionary source IDs (used to tag SourceRef.is_dict_source)
    _DICT_SOURCE_IDS: set = set(SOURCE_MAP.keys()) if SOURCE_MAP else set()

    def __init__(self, path: Path):
        self.path = path

    def _source_info(self, raw: str) -> SourceInfo:
        return self.SOURCE_MAP.get(raw.strip(), self._FALLBACK_SOURCE)

    def parse(self) -> LexiconData:
        tree = ET.parse(self.path)
        root = tree.getroot()

        entries:       List[EntryData] = []
        source_counts: Dict[str, int]  = defaultdict(int)

        for entry_el in root.findall(".//tei:entry", NS):
            e = self._parse_entry(entry_el)
            if e:
                entries.append(e)
                source_counts[e.source_group] += 1

        entries.sort(key=geo_sort_key)

        by_letter: Dict[str, List[EntryData]] = defaultdict(list)
        for e in entries:
            first = e.lemma[0] if e.lemma else "?"
            by_letter[first].append(e)

        alphabet = [l for l in GEO_ALPHA if l in by_letter]

        # Build available_sources in fixed display order, skipping empty ones
        ORDER = [
            "imnaishvili-1975", "abuladze1973", "shanidze1971",
            "sarjveladze1995", "corpus",
        ]
        seen_groups: set = set()
        available_sources: List[SourceInfo] = []
        for src_id in ORDER:
            info  = self.SOURCE_MAP.get(src_id, self._FALLBACK_SOURCE)
            group = info.group
            if group in seen_groups:
                continue
            if source_counts.get(group, 0) == 0:
                continue
            seen_groups.add(group)
            available_sources.append(SourceInfo(
                id=info.id, group=group,
                label_short=info.label_short, label_full=info.label_full,
                pdf_url=info.pdf_url,
                count=source_counts[group],
            ))

        return LexiconData(
            entries=entries,
            entries_by_letter=dict(by_letter),
            alphabet=alphabet,
            pos_list=self.POS_TABLE,
            available_sources=available_sources,
        )

    def _parse_entry(self, el: ET.Element) -> Optional[EntryData]:
        xml_id  = _xml_id(el)
        corresp = _attr(el, "corresp", "")
        bog_id  = corresp.replace("bog:", "") if corresp.startswith("bog:") else ""
        source  = _attr(el, "source", "corpus")

        src_info     = self._source_info(source)
        source_label = src_info.label_full
        source_group = src_info.group
        pdf_url      = src_info.pdf_url

        # Lemma
        form_el = el.find("tei:form[@type='lemma']/tei:orth", NS)
        lemma   = (form_el.text or "").strip() if form_el is not None else ""
        if not lemma:
            return None

        # Variant forms (shown after the headword)
        variants = [(o.text or "").strip()
                    for o in el.findall("tei:form[@type='variant']/tei:orth", NS)
                    if o.text and o.text.strip()]

        # POS — only label it when a real POS value is present (Imnaishvili has none)
        gram_el = el.find("tei:gramGrp[tei:pos]", NS)
        pos_raw = _t(gram_el, "tei:pos") if gram_el is not None else ""
        gender  = _t(gram_el, "tei:gen") if gram_el is not None else ""
        pos_id  = self.POS_NORM.get(pos_raw.lower(), "other") if pos_raw else "other"
        pos_rec = next((p for p in self.POS_TABLE if p.id == pos_id), self.POS_TABLE[-1])
        pos_label = pos_rec.abbr if pos_raw else ""

        # Greek equivalents — ONLY actual grc translations (not Imnaishvili's ka renderings)
        greek = greek_alt = greek_logeion = ""
        for i, cit_el in enumerate(
                el.findall(".//tei:cit[@type='translation'][@xml:lang='grc']", NS)):
            q = _t(cit_el, "tei:quote")
            if i == 0:
                greek = greek_logeion = q
            elif not greek_alt:
                greek_alt = q

        # OLiA
        olia_el  = el.find(".//tei:xr[@type='lod']/tei:ref", NS)
        olia_uri = _attr(olia_el, "target") if olia_el is not None else ""

        # Senses (recursive — Imnaishvili nests senses) with examples
        senses: List[SenseData] = self._collect_senses(el)

        citation = None          # superseded by per-sense examples
        see_also: List[SeeAlso] = []   # cross-refs are inlined in def_html

        # Source references — distinguish corpus text links from dictionary attributions
        # Corpus text refs use a # prefix: target="#mrav-kharbeba-1"
        # Dictionary refs have no #:      target="abuladze1973"
        sources: List[SourceRef] = []
        MAX_DISPLAYED = 4
        for xr_el in el.findall("tei:xr[@type='source']", NS):
            for ref_el in xr_el.findall("tei:ref", NS):
                raw_target     = _attr(ref_el, "target", "")
                is_dict_source = not raw_target.startswith("#")
                target         = raw_target.lstrip("#")
                label          = (ref_el.text or target).strip()
                sources.append(SourceRef(
                    text_id=target,
                    label=label,
                    is_dict_source=is_dict_source,
                ))

        sources_more = max(0, len(sources) - MAX_DISPLAYED)
        sources      = sources[:MAX_DISPLAYED]

        return EntryData(
            xml_id=xml_id, lemma=lemma, pos=pos_id, pos_label=pos_label,
            gender=self.GENDER_MAP.get(gender, gender),
            greek=greek, greek_alt=greek_alt, greek_logeion=greek_logeion,
            senses=senses, citation=citation, see_also=see_also,
            sources=sources, sources_more=sources_more,
            bog_id=bog_id, olia_uri=olia_uri,
            source=source,
            source_label=source_label,
            source_group=source_group,
            pdf_url=pdf_url,
            variants=variants,
        )

    def _collect_senses(self, el) -> List["SenseData"]:
        """Recursively gather senses. Each yields def (with inline xref links),
        construction formula, illustrative examples (quote + Shanidze ref +
        translation) and bare attestation refs."""
        out: List[SenseData] = []
        for sense_el in el.findall("tei:sense", NS):
            def_el = sense_el.find("tei:def", NS)
            def_html = _inline_html(def_el) if def_el is not None else ""
            def_ka   = "".join(def_el.itertext()).strip() if def_el is not None else ""
            note     = _t(sense_el, "tei:note")
            constr   = _t(sense_el, "tei:gramGrp/tei:gram")
            examples: List[ExampleData] = []
            refs: List[str] = []
            for cit_el in sense_el.findall("tei:cit[@type='example']", NS):
                q_el   = cit_el.find("tei:quote", NS)
                bibl   = cit_el.find("tei:bibl", NS)
                ref    = _shanidze_ref(bibl)
                tr_el  = cit_el.find("tei:cit[@type='translation']/tei:quote", NS)
                if q_el is not None:
                    examples.append(ExampleData(
                        quote_html=_inline_html(q_el),
                        ref=ref,
                        translation=_inline_html(tr_el) if tr_el is not None else "",
                    ))
                elif ref:
                    refs.append(ref)
            if def_html or examples or refs or constr:
                sd = SenseData(def_ka=def_ka, note=note, def_html=def_html,
                               construction=constr, examples=examples)
                sd.refs = refs
                out.append(sd)
            # nested senses
            out.extend(self._collect_senses(sense_el))
        return out
