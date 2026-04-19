#!/usr/bin/env python3
"""
Phase 1 — Tokenize TEI XML texts into TSV.

For each Georgian word token in each <p> element:
  - skips tokens already inside <w>
  - skips text inside <lem>, <rdg>, <hi rend="initial">, <head>, <note>, <label>
  - still processes .tail text of skipped elements (tail belongs to parent)
  - records enough positional info for Phase 5 to re-inject <w> tags

Special handling: Asomtavruli initials
  When a <hi rend="initial"> element contains an Asomtavruli letter, the tail
  begins with the rest of the word (e.g. "კუეთუ" after "Ⴓ" U+10B3).
  The column `initial_char` records the Mkhedruli equivalent (e.g. "უ") so that
  Phase 2 can look up "უკუეთუ" instead of the meaningless "კუეთუ".
  Only the FIRST token in such a tail receives a non-empty initial_char.

  Mapping formula: chr(ord(Asomtavruli) - 0x10A0 + 0x10D0)
  This is the standard Unicode Georgian case-folding offset.
  Verified against corpus data: U+10B3 (Ⴓ) → 'უ', correct for "უკუეთუ".

  Archaic Asomtavruli letters U+10C1-U+10C5 (no position in main Mkhedruli block)
  are handled by the ARCHAIC_FALLBACK table.

Output: data/tokens.tsv
Columns:
  token_id    | unique ID: {text_id}_{para_id}_t{k}
  surface     | raw form from XML (without initial)
  norm        | normalised effective form (initial_char + surface, normalised)
  text_id     | xml:id of the TEI document
  para_id     | xml:id of the enclosing <p>
  node_idx    | DFS index of the element in the <p> subtree (for re-injection)
  is_tail     | 0 = element.text, 1 = element.tail
  char_start  | start offset in that text string
  char_end    | end offset in that text string
  initial_char| Mkhedruli equivalent of preceding Asomtavruli initial (or empty)

Run from project root:
  python3 scripts/phase1_tokenize.py
"""

import csv
import re
import sys
from pathlib import Path

from lxml import etree

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT      = Path(__file__).resolve().parent.parent
TEXTS_DIR = ROOT / "tei" / "texts"
OUT_TSV   = ROOT / "data" / "tokens.tsv"

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
TEI = "http://www.tei-c.org/ns/1.0"

# ── Asomtavruli → Mkhedruli conversion ───────────────────────────────────────
#
# Formula: chr(ord(asomtavruli) - 0x10A0 + 0x10D0)
# This is the standard Unicode Georgian case-folding offset (0x30).
# Each Asomtavruli codepoint maps to exactly the corresponding Mkhedruli position:
#   U+10A0 → U+10D0 ა, U+10A8 → U+10D8 ი, U+10B3 → U+10E3 უ, etc.
#
# Archaic Asomtavruli letters U+10C1-U+10C5 have no position in the main
# Mkhedruli block (U+10D0-U+10F0) and use the fallback table.

_ARCHAIC_FALLBACK = {
    '\u10C1': 'ჯ',   # Ⴡ
    '\u10C2': 'ჰ',   # Ⴢ
    '\u10C3': 'ჴ',   # Ⴣ archaic Xan; normaliser maps ჴ→ხ
    '\u10C4': 'ხ',   # Ⴤ treated as ხ in manuscripts
    '\u10C5': 'ჵ',   # Ⴥ archaic Hoe
}

def asomtavruli_to_mkhedruli(char: str) -> str:
    """Convert a single Asomtavruli character to its Mkhedruli equivalent."""
    cp = ord(char)
    if 0x10A0 <= cp <= 0x10C0:
        return chr(cp - 0x10A0 + 0x10D0)
    return _ARCHAIC_FALLBACK.get(char, char)

def extract_initial_char(hi_element: etree._Element) -> str:
    """Return the Mkhedruli letter for the Asomtavruli initial, or ''."""
    text = (hi_element.text or "").strip()
    if not text:
        return ""
    first = text[0]
    if '\u10A0' <= first <= '\u10C5':
        return asomtavruli_to_mkhedruli(first)
    return ""


# ── Elements whose .text content is skipped (tail is still processed) ─────────

SKIP_TEXT_TAGS = {
    f"{{{TEI}}}w",
    f"{{{TEI}}}lem",
    f"{{{TEI}}}rdg",
    f"{{{TEI}}}head",
    f"{{{TEI}}}note",
    f"{{{TEI}}}label",
    f"{{{TEI}}}pb",
    f"{{{TEI}}}lb",
    f"{{{TEI}}}cb",
}

def is_skip_element(el: etree._Element) -> bool:
    tag = el.tag
    if tag in SKIP_TEXT_TAGS:
        return True
    if tag == f"{{{TEI}}}hi" and "initial" in el.get("rend", ""):
        return True
    return False

def is_initial_element(el: etree._Element) -> bool:
    return (el.tag == f"{{{TEI}}}hi" and
            "initial" in el.get("rend", ""))


# ── Georgian Unicode ranges ───────────────────────────────────────────────────

GEO_TOKEN_RE = re.compile(
    r"[\u10A0-\u10C5\u10D0-\u10FF\u2D00-\u2D2F]+"
)

# ── Normalisation ─────────────────────────────────────────────────────────────

NORM_TABLE = str.maketrans("ჳჲჱჴ", "ვიეხ")
SUFFIX_RE  = re.compile(r"ჲ(?:ს)?$")

def normalise(surface: str) -> str:
    s = surface.translate(NORM_TABLE)
    s = SUFFIX_RE.sub("", s)
    return s


# ── DFS traversal ─────────────────────────────────────────────────────────────

