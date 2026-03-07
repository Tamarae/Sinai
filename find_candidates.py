#!/usr/bin/env python3
"""
find_candidates.py — Sinai Mravaltavi Digital Edition

Finds Imnaishvili dictionary entries whose lemma or inflected forms appear
in a given TEI text file, and outputs candidate <entry> elements ready
to merge into tei/lexicon.xml.

Usage:
    python find_candidates.py
    python find_candidates.py --text tei/texts/mrav-kharbeba-1.xml \\
                              --out candidates.xml
    python find_candidates.py --help
"""

import argparse
import html
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"tei": "http://www.tei-c.org/ns/1.0"}

# Georgian script Unicode ranges: Mkhedruli (U+10D0–U+10FF) + Asomtavruli (U+10A0–U+10CF)
GEO_RE = re.compile(r"[\u10A0-\u10FF]+")


# ── Text normalisation ────────────────────────────────────────────────────────

def normalize(word: str) -> str:
    """Keep only Georgian letters, NFC-normalised, lowercased (Mkhedruli)."""
    word = unicodedata.normalize("NFC", word)
    # Asomtavruli → Mkhedruli shift: U+10A0–U+10C5 map to U+10D0–U+10F5
    result = []
    for ch in word:
        cp = ord(ch)
        if 0x10A0 <= cp <= 0x10C5:          # Asomtavruli capital
            result.append(chr(cp - 0x10A0 + 0x10D0))
        elif 0x10D0 <= cp <= 0x10FF:        # Mkhedruli
            result.append(ch)
        # else: discard non-Georgian
    return "".join(result)


def tokenize(text: str) -> list[str]:
    """Return all normalised Georgian tokens from a string."""
    tokens = []
    for raw in GEO_RE.findall(text):
        tok = normalize(raw)
        if tok:
            tokens.append(tok)
    return tokens


# ── XML helpers ───────────────────────────────────────────────────────────────

def iter_text(el: ET.Element) -> str:
    """Recursively collect all text content of an element."""
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        parts.append(iter_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts)


# ── Step 1: Extract word tokens from the target TEI text ─────────────────────

def extract_text_words(xml_path: Path) -> set[str]:
    """Return all normalised Georgian word tokens found in a TEI text body."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    words: set[str] = set()

    # Body prose elements
    for tag in ("tei:p", "tei:quote", "tei:head", "tei:trailer", "tei:note"):
        for el in root.findall(f".//{tag}", NS):
            for tok in tokenize(iter_text(el)):
                words.add(tok)

    # Apparatus <lem> (base-text readings)
    for el in root.findall(".//tei:lem", NS):
        for tok in tokenize(iter_text(el)):
            words.add(tok)

    return words


# ── Step 2: Load existing lexicon lemmas (to skip duplicates) ────────────────

def get_existing_lemmas(lexicon_path: Path) -> set[str]:
    if not lexicon_path.exists():
        return set()
    tree = ET.parse(lexicon_path)
    root = tree.getroot()
    lemmas: set[str] = set()
    for orth in root.findall(".//tei:form[@type='lemma']/tei:orth", NS):
        if orth.text:
            lemmas.add(normalize(orth.text.strip()))
    return lemmas


# ── Step 3: Load Imnaishvili entries ─────────────────────────────────────────

def load_imnaishvili(xml_path: Path) -> list[tuple]:
    """
    Returns list of tuples:
        (entry_el, lemma_str, lemma_norm, inflected_norms: set[str])
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    entries = []

    for entry_el in root.findall(".//tei:entry", NS):
        orth_el = entry_el.find("tei:form[@type='lemma']/tei:orth", NS)
        if orth_el is None or not orth_el.text:
            continue
        lemma = orth_el.text.strip()
        lemma_norm = normalize(lemma)

        # Collect inflected forms; strip internal hyphens (e.g. "ანგელოზ-ი" → "ანგელოზი")
        inflected: set[str] = set()
        for form_el in entry_el.findall("tei:form[@type='inflected']/tei:orth", NS):
            if form_el.text:
                raw = form_el.text.strip()
                inflected.add(normalize(raw.replace("-", "")))
                inflected.add(normalize(raw))  # also without strip, in case no dash

        entries.append((entry_el, lemma, lemma_norm, inflected))

    return entries


# ── Step 4: Format a candidate entry ─────────────────────────────────────────

def _esc(s: str) -> str:
    """XML-escape a string for safe embedding in element content."""
    return html.escape(s, quote=False)


def _imnaishvili_id_to_slug(xml_id: str) -> str:
    """
    Convert Imnaishvili xml:id (e.g. "lex-brtsqinvale") to bare slug
    ("brtsqinvale") used in the output xml:id and corresp attribute.
    """
    slug = xml_id.strip()
    if slug.startswith("lex-"):
        slug = slug[4:]
    return slug or "unknown"


