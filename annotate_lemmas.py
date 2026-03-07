#!/usr/bin/env python3
"""
annotate_lemmas.py — Sinai Mravaltavi Digital Edition

Wraps attested lexemes in a TEI text file with <w lemma="#lex-{id}"> elements,
matching against tei/lexicon.xml.

Matching rules:
  - Stem match: strip one terminal vowel (ი/ა/ე/ო/უ) from the lemma;
    text word must start with the resulting stem (min 3 chars).
  - Exact match takes priority over stem match.
  - Longest stem wins when multiple entries could apply.
  - Only tags words ≥ 3 Georgian characters.

Scope rules:
  - Annotates text content inside: <p>, <quote>, <head>, <trailer>
  - Skips entire subtrees:        <app>, <lem>, <rdg>   (apparatus untouched)
  - Skips existing:               <w>                   (idempotent)
  - Processes the TAIL of skip-tag elements (e.g. text after </app>).

Usage:
    python annotate_lemmas.py
    python annotate_lemmas.py --text tei/texts/mrav-kharbeba-1.xml \\
                              --lexicon tei/lexicon.xml \\
                              --out tei/texts/mrav-kharbeba-1.xml
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:
    from lxml import etree
except ImportError:
    sys.exit("lxml is required: pip install lxml")

# ── Constants ─────────────────────────────────────────────────────────────────

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NSMAP  = {None: TEI_NS}          # default namespace map for new elements

GEO_RE = re.compile(r"[\u10A0-\u10FF]+")   # Georgian script token

# Tags whose text content we annotate
ANNOTATE = frozenset(f"{{{TEI_NS}}}{t}" for t in ("p", "quote", "head", "trailer"))
# Tags whose subtree we leave completely untouched (apparatus + existing <w>)
SKIP     = frozenset(f"{{{TEI_NS}}}{t}" for t in ("app", "lem", "rdg", "w"))


# ── Normalisation ─────────────────────────────────────────────────────────────

def normalize(s: str) -> str:
    """NFC + Asomtavruli capitals → Mkhedruli; keep only Georgian script."""
    s = unicodedata.normalize("NFC", s)
    out = []
    for ch in s:
        cp = ord(ch)
        if 0x10A0 <= cp <= 0x10C5:          # Asomtavruli → Mkhedruli
            out.append(chr(cp - 0x10A0 + 0x10D0))
        elif 0x10D0 <= cp <= 0x10FF:        # Mkhedruli
            out.append(ch)
    return "".join(out)


def make_stem(norm: str) -> str:
    """Strip one terminal vowel to produce a matching stem (min 3 chars)."""
    for suf in ("ი", "ა", "ე", "ო", "უ"):
        if norm.endswith(suf) and len(norm) - 1 >= 3:
            return norm[:-1]
    return norm


# ── Lexicon loading ───────────────────────────────────────────────────────────

def load_lexicon(path: Path) -> tuple[dict, dict]:
    """
    Parse tei/lexicon.xml.
    Returns:
      exact : {normalised_lemma → xml_id}   — exact-form lookup
      stems : {stem_prefix     → xml_id}   — prefix-match lookup
                                              (longer stem wins on collision)
    """
    tree = etree.parse(str(path))
    root = tree.getroot()

    exact: dict[str, str] = {}
    stem_pairs: list[tuple[str, str]] = []

    for entry in root.iter(f"{{{TEI_NS}}}entry"):
        xml_id = entry.get(f"{{{XML_NS}}}id") or ""
        if not xml_id:
            continue
        for form in entry.findall(f"{{{TEI_NS}}}form"):
            if form.get("type") == "lemma":
                orth = form.find(f"{{{TEI_NS}}}orth")
                if orth is not None and orth.text:
                    norm = normalize(orth.text.strip())
                    if norm:
                        exact[norm] = xml_id
                        stem_pairs.append((make_stem(norm), xml_id))
                break

    # Build stem index — longer stem overwrites shorter on collision
    stems: dict[str, str] = {}
    for stem, xml_id in sorted(stem_pairs, key=lambda x: len(x[0])):
        stems[stem] = xml_id

    return exact, stems


# ── Matching ──────────────────────────────────────────────────────────────────

def find_match(word_norm: str, exact: dict, stems: dict) -> str | None:
    """Return xml_id for the best-matching entry, or None."""
    if len(word_norm) < 3:
        return None
    if word_norm in exact:
        return exact[word_norm]
    best_id, best_len = None, 2   # require stem > 2 chars
    for stem, xml_id in stems.items():
        if len(stem) > best_len and word_norm.startswith(stem):
            best_id, best_len = xml_id, len(stem)
    return best_id


# ── Text parsing ──────────────────────────────────────────────────────────────

def parse_text(text: str, exact: dict, stems: dict) -> list:
    """
    Tokenise text and annotate.
    Returns list of ('text', str) | ('w', (original_word, xml_id)).
    """
    parts: list = []
    last = 0
    for m in GEO_RE.finditer(text):
        word   = m.group()
        xml_id = find_match(normalize(word), exact, stems)
        if xml_id:
            if m.start() > last:
                parts.append(("text", text[last:m.start()]))
            parts.append(("w", (word, xml_id)))
            last = m.end()
    if last < len(text):
        parts.append(("text", text[last:]))
    return parts


def _build_insertions(parts: list) -> tuple[str, list]:
    """
    Convert parts list into (prefix_text, [[word, xml_id, tail_text], ...]).
    prefix_text  — text before the first match
    Each item    — [word, xml_id, trailing_text_until_next_match_or_end]
    """
    prefix = ""
    items: list = []   # mutable lists so we can update the tail in place
    buf = ""

    for ptype, pval in parts:
        if ptype == "text":
            if not items:
                prefix += pval
            else:
                buf += pval
        else:
            if items:
                items[-1][2] = buf
                buf = ""
            items.append([pval[0], pval[1], ""])

    if items:
        items[-1][2] = buf

    return prefix, items


# ── XML element helpers ───────────────────────────────────────────────────────

def _make_w(word: str, xml_id: str, tail: str) -> etree._Element:
    w = etree.Element(f"{{{TEI_NS}}}w", nsmap=NSMAP)
    w.set("lemma", f"#{xml_id}")
    w.text = word
    w.tail = tail
    return w


def _apply_to_text(el: etree._Element, parts: list) -> int:
    """
    Replace el.text with content from parts; insert <w> children at front.
    Returns number of elements inserted.
    """
    if not any(t == "w" for t, _ in parts):
        return 0
    prefix, items = _build_insertions(parts)
    el.text = prefix
    for i, (word, xml_id, tail) in enumerate(items):
        el.insert(i, _make_w(word, xml_id, tail))
    return len(items)


def _apply_to_tail(prev: etree._Element, parent: etree._Element,
                   insert_pos: int, parts: list) -> int:
    """
    Replace prev.tail with content from parts; insert <w> siblings into parent.
    Returns number of elements inserted.
    """
    if not any(t == "w" for t, _ in parts):
        return 0
    prefix, items = _build_insertions(parts)
    prev.tail = prefix
    for j, (word, xml_id, tail) in enumerate(items):
        parent.insert(insert_pos + j, _make_w(word, xml_id, tail))
    return len(items)


# ── Recursive annotation ──────────────────────────────────────────────────────

def annotate_element(el: etree._Element, exact: dict, stems: dict,
                     in_scope: bool = False) -> int:
    """
    Recursively annotate text content of el.
    in_scope: True when we are already inside an ANNOTATE element.
    Returns total number of <w> elements inserted in this subtree.
    """
    tag = el.tag
    if tag in SKIP:
        return 0

    scope = in_scope or (tag in ANNOTATE)
    total = 0

    # ── Annotate el.text ──────────────────────────────────────────────────────
    pre_inserted = 0
    if scope and el.text:
        parts = parse_text(el.text, exact, stems)
        pre_inserted = _apply_to_text(el, parts)
        total += pre_inserted

    # ── Process children ──────────────────────────────────────────────────────
    # Original children start at index `pre_inserted` (newly added <w> are 0..pre-1)
    i = pre_inserted
    while i < len(el):
        child = el[i]

        # Recurse into non-skip children
        if child.tag not in SKIP:
            total += annotate_element(child, exact, stems, in_scope=scope)

        # Annotate child.tail — even for SKIP children (e.g. text after </app>)
        if scope and child.tail:
            parts = parse_text(child.tail, exact, stems)
            n = _apply_to_tail(child, el, i + 1, parts)
            total += n
            i += n   # jump over newly inserted siblings

        i += 1

    return total


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Annotate TEI text tokens with <w lemma> from the lexicon."
    )
    ap.add_argument("--text",    default="tei/texts/mrav-kharbeba-1.xml")
    ap.add_argument("--lexicon", default="tei/lexicon.xml")
    ap.add_argument("--out",     default=None,
                    help="Output path (default: overwrite --text)")
    args = ap.parse_args()

    text_path = Path(args.text)
    lex_path  = Path(args.lexicon)
    out_path  = Path(args.out) if args.out else text_path

    # ── Load lexicon ──────────────────────────────────────────────────────────
    print(f"[1/3] Lexicon: {lex_path}")
    exact, stems = load_lexicon(lex_path)
    print(f"      {len(exact)} entries")
    for norm, xid in sorted(exact.items()):
        print(f"        {xid}: {norm!r}  (stem: {make_stem(norm)!r})")

    # ── Parse XML ─────────────────────────────────────────────────────────────
    print(f"\n[2/3] Parsing: {text_path}")
    tree = etree.parse(str(text_path))
    root = tree.getroot()

    # ── Annotate ──────────────────────────────────────────────────────────────
    print(f"\n[3/3] Annotating …")
    body = root.find(f".//{{{TEI_NS}}}body")
    if body is None:
        body = root
    total = annotate_element(body, exact, stems)
    print(f"      {total} <w> elements inserted")

    # Print summary by entry
    counts: dict[str, int] = {}
    for w_el in body.iter(f"{{{TEI_NS}}}w"):
        lemma = w_el.get("lemma", "")
        counts[lemma] = counts.get(lemma, 0) + 1
    for lemma, n in sorted(counts.items()):
        print(f"        {lemma}: {n}")

    # ── Write ─────────────────────────────────────────────────────────────────
    print(f"\nWriting → {out_path}")
    tree.write(
        str(out_path),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
    )
    print("Done.")


if __name__ == "__main__":
    main()
