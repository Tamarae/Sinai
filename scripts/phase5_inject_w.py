#!/usr/bin/env python3
"""
Phase 5 — Inject <w>, <persName>, <placeName> tags into TEI source files.

Reads:
  data/tokens_matched.tsv        (Phase 2 output)
  tei/texts/*.xml                (source TEI files — modified in place)

Tagging rules by match_tier / confidence:
  imnaishvili/exact  → <w lemmaRef="#xml_id">surface</w>
  imnaishvili/norm   → <w lemmaRef="#xml_id">surface</w>
  master/exact       → <w lemmaRef="#xml_id">surface</w>
  master/norm        → SKIP
  authority/person   → <persName ref="#xml_id">surface</persName>
  authority/place    → <placeName ref="#xml_id">surface</placeName>
  stopword / none    → SKIP

Safety model:
  Safety checks run BEFORE and AFTER injection.
  The file is only rejected if Phase 5 INTRODUCES NEW violations —
  pre-existing issues (from previous pipeline runs) are logged but do not
  block the write.

Run from project root:
  python3 scripts/phase5_inject_w.py [--dry-run] [--text TEXT_ID]

Options:
  --dry-run       Report what would be tagged without modifying files
  --text TEXT_ID  Process only one text (e.g. mrav-kharbeba-1)
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT      = Path(__file__).resolve().parent.parent
DATA      = ROOT / "data"
TEXTS_DIR = ROOT / "tei" / "texts"

TOKENS_TSV = DATA / "tokens_matched.tsv"

NS     = {"tei": "http://www.tei-c.org/ns/1.0",
          "xml": "http://www.w3.org/XML/1998/namespace"}
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

# ── Tiers to tag ──────────────────────────────────────────────────────────────

LEX_TIERS = {
    ("imnaishvili", "exact"),
    ("imnaishvili", "norm"),
    ("master",      "exact"),
}

AUTH_TIER = "authority"

# ── Authority entity → tag ────────────────────────────────────────────────────

def entity_tag(match_source: str) -> str:
    if "place" in match_source:
        return f"{{{TEI_NS}}}placeName"
    return f"{{{TEI_NS}}}persName"


# ── Load tokens ───────────────────────────────────────────────────────────────

def load_tokens(path: Path, text_filter: str | None) -> dict:
    """
    Returns: { text_id: { para_id: [ token_record, ... ] } }
    Only tokens that should be tagged.
    """
    data: dict = defaultdict(lambda: defaultdict(list))

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            text_id    = row["text_id"]
            if text_filter and text_id != text_filter:
                continue

            tier       = row["match_tier"]
            confidence = row["confidence"]
            match_id   = row["match_id"]
            source     = row["match_source"]

            tag_it = False
            if tier == AUTH_TIER and match_id:
                tag_it = True
            elif (tier, confidence) in LEX_TIERS and match_id:
                tag_it = True

            if not tag_it:
                continue

            data[text_id][row["para_id"]].append({
                "token_id":     row["token_id"],
                "surface":      row["surface"],
                "node_idx":     int(row["node_idx"]),
                "is_tail":      row["is_tail"] == "1",
                "char_start":   int(row["char_start"]),
                "char_end":     int(row["char_end"]),
                "initial_char": row.get("initial_char", ""),
                "match_id":     match_id,
                "match_tier":   tier,
                "match_source": source,
            })

    return data


# ── DFS index ─────────────────────────────────────────────────────────────────

def build_dfs_index(para: etree._Element) -> list:
    result = []
    def _walk(el):
        result.append(el)
        for child in el:
            _walk(child)
    _walk(para)
    return result


# ── Wrap a substring ─────────────────────────────────────────────────────────

def wrap_token(text: str, char_start: int, char_end: int,
               tag: str, attrib: dict):
    before  = text[:char_start]
    surface = text[char_start:char_end]
    after   = text[char_end:]
    el = etree.Element(tag)
    for k, v in attrib.items():
        el.set(k, v)
    el.text = surface
    return before, el, after


# ── Safety checks ─────────────────────────────────────────────────────────────

def count_violations(tree: etree._ElementTree) -> dict:
    """Count structural violations. Used for pre/post comparison."""
    ns = {"tei": TEI_NS}
    return {
        "nested_w":  len(tree.xpath("//tei:w//tei:w",   namespaces=ns)),
        "w_in_lem":  len(tree.xpath("//tei:lem//tei:w", namespaces=ns)),
        "w_in_rdg":  len(tree.xpath("//tei:rdg//tei:w", namespaces=ns)),
        "w_in_head": len(tree.xpath("//tei:head//tei:w",namespaces=ns)),
        "w_in_note": len(tree.xpath("//tei:note//tei:w",namespaces=ns)),
    }

def new_violations(before: dict, after: dict) -> list[str]:
    """Return descriptions of violations introduced by Phase 5 (after > before)."""
    msgs = []
    labels = {
        "nested_w":  "Nested <w>",
        "w_in_lem":  "<w> inside <lem>",
        "w_in_rdg":  "<w> inside <rdg>",
        "w_in_head": "<w> inside <head>",
        "w_in_note": "<w> inside <note>",
    }
    for key, label in labels.items():
        delta = after[key] - before[key]
        if delta > 0:
            msgs.append(f"{label}: +{delta} new (was {before[key]}, now {after[key]})")
    return msgs


# ── Process one paragraph ─────────────────────────────────────────────────────

def process_para(para: etree._Element, tokens: list, dry_run: bool) -> int:
    injected = 0

    # Sort descending so later offsets don't shift earlier ones
    tokens_sorted = sorted(
        tokens,
        key=lambda t: (t["node_idx"], t["is_tail"], t["char_start"]),
        reverse=True,
    )

    dfs = build_dfs_index(para)

    for tok in tokens_sorted:
        node_idx   = tok["node_idx"]
        is_tail    = tok["is_tail"]
        char_start = tok["char_start"]
        char_end   = tok["char_end"]
        match_id   = tok["match_id"]
        match_tier = tok["match_tier"]
        match_src  = tok["match_source"]
        surface    = tok["surface"]

        if node_idx >= len(dfs):
            continue

        el = dfs[node_idx]

        # Determine tag and attributes
        if match_tier == AUTH_TIER:
            tag    = entity_tag(match_src)
            attrib = {"ref": f"#{match_id}"}
        else:
            tag    = f"{{{TEI_NS}}}w"
            attrib = {"lemmaRef": f"#{match_id}"}

        # Get the text string
        text = el.tail if is_tail else el.text
        if not text:
            continue

        # Validate / recover offset
        if text[char_start:char_end] != surface:
            idx = text.find(surface, max(0, char_start - 5))
            if idx == -1 or abs(idx - char_start) > 10:
                continue
            char_start = idx
            char_end   = idx + len(surface)

        if dry_run:
            injected += 1
            continue

        before, new_el, after = wrap_token(text, char_start, char_end, tag, attrib)
        parent = el.getparent() if is_tail else el

        if is_tail:
            el.tail     = before or None
            new_el.tail = after  or None
            idx_in_parent = list(parent).index(el)
            parent.insert(idx_in_parent + 1, new_el)

            dfs.insert(node_idx + 1, new_el)
            for other in tokens_sorted:
                if other["node_idx"] > node_idx:
                    other["node_idx"] += 1
                elif (other["node_idx"] == node_idx and
                      other["is_tail"] and
                      other["char_start"] < char_start):
                    other["node_idx"] += 1
        else:
            el.text     = before or None
            new_el.tail = after  or None
            el.insert(0, new_el)

            dfs.insert(node_idx + 1, new_el)
            for other in tokens_sorted:
                if other["node_idx"] > node_idx:
                    other["node_idx"] += 1

        injected += 1

    return injected


# ── Process one file ──────────────────────────────────────────────────────────

def process_file(xml_path: Path, para_tokens: dict, dry_run: bool) -> dict:
    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(xml_path), parser)

    stats = {"injected": 0, "paras": 0,
             "errors": [], "preexisting": [], "skipped_write": False}

    # ── Pre-injection safety snapshot ─────────────────────────────────────────
    pre = count_violations(tree)
    if any(v > 0 for v in pre.values()):
        for key, count in pre.items():
            if count > 0:
                stats["preexisting"].append(
                    f"Pre-existing {key.replace('_',' ')}: {count}"
                )

    # ── Inject ────────────────────────────────────────────────────────────────
    for para_id, tokens in para_tokens.items():
        paras = tree.xpath(f"//tei:p[@xml:id='{para_id}']", namespaces=NS)
        if not paras:
            stats["errors"].append(f"Para not found: {para_id}")
            continue
        n = process_para(paras[0], tokens, dry_run)
        stats["injected"] += n
        stats["paras"]    += 1

    if dry_run or stats["injected"] == 0:
        return stats

    # ── Post-injection safety check — only NEW violations block write ──────────
    post = count_violations(tree)
    introduced = new_violations(pre, post)
    if introduced:
        stats["errors"].extend(introduced)
        stats["skipped_write"] = True
        print(f"  [SAFETY FAIL] {xml_path.name} — Phase 5 introduced violations:")
        for msg in introduced:
            print(f"    {msg}")
        print(f"  File NOT written.")
        return stats

    # ── Write ─────────────────────────────────────────────────────────────────
    tree.write(str(xml_path), encoding="UTF-8",
               xml_declaration=True, pretty_print=False)

    return stats


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Phase 5: inject <w> tags")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--text", default=None)
    args = ap.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n[Phase 5] Injecting tags ({mode})\n")

    if not TOKENS_TSV.exists():
        print(f"[ERROR] {TOKENS_TSV} not found.", file=sys.stderr)
        sys.exit(1)

    print("Loading tokens …")
    all_tokens = load_tokens(TOKENS_TSV, args.text)
    total_to_tag = sum(
        len(toks)
        for pd in all_tokens.values()
        for toks in pd.values()
    )
    print(f"  Texts to process : {len(all_tokens)}")
    print(f"  Tokens to tag    : {total_to_tag}\n")

    total_injected = 0
    total_errors   = []
    total_preexist = []
    skipped        = 0
    file_stats     = {}

    for text_id, para_tokens in sorted(all_tokens.items()):
        xml_path = TEXTS_DIR / f"{text_id}.xml"
        if not xml_path.exists():
            candidates = [c for c in TEXTS_DIR.glob(f"*{text_id}*.xml")
                          if not c.name.endswith(".bak")]
            if not candidates:
                print(f"  [SKIP] {text_id}: XML not found")
                continue
            xml_path = candidates[0]

        stats = process_file(xml_path, para_tokens, args.dry_run)
        file_stats[text_id] = stats
        total_injected += stats["injected"]
        total_errors.extend(stats["errors"])
        total_preexist.extend(stats["preexisting"])

        if stats["skipped_write"]:
            skipped += 1

        status = "!" if (stats["errors"] or stats["skipped_write"]) else "✓"
        pre_note = f"  [{len(stats['preexisting'])} pre-existing]" if stats["preexisting"] else ""
        print(f"  {status} {text_id:<45} "
              f"+{stats['injected']:>4} tags  "
              f"({stats['paras']} paras){pre_note}")

        for msg in stats["errors"]:
            print(f"      [ERROR] {msg}")

    print(f"\n── Summary ──────────────────────────────────────────────────────")
    print(f"  Files processed  : {len(file_stats)}")
    print(f"  Tags injected    : {total_injected}")
    print(f"  Files skipped    : {skipped}  (Phase 5 introduced violations)")
    print(f"  Pre-existing     : {len(total_preexist)}  (not caused by Phase 5)")
    print(f"  New errors       : {len(total_errors)}")
    if args.dry_run:
        print(f"\n  DRY RUN — no files modified.")
    else:
        print(f"\n  Files written successfully.")
    print(f"─────────────────────────────────────────────────────────────────")
    print(f"\n[Phase 5 complete]\n")


if __name__ == "__main__":
    main()