def iter_text_nodes(para: etree._Element):
    """
    Yields (node_idx, element, is_tail, text_string, initial_char).
    initial_char is non-empty only for the tail of <hi rend="initial">.
    """
    dfs_idx = [0]

    def _walk(el: etree._Element, skip_text: bool):
        idx = dfs_idx[0]
        dfs_idx[0] += 1

        skip_this = is_skip_element(el)

        if not skip_text and not skip_this:
            text = el.text or ""
            if text:
                yield (idx, el, False, text, "")

        for child in el:
            yield from _walk(child, skip_text or skip_this)

            child_idx = dfs_idx[0] - 1
            tail = child.tail or ""
            if tail and not skip_text and not skip_this:
                initial_char = (extract_initial_char(child)
                                if is_initial_element(child) else "")
                yield (child_idx, child, True, tail, initial_char)

    yield from _walk(para, skip_text=False)


# ── Tokenise a single text node ───────────────────────────────────────────────

def tokenise_text_node(text: str):
    for m in GEO_TOKEN_RE.finditer(text):
        yield m.group(), m.start(), m.end()


# ── Verify mapping at startup ─────────────────────────────────────────────────

def verify_mapping():
    """
    Sanity-check the Asomtavruli→Mkhedruli formula against known codepoints.
    All expected values derived from formula chr(ord(char) - 0x10A0 + 0x10D0).
    Corpus-verified: U+10B3 (Ⴓ) → 'უ' confirmed by "Ⴓკუეთუ" → "უკუეთუ".
    """
    checks = [
        ('\u10A0', 'ა'),   # Ⴀ An  → ა
        ('\u10A3', 'დ'),   # Ⴃ Don → დ
        ('\u10A8', 'ი'),   # Ⴈ In  → ი  (NOT თ — U+10A8 is IN, not TAN)
        ('\u10B3', 'უ'),   # Ⴓ Un  → უ  (corpus-verified)
        ('\u10B5', 'ქ'),   # Ⴕ Phar→ ქ
        ('\u10BA', 'ც'),   # Ⴚ Tzan→ ც  (NOT შ — U+10BA is TZAN, not SHIN)
        ('\u10BE', 'ხ'),   # Ⴞ Xan → ხ
        ('\u10C0', 'ჰ'),   # Ⴠ Hae → ჰ
    ]
    errors = []
    for asm, expected in checks:
        got = asomtavruli_to_mkhedruli(asm)
        if got != expected:
            errors.append(f"  U+{ord(asm):04X} → got '{got}', expected '{expected}'")
    if errors:
        print("[ERROR] Asomtavruli mapping errors:")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print("  Asomtavruli mapping: OK "
              "(formula chr(cp-0x10A0+0x10D0), U+10B3→'უ' corpus-verified)")


# ── Process one TEI file ──────────────────────────────────────────────────────

def process_file(xml_path: Path, writer: csv.writer, counters: dict):
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    text_id = root.get("{http://www.w3.org/XML/1998/namespace}id", xml_path.stem)
    paras   = root.xpath("//tei:p[@xml:id]", namespaces=NS)
    if not paras:
        print(f"  [WARN] {xml_path.name}: no <p xml:id> found")
        return

    file_tokens   = 0
    file_paras    = 0
    initial_fixes = 0

    for para in paras:
        para_id = para.get("{http://www.w3.org/XML/1998/namespace}id", "")
        if not para_id:
            continue

        para_token_k = 0

        for node_idx, el, is_tail, text, initial_char in iter_text_nodes(para):
            first_in_node = True
            for surface, char_start, char_end in tokenise_text_node(text):
                if first_in_node and initial_char:
                    effective_surface = initial_char + surface
                    first_in_node = False
                    initial_fixes += 1
                else:
                    effective_surface = surface
                    first_in_node = False

                norm     = normalise(effective_surface)
                token_id = f"{text_id}_{para_id}_t{para_token_k}"

                writer.writerow([
                    token_id,
                    surface,
                    norm,
                    text_id,
                    para_id,
                    node_idx,
                    1 if is_tail else 0,
                    char_start,
                    char_end,
                    initial_char,
                ])
                para_token_k += 1
                file_tokens  += 1

        if para_token_k > 0:
            file_paras += 1

    counters["total_tokens"]  += file_tokens
    counters["total_paras"]   += file_paras
    counters["initial_fixes"] += initial_fixes
    suffix = f"  [{initial_fixes} initial joins]" if initial_fixes else ""
    print(f"  {xml_path.name}: {file_paras} paragraphs, {file_tokens} tokens{suffix}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    xml_files = sorted(TEXTS_DIR.glob("*.xml"))
    if not xml_files:
        print(f"[ERROR] No XML files found in {TEXTS_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[Phase 1] Tokenising {len(xml_files)} TEI file(s)\n")
    verify_mapping()
    print()

    counters = {"total_tokens": 0, "total_paras": 0, "initial_fixes": 0}

    with open(OUT_TSV, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow([
            "token_id", "surface", "norm",
            "text_id", "para_id",
            "node_idx", "is_tail",
            "char_start", "char_end",
            "initial_char",
        ])
        for xml_path in xml_files:
            process_file(xml_path, writer, counters)

    print(f"\n── Summary ──────────────────────────────────────────────────────")
    print(f"  Files processed  : {len(xml_files)}")
    print(f"  Paragraphs       : {counters['total_paras']}")
    print(f"  Tokens output    : {counters['total_tokens']}")
    print(f"  Initial joins    : {counters['initial_fixes']}  "
          f"(tail tokens rejoined with Asomtavruli initial)")
    print(f"  Output           : {OUT_TSV}")
    print(f"─────────────────────────────────────────────────────────────────")
    print(f"\n[Phase 1 complete] — re-run phase2 and phase3 after this\n")


if __name__ == "__main__":
    main()
