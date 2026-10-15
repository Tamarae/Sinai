"""
src/research_parser.py
Globs tei/research/*.xml and parses each TEI research article into dataclasses.
Consumed by build.py → build_research() → templates/research/index.html + article.html

Rendering model
---------------
Each <div> becomes an ArticleSection whose `blocks` list keeps the document
order of everything inside it: paragraphs, run-in labels, block quotations and
verse, lists, tables, page breaks between blocks, section milestones, closers
and nested sub-sections (any depth). The template walks `blocks` recursively.

`paragraphs` and `subsections` are still filled for backward compatibility.

A <head rend="run-in"> (numbered § opening a paragraph, as printed) is merged
into the start of the division's first paragraph; the section keeps its id and
still appears in the table of contents.

Divisions in <back> are rendered only when their @type is in RENDER_BACK_TYPES
(e.g. errata); colophons, series lists etc. stay in the XML only.

Inline content (in paragraphs, heads, list items, verse lines, table cells,
quotations and notes) goes through one renderer, so a <note> or <pb> is handled
wherever it occurs, and typography (<hi rend="bold|letterspaced|spaced|italic|
sup|sub">), <foreign>, <unclear>, <gap>, <supplied> and <lb> are kept. A second
call to an existing footnote (<ref type="noteAnchor" target="#note-id">) renders
as a link to that footnote. Elements without a dedicated rule render their
content as plain text, so no text is ever dropped.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from lxml import etree

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
XML_ID   = "{http://www.w3.org/XML/1998/namespace}id"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# <back> divisions shown on the article page (others stay in the XML only)
RENDER_BACK_TYPES = {"errata", "corrigenda", "appendix"}


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
class Block:
    kind:    str                              # p | label | quote | list | table | gap | pb | milestone | closer | section
    html:    str = ""
    xml_id:  str = ""
    section: "ArticleSection | None" = None   # only for kind == "section"


@dataclass
class ArticleSection:
    n:           str
    xml_id:      str
    head:        str                          # plain text (TOC, titles)
    paragraphs:  list[Paragraph] = field(default_factory=list)
    subsections: list["ArticleSection"] = field(default_factory=list)
    notes:       list[NoteContent] = field(default_factory=list)
    level:       int = 0                      # 0 = top-level division
    head_html:   str = ""                     # heading with formatting + note refs
    blocks:      list[Block] = field(default_factory=list)
    run_in:      bool = False                 # head merged into first paragraph


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


def _local(el) -> str:
    return etree.QName(el.tag).localname


def _text(el) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _plain(el) -> str:
    """Visible text of an element without notes and gap descriptions; <lb/> → space."""
    if el is None:
        return ""
    out: list[str] = []

    def walk(e):
        if e.text:
            out.append(e.text)
        for c in e:
            if _is_element(c):
                tag = _local(c)
                if tag == "lb":
                    out.append(" ")
                elif tag == "supplied":
                    out.append("[" + _plain(c) + "]")
                elif tag == "gap":
                    out.append("[…]")
                elif tag not in ("note", "desc"):
                    walk(c)
            if c.tail:
                out.append(c.tail)

    walk(el)
    return " ".join("".join(out).split())


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
    """Plain-text bibl renderer (kept for callers outside ArticleParser)."""
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
            lang = child.get(XML_LANG, "")
            cls  = "bib-title-foreign" if lang and lang != "ka" else "bib-title"
            parts.append(f'<cite class="{cls}">{_escape(_text(child))}</cite>')
        elif tag == "series":
            parts.append(f'<span class="bib-series">{_escape(_text(child))}</span>')
        elif tag == "ref":
            parts.append(_render_ref(child))
        else:
            parts.append(_escape(_text(child)))
        if child.tail:
            parts.append(_escape(child.tail))
    return "".join(parts)


HI_TAGS = {
    "bold":         ('<strong>', '</strong>'),
    "b":            ('<strong>', '</strong>'),
    "letterspaced": ('<span class="ls">', '</span>'),
    "spaced":       ('<span class="ls">', '</span>'),
    "italic":       ('<em>', '</em>'),
    "i":            ('<em>', '</em>'),
    "sup":          ('<sup>', '</sup>'),
    "superscript":  ('<sup>', '</sup>'),
    "sub":          ('<sub>', '</sub>'),
    "subscript":    ('<sub>', '</sub>'),
}


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

        xml_id = root.get(XML_ID, path.stem)

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
            abstract = (_plain(first_p)[:280] + "…") if first_p is not None else ""

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
        sections: list[ArticleSection] = []
        all_notes: list[NoteContent] = []

        divs: list[etree._Element] = []
        if body is not None:
            divs += [d for d in body if _is_element(d) and _local(d) == "div"]
        back = self._root.find(".//tei:text/tei:back", NS)
        if back is not None:
            divs += [d for d in back if _is_element(d) and _local(d) == "div"
                     and d.get("type") in RENDER_BACK_TYPES]

        for div in divs:
            sec, notes = self._parse_div(div, level=0)
            sections.append(sec)
            all_notes.extend(notes)

        return Article(meta=meta, sections=sections, all_notes=all_notes)

    # ── divisions ─────────────────────────────────────

    def _parse_div(self, div: etree._Element, level: int = 0
                   ) -> tuple[ArticleSection, list[NoteContent]]:
        n      = div.get("n", "")
        xml_id = div.get(XML_ID, "")
        head_el = div.find("tei:head", NS)

        section_notes: list[NoteContent] = []
        head_html = self._inline(head_el, section_notes) if head_el is not None else ""
        head      = _plain(head_el)

        paragraphs:  list[Paragraph]      = []
        subsections: list[ArticleSection] = []
        blocks:      list[Block]          = []

        for child in div:
            if not _is_element(child):
                continue
            tag = _local(child)

            if tag == "head":
                if child is not head_el:          # a second head: show as label
                    blocks.append(Block("label",
                        f'<p class="label-p">{self._inline(child, section_notes)}</p>'))
                continue

            if tag == "div":
                sub, sub_notes = self._parse_div(child, level + 1)
                subsections.append(sub)
                section_notes.extend(sub_notes)
                blocks.append(Block("section", section=sub, xml_id=sub.xml_id))

            elif tag == "p":
                html = self._inline(child, section_notes)
                if child.get("rend") == "label":
                    blocks.append(Block("label", f'<p class="label-p">{html}</p>'))
                else:
                    p_id = child.get(XML_ID, "")
                    paragraphs.append(Paragraph(xml_id=p_id, html=html))
                    blocks.append(Block("p", html, xml_id=p_id))

            elif tag == "quote":
                blocks.append(Block("quote", self._render_quote(child, section_notes)))

            elif tag == "lg":
                blocks.append(Block("quote",
                    '<blockquote class="block-quote">'
                    + self._render_lg(child, section_notes) + '</blockquote>'))

            elif tag == "list":
                blocks.append(Block("list", self._render_list(child, section_notes)))

            elif tag == "table":
                blocks.append(Block("table", self._render_table(child, section_notes)))

            elif tag == "pb":
                blocks.append(Block("pb",
                    f'<div class="pb-block">{self._render_pb(child)}</div>'))

            elif tag == "milestone":
                if child.get("rend") == "asterism":
                    blocks.append(Block("milestone",
                        '<p class="asterism" aria-hidden="true">*&#8195;*&#8195;*</p>'))

            elif tag == "closer":
                blocks.append(Block("closer",
                    f'<div class="closer">{self._inline(child, section_notes)}</div>'))

            elif tag == "gap":
                blocks.append(Block("gap",
                    f'<p class="gap-block">{self._inline_el(child, section_notes)}</p>'))

            else:
                # note at division level, ab, etc. — render inline content as a paragraph
                html = (self._inline_el(child, section_notes)
                        if tag in ("note", "ref", "supplied") else self._inline(child, section_notes))
                if html.strip():
                    blocks.append(Block("p", html))

        # Run-in head: print it at the start of the first paragraph, as in the book.
        # Only when the paragraph is the first thing after the head (page breaks
        # in between are moved after the head text).
        run_in = False
        if head_el is not None and head_el.get("rend") == "run-in" and head_html:
            lead = 0
            while lead < len(blocks) and blocks[lead].kind == "pb":
                lead += 1
            if lead < len(blocks) and blocks[lead].kind == "p":
                first = blocks[lead]
                pbs = "".join(
                    b.html.replace('<div class="pb-block">', "").replace("</div>", "")
                    for b in blocks[:lead])
                first.html = (f'<strong class="run-in-head" id="{_escape(xml_id)}">'
                              f'{head_html}</strong> {pbs}{first.html}')
                for p in paragraphs:
                    if p.xml_id == first.xml_id:
                        p.html = first.html
                        break
                blocks = blocks[lead:]
                run_in = True

        sec = ArticleSection(
            n=n, xml_id=xml_id, head=head,
            paragraphs=paragraphs,
            subsections=subsections,
            notes=section_notes,
            level=level,
            head_html=head_html,
            blocks=blocks,
            run_in=run_in,
        )
        return sec, section_notes

    # ── block renderers ───────────────────────────────

    def _render_quote(self, q: etree._Element, notes: list[NoteContent]) -> str:
        parts: list[str] = ['<blockquote class="block-quote">']
        if q.text and q.text.strip():
            parts.append(f'<p class="quote-p">{_escape(q.text)}')
            open_p = True
        else:
            open_p = False
        for child in q:
            if not _is_element(child):
                if child.tail and child.tail.strip():
                    parts.append(_escape(child.tail))
                continue
            tag = _local(child)
            if tag in ("lg", "p", "bibl", "list") and open_p:
                parts.append("</p>")
                open_p = False
            if tag == "lg":
                parts.append(self._render_lg(child, notes))
            elif tag == "l":
                parts.append(f'<span class="l">{self._inline(child, notes)}</span>')
            elif tag == "p":
                parts.append(f'<p class="quote-p">{self._inline(child, notes)}</p>')
            elif tag == "bibl":
                parts.append(f'<span class="quote-bibl">{self._inline(child, notes)}</span>')
            elif tag == "list":
                parts.append(self._render_list(child, notes))
            else:
                parts.append(self._inline_el(child, notes))
            if child.tail and child.tail.strip():
                parts.append(_escape(child.tail))
        if open_p:
            parts.append("</p>")
        parts.append("</blockquote>")
        return "".join(parts)

    def _render_lg(self, lg: etree._Element, notes: list[NoteContent]) -> str:
        parts: list[str] = ['<div class="lg">']
        for child in lg:
            if not _is_element(child):
                continue
            tag = _local(child)
            if tag == "l":
                parts.append(f'<span class="l">{self._inline(child, notes)}</span>')
            elif tag == "lg":
                parts.append(self._render_lg(child, notes))
            elif tag == "pb":
                parts.append(f'<span class="l l-pb">{self._render_pb(child)}</span>')
            else:
                parts.append(f'<span class="l">{self._inline_el(child, notes)}</span>')
        parts.append("</div>")
        return "".join(parts)

    def _render_list(self, lst: etree._Element, notes: list[NoteContent]) -> str:
        parts: list[str] = ['<div class="art-list-wrap">']
        items: list[str] = []
        for child in lst:
            if not _is_element(child):
                continue
            tag = _local(child)
            if tag == "head":
                parts.append(f'<p class="list-head">{self._inline(child, notes)}</p>')
            elif tag == "item":
                items.append(f'<li>{self._render_item(child, notes)}</li>')
            elif tag == "label":
                items.append(f'<li class="item-label">{self._inline(child, notes)}</li>')
            elif tag == "pb":
                items.append(f'<li class="li-pb">{self._render_pb(child)}</li>')
            else:
                items.append(f'<li>{self._inline_el(child, notes)}</li>')
        parts.append('<ul class="art-list">' + "".join(items) + '</ul></div>')
        return "".join(parts)

    def _render_item(self, item: etree._Element, notes: list[NoteContent]) -> str:
        """An <item> with <p>/<label> children renders them as blocks; otherwise inline."""
        if not any(_is_element(c) and _local(c) in ("p", "label", "list") for c in item):
            return self._inline(item, notes)
        parts: list[str] = []
        if item.text and item.text.strip():
            parts.append(_escape(item.text))
        for child in item:
            if not _is_element(child):
                continue
            tag = _local(child)
            if tag == "p":
                parts.append(f'<p class="item-p">{self._inline(child, notes)}</p>')
            elif tag == "label":
                parts.append(f'<span class="item-label">{self._inline(child, notes)}</span>')
            elif tag == "list":
                parts.append(self._render_list(child, notes))
            else:
                parts.append(self._inline_el(child, notes))
            if child.tail and child.tail.strip():
                parts.append(_escape(child.tail))
        return "".join(parts)

    def _render_table(self, table: etree._Element, notes: list[NoteContent]) -> str:
        parts: list[str] = ['<div class="table-wrap"><table class="art-table">']
        head = table.find("tei:head", NS)
        if head is not None:
            parts.append(f'<caption>{self._inline(head, notes)}</caption>')
        for row in table:
            if not _is_element(row):
                continue
            if _local(row) == "pb":
                continue
            if _local(row) != "row":
                continue
            is_label = row.get("role") == "label"
            cells: list[str] = []
            for cell in row:
                if not _is_element(cell) or _local(cell) != "cell":
                    continue
                tag = "th" if is_label or cell.get("role") == "label" else "td"
                span = ""
                if cell.get("cols"):
                    span += f' colspan="{_escape(cell.get("cols"))}"'
                if cell.get("rows"):
                    span += f' rowspan="{_escape(cell.get("rows"))}"'
                cells.append(f'<{tag}{span}>{self._inline(cell, notes)}</{tag}>')
            parts.append("<tr>" + "".join(cells) + "</tr>")
        parts.append("</table></div>")
        return "".join(parts)

    @staticmethod
    def _render_pb(pb: etree._Element) -> str:
        pb_n = pb.get("n", "")
        if not pb_n:
            return ""
        return f'<span class="pb-marker" title="გვ. {_escape(pb_n)}">[გვ. {_escape(pb_n)}]</span>'

    # ── inline renderer ───────────────────────────────

    def _render_p(self, p_el: etree._Element) -> tuple[str, list[NoteContent]]:
        """Kept for compatibility: render one <p>, return (html, notes)."""
        notes: list[NoteContent] = []
        return self._inline(p_el, notes), notes

    def _inline(self, el: etree._Element, notes: list[NoteContent], ctx: str = "text") -> str:
        """Render the content of el (its text, children and their tails)."""
        if el is None:
            return ""
        parts: list[str] = []
        if el.text:
            parts.append(_escape(el.text))
        for child in el:
            if _is_element(child):
                parts.append(self._inline_el(child, notes, ctx))
            if child.tail:
                parts.append(_escape(child.tail))
        return "".join(parts)

    def _inline_el(self, child: etree._Element, notes: list[NoteContent],
                   ctx: str = "text") -> str:
        """Render one inline element (without its tail)."""
        tag = _local(child)

        if tag == "note":
            if ctx == "note":                       # note inside a note: inline text
                return self._inline(child, notes, ctx)
            self._note_counter += 1
            n      = child.get("n", str(self._note_counter))
            xml_id = child.get(XML_ID, f"note-{self._note_counter}")
            note_html = self._render_note_content(child)
            notes.append(NoteContent(n=n, xml_id=xml_id, html=note_html))
            return (
                f'<span class="note-ref-wrap" data-note-id="{_escape(xml_id)}">'
                f'<a href="#fn-{_escape(xml_id)}" class="note-ref" '
                f'id="ref-{_escape(xml_id)}">{_escape(n)}</a>'
                f'</span>'
            )

        if tag == "pb":
            return self._render_pb(child)

        if tag == "ref" and child.get("type") == "noteAnchor":
            # second call to a footnote that is printed once
            target = child.get("target", "").lstrip("#")
            n = child.get("n", "")
            if not n:
                hit = self._root.xpath("//tei:note[@xml:id=$i]", namespaces=NS, i=target)
                n = hit[0].get("n", "") if hit else ""
            return (
                f'<span class="note-ref-wrap" data-note-id="{_escape(target)}">'
                f'<a href="#fn-{_escape(target)}" class="note-ref">{_escape(n)}</a>'
                f'</span>'
            )

        if tag == "ref":
            return _render_ref(child)

        if tag == "supplied":
            return f'<span class="supplied" title="ედიტორის დამატება">[{self._inline(child, notes, ctx)}]</span>'

        if tag == "table":
            return self._render_table(child, notes)

        if tag == "persName":
            return f'<span class="persname">{self._inline(child, notes, ctx)}</span>'

        if tag == "hi":
            open_t, close_t = HI_TAGS.get((child.get("rend") or "").strip(), ("", ""))
            return f'{open_t}{self._inline(child, notes, ctx)}{close_t}'

        if tag == "foreign":
            lang = child.get(XML_LANG, "")
            lang_attr = f' lang="{_escape(lang)}"' if lang else ""
            return f'<span class="foreign"{lang_attr}>{self._inline(child, notes, ctx)}</span>'

        if tag == "unclear":
            return (f'<span class="unclear" title="საეჭვო წაკითხვა">'
                    f'{self._inline(child, notes, ctx)}</span>')

        if tag == "gap":
            desc = _text(child.find("tei:desc", NS)) or child.get("reason", "")
            extent = child.get("extent", "")
            title = "; ".join(x for x in (desc, extent) if x)
            return f'<span class="gap" title="{_escape(title)}">[…]</span>'

        if tag == "desc":
            return ""

        if tag == "lb":
            return "<br>"

        if tag == "l":
            return f'<span class="l">{self._inline(child, notes, ctx)}</span>'

        if tag == "lg":
            return self._render_lg(child, notes)

        if ctx == "note":
            if tag == "bibl":
                return f'<span class="bibl">{self._render_bibl(child, notes)}</span>'
            if tag == "title":
                lang = child.get(XML_LANG, "")
                cls  = "title-foreign" if lang and lang != "ka" else "title"
                return f'<cite class="{cls}">{self._inline(child, notes, ctx)}</cite>'
            if tag == "author":
                return f'<span class="author">{self._inline(child, notes, ctx)}</span>'

        if tag == "bibl":
            return f'<span class="bibl">{self._inline(child, notes, ctx)}</span>'

        # Any other element (title, date, num, measure, mentioned, quote, …): content only
        return self._inline(child, notes, ctx)

    def _render_bibl(self, bibl_el: etree._Element, notes: list[NoteContent]) -> str:
        parts: list[str] = []
        if bibl_el.text:
            parts.append(_escape(bibl_el.text))
        for child in bibl_el:
            if _is_element(child):
                tag = _local(child)
                if tag == "author":
                    parts.append(f'<span class="bib-author">{self._inline(child, notes, "note")}</span>')
                elif tag == "title":
                    lang = child.get(XML_LANG, "")
                    cls  = "bib-title-foreign" if lang and lang != "ka" else "bib-title"
                    parts.append(f'<cite class="{cls}">{self._inline(child, notes, "note")}</cite>')
                elif tag == "series":
                    parts.append(f'<span class="bib-series">{self._inline(child, notes, "note")}</span>')
                else:
                    parts.append(self._inline_el(child, notes, "note"))
            if child.tail:
                parts.append(_escape(child.tail))
        return "".join(parts)

    def _render_note_content(self, note_el: etree._Element) -> str:
        """Render the content of a <note> for the footnote list and hover tooltip."""
        inner_notes: list[NoteContent] = []
        return self._inline(note_el, inner_notes, ctx="note")
