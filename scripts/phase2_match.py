#!/usr/bin/env python3
"""
Phase 2 — Match tokens against authority list, then dictionaries.

Reads:
  data/tokens.tsv                      (Phase 1 output)
  data/stopwords.txt                   (conjunctions, particles — skip tagging)
  tei/authority.xml                    (persons, places — encode as persName/placeName)
  scripts/cache/imnaishvili_lookup.json
  scripts/cache/master_lookup.json
  scripts/cache/lexicon_ids.json

Outputs:
  data/tokens_matched.tsv
  data/authority_candidates.tsv        new names detected, not yet in authority.xml

Match tiers (cascade order):
  stopword   — surface or norm in stopwords.txt → skip entirely
  authority  — surface or norm matches <persName/placeName type="variant"> → persName tag
  1. imnaishvili/exact
  2. master/exact
  3. imnaishvili/norm
  4. master/norm
  5. none (OOV)

Run from project root:
  python3 scripts/phase2_match.py
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT      = Path(__file__).resolve().parent.parent
DATA      = ROOT / "data"
TEI_DIR   = ROOT / "tei"
CACHE     = ROOT / "scripts" / "cache"

TOKENS_IN        = DATA / "tokens.tsv"
TOKENS_OUT       = DATA / "tokens_matched.tsv"
AUTH_CAND_OUT    = DATA / "authority_candidates.tsv"
STOPWORDS_FILE   = DATA / "stopwords.txt"
AUTHORITY_XML    = TEI_DIR / "authority.xml"

IMN_JSON     = CACHE / "imnaishvili_lookup.json"
MASTER_JSON  = CACHE / "master_lookup.json"
LEX_IDS_JSON = CACHE / "lexicon_ids.json"

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

# ── Normalisation ─────────────────────────────────────────────────────────────

NORM_TABLE = str.maketrans("ჳჲჱჴ", "ვიეხ")
SUFFIX_RE  = re.compile(r"ჲ(?:ს)?$")

def normalise(s: str) -> str:
    s = s.translate(NORM_TABLE)
    s = SUFFIX_RE.sub("", s)
    return s

# ── Load helpers ──────────────────────────────────────────────────────────────

def load_json(path: Path) -> object:
    if not path.exists():
        print(f"[ERROR] {path} not found. Run phase0_build_lookups.py first.",
              file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_stopwords(path: Path) -> set:
    if not path.exists():
        print(f"  [INFO] No stopwords file at {path} — none applied")
        return set()
    words = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        w = line.strip()
        if w and not w.startswith("#"):
            words.add(w)
            words.add(normalise(w))
    return words


def load_authority(path: Path) -> dict:
    """
    Parse tei/authority.xml.

    Returns:
      lookup: { surface_form: { "xml_id": "pers-X", "type": "martyr",
                                "main_ka": "სტეფანე...", "entity": "person"|"place" } }
      known_ids: set of xml:ids already in authority.xml
    """
    lookup: dict   = {}
    known_ids: set = set()

    if not path.exists():
        print(f"  [INFO] No authority.xml at {path} — authority tier disabled")
        return lookup, known_ids

    tree = etree.parse(str(path))

    # ── Persons ───────────────────────────────────────────────────────────────
    for person in tree.xpath("//tei:person", namespaces=NS):
        xml_id   = person.get("{http://www.w3.org/XML/1998/namespace}id", "")
        pers_type = person.get("type", "")
        if not xml_id:
            continue
        known_ids.add(xml_id)

        # Main name in Georgian
        main_ka = ""
        for pn in person.xpath("tei:persName[@type='main'][@xml:lang='ka']",
                               namespaces=NS):
            main_ka = (pn.text or "").strip()
            break

        record = {
            "xml_id":   xml_id,
            "type":     pers_type,
            "main_ka":  main_ka,
            "entity":   "person",
        }

        # Index all variant surface forms
        for pn in person.xpath("tei:persName[@type='variant']", namespaces=NS):
            surface = (pn.text or "").strip()
            if surface:
                lookup[surface]           = record
                lookup[normalise(surface)] = record

    # ── Places ────────────────────────────────────────────────────────────────
    for place in tree.xpath("//tei:place", namespaces=NS):
        xml_id     = place.get("{http://www.w3.org/XML/1998/namespace}id", "")
        place_type = place.get("type", "")
        if not xml_id:
            continue
        known_ids.add(xml_id)

        main_ka = ""
        for pn in place.xpath("tei:placeName[@type='main'][@xml:lang='ka']",
                               namespaces=NS):
            main_ka = (pn.text or "").strip()
            break

        record = {
            "xml_id":   xml_id,
            "type":     place_type,
            "main_ka":  main_ka,
            "entity":   "place",
        }

        for pn in place.xpath("tei:placeName[@type='variant']", namespaces=NS):
            surface = (pn.text or "").strip()
            if surface:
                lookup[surface]            = record
                lookup[normalise(surface)] = record

    return lookup, known_ids


# ── Match one token ───────────────────────────────────────────────────────────

def match_token(surface: str, norm: str,
                stopwords: set,
                auth_lookup: dict,
                imn: dict, master: dict,
                existing_ids: set) -> dict:

    # Stopword
    if surface in stopwords or norm in stopwords:
        return _stopword(surface)

    # Authority (persons / places)
    if surface in auth_lookup:
        return _auth_hit(auth_lookup[surface])
    if norm and norm != surface and norm in auth_lookup:
        return _auth_hit(auth_lookup[norm])

    # Tier 1: Imnaishvili exact
    if surface in imn:
        return _lex_hit(imn[surface], "imnaishvili", "exact", existing_ids)

    # Tier 2: Rukhadze exact
    if surface in master:
        return _lex_hit(master[surface], "master", "exact", existing_ids)

    # Tier 3: Imnaishvili normalised
    if norm and norm != surface and norm in imn:
        return _lex_hit(imn[norm], "imnaishvili", "norm", existing_ids)

    # Tier 4: Rukhadze normalised
    if norm and norm != surface and norm in master:
        return _lex_hit(master[norm], "master", "norm", existing_ids)

    # OOV
    return {
        "match_tier":   "none",
        "match_id":     "",
        "match_lemma":  "",
        "match_def_ka": "",
        "match_source": "",
        "confidence":   "none",
        "in_lexicon":   "0",
    }


def _stopword(surface: str) -> dict:
    return {
        "match_tier":   "stopword",
        "match_id":     "",
        "match_lemma":  surface,
        "match_def_ka": "",
        "match_source": "stopwords",
        "confidence":   "stopword",
        "in_lexicon":   "0",
    }


def _auth_hit(rec: dict) -> dict:
    return {
        "match_tier":   "authority",
        "match_id":     rec["xml_id"],
        "match_lemma":  rec["main_ka"],
        "match_def_ka": rec["type"],
        "match_source": f"authority/{rec['entity']}",
        "confidence":   "exact",
        "in_lexicon":   "0",
    }


def _lex_hit(rec: dict, tier: str, confidence: str, existing_ids: set) -> dict:
    xml_id = rec.get("xml_id", "")
    source = rec.get("source", rec.get("source_id", ""))
    if "tsv_supplements" in rec:
        supp = "|".join(s.get("source_id", "")
                        for s in rec["tsv_supplements"] if s.get("source_id"))
        if supp:
            source = f"{source}+{supp}"
    return {
        "match_tier":   tier,
        "match_id":     xml_id,
        "match_lemma":  rec.get("lemma", ""),
        "match_def_ka": rec.get("def_ka", "")[:120],
        "match_source": source,
        "confidence":   confidence,
        "in_lexicon":   "1" if xml_id in existing_ids else "0",
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n[Phase 2] Matching tokens against authority list and dictionaries\n")

    print("Loading caches …")
    imn         = load_json(IMN_JSON)
    master      = load_json(MASTER_JSON)
    lex_ids     = set(load_json(LEX_IDS_JSON))
    stopwords   = load_stopwords(STOPWORDS_FILE)
    auth_lookup, auth_ids = load_authority(AUTHORITY_XML)

    print(f"  Imnaishvili keys : {len(imn):>6}")
    print(f"  Rukhadze keys    : {len(master):>6}")
    print(f"  Lexicon entries  : {len(lex_ids):>6}")
    print(f"  Stopwords        : {len(stopwords):>6}  (surface + normalised)")
    print(f"  Authority forms  : {len(auth_lookup):>6}  "
          f"({len(auth_ids)} entities in authority.xml)")

    if not TOKENS_IN.exists():
        print(f"[ERROR] {TOKENS_IN} not found.", file=sys.stderr)
        sys.exit(1)

    tier_counts  = defaultdict(int)
    conf_counts  = defaultdict(int)
    in_lex_count = 0
    total        = 0
    text_stats   = defaultdict(lambda: {"total": 0, "matched": 0, "in_lex": 0})

    # Track high-frequency OOV for authority candidate suggestions
    oov_freq:  dict[str, int] = defaultdict(int)
    oov_texts: dict[str, set] = defaultdict(set)

    out_cols = [
        "token_id", "surface", "norm",
        "text_id", "para_id",
        "node_idx", "is_tail", "char_start", "char_end",
        "initial_char",
        "match_tier", "match_id", "match_lemma",
        "match_def_ka", "match_source", "confidence", "in_lexicon",
    ]

    with open(TOKENS_IN,  encoding="utf-8", newline="") as fin, \
         open(TOKENS_OUT, "w", encoding="utf-8", newline="") as fout:

        reader = csv.DictReader(fin, delimiter="\t")
        writer = csv.DictWriter(fout, fieldnames=out_cols,
                                delimiter="\t", extrasaction="ignore")
        writer.writeheader()

        for row in reader:
            surface = row["surface"]
            norm    = row["norm"]
            text_id = row["text_id"]

            m = match_token(surface, norm, stopwords, auth_lookup,
                            imn, master, lex_ids)
            row.update(m)
            writer.writerow(row)

            total += 1
            tier   = m["match_tier"]
            tier_counts[tier] += 1
            conf_counts[m["confidence"]] += 1

            ts = text_stats[text_id]
            ts["total"] += 1
            if tier not in ("none", "stopword"):
                ts["matched"] += 1
            if m["in_lexicon"] == "1":
                ts["in_lex"] += 1
                in_lex_count += 1

            if tier == "none":
                oov_freq[surface]  += 1
                oov_texts[surface].add(text_id)

    # ── Authority candidate detection ─────────────────────────────────────────
    # Heuristic: capitalised-looking tokens (starts with specific letters common
    # in Georgian proper names) that appear >= 3 times in <= 10 texts.
    # Old Georgian has no capitalisation — we rely on frequency + dispersion only.
    # Exclude tokens already matched or stopworded.

    KNOWN_PROPER_STEMS = {
        "პეტრ", "პავლ", "იოან", "იაკობ", "მარიამ", "ბასილ", "ეფრემ",
        "ათანას", "კირილ", "მოსე", "დავით", "სოლომონ", "ისაი", "იერემი",
        "ეზეკიელ", "ანტიოქ", "იოსებ", "აბრაამ", "იაკობ", "ნინო",
        "გიორგ", "თეოდორ", "მიხეილ", "გაბრიელ", "მიქაელ", "სარა",
        "სიმეონ", "ზაქარი", "ელისაბედ", "ლაზარ", "ბართლომ", "ანდრი",
    }

    candidates = []
    for surface, freq in oov_freq.items():
        if freq < 3:
            continue
        texts = oov_texts[surface]
        if len(texts) > 15:
            continue   # too dispersed — probably a function word
        norm_s = normalise(surface)
        # Check if surface starts with a known proper name stem
        is_proper = any(norm_s.startswith(stem) or surface.startswith(stem)
                        for stem in KNOWN_PROPER_STEMS)
        if is_proper:
            candidates.append({
                "surface":    surface,
                "norm":       norm_s,
                "freq":       freq,
                "text_count": len(texts),
                "texts":      "|".join(sorted(texts)),
                "suggested_type": "unknown — assign manually",
            })

    candidates.sort(key=lambda r: -r["freq"])

    cand_cols = ["surface", "norm", "freq", "text_count", "texts", "suggested_type"]
    with open(AUTH_CAND_OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cand_cols, delimiter="\t")
        w.writeheader()
        w.writerows(candidates)

    # ── Report ────────────────────────────────────────────────────────────────

    matched    = tier_counts["imnaishvili"] + tier_counts["master"]
    stopworded = tier_counts["stopword"]
    authority  = tier_counts["authority"]
    oov        = tier_counts["none"]

    print(f"\n── Overall ──────────────────────────────────────────────────────")
    print(f"  Total tokens            : {total:>7}")
    print(f"  Stopworded (skipped)    : {stopworded:>7}  ({stopworded/total*100:.1f}%)")
    print(f"  Authority (pers/place)  : {authority:>7}  ({authority/total*100:.1f}%)")
    print(f"  Matched (dictionaries)  : {matched:>7}  ({matched/total*100:.1f}%)")
    print(f"  OOV (unmatched)         : {oov:>7}  ({oov/total*100:.1f}%)")
    print(f"  Covered by lexicon.xml  : {in_lex_count:>7}  ({in_lex_count/total*100:.1f}%)")

    print(f"\n── By tier ──────────────────────────────────────────────────────")
    for tier in ["imnaishvili", "master", "authority", "stopword", "none"]:
        n = tier_counts[tier]
        print(f"  {tier:<16} : {n:>7}  ({n/total*100:.1f}%)")

    print(f"\n── Authority matches by entity type ─────────────────────────────")
    # Count by match_id prefix would require re-reading; summarise by candidate count
    print(f"  Entities in authority.xml : {len(auth_ids)}")
    print(f"  Authority surface keys    : {len(auth_lookup)}")
    print(f"  Authority candidate file  : {AUTH_CAND_OUT}")
    if candidates:
        print(f"  New name candidates       : {len(candidates)}  "
              f"(freq≥3, dispersion≤15 texts)")
        print(f"\n  Top candidates for authority.xml:")
        for r in candidates[:20]:
            print(f"    {r['surface']:<30} freq={r['freq']:>4}  "
                  f"texts={r['text_count']:>2}  {r['norm']}")

    print(f"\n── Per-text coverage ────────────────────────────────────────────")
    for tid in sorted(text_stats):
        ts  = text_stats[tid]
        t   = ts["total"]
        m   = ts["matched"]
        il  = ts["in_lex"]
        pct_m  = m / t * 100 if t else 0
        pct_il = il / t * 100 if t else 0
        print(f"  {tid:<45} {m:>5}/{t:<5} ({pct_m:4.1f}%)  "
              f"in_lex: {il:>5} ({pct_il:4.1f}%)")

    print(f"\n  Output: {TOKENS_OUT}")
    print(f"─────────────────────────────────────────────────────────────────")
    print(f"\n[Phase 2 complete] — next: phase3_oov.py\n")


if __name__ == "__main__":
    main()
