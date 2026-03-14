"""
src/bibliography_parser.py
Parses tei/bibliography.xml (TEI <listBibl> structure) into Python dataclasses.
Consumed by build.py → build_bibliography() → templates/bibliography/index.html
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from lxml import etree

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

# Human-readable labels for each type value in bibliography.xml
TYPE_LABELS: dict[str, str] = {
    "manuscript": "პირველწყაროები — ხელნაწერები",
    "edition":    "კრიტიკული გამოცემები",
    "secondary":  "კვლევები",
    "digital":    "ციფრული ჰუმანიტარია",
}

TYPE_ORDER = ["manuscript", "edition", "secondary", "digital"]


# ── Dataclasses ───────────────────────────────────────

@dataclass
class BibAuthor:
    surname:  str = ""
    forename: str = ""
    org:      str = ""   # for <orgName> authors

    @property
    def display(self) -> str:
        if self.org:
            return self.org
        parts = []
        if self.surname:
            parts.append(self.surname)
        if self.forename:
            parts.append(self.forename)
        return ", ".join(parts) if parts else ""

    @property
    def sort_key(self) -> str:
        return (self.surname or self.org or "").lower()


@dataclass
class BibEntry:
    xml_id:    str
    bib_type:  str          # manuscript | edition | secondary | digital
    title:     str = ""
    title_short: str = ""
    authors:   list[BibAuthor] = field(default_factory=list)
    # journal / series analytic title
    journal:   str = ""
    # monograph-level info
    pub_place: str = ""
    publisher: str = ""
    date:      str = ""
    series:    str = ""
    extent:    str = ""
    # article-level scope
    volume:    str = ""
    issue:     str = ""
    pages:     str = ""
    # identifiers
    doi:       str = ""
    iiif:      str = ""
    shelfmark: str = ""
    siglum:    str = ""
    url:       str = ""
    # free note
    note:      str = ""

    @property
    def author_display(self) -> str:
        return "; ".join(a.display for a in self.authors) if self.authors else ""

    @property
    def sort_key(self) -> str:
        if self.authors:
            return self.authors[0].sort_key
        return self.title.lower()

    @property
    def is_article(self) -> bool:
        return bool(self.journal)

    @property
    def type_label(self) -> str:
        return TYPE_LABELS.get(self.bib_type, self.bib_type)


@dataclass
class BibliographyData:
    entries:        list[BibEntry]
    entries_by_type: dict[str, list[BibEntry]]
    types:          list[str]   # ordered list of types present in data


# ── Parser ────────────────────────────────────────────

class BibliographyParser:
    def __init__(self, path: Path):
        self.path = path
        self._tree = etree.parse(str(path))
        self._root = self._tree.getroot()

    # ── Public entry point ────────────────────────────
    def parse(self) -> BibliographyData:
        all_entries: list[BibEntry] = []

        # Walk every <biblStruct> anywhere in the document
        for bstruct in self._root.iter("{http://www.tei-c.org/ns/1.0}biblStruct"):
            entry = self._parse_biblstruct(bstruct)
            if entry:
                all_entries.append(entry)

        # Group by type, preserving TYPE_ORDER
        by_type: dict[str, list[BibEntry]] = {}
        for entry in all_entries:
            by_type.setdefault(entry.bib_type, []).append(entry)

        # Sort each group by author/title
        for grp in by_type.values():
            grp.sort(key=lambda e: e.sort_key)

        # Build ordered list of types that actually have entries
        types_present = [t for t in TYPE_ORDER if t in by_type]
        # Append any unlisted types at the end
        for t in by_type:
            if t not in types_present:
                types_present.append(t)

        return BibliographyData(
            entries=all_entries,
            entries_by_type=by_type,
            types=types_present,
        )

    # ── Internal helpers ──────────────────────────────
    def _parse_biblstruct(self, el: etree._Element) -> BibEntry | None:
        xml_id = el.get("{http://www.w3.org/XML/1998/namespace}id", "")
        if not xml_id:
            return None

        # Inherit type from parent <listBibl type="..."> if not on <biblStruct>
        bib_type = el.get("type") or self._inherited_type(el)

        entry = BibEntry(xml_id=xml_id, bib_type=bib_type)

        # ── <analytic> — article-level ────────────────
        analytic = el.find("tei:analytic", NS)
        if analytic is not None:
            entry.authors.extend(self._parse_authors(analytic))
            t = analytic.find("tei:title[@level='a']", NS)
            if t is None:
                t = analytic.find("tei:title", NS)
            if t is not None:
                entry.title = self._text(t)

        # ── <monogr> — monograph / journal level ──────
        monogr = el.find("tei:monogr", NS)
        if monogr is not None:
            # Authors only if not already from <analytic>
            if not entry.authors:
                entry.authors.extend(self._parse_authors(monogr))

            # Title: prefer level="m", fall back to level="j" or first title
            for lvl in ("m", "j", None):
                if lvl:
                    t = monogr.find(f"tei:title[@level='{lvl}']", NS)
                else:
                    t = monogr.find("tei:title", NS)
                if t is not None:
                    if entry.is_article or not entry.title:
                        # journal title → entry.journal; monograph title → entry.title
                        if lvl == "j":
                            entry.journal = self._text(t)
                        else:
                            if not entry.title:
                                entry.title = self._text(t)
                    break

            # Short title
            ts = monogr.find("tei:title[@type='short']", NS)
            if ts is not None:
                entry.title_short = self._text(ts)

            # journal-level title when analytic exists
            if analytic is not None:
                jt = monogr.find("tei:title[@level='j']", NS)
                if jt is not None:
                    entry.journal = self._text(jt)

            # <imprint>
            imprint = monogr.find("tei:imprint", NS)
            if imprint is not None:
                pp = imprint.find("tei:pubPlace", NS)
                if pp is not None:
                    entry.pub_place = self._text(pp)
                pub = imprint.find("tei:publisher", NS)
                if pub is not None:
                    entry.publisher = self._text(pub)
                # date
                d = imprint.find("tei:date", NS)
                if d is not None:
                    entry.date = (
                        d.get("when")
                        or d.get("notBefore", "") + "–" + d.get("notAfter", "")
                        or self._text(d)
                    ).strip("–")

            # <biblScope>
            for scope in monogr.findall("tei:biblScope", NS):
                u = scope.get("unit", "")
                v = self._text(scope)
                if u == "series":
                    entry.series = v
                elif u == "volume":
                    entry.volume = v
                elif u == "issue":
                    entry.issue = v
                elif u in ("pp", "page"):
                    entry.pages = v

            # <extent>
            ext = monogr.find("tei:extent", NS)
            if ext is not None:
                entry.extent = self._text(ext)

            # <ref> inside <monogr> (e.g. bib-tei-p5)
            ref = monogr.find("tei:ref", NS)
            if ref is not None:
                entry.url = ref.get("target", "")

        # ── <ref> as direct child of <biblStruct> ─────
        # Covers cases like bib-gippert2011 where <ref> sits beside <analytic>/<monogr>
        if not entry.url:
            top_ref = el.find("tei:ref", NS)
            if top_ref is not None:
                entry.url = top_ref.get("target", "")

        # ── <idno> ────────────────────────────────────
        for idno in el.iter("{http://www.tei-c.org/ns/1.0}idno"):
            t = idno.get("type", "")
            v = self._text(idno)
            if t == "DOI":
                entry.doi = v
            elif t == "IIIF":
                entry.iiif = v
            elif t == "shelfmark":
                entry.shelfmark = v
            elif t == "siglum":
                entry.siglum = v

        # ── <note> ────────────────────────────────────
        note = el.find("tei:note", NS)
        if note is not None:
            entry.note = self._text(note)

        return entry

    def _parse_authors(self, parent: etree._Element) -> list[BibAuthor]:
        authors = []
        for a in parent.findall("tei:author", NS):
            surname  = self._child_text(a, "tei:surname")
            forename = self._child_text(a, "tei:forename")
            org      = self._child_text(a, "tei:orgName")
            # fall back to direct text if no sub-elements
            if not (surname or forename or org):
                org = self._text(a)
            authors.append(BibAuthor(surname=surname, forename=forename, org=org))
        return authors

    def _inherited_type(self, el: etree._Element) -> str:
        """Walk up to nearest <listBibl type="..."> to inherit type."""
        parent = el.getparent()
        while parent is not None:
            tag = etree.QName(parent.tag).localname
            if tag == "listBibl":
                t = parent.get("type")
                if t:
                    return t
            parent = parent.getparent()
        return "other"

    @staticmethod
    def _text(el: etree._Element) -> str:
        return "".join(el.itertext()).strip()

    def _child_text(self, parent: etree._Element, xpath: str) -> str:
        child = parent.find(xpath, NS)
        return self._text(child) if child is not None else ""
