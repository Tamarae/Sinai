"""
src/research_parser.py
Globs tei/research/*.xml and parses each TEI research article into dataclasses.
Consumed by build.py → build_research() → templates/research/index.html + article.html
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from lxml import etree

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


# ── Dataclasses ───────────────────────────────────────

@dataclass
class NoteContent:
    n:      str
    xml_id: str
    html:   str   # rendered inner content


@dataclass
class Paragraph:
    xml_id: str
    html:   str   # rendered HTML with inline note superscripts


@dataclass
class ArticleSection:
    n:           str
    xml_id:      str
    head:        str
    paragraphs:  list[Paragraph] = field(default_factory=list)
    subsections: list["ArticleSection"] = field(default_factory=list)
    notes:       list[NoteContent] = field(default_factory=list)


@dataclass
class ArticleMeta:
    xml_id:    str
    file_path: Path
    title:     str
    title_en:  str
    author:    str
    date:      str
    abstract:  str


@dataclass
class Article:
    meta:      ArticleMeta
    sections:  list[ArticleSection]
    all_notes: list[NoteContent] = field(default_factory=list)


@dataclass
class ResearchData:
    articles: list[ArticleMeta]


# ── Helpers ───────────────────────────────────────────

def _is_element(node) -> bool:
    """Return True only for real Element nodes — skips comments, PIs, entities."""
    return isinstance(node.tag, str)


def _text(el) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _escape(s: str) -> str:
    return (s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;"))


def _render_ref(child: etree._Element) -> str:
    """Render <ref target="..."> as an HTML anchor.

    External URLs (http/https) → .ext-link, opens in new tab.
    Internal anchors (#bib-…)  → .bib-ref, same page.
    No text content             → empty string (silent machine pointer).
    """
    target = child.get("target", "")
    inner  = _text(child)
    if not inner:
        return ""
    if not target:
        return _escape(inner)
    if target.startswith("http://") or target.startswith("https://"):
        return (
            f'<a href="{_escape(target)}" class="ext-link" '
            f'target="_blank" rel="noopener noreferrer">{_escape(inner)}</a>'
        )
    return f'<a href="{_escape(target)}" class="bib-ref">{_escape(inner)}</a>'


def _render_bibl(bibl_el: etree._Element) -> str:
    parts: list[str] = []
    if bibl_el.text:
        parts.append(_escape(bibl_el.text))
    for child in bibl_el:
        if not _is_element(child):
            if child.tail:
                parts.append(_escape(child.tail))
            continue
        tag = etree.QName(child.tag).localname
        if tag == "author":
            parts.append(f'<span class="bib-author">{_escape(_text(child))}</span>')
        elif tag == "title":
            lang = child.get("{http://www.w3.org/XML/1998/namespace}lang", "")
            cls  = "bib-title-foreign" if lang and lang != "ka" else "bib-title"
            parts.append(f'<cite class="{cls}">{_escape(_text(child))}</cite>')
        elif tag == "series":
            parts.append(f'<span class="bib-series">{_escape(_text(child))}</span>')
        elif tag == "ref":
            # Inside <bibl>: render only if there is visible text; otherwise silent
            parts.append(_render_ref(child))
        else:
            parts.append(_escape(_text(child)))
        if child.tail:
            parts.append(_escape(child.tail))
    return "".join(parts)


# ── Index parser (metadata only) ─────────────────────

class ResearchIndexParser:
    """Globs tei/research/ and returns lightweight metadata for the index page."""

    def __init__(self, research_dir: Path):
        self.research_dir = research_dir

    def parse(self) -> ResearchData:
        articles = []
        for xml_path in sorted(self.research_dir.glob("*.xml")):
            meta = self._parse_meta(xml_path)
            if meta:
                articles.append(meta)
        return ResearchData(articles=articles)

    def _parse_meta(self, path: Path) -> ArticleMeta | None:
        try:
            tree = etree.parse(str(path))
            root = tree.getroot()
        except etree.XMLSyntaxError:
            return None

        xml_id = root.get("{http://www.w3.org/XML/1998/namespace}id", path.stem)

        title_el = root.find(".//tei:titleStmt/tei:title[@xml:lang='ka']", NS)
        if title_el is None:
            title_el = root.find(".//tei:titleStmt/tei:title", NS)
        title = _text(title_el) if title_el is not None else xml_id

        title_en_el = root.find(".//tei:titleStmt/tei:title[@type='sub']", NS)
        title_en = _text(title_en_el) if title_en_el is not None else ""

        author_el = root.find(".//tei:titleStmt/tei:author/tei:persName[@xml:lang='ka']", NS)
        if author_el is None:
            author_el = root.find(".//tei:titleStmt/tei:author", NS)
        author = _text(author_el) if author_el is not None else ""

        date_el = root.find(".//tei:publicationStmt/tei:date", NS)
        date = date_el.get("when", _text(date_el)) if date_el is not None else ""

        abstract_el = root.find(".//tei:abstract/tei:p", NS)
        if abstract_el is not None:
            abstract = _text(abstract_el)
        else:
            first_p = root.find(".//tei:body//tei:p", NS)
            abstract = (_text(first_p)[:280] + "…") if first_p is not None else ""

        return ArticleMeta(
            xml_id=xml_id,
            file_path=path,
            title=title,
            title_en=title_en,
            author=author,
            date=date,
            abstract=abstract,
        )


# ── Full article parser ───────────────────────────────

class ArticleParser:
    """Parses a single research XML file into a full Article for the article page."""

    def __init__(self, path: Path):
        self.path = path
        self._tree = etree.parse(str(path))
        self._root = self._tree.getroot()
        self._note_counter = 0

    def parse(self) -> Article:
        meta = ResearchIndexParser(self.path.parent)._parse_meta(self.path)

        body = self._root.find(".//tei:body", NS)
        sections = []
        all_notes = []

        if body is not None:
            for div in body:
                if not _is_element(div):
                    continue
                if etree.QName(div.tag).localname == "div":
                    sec, notes = self._parse_div(div)
                    sections.append(sec)
                    all_notes.extend(notes)

        return Article(meta=meta, sections=sections, all_notes=all_notes)

    def _parse_div(self, div: etree._Element) -> tuple[ArticleSection, list[NoteContent]]:
        n      = div.get("n", "")
        xml_id = div.get("{http://www.w3.org/XML/1998/namespace}id", "")
        head_el = div.find("tei:head", NS)
        head   = _text(head_el) if head_el is not None else ""

        paragraphs:    list[Paragraph]      = []
        subsections:   list[ArticleSection] = []
        section_notes: list[NoteContent]    = []

        for child in div:
            if not _is_element(child):
                continue
            tag = etree.QName(child.tag).localname
            if tag == "p":
                p_id = child.get("{http://www.w3.org/XML/1998/namespace}id", "")
                html, notes = self._render_p(child)
                paragraphs.append(Paragraph(xml_id=p_id, html=html))
                section_notes.extend(notes)
            elif tag == "div":
                sub, sub_notes = self._parse_div(child)
                subsections.append(sub)
                section_notes.extend(sub_notes)

        sec = ArticleSection(
            n=n, xml_id=xml_id, head=head,
            paragraphs=paragraphs,
            subsections=subsections,
            notes=section_notes,
        )
        return sec, section_notes

    def _render_p(self, p_el: etree._Element) -> tuple[str, list[NoteContent]]:
        """
        Convert <p> to HTML. Footnote <note> elements become:
          <span class="note-ref-wrap" data-note-id="{xml_id}">
            <a href="#fn-{xml_id}" class="note-ref">{n}</a>
          </span>
        The full footnote text goes into all_notes; JS builds tooltips from there.
        """
        notes_found: list[NoteContent] = []
        parts: list[str] = []

        if p_el.text:
            parts.append(_escape(p_el.text))

        for child in p_el:
            if not _is_element(child):
                if child.tail:
                    parts.append(_escape(child.tail))
                continue

            tag = etree.QName(child.tag).localname

            if tag == "note":
                self._note_counter += 1
                n      = child.get("n", str(self._note_counter))
                xml_id = child.get("{http://www.w3.org/XML/1998/namespace}id",
                                   f"note-{self._note_counter}")
                note_html = self._render_note_content(child)
                notes_found.append(NoteContent(n=n, xml_id=xml_id, html=note_html))
                parts.append(
                    f'<span class="note-ref-wrap" data-note-id="{xml_id}">'
                    f'<a href="#fn-{xml_id}" class="note-ref" id="ref-{xml_id}">{n}</a>'
                    f'</span>'
                )

            elif tag == "persName":
                parts.append(f'<span class="persname">{_escape(_text(child))}</span>')

            elif tag == "pb":
                pb_n = child.get("n", "")
                parts.append(
                    f'<span class="pb-marker" title="გვ. {pb_n}">[გვ. {pb_n}]</span>'
                )

            elif tag == "ref":
                parts.append(_render_ref(child))

            else:
                parts.append(_escape(_text(child)))

            if child.tail:
                parts.append(_escape(child.tail))

        return "".join(parts), notes_found

    def _render_note_content(self, note_el: etree._Element) -> str:
        """Render the content of a <note> for the footnote list and hover tooltip.
        Handles <bibl>, <title>, <author>, <persName>, and <ref> (external + internal).
        """
        parts: list[str] = []
        if note_el.text:
            parts.append(_escape(note_el.text))
        for child in note_el:
            if not _is_element(child):
                if child.tail:
                    parts.append(_escape(child.tail))
                continue
            tag = etree.QName(child.tag).localname
            if tag == "bibl":
                parts.append(f'<span class="bibl">{_render_bibl(child)}</span>')
            elif tag == "title":
                lang = child.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                cls  = "title-foreign" if lang and lang != "ka" else "title"
                parts.append(f'<cite class="{cls}">{_escape(_text(child))}</cite>')
            elif tag == "author":
                parts.append(f'<span class="author">{_escape(_text(child))}</span>')
            elif tag == "persName":
                parts.append(f'<span class="persname">{_escape(_text(child))}</span>')
            elif tag == "ref":
                parts.append(_render_ref(child))
            else:
                parts.append(_escape(_text(child)))
            if child.tail:
                parts.append(_escape(child.tail))
        return "".join(parts)
