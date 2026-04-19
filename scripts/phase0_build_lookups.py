#!/usr/bin/env python3
"""
Phase 0 — Build lookup tables from both dictionary sources.

Outputs:
  scripts/cache/imnaishvili_lookup.json   keyed by Georgian surface form
  scripts/cache/master_lookup.json        keyed by Georgian surface form
  scripts/cache/lexicon_ids.json          set of xml:ids already in lexicon.xml

Run from project root:
  python3 scripts/phase0_build_lookups.py
"""

import csv
import json
import os
import re
import sys
from pathlib import Path

from lxml import etree

# ── Paths ────────────────────────────────────────────────────────────────────

ROOT        = Path(__file__).resolve().parent.parent
DATA        = ROOT / "data"
TEI_DIR     = ROOT / "tei"
CACHE       = ROOT / "scripts" / "cache"

IMNAISHVILI_XML = DATA / "imnaishvili-extracted.xml"
UKHADZE_TSV     = DATA / "rukhadze_lexicon.tsv"
LEXICON_XML     = TEI_DIR / "lexicon.xml"

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

# ── Georgian → ASCII romanisation for ID generation ─────────────────────────
# Used only when a TSV-only entry has no usable xml_id.

GEO_ROMAN = {
    'ა':'a','ბ':'b','გ':'g','დ':'d','ე':'e','ვ':'v','ზ':'z','თ':'t',
    'ი':'i','კ':'k','ლ':'l','მ':'m','ნ':'n','ო':'o','პ':'p','ჟ':'zh',
    'რ':'r','ს':'s','ტ':'t','უ':'u','ფ':'f','ქ':'q','ღ':'gh','ყ':'y',
    'შ':'sh','ჩ':'ch','ც':'ts','ძ':'dz','წ':'w','ჭ':'j','ხ':'x',
    'ჯ':'J','ჰ':'h',
    # archaic letters
    'ჱ':'e','ჲ':'i','ჳ':'v','ჴ':'x','ჵ':'o','ჶ':'f',
}

def geo_to_id(georgian: str) -> str:
    """Convert Georgian string to a safe xml:id fragment."""
    s = georgian.strip()
    result = ''.join(GEO_ROMAN.get(c, '') for c in s).lower()
    return f"lex-{result}" if result else ""


def dot_to_dash(tsv_id: str) -> str:
    """Convert lex.foo_bar → lex-foo-bar."""
    s = tsv_id.strip()
    if s.startswith("lex."):
        s = "lex-" + s[4:]
    return s.replace(".", "-").replace("_", "-")


# ── Normalisation table (Old Georgian orthographic variants) ─────────────────

NORM_TABLE = str.maketrans(
    "ჳჲჱჴ",   # archaic Unicode Georgian letters
    "ვიეხ",
)

SUFFIX_PATTERNS = [
    re.compile(r"ჲ$"),          # archaic nominative marker
    re.compile(r"ჲს$"),         # archaic genitive
]

def normalise(surface: str) -> str:
    """Apply deterministic Old Georgian normalisation."""
    s = surface.strip()
    s = s.translate(NORM_TABLE)
    for pat in SUFFIX_PATTERNS:
        s = pat.sub("", s)
    return s


def strip_inflection_marker(form: str) -> str:
    """
    Imnaishvili inflected forms use '-' to mark suffix boundary,
    e.g. 'აჩრდილ-ი' → 'აჩრდილ'.
    Also handles 'სიტყუა-ჲ', 'კაც-ი', etc.
    """
    return form.split("-")[0].strip()


# ── Parse current lexicon.xml → set of existing xml:ids ─────────────────────

def load_existing_lexicon_ids(path: Path) -> set:
    if not path.exists():
        print(f"  [WARN] lexicon.xml not found at {path}", file=sys.stderr)
        return set()
    tree = etree.parse(str(path))
    ids = set()
    for entry in tree.xpath("//tei:entry", namespaces=NS):
        xml_id = entry.get("{http://www.w3.org/XML/1998/namespace}id")
        if xml_id:
            ids.add(xml_id)
    return ids


