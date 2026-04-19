#!/usr/bin/env python3
"""
Phase 0b — Expand both Imnaishvili and Rukhadze lookups with Old Georgian
inflected paradigm forms.

For each entry in both lookup JSONs, derives the nominal stem and generates
standard Old Georgian case/number endings as additional lookup keys.

Noun classes handled:
  Class I  — consonant-stem (lemma ends in -ი): strip -ი → append suffixes
  Class II — vowel-ა stem  (lemma ends in -ა): keep stem → append suffixes
  Class III— vowel-ე stem  (lemma ends in -ე): strip -ე → append suffixes
  Class IV — vowel-ო stem  (lemma ends in -ო): keep stem → append suffixes
  Class V  — vowel-უ stem  (lemma ends in -უ): keep stem → append suffixes

Keys already present in lookup are NEVER overwritten.
For Rukhadze expansion, Imnaishvili keys also take priority: if a generated
Rukhadze paradigm form matches an existing Imnaishvili key, it is skipped.

Updates both JSON files in place.
Run AFTER phase0_build_lookups.py, BEFORE phase1_tokenize.py.

Run from project root:
  python3 scripts/phase0b_expand_paradigms.py
"""

import json
import re
from collections import defaultdict
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT     = Path(__file__).resolve().parent.parent
CACHE    = ROOT / "scripts" / "cache"
IMN_JSON = CACHE / "imnaishvili_lookup.json"
MST_JSON = CACHE / "master_lookup.json"

MIN_STEM_LEN = 3

# ── Paradigm suffixes by stem class ──────────────────────────────────────────

PARADIGMS: dict[str, list[str]] = {
    "consonant": [
        "ი",
        "მა", "მან",
        "სა", "ს",
        "ისა", "ის",
        "ითა", "ით",
        "ად",
        "ო",
        "ნი",
        "თა",
        "ჲ",
    ],
    "vowel_a": [
        "სა", "ს",
        "ისა", "ის",
        "ჲ",
        "ათა", "ათ",
        "ად",
        "ნი", "ანი",
        "თა",
        "ო",
        "მა", "მან",
    ],
    "vowel_e": [
        "ისა", "ის",
        "სა", "ს",
        "ითა", "ით",
        "ად",
        "ნი",
        "თა",
        "ო",
        "მა", "მან",
    ],
    "vowel_o": [
        "სა", "ს",
        "ისა", "ის",
        "თა",
        "ად",
        "ნი",
    ],
    "vowel_u": [
        "სა", "ს",
        "ისა", "ის",
        "ითა", "ით",
        "თა",
        "ნი",
        "ად",
    ],
}

# ── Normalisation ─────────────────────────────────────────────────────────────

NORM_TABLE = str.maketrans("ჳჲჱჴ", "ვიეხ")
SUFFIX_RE  = re.compile(r"ჲ(?:ს)?$")

def normalise(s: str) -> str:
    s = s.translate(NORM_TABLE)
    s = SUFFIX_RE.sub("", s)
    return s

# ── Multi-lemma splitting (Rukhadze has "ლემა1, ლემა2" entries) ──────────────

MULTI_RE = re.compile(r"[,;]\s*")

def get_lemmas(record: dict) -> list[str]:
    """Return all lemma variants for a record."""
    lemmas = []
    # Primary lemma
    primary = record.get("lemma", "").strip()
    if primary:
        lemmas.append(primary)
    # Variants list (Rukhadze records have this from parse_ukhadze)
    for v in record.get("variants", []):
        v = v.strip()
        if v and v not in lemmas:
            lemmas.append(v)
    return lemmas

# ── Stem extraction ───────────────────────────────────────────────────────────

def get_stem_and_class(lemma: str) -> tuple[str, str] | None:
    if not lemma:
        return None
    if lemma.endswith("ი"):
        stem = lemma[:-1]
        return (stem, "consonant") if len(stem) >= MIN_STEM_LEN else None
    if lemma.endswith("ა"):
        return (lemma, "vowel_a") if len(lemma) >= MIN_STEM_LEN else None
    if lemma.endswith("ე"):
        stem = lemma[:-1]
        return (stem, "vowel_e") if len(stem) >= MIN_STEM_LEN else None
    if lemma.endswith("ო"):
        return (lemma, "vowel_o") if len(lemma) >= MIN_STEM_LEN else None
    if lemma.endswith("უ"):
        return (lemma, "vowel_u") if len(lemma) >= MIN_STEM_LEN else None
    # Bare consonant stem (no vowel ending — uninflected form)
    return (lemma, "consonant") if len(lemma) >= MIN_STEM_LEN else None

