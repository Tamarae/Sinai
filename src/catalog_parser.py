"""
src/catalog_parser.py
Parses tei/catalog.xml into Python dataclasses consumed by build.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib     import Path
from typing      import List, Optional, Dict
import xml.etree.ElementTree as ET

# Namespaces — xml: must be declared explicitly for ElementTree XPath predicates
NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

# Expanded attribute names for direct .get() calls (ElementTree requires full URI)
_XML_ID   = "{http://www.w3.org/XML/1998/namespace}id"
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _t(el, xpath: str) -> str:
    """Return stripped text of first matching element, or ''."""
    node = el.find(xpath, NS)
    return (node.text or "").strip() if node is not None else ""


def _attr(el, attrib: str, default: str = "") -> str:
    return el.get(attrib, default)


def _xml_id(el) -> str:
    return el.get(_XML_ID, "")


def _xml_lang(el) -> str:
    return el.get(_XML_LANG, "")


def _clean_idno(raw: str) -> str:
    """
    Strip placeholder values so absent identifiers become empty string.
    Treats as absent: empty, whitespace-only, or XML comment text
    (ElementTree strips comments so this mainly guards against empty elements
    and any residual whitespace).
    """
    s = raw.strip()
    # XML comments are invisible to ElementTree, so s will simply be '' for
    # elements whose only content is a comment — no extra handling needed.
    return s


# ── Data classes ──────────────────────────────────────

@dataclass
class WitnessMeta:
    xml_id:  str
    siglum:  str
    idno:    str
    date:    str
    leaves:  str
    script:  str
    note:    str


@dataclass
class FeastMeta:
    id:           str
    label_ka:     str
    label_la:     str
    date_display: str
    fixed_month:  Optional[str]
    is_moveable:  bool


@dataclass
class AuthorMeta:
    id:        str
    name_ka:   str
    name_la:   str
    short_ka:  str
    dates:     str
    # Constructed-URL identifiers (empty string = absent)
    viaf:      str
    cpg:       str
    tm:        str
    # Arbitrary external authority links: list of {"label": str, "url": str}
    # Populated from <idno type="URI" subtype="…">full-url</idno> elements.
    # Any number of entries allowed; each renders as its own pill in the UI.
    uri_links: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class TextMeta:
    xml_id:         str
    label_ka:       str
    ms_heading:     str
    author_id:      str
    author_short:   str
    author_name_ka: str
    author_name_la: str
    feast_id:       str
    feast_label:    str
    feast_label_la: str
    genre:          str
    genre_class:    str
    genre_label:    str
    locus_n35:      str
    locus_n50:      str
    cpg:            str
    file_path:      str
    status:         str
    status_class:   str
    status_label:   str

    prev: Optional[object] = field(default=None, repr=False)
    next: Optional[object] = field(default=None, repr=False)


# ── Parser ────────────────────────────────────────────

class CatalogParser:

    GENRE_MAP = {
        "genre-homily":    ("homily",    "ჰომ."),
        "genre-life":      ("life",      "ცხ."),
        "genre-martyrdom": ("martyrdom", "წამ."),
        "genre-encomium":  ("encomium",  "ქება"),
        "genre-colophon":  ("colophon",  "ანდ."),
        "genre-other":     ("other",     "სხვ."),
    }

    STATUS_MAP = {
        "done":                 ("done",     "დასრ."),
        "encoding-in-progress": ("progress", "მიმდ."),
        "planned":              ("planned",  "დაგეგ."),
    }

    MONTH_LABELS = {
        "01": "იანვარი",    "02": "თებერვალი", "03": "მარტი",
        "04": "აპრილი",    "05": "მაისი",      "06": "ივნისი",
        "07": "ივლისი",    "08": "აგვისტო",    "09": "სექტემბერი",
        "10": "ოქტომბერი", "11": "ნოემბერი",   "12": "დეკემბერი",
    }

    def __init__(self, catalog_path: Path):
        self.path      = catalog_path
        self.witnesses: List[WitnessMeta] = []
        self.feasts:    List[FeastMeta]   = []
        self.authors:   List[AuthorMeta]  = []
        self.texts:     List[TextMeta]    = []
        self._feast_idx:  Dict[str, FeastMeta]  = {}
        self._author_idx: Dict[str, AuthorMeta] = {}

    # ── Top-level ──────────────────────────────────────

    def parse(self):
        tree          = ET.parse(self.path)
        self.root_el  = tree.getroot()
        self._parse_witnesses()
        self._parse_authors()
        self._parse_feasts()
        self._parse_texts()

    # ── Witnesses ─────────────────────────────────────

    def _parse_witnesses(self):
        for w in self.root_el.findall(".//tei:listWit/tei:witness", NS):
            xml_id = _xml_id(w)
            siglum = _t(w, "tei:abbr")
            msDesc = w.find("tei:msDesc", NS)
            idno   = _t(msDesc, ".//tei:idno") if msDesc is not None else ""

            date_orig = msDesc.find(".//tei:origDate", NS) if msDesc is not None else None
            date_str  = ""
            if date_orig is not None:
                when = _attr(date_orig, "when")
                nb   = _attr(date_orig, "notBefore")
                na   = _attr(date_orig, "notAfter")
                date_str = when or (f"{nb}–{na}" if nb and na else "")

            leaves = _t(msDesc, ".//tei:measure") if msDesc is not None else ""
            hand   = msDesc.find(".//tei:handNote", NS) if msDesc is not None else None
            script = _attr(hand, "script") if hand is not None else ""
            note   = _t(msDesc, ".//tei:note") if msDesc is not None else ""

            self.witnesses.append(WitnessMeta(
                xml_id=xml_id, siglum=siglum, idno=idno,
                date=date_str, leaves=leaves, script=script, note=note,
            ))

    # ── Authors ───────────────────────────────────────

    def _parse_authors(self):
        for p in self.root_el.findall(".//tei:listPerson[@type='authors']/tei:person", NS):
            xml_id  = _xml_id(p)
            name_ka = name_la = ""
            for pn in p.findall("tei:persName", NS):
                lang = _xml_lang(pn)
                txt  = (pn.text or "").strip()
                if lang == "ka" and not name_ka: name_ka = txt
                if lang == "la" and not name_la: name_la = txt

            birth   = p.find("tei:birth", NS)
            death   = p.find("tei:death", NS)
            floruit = p.find("tei:floruit", NS)
            dates   = ""
            if birth is not None and death is not None:
                b = _attr(birth, "when", "").lstrip("0")
                d = _attr(death, "when", "").lstrip("0")
                dates = f"{b}–{d}"
            elif floruit is not None:
                nb = _attr(floruit, "notBefore", "").lstrip("0")
                na = _attr(floruit, "notAfter",  "").lstrip("0")
                dates = f"c. {nb}–{na}" if nb and na else ""

            # ── Constructed-URL identifiers ────────────
            # All three use _clean_idno so empty elements and comment-only
            # elements (ElementTree sees them as '') are treated as absent.
            viaf = _clean_idno(_t(p, "tei:idno[@type='VIAF']"))
            cpg  = _clean_idno(_t(p, "tei:idno[@type='CPG']"))
            tm   = _clean_idno(_t(p, "tei:idno[@type='TM']"))

            # ── Arbitrary URI links ────────────────────
            # Collect every <idno type="URI" subtype="…">full-url</idno>.
            # @subtype becomes the display label; element text is the full URL.
            # The XPath predicate [@type='URI'] works because ElementTree
            # matches on the bare attribute name (no namespace prefix needed
            # for non-namespaced attributes).
            uri_links: List[Dict[str, str]] = []
            for idno_el in p.findall("tei:idno[@type='URI']", NS):
                url   = _clean_idno((idno_el.text or "").strip())
                label = idno_el.get("subtype", "").strip()
                if url and label:
                    uri_links.append({"label": label, "url": url})

            words    = name_ka.split()
            short_ka = " ".join(words[:2]) if len(words) >= 2 else name_ka

            a = AuthorMeta(
                id=xml_id, name_ka=name_ka, name_la=name_la,
                short_ka=short_ka, dates=dates,
                viaf=viaf, cpg=cpg, tm=tm,
                uri_links=uri_links,
            )
            self.authors.append(a)
            self._author_idx[xml_id] = a

    # ── Feasts ────────────────────────────────────────

    def _parse_feasts(self):
        for cat in self.root_el.findall(
            ".//tei:taxonomy[@xml:id='feasts']/tei:category", NS
        ):
            xml_id   = _xml_id(cat)
            label_ka = label_la = ""

            n_val    = _attr(cat, "n")
            date_val = n_val if n_val.startswith("--") else ""
            moveable = n_val == "moveable"

            for cd in cat.findall("tei:catDesc", NS):
                lang = _xml_lang(cd)
                txt  = (cd.text or "").strip()
                if lang == "ka": label_ka = txt
                if lang == "la": label_la = txt

            fixed_month  = None
            date_display = ""
            if date_val.startswith("--"):
                parts = date_val.lstrip("-").split("-")
                if len(parts) >= 2:
                    month, day   = parts[0], parts[1]
                    fixed_month  = month
                    date_display = f"{int(day)} {self.MONTH_LABELS.get(month, month)}"
            elif moveable:
                date_display = "მოძრავი"

            f = FeastMeta(
                id=xml_id, label_ka=label_ka, label_la=label_la,
                date_display=date_display, fixed_month=fixed_month,
                is_moveable=moveable,
            )
            self.feasts.append(f)
            self._feast_idx[xml_id] = f

    @property
    def feasts_ordered(self) -> List[FeastMeta]:
        """Liturgical order: fixed feasts by month (Sep-Aug), then moveable, then misc."""
        def sort_key(f: FeastMeta):
            if f.fixed_month:
                m = int(f.fixed_month)
                return (0, (m - 9) % 12)
            if f.is_moveable:
                return (1, 0)
            return (2, 0)
        return sorted(self.feasts, key=sort_key)

    # ── Texts ─────────────────────────────────────────

    def _parse_texts(self):
        for ev in self.root_el.findall(".//tei:listEvent/tei:event", NS):
            xml_id    = _xml_id(ev)
            feast_ref = _attr(ev, "corresp").lstrip("#")
            genre_ref = _attr(ev, "type").lstrip("#")

            label_ka   = _t(ev, "tei:label[@xml:lang='ka']") or _t(ev, "tei:label")
            ms_heading = _t(ev, "tei:desc[@xml:lang='ka']")  or _t(ev, "tei:desc")

            author_el  = ev.find("tei:note[@type='author']", NS)
            author_ref = _attr(author_el, "corresp").lstrip("#") if author_el is not None else "aut-anon"
            author     = self._author_idx.get(author_ref, AuthorMeta(
                id=author_ref, name_ka="?", name_la="?",
                short_ka="?", dates="", viaf="", cpg="", tm="", uri_links=[],
            ))

            locus_n35 = locus_n50 = ""
            for ms in ev.findall("tei:msDesc", NS):
                idno_el  = ms.find("tei:msIdentifier/tei:idno", NS)
                wit_id   = (idno_el.text or "").strip() if idno_el is not None else ""
                locus_el = ms.find("tei:locus", NS)
                locus_str = ""
                if locus_el is not None:
                    frm = _attr(locus_el, "from")
                    to  = _attr(locus_el, "to")
                    locus_str = (
                        f"ff. {frm}-{to}" if frm and to
                        else (locus_el.text or "").strip()
                    )
                if wit_id == "N35":   locus_n35 = locus_str
                elif wit_id == "N50": locus_n50 = locus_str

            cpg        = _t(ev, "tei:note[@type='CPG']")
            file_path  = _t(ev, "tei:note[@type='file']")
            status_raw = _t(ev, "tei:note[@type='status']") or "planned"

            genre_class, genre_label = self.GENRE_MAP.get(genre_ref, ("other", "სხვ."))
            status_class, status_label = self.STATUS_MAP.get(status_raw, ("planned", "დაგეგ."))

            feast = self._feast_idx.get(feast_ref, FeastMeta(
                id=feast_ref, label_ka=feast_ref, label_la="",
                date_display="", fixed_month=None, is_moveable=False,
            ))

            self.texts.append(TextMeta(
                xml_id=xml_id,
                label_ka=label_ka,
                ms_heading=ms_heading,
                author_id=author_ref,
                author_short=author.short_ka,
                author_name_ka=author.name_ka,
                author_name_la=author.name_la,
                feast_id=feast_ref,
                feast_label=feast.label_ka,
                feast_label_la=feast.label_la,
                genre=genre_ref,
                genre_class=genre_class,
                genre_label=genre_label,
                locus_n35=locus_n35,
                locus_n50=locus_n50,
                cpg=cpg,
                file_path=file_path,
                status=status_raw,
                status_class=status_class,
                status_label=status_label,
            ))