# ── Parse Imnaishvili XML ────────────────────────────────────────────────────

def parse_imnaishvili(path: Path, existing_ids: set) -> dict:
    """
    Returns lookup dict: { surface_form: entry_dict }
    Multiple surface forms per entry (lemma, inflected-stripped, normalised).
    """
    if not path.exists():
        print(f"  [ERROR] {path} not found", file=sys.stderr)
        return {}

    tree = etree.parse(str(path))
    lookup: dict = {}
    entry_count = 0
    key_count   = 0

    for entry in tree.xpath("//tei:entry", namespaces=NS):
        xml_id = entry.get("{http://www.w3.org/XML/1998/namespace}id", "")
        if not xml_id:
            continue

        # Collect all definition texts
        defs = []
        for d in entry.xpath(".//tei:sense/tei:def", namespaces=NS):
            t = (d.text or "").strip()
            if t:
                defs.append(t)

        # Collect example citations
        examples = []
        for q in entry.xpath(".//tei:cit[@type='example']/tei:quote", namespaces=NS):
            t = (q.text or "").strip()
            if t:
                examples.append(t)

        record = {
            "xml_id":      xml_id,
            "source":      "imnaishvili-1975",
            "def_ka":      " / ".join(defs),
            "examples":    examples,
            "in_lexicon":  xml_id in existing_ids,
        }

        # Collect all surface keys for this entry
        surface_keys: set[str] = set()

        for form in entry.xpath(".//tei:form", namespaces=NS):
            form_type = form.get("type", "")
            for orth in form.xpath(".//tei:orth", namespaces=NS):
                raw = (orth.text or "").strip()
                if not raw:
                    continue

                if form_type == "lemma":
                    surface_keys.add(raw)
                    surface_keys.add(normalise(raw))
                    record["lemma"] = raw          # primary lemma

                elif form_type == "inflected":
                    stripped = strip_inflection_marker(raw)
                    surface_keys.add(stripped)
                    surface_keys.add(normalise(stripped))

        # Register all keys
        for key in surface_keys:
            if key:
                if key in lookup and lookup[key]["xml_id"] != xml_id:
                    # Collision: keep first (earlier in file = more specific)
                    pass
                else:
                    lookup[key] = record

        entry_count += 1
        key_count += len(surface_keys)

    print(f"  Imnaishvili: {entry_count} entries → {key_count} surface keys "
          f"→ {len(lookup)} unique keys after dedup")
    return lookup


# ── Parse Ukhadze TSV ────────────────────────────────────────────────────────

MULTI_LEMMA_RE = re.compile(r"[,;]\s*")