# ── Core expansion function ───────────────────────────────────────────────────

def expand_lookup(lookup: dict,
                  label: str,
                  protected_keys: set | None = None) -> dict[str, int]:
    """
    Expand lookup in place with paradigm forms.
    protected_keys: set of keys that must not be overwritten (used for Rukhadze
                    to preserve Imnaishvili supremacy).
    Returns stats dict.
    """
    if protected_keys is None:
        protected_keys = set()

    # Collect unique entries by xml_id to avoid duplicate processing
    entries_by_id: dict[str, dict] = {}
    for record in lookup.values():
        xml_id = record.get("xml_id", "")
        if xml_id and xml_id not in entries_by_id:
            entries_by_id[xml_id] = record

    stats = defaultdict(int)
    stats["unique_entries"] = len(entries_by_id)

    for xml_id, record in entries_by_id.items():
        lemmas = get_lemmas(record)
        if not lemmas:
            stats["skipped_no_lemma"] += 1
            continue

        for lemma in lemmas:
            result = get_stem_and_class(lemma)
            if result is None:
                continue
            stem, cls = result
            stats[f"class_{cls}"] += 1

            for suffix in PARADIGMS[cls]:
                form   = stem + suffix
                form_n = normalise(form)

                for key in {form, form_n}:
                    if not key:
                        continue
                    if key in lookup:
                        continue          # don't overwrite existing key
                    if key in protected_keys:
                        continue          # Imnaishvili has priority
                    lookup[key] = record
                    stats["new_keys"] += 1

    return stats


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n[Phase 0b] Expanding lookup tables with paradigm forms\n")

    for path in (IMN_JSON, MST_JSON):
        if not path.exists():
            print(f"[ERROR] {path} not found. Run phase0_build_lookups.py first.")
            return

    # ── Expand Imnaishvili ────────────────────────────────────────────────────
    print("Loading Imnaishvili …")
    with open(IMN_JSON, encoding="utf-8") as f:
        imn: dict = json.load(f)

    print(f"  Keys before expansion : {len(imn)}")
    imn_stats = expand_lookup(imn, "Imnaishvili", protected_keys=set())
    print(f"  New keys added        : {imn_stats['new_keys']}")
    print(f"  Total keys now        : {len(imn)}")
    print(f"  Unique entries        : {imn_stats['unique_entries']}")

    print(f"\n  By stem class:")
    for cls in ["consonant", "vowel_a", "vowel_e", "vowel_o", "vowel_u"]:
        n = imn_stats.get(f"class_{cls}", 0)
        if n:
            print(f"    {cls:<15} : {n:>5}")

    with open(IMN_JSON, "w", encoding="utf-8") as f:
        json.dump(imn, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved: {IMN_JSON}")

    # ── Expand Rukhadze (Imnaishvili keys are protected) ─────────────────────
    print("\nLoading Rukhadze …")
    with open(MST_JSON, encoding="utf-8") as f:
        master: dict = json.load(f)

    imn_keys = set(imn.keys())   # all Imnaishvili keys (including new paradigm forms)
    print(f"  Keys before expansion : {len(master)}")
    print(f"  Protected (Imnaishvili) keys : {len(imn_keys)}")

    mst_stats = expand_lookup(master, "Rukhadze", protected_keys=imn_keys)
    print(f"  New keys added        : {mst_stats['new_keys']}")
    print(f"  Total keys now        : {len(master)}")
    print(f"  Unique entries        : {mst_stats['unique_entries']}")

    print(f"\n  By stem class:")
    for cls in ["consonant", "vowel_a", "vowel_e", "vowel_o", "vowel_u"]:
        n = mst_stats.get(f"class_{cls}", 0)
        if n:
            print(f"    {cls:<15} : {n:>5}")

    with open(MST_JSON, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved: {MST_JSON}")

    # ── Combined summary ──────────────────────────────────────────────────────
    print(f"\n── Summary ───────────────────────────────────────────────────────")
    print(f"  Imnaishvili total keys : {len(imn):>7}")
    print(f"  Rukhadze total keys    : {len(master):>7}")
    print(f"  Combined unique keys   : {len(set(imn) | set(master)):>7}")
    print(f"─────────────────────────────────────────────────────────────────")
    print(f"\n[Phase 0b complete] — re-run phase1, phase2, phase3\n")


if __name__ == "__main__":
    main()
