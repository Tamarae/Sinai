#!/usr/bin/env python3
"""
build.py  —  Sinai Mravaltavi Digital Edition
Reads tei/catalog.xml + individual tei/texts/*.xml + tei/lexicon.xml +
tei/bibliography.xml + tei/research/*.xml and renders static HTML into build/.

Usage:
    python build.py                  # full build
    python build.py --texts          # texts only
    python build.py --lexicon        # lexicon only
    python build.py --bibliography   # bibliography only
    python build.py --research       # research only
    python build.py --index          # index + navigation pages only
"""

import argparse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.catalog_parser import CatalogParser
from src.text_parser    import TextParser
from src.lexicon_parser import LexiconParser

# ── Paths ─────────────────────────────────────────────
ROOT             = Path(__file__).parent
TEI_DIR          = ROOT / "tei"
BUILD_DIR        = ROOT / "build"
TMPL_DIR         = ROOT / "templates"

CATALOG_XML      = TEI_DIR / "catalog.xml"
LEXICON_XML      = TEI_DIR / "lexicon.xml"
BIBLIOGRAPHY_XML = TEI_DIR / "bibliography.xml"
RESEARCH_DIR     = TEI_DIR / "research"
TEXTS_DIR        = TEI_DIR / "texts"

# ── Jinja2 environment ────────────────────────────────
env = Environment(
    loader=FileSystemLoader(str(TMPL_DIR)),
    autoescape=select_autoescape(["html"]),
)

import urllib.parse
env.filters["urlencode"] = urllib.parse.quote

# ── Helpers ───────────────────────────────────────────
def render(template_path: str, dest: Path, **ctx):
    """Render a Jinja2 template to dest, creating parent dirs as needed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmpl = env.get_template(template_path)
    dest.write_text(tmpl.render(**ctx), encoding="utf-8")
    print(f"  → {dest.relative_to(ROOT)}")


# ─────────────────────────────────────────────────────
# 1.  CATALOG / INDEX PAGES
# ─────────────────────────────────────────────────────
def build_index(catalog: CatalogParser):
    print("\n[index]")
    render(
        "index.html",
        BUILD_DIR / "index.html",
        root="",
        active="home",
        catalog=catalog,
    )
    render(
        "manuscripts.html",
        BUILD_DIR / "manuscripts.html",
        root="",
        active="manuscripts",
        witnesses=catalog.witnesses,
    )
    render(
        "about.html",
        BUILD_DIR / "about.html",
        root="",
        active="about",
        catalog=catalog,
    )


# ─────────────────────────────────────────────────────
# 2.  TEXTS BROWSER  (texts/index.html)
# ─────────────────────────────────────────────────────
def build_texts_index(catalog: CatalogParser):
    print("\n[texts/index]")
    render(
        "texts/index.html",
        BUILD_DIR / "texts" / "index.html",
        root="../",
        active="texts",
        texts=catalog.texts,
        feasts=catalog.feasts,
        feasts_ordered=catalog.feasts_ordered,
        authors=catalog.authors,
    )


# ─────────────────────────────────────────────────────
# 3.  INDIVIDUAL TEXT PAGES
# ─────────────────────────────────────────────────────
def build_texts(catalog: CatalogParser):
    print("\n[texts]")
    text_list = catalog.texts

    for i, meta in enumerate(text_list):
        xml_path = ROOT / meta.file_path
        if not xml_path.exists():
            print(f"  ⚠  {meta.xml_id}: XML not found, skipping")
            continue

        parser = TextParser(xml_path, meta)
        text   = parser.parse()

        text.prev = text_list[i - 1] if i > 0                 else None
        text.next = text_list[i + 1] if i < len(text_list) - 1 else None

        render(
            "texts/text.html",
            BUILD_DIR / "texts" / f"{meta.xml_id}.html",
            root="../",
            active="texts",
            text=text,
        )


# ─────────────────────────────────────────────────────
# 4.  LEXICON
# ─────────────────────────────────────────────────────
def build_lexicon():
    print("\n[lexicon]")
    parser = LexiconParser(LEXICON_XML)
    data   = parser.parse()

    render(
        "lexicon/index.html",
        BUILD_DIR / "lexicon" / "index.html",
        root="../",
        active="lexicon",
        entries=data.entries,
        entries_by_letter=data.entries_by_letter,
        alphabet=data.alphabet,
        pos_list=data.pos_list,
    )


# ─────────────────────────────────────────────────────
# 5.  RESEARCH
# ─────────────────────────────────────────────────────
def build_research():
    if not RESEARCH_DIR.exists() or not any(RESEARCH_DIR.glob("*.xml")):
        print("\n[research] — skipped (tei/research/*.xml not found)")
        return

    print("\n[research]")
    from src.research_parser import ResearchIndexParser, ArticleParser

    # Index page
    index_parser = ResearchIndexParser(RESEARCH_DIR)
    data = index_parser.parse()
    render(
        "research/index.html",
        BUILD_DIR / "research" / "index.html",
        root="../",
        active="research",
        articles=data.articles,
    )

    # Individual article pages
    for meta in data.articles:
        article_parser = ArticleParser(meta.file_path)
        article = article_parser.parse()
        render(
            "research/article.html",
            BUILD_DIR / "research" / f"{meta.xml_id}.html",
            root="../",
            active="research",
            article=article,
        )


# ─────────────────────────────────────────────────────
# 6.  BIBLIOGRAPHY
# ─────────────────────────────────────────────────────
def build_bibliography():
    if not BIBLIOGRAPHY_XML.exists():
        print("\n[bibliography] — skipped (tei/bibliography.xml not found)")
        return
    print("\n[bibliography]")
    from src.bibliography_parser import BibliographyParser
    parser = BibliographyParser(BIBLIOGRAPHY_XML)
    data   = parser.parse()

    render(
        "bibliography/index.html",
        BUILD_DIR / "bibliography" / "index.html",
        root="../",
        active="bibliography",
        entries=data.entries,
        entries_by_type=data.entries_by_type,
        types=data.types,
    )


# ─────────────────────────────────────────────────────
# 7.  STATIC ASSETS
# ─────────────────────────────────────────────────────
def copy_static():
    import shutil
    src = ROOT / "static"
    dst = BUILD_DIR / "static"
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"\n[static] → {dst.relative_to(ROOT)}")


# ─────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Build Mravaltavi edition")
    parser.add_argument("--texts",        action="store_true")
    parser.add_argument("--lexicon",      action="store_true")
    parser.add_argument("--bibliography", action="store_true")
    parser.add_argument("--research",     action="store_true")
    parser.add_argument("--index",        action="store_true")
    args = parser.parse_args()

    full_build = not any([
        args.texts, args.lexicon, args.bibliography,
        args.research, args.index,
    ])

    print("[catalog] parsing tei/catalog.xml …")
    catalog = CatalogParser(CATALOG_XML)
    catalog.parse()
    print(f"  {len(catalog.texts)} texts · {len(catalog.feasts)} feasts · {len(catalog.authors)} authors")

    if full_build or args.index:
        build_index(catalog)
        build_texts_index(catalog)

    if full_build or args.texts:
        build_texts_index(catalog)
        build_texts(catalog)

    if full_build or args.lexicon:
        build_lexicon()

    if full_build or args.bibliography:
        build_bibliography()

    if full_build or args.research:
        build_research()

    if full_build:
        copy_static()

    print("\n✓ done")


if __name__ == "__main__":
    main()
