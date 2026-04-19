#!/usr/bin/env python3
"""
Phase 3 — OOV analysis: frequency and dispersion of unmatched tokens.

Reads:
  data/tokens_matched.tsv              (Phase 2 output)

Outputs:
  data/oov_all.tsv                     all OOV types, sorted by frequency
  data/oov_review.tsv                  high-value candidates for manual review
  data/oov_function_words.tsv          high-freq / high-dispersion (probable function words)

Columns in oov_all.tsv:
  surface | norm | freq | text_count | pct_texts | texts | category

Categories (auto-assigned, for guidance only — verify manually):
  FUNCTION   freq >= 10 AND text_count >= 20   (conjunctions, postpositions, particles)
  VERB       surface matches known verbal morphology patterns
  REVIEW     freq >= 5 AND text_count <= 15    ← your primary manual workload
  RARE       freq < 5                          (hapax and near-hapax)

Run from project root:
  python3 scripts/phase3_oov.py
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT     = Path(__file__).resolve().parent.parent
DATA     = ROOT / "data"

MATCHED_TSV       = DATA / "tokens_matched.tsv"
OOV_ALL_TSV       = DATA / "oov_all.tsv"
OOV_REVIEW_TSV    = DATA / "oov_review.tsv"
OOV_FUNCTION_TSV  = DATA / "oov_function_words.tsv"

# ── Verbal morphology heuristics for Old Georgian ─────────────────────────────
# These prefixes/suffixes strongly suggest inflected verb forms.
# Not a stemmer — just a flag to deprioritise from manual review.

PREVERBS = re.compile(
    r"^(?:მი|მო|გა|გამო|გადა|შე|შემო|ა|აღ|და|ჩა|ჩამო|წა|წამო|ზე|ზემო|"
    r"გარდა|გარე|თა|სრ|სულ)"
)

# Common screeve/person suffixes that appear word-finally in Old Georgian verbs
VERB_SUFFIXES = re.compile(
    r"(?:ებ|ოდ|ავ|ევ|ვარ|ხარ|არს|ვართ|ართ|არიან|ვიყ|იყ|იყო|ეყო|"
    r"დეს|ნეს|ოდეს|ავდ|ევდ|ოდი|ავდი|ევდი|ვიდ|იდ|ედ|ოდით|ავდით|"
    r"ვიდეთ|იდეთ|ედით|ნნ|ნენ|ნეს|ვდეთ|ვდით|ოდეთ)$"
)

# Georgian postpositions and conjunctions (common function words)
KNOWN_FUNCTION = {
    "და", "თუ", "ანუ", "ვითარ", "ვინ", "რამეთუ", "ამისთჳს", "ესე",
    "იგი", "მან", "მას", "მათ", "ჩუენ", "თქუენ", "ვინმე", "რაჲ", "არარაჲ",
    "არარა", "არარ", "არარ", "არარ", "არარ", "არარ", "სადა", "ოდეს",
    "ვიდრე", "ვიდრემდე", "ვითარცა", "ვინაჲთგან", "ეგე", "ამა", "ამის",
    "მისა", "მისგან", "მათგან", "ჩუენგან", "თქუენგან",
}

def auto_category(surface: str, norm: str, freq: int, text_count: int,
                  n_texts: int) -> str:
    """Assign a heuristic category to an OOV token."""
    # Known function words
    if surface in KNOWN_FUNCTION or norm in KNOWN_FUNCTION:
        return "FUNCTION"
    # High frequency + high dispersion → likely function word / grammatical form
    if freq >= 10 and text_count >= max(15, n_texts // 3):
        return "FUNCTION"
    # Verbal morphology signals
    if PREVERBS.match(surface) or VERB_SUFFIXES.search(surface):
        if freq >= 3:
            return "VERB"
    # Primary review candidates: lexically meaningful, appearing in multiple texts
    if freq >= 5 and text_count <= min(15, n_texts // 3):
        return "REVIEW"
    if freq >= 3 and text_count <= 5:
        return "REVIEW"
    # Rare
    return "RARE"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n[Phase 3] OOV analysis\n")

    if not MATCHED_TSV.exists():
        print(f"[ERROR] {MATCHED_TSV} not found. Run phase2_match.py first.",
              file=sys.stderr)
        sys.exit(1)

    # ── Collect OOV tokens ────────────────────────────────────────────────────
    # For each unique (surface, norm) pair: count freq and which texts it appears in

    oov_freq:       dict[str, int]       = defaultdict(int)
    oov_norm:       dict[str, str]       = {}
    oov_texts:      dict[str, set]       = defaultdict(set)

    total_tokens = 0
    total_oov    = 0

    with open(MATCHED_TSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            total_tokens += 1
            if row["match_tier"] != "none":
                continue
            total_oov += 1
            surface = row["surface"]
            norm    = row["norm"]
            text_id = row["text_id"]
            oov_freq[surface]  += 1
            oov_norm[surface]   = norm
            oov_texts[surface].add(text_id)

    n_texts = len({})  # will compute below
    # Collect all text IDs seen
    with open(MATCHED_TSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        all_text_ids = {row["text_id"] for row in reader}
    n_texts = len(all_text_ids)

    print(f"  Total tokens     : {total_tokens:>7}")
    print(f"  OOV tokens       : {total_oov:>7}  ({total_oov/total_tokens*100:.1f}%)")
    print(f"  OOV types        : {len(oov_freq):>7}  (unique surface forms)")
    print(f"  Texts in corpus  : {n_texts:>7}")

    # ── Build sorted records ──────────────────────────────────────────────────

    records = []
    for surface, freq in oov_freq.items():
        norm       = oov_norm[surface]
        texts      = oov_texts[surface]
        text_count = len(texts)
        pct_texts  = text_count / n_texts * 100
        category   = auto_category(surface, norm, freq, text_count, n_texts)
        records.append({
            "surface":    surface,
            "norm":       norm,
            "freq":       freq,
            "text_count": text_count,
            "pct_texts":  f"{pct_texts:.1f}",
            "texts":      "|".join(sorted(texts)),
            "category":   category,
        })

    # Sort: REVIEW first (by freq desc), then VERB, FUNCTION, RARE
    CAT_ORDER = {"REVIEW": 0, "VERB": 1, "FUNCTION": 2, "RARE": 3}
    records.sort(key=lambda r: (CAT_ORDER[r["category"]], -r["freq"]))

    cols = ["surface", "norm", "freq", "text_count", "pct_texts", "texts", "category"]

    # ── Write oov_all.tsv ─────────────────────────────────────────────────────
    with open(OOV_ALL_TSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(records)
    print(f"\n  Wrote {len(records)} OOV types → {OOV_ALL_TSV}")

    # ── Write oov_review.tsv (REVIEW category only) ───────────────────────────
    review = [r for r in records if r["category"] == "REVIEW"]
    with open(OOV_REVIEW_TSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(review)
    print(f"  Wrote {len(review)} REVIEW candidates → {OOV_REVIEW_TSV}")

    # ── Write oov_function_words.tsv ──────────────────────────────────────────
    function = [r for r in records if r["category"] == "FUNCTION"]
    with open(OOV_FUNCTION_TSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(function)
    print(f"  Wrote {len(function)} FUNCTION words → {OOV_FUNCTION_TSV}")

    # ── Category breakdown ────────────────────────────────────────────────────
    cat_counts = defaultdict(lambda: {"types": 0, "tokens": 0})
    for r in records:
        cat = r["category"]
        cat_counts[cat]["types"]  += 1
        cat_counts[cat]["tokens"] += r["freq"]

    print(f"\n── OOV breakdown by category ─────────────────────────────────────")
    print(f"  {'Category':<12} {'Types':>7}  {'Tokens':>8}  {'% of OOV tokens':>16}")
    for cat in ["REVIEW", "VERB", "FUNCTION", "RARE"]:
        d = cat_counts[cat]
        pct = d["tokens"] / total_oov * 100 if total_oov else 0
        print(f"  {cat:<12} {d['types']:>7}  {d['tokens']:>8}  {pct:>15.1f}%")

    # ── Top 50 REVIEW candidates ──────────────────────────────────────────────
    print(f"\n── Top 50 REVIEW candidates (your manual workload) ───────────────")
    print(f"  {'surface':<30} {'freq':>5}  {'texts':>6}  norm")
    print(f"  {'─'*30} {'─'*5}  {'─'*6}  {'─'*20}")
    for r in review[:50]:
        print(f"  {r['surface']:<30} {r['freq']:>5}  {r['text_count']:>6}  {r['norm']}")

    print(f"\n── Top 30 FUNCTION words (likely grammatical, skip manual review) ─")
    print(f"  {'surface':<30} {'freq':>6}  {'%texts':>7}")
    func_by_freq = sorted(function, key=lambda r: -r["freq"])
    for r in func_by_freq[:30]:
        print(f"  {r['surface']:<30} {r['freq']:>6}  {r['pct_texts']:>6}%")

    print(f"\n[Phase 3 complete] — review data/oov_review.tsv for manual lemmatisation\n")


if __name__ == "__main__":
    main()