def format_candidate(entry_el: ET.Element, lemma: str) -> str:
    """
    Render one Imnaishvili entry as a candidate <entry> block matching
    the exact lexicon.xml schema requested by the editor.
    """
    raw_id = entry_el.get("{http://www.w3.org/XML/1998/namespace}id", "")
    slug   = _imnaishvili_id_to_slug(raw_id)
    entry_id = f"lex-{slug}"

    lines = []
    lines.append(f"        <entry xml:id=\"{entry_id}\" corresp=\"bog:{slug}\">")
    lines.append(f"          <form type=\"lemma\"><orth xml:lang=\"ka\">{_esc(lemma)}</orth></form>")
    lines.append(f"          <gramGrp>")
    lines.append(f"            <pos><!-- noun / verb / adjective / adverb --></pos>")
    lines.append(f"          </gramGrp>")

    # Senses — omit empty ones; drop Imnaishvili page-reference notes
    written = 0
    for sense_el in entry_el.findall("tei:sense", NS):
        def_el   = sense_el.find("tei:def", NS)
        def_text = (def_el.text or "").strip() if def_el is not None else ""
        if not def_text:
            continue
        written += 1
        lines.append(f"          <sense n=\"{written}\">")
        lines.append(f"            <def xml:lang=\"ka\">{_esc(def_text)}</def>")
        lines.append(f"          </sense>")

    lines.append(f"          <!-- ENRICH: add grc, OLiA, source xr -->")
    lines.append(f"        </entry>")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Find Imnaishvili candidates present in a TEI text file."
    )
    ap.add_argument("--text",        default="tei/texts/mrav-kharbeba-1.xml",
                    help="TEI text to scan (default: mrav-kharbeba-1.xml)")
    ap.add_argument("--imnaishvili", default="tei/imnaishvili-extracted.xml",
                    help="Imnaishvili source XML")
    ap.add_argument("--lexicon",     default="tei/lexicon.xml",
                    help="Existing lexicon (entries already here are skipped)")
    ap.add_argument("--out",         default="candidates.xml",
                    help="Output file for candidate entries")
    ap.add_argument("--text-id",     default="mrav-kharbeba-1",
                    help="xml:id of the source text for <xr type='source'>")
    ap.add_argument("--text-label",  default="ხარება I",
                    help="Human-readable label for the source text")
    args = ap.parse_args()

    text_path = Path(args.text)
    imn_path  = Path(args.imnaishvili)
    lex_path  = Path(args.lexicon)
    out_path  = Path(args.out)

    print(f"[1/4] Extracting words from {text_path} …")
    text_words = extract_text_words(text_path)
    print(f"      {len(text_words)} unique Georgian tokens")

    print(f"[2/4] Loading existing lexicon from {lex_path} …")
    existing = get_existing_lemmas(lex_path)
    print(f"      {len(existing)} existing lemmas (will be skipped)")

    print(f"[3/4] Loading Imnaishvili from {imn_path} …")
    imn_entries = load_imnaishvili(imn_path)
    print(f"      {len(imn_entries)} entries loaded")

    print(f"[4/4] Matching …")
    candidates: list[tuple[ET.Element, str]] = []
    skipped_existing  = 0
    skipped_duplicate = 0
    seen_lemmas: set[str] = set()

    for entry_el, lemma, lemma_norm, inflected in imn_entries:
        if lemma_norm in existing:
            skipped_existing += 1
            continue
        # Match: lemma itself, or any inflected form, appears as a text token
        match_set = {lemma_norm} | inflected
        if not (match_set & text_words):
            continue
        # Deduplicate by normalised lemma — keep first match (usually richer entry)
        if lemma_norm in seen_lemmas:
            skipped_duplicate += 1
            continue
        seen_lemmas.add(lemma_norm)
        candidates.append((entry_el, lemma))

    print(f"      {len(candidates)} candidates found")
    print(f"      ({skipped_existing} skipped — already in lexicon, "
          f"{skipped_duplicate} skipped — duplicate lemma)")

    # ── Write output ──────────────────────────────────────────────────────────
    blocks = [format_candidate(el, lemma) for el, lemma in candidates]

    header = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<!-- Candidate lexicon entries — {len(candidates)} entries',
        f'     Text:   {args.text}',
        f'     Source: {args.imnaishvili}',
        '',
        '     Instructions:',
        '       1. For each entry: fill in <pos>.',
        '          Replace the ENRICH comment with: Greek cit type=translation,',
        '          OLiA xr type=lod, and source xr type=source target=#...',
        '       2. Paste approved entries into tei/lexicon.xml <div type="lexicon">.',
        '-->',
        '<candidates xmlns="http://www.tei-c.org/ns/1.0">',
        '',
    ])
    footer = "\n</candidates>\n"

    out_path.write_text(header + "\n\n".join(blocks) + footer, encoding="utf-8")
    print(f"\nWritten → {out_path}")
    print(f"Next: review {out_path}, fill TODOs, then merge into tei/lexicon.xml")


if __name__ == "__main__":
    main()