def parse_ukhadze(path: Path, imnaishvili_lookup: dict, existing_ids: set) -> dict:
    """
    Returns lookup dict: { surface_form: entry_dict }
    Skips any surface form already covered by Imnaishvili.
    """
    if not path.exists():
        print(f"  [ERROR] {path} not found", file=sys.stderr)
        return {}

    lookup: dict = {}
    entry_count  = 0
    key_count    = 0
    skipped_imn  = 0

    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            raw_id   = (row.get("xml_id")    or "").strip()
            raw_lem  = (row.get("lemma")     or "").strip()
            def_ka   = (row.get("definition") or "").strip()
            source_id = (row.get("source_id") or "").strip()
            source_sig = (row.get("source_siglum") or "").strip()
            cross_raw = (row.get("cross_refs") or "").strip()

            if not raw_lem:
                continue

            xml_id = dot_to_dash(raw_id) if raw_id else geo_to_id(raw_lem)
            cross_refs = [c.strip() for c in cross_raw.split("|") if c.strip()]

            # Split multi-form lemmas: "აბა, ჰაბა" → ["აბა", "ჰაბა"]
            variants = [v.strip() for v in MULTI_LEMMA_RE.split(raw_lem) if v.strip()]
            primary_lemma = variants[0]

            record = {
                "xml_id":           xml_id,
                "lemma":            primary_lemma,
                "variants":         variants,
                "def_ka":           def_ka,
                "source_id":        source_id,
                "source_siglum":    source_sig,
                "cross_refs":       cross_refs,
                "in_imnaishvili":   False,   # updated below
                "in_lexicon":       xml_id in existing_ids,
            }

            surface_keys: set[str] = set()
            for v in variants:
                surface_keys.add(v)
                surface_keys.add(normalise(v))

            for key in surface_keys:
                if not key:
                    continue
                if key in imnaishvili_lookup:
                    record["in_imnaishvili"] = True
                    skipped_imn += 1
                    # Don't overwrite Imnaishvili key — but record cross-source
                    # Store TSV supplement info on the Imnaishvili record
                    imn_rec = imnaishvili_lookup[key]
                    if "tsv_supplements" not in imn_rec:
                        imn_rec["tsv_supplements"] = []
                    imn_rec["tsv_supplements"].append({
                        "source_id":     source_id,
                        "source_siglum": source_sig,
                        "def_ka":        def_ka,
                        "cross_refs":    cross_refs,
                    })
                else:
                    lookup[key] = record

            entry_count += 1
            key_count += len(surface_keys)

    print(f"  Ukhadze TSV: {entry_count} entries → {key_count} surface keys "
          f"→ {len(lookup)} unique keys (Imnaishvili already covers {skipped_imn} keys)")
    return lookup


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    print("\n[Phase 0] Building lookup tables\n")

    print("Loading existing lexicon.xml …")
    existing_ids = load_existing_lexicon_ids(LEXICON_XML)
    print(f"  {len(existing_ids)} existing entries in lexicon.xml")

    print("\nParsing Imnaishvili …")
    imn_lookup = parse_imnaishvili(IMNAISHVILI_XML, existing_ids)

    print("\nParsing Ukhadze TSV …")
    master_lookup = parse_ukhadze(UKHADZE_TSV, imn_lookup, existing_ids)

    # ── Overlap / diagnostic stats ───────────────────────────────────────────
    imn_in_lexicon    = sum(1 for v in imn_lookup.values() if v.get("in_lexicon"))
    imn_not_in_lexicon = len({v["xml_id"] for v in imn_lookup.values()}) - imn_in_lexicon
    master_in_lexicon = sum(1 for v in master_lookup.values() if v.get("in_lexicon"))
    imn_with_tsv_supp = sum(1 for v in imn_lookup.values() if "tsv_supplements" in v)

    print("\n── Diagnostic ──────────────────────────────────────────────────")
    print(f"  Imnaishvili unique surface keys : {len(imn_lookup):>6}")
    print(f"  Master (Ukhadze) unique keys    : {len(master_lookup):>6}")
    print(f"  Imnaishvili entries in lexicon  : {imn_in_lexicon:>6}  (already encoded)")
    print(f"  Imnaishvili entries NOT yet in  : {imn_not_in_lexicon:>6}  (candidates)")
    print(f"  Imnaishvili + TSV supplement    : {imn_with_tsv_supp:>6}  (enriched records)")
    print(f"  Master-only keys (new to add)   : {len(master_lookup):>6}")
    print(f"  Master entries in lexicon       : {master_in_lexicon:>6}")
    print("────────────────────────────────────────────────────────────────")

    # ── Serialise ────────────────────────────────────────────────────────────
    imn_out    = CACHE / "imnaishvili_lookup.json"
    master_out = CACHE / "master_lookup.json"
    ids_out    = CACHE / "lexicon_ids.json"

    with open(imn_out,    "w", encoding="utf-8") as f:
        json.dump(imn_lookup,    f, ensure_ascii=False, indent=2)
    with open(master_out, "w", encoding="utf-8") as f:
        json.dump(master_lookup, f, ensure_ascii=False, indent=2)
    with open(ids_out,    "w", encoding="utf-8") as f:
        json.dump(sorted(existing_ids), f, ensure_ascii=False, indent=2)

    print(f"\nWrote:\n  {imn_out}\n  {master_out}\n  {ids_out}")
    print("\n[Phase 0 complete]\n")


if __name__ == "__main__":
    main()
