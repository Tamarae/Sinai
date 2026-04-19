#!/usr/bin/env python3
"""
Phase 4 — Auto-create skeleton lexicon.xml entries for matched tokens.

Reads:
  data/tokens_matched.tsv
  tei/lexicon.xml                (existing entries — never overwritten)
  scripts/cache/imnaishvili_lookup.json
  scripts/cache/master_lookup.json

Creates skeleton <entry> elements for tokens where:
  - match_tier in ('imnaishvili', 'master')
  - confidence == 'exact'
  - in_lexicon == '0'
  - match_id not already in lexicon.xml

Does NOT create entries for:
  - stopword / authority / none tiers
  - normalised matches (confidence != 'exact') — less certain
  - lemmas shorter than 2 characters
  - xml:ids already present in lexicon.xml

Entry quality by tier:
  imnaishvili/exact → full skeleton with definition, source="imnaishvili-1975"
  master/exact      → skeleton with definition, source="rukhadze-2008",
                       <note type="certainty">unverified</note>

Also adds <note type="source">Sinai Mravaltavi corpus, 2026</note> to
existing corpus-sourced entries (xml:ids not found in either dictionary).

Run from project root:
  python3 scripts/phase4_update_lexicon.py
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT        = Path(__file__).resolve().parent.parent
DATA        = ROOT / "data"
TEI_DIR     = ROOT / "tei"
CACHE       = ROOT / "scripts" / "cache"

TOKENS_TSV  = DATA / "tokens_matched.tsv"
LEXICON_XML = TEI_DIR / "lexicon.xml"
IMN_JSON    = CACHE / "imnaishvili_lookup.json"
MST_JSON    = CACHE / "master_lookup.json"

NS     = {"tei": "http://www.tei-c.org/ns/1.0",
          "xml": "http://www.w3.org/XML/1998/namespace"}
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

SOURCE_LABELS = {
    "imnaishvili-1975":  "ივ. იმნაიშვილი 1975",
    "imnaishvili":       "ივ. იმნაიშვილი",
    "rukhadze-2008":     "გ. რუხაძე 2008",
    "abuladze1973":      "ილ. აბულაძე 1973",
    "shanidze1971":      "აკ. შანიძე 1971",
    "sarjveladze1995":   "ზ. სარჯველაძე 1995",
    "misc":              "სხვადასხვა",
}

def primary_source(source_str: str) -> str:
    """Return only the primary source id — everything before first + or |."""
    return re.split(r"[+|]", source_str)[0].strip()

def source_label(source_id: str) -> str:
    """Human-readable label for a single source_id."""
    return SOURCE_LABELS.get(source_id, source_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def get_existing_ids(tree: etree._ElementTree) -> set:
    ids = set()
    for entry in tree.xpath("//tei:entry", namespaces=NS):
        xml_id = entry.get(f"{{{XML_NS}}}id", "")
        if xml_id:
            ids.add(xml_id)
    return ids

def get_corpus_sourced_ids(existing_ids: set,
                            imn_ids: set, mst_ids: set) -> set:
    return existing_ids - imn_ids - mst_ids


# ── Build a skeleton <entry> element ──────────────────────────────────────────

def make_entry(xml_id: str, lemma: str, def_ka: str, source: str,
               tier: str, freq: int, text_count: int) -> etree._Element:
    """
    Build a minimal TEI <entry> element.

    Fixes vs. original version:
      - @source and @target use primary_source() — no + or | separators
      - <pos/> is left truly empty (no escaped comment placeholder)
      - <xr type="source"> only added when source is non-empty
      - Parser uses remove_blank_text=True so pretty_print indents correctly
    """
    src = primary_source(source)

    entry = etree.Element(f"{{{TEI_NS}}}entry")
    entry.set(f"{{{XML_NS}}}id", xml_id)
    if src:
        entry.set("source", src)

    # <form type="lemma">
    form = etree.SubElement(entry, f"{{{TEI_NS}}}form")
    form.set("type", "lemma")
    orth = etree.SubElement(form, f"{{{TEI_NS}}}orth")
    orth.set(f"{{{XML_NS}}}lang", "ka")
    orth.text = lemma

    # <gramGrp><pos/> — empty, assign manually in Oxygen
    gram = etree.SubElement(entry, f"{{{TEI_NS}}}gramGrp")
    etree.SubElement(gram, f"{{{TEI_NS}}}pos")

    # <sense n="1"><def>
    if def_ka:
        sense = etree.SubElement(entry, f"{{{TEI_NS}}}sense")
        sense.set("n", "1")
        defn  = etree.SubElement(sense, f"{{{TEI_NS}}}def")
        defn.set(f"{{{XML_NS}}}lang", "ka")
        defn.text = def_ka[:200]

    # <xr type="source"> — only when source is known and non-empty
    if src:
        xr  = etree.SubElement(entry, f"{{{TEI_NS}}}xr")
        xr.set("type", "source")
        ref = etree.SubElement(xr, f"{{{TEI_NS}}}ref")
        ref.set("target", src)
        ref.text = source_label(src)

    # <note type="certainty"> for master-only entries
    if tier == "master":
        note_cert = etree.SubElement(entry, f"{{{TEI_NS}}}note")
        note_cert.set("type", "certainty")
        note_cert.text = "unverified — sourced from Rukhadze 2008 composite dictionary"

    # <note type="corpus">
    note_corp = etree.SubElement(entry, f"{{{TEI_NS}}}note")
    note_corp.set("type", "corpus")
    note_corp.text = f"freq={freq}; texts={text_count}"

    return entry


def make_corpus_note() -> etree._Element:
    note = etree.Element(f"{{{TEI_NS}}}note")
    note.set("type", "source")
    note.text = "Sinai Mravaltavi corpus, 2026"
    return note


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n[Phase 4] Updating lexicon.xml with new skeleton entries\n")

    print("Loading caches …")
    imn    = load_json(IMN_JSON)
    master = load_json(MST_JSON)
    imn_ids = {v["xml_id"] for v in imn.values()}
    mst_ids = {v["xml_id"] for v in master.values()}
    print(f"  Imnaishvili IDs  : {len(imn_ids)}")
    print(f"  Rukhadze IDs     : {len(mst_ids)}")

    print(f"\nParsing {LEXICON_XML} …")
    # remove_blank_text=True is required for pretty_print to produce
    # correct indentation on the entire file including new entries
    parser = etree.XMLParser(remove_blank_text=True)
    tree   = etree.parse(str(LEXICON_XML), parser)
    existing_ids = get_existing_ids(tree)
    print(f"  Existing entries : {len(existing_ids)}")

    corpus_ids = get_corpus_sourced_ids(existing_ids, imn_ids, mst_ids)
    print(f"  Corpus-sourced (neither dict): {len(corpus_ids)}")

    print(f"\nReading {TOKENS_TSV} …")
    if not TOKENS_TSV.exists():
        print(f"[ERROR] {TOKENS_TSV} not found.", file=sys.stderr)
        sys.exit(1)

    candidates:  dict[str, dict] = {}
    token_freq:  dict[str, int]  = defaultdict(int)
    token_texts: dict[str, set]  = defaultdict(set)

    with open(TOKENS_TSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            tier       = row["match_tier"]
            confidence = row["confidence"]
            in_lexicon = row["in_lexicon"]
            xml_id     = row["match_id"]
            lemma      = row["match_lemma"]
            def_ka     = row["match_def_ka"]
            source     = row["match_source"]
            text_id    = row["text_id"]

            if tier not in ("imnaishvili", "master"):
                continue
            if confidence != "exact":
                continue
            if in_lexicon == "1":
                continue
            if not xml_id or not lemma:
                continue
            if len(lemma) < 2:
                continue
            if xml_id in existing_ids:
                continue

            token_freq[xml_id]  += 1
            token_texts[xml_id].add(text_id)

            if xml_id not in candidates:
                candidates[xml_id] = {
                    "xml_id": xml_id,
                    "lemma":  lemma,
                    "def_ka": def_ka,
                    "source": source,
                    "tier":   tier,
                }

    print(f"  New entry candidates : {len(candidates)}")
    imn_cands = {k: v for k, v in candidates.items() if v["tier"] == "imnaishvili"}
    mst_cands = {k: v for k, v in candidates.items() if v["tier"] == "master"}
    print(f"    Imnaishvili/exact  : {len(imn_cands)}")
    print(f"    Rukhadze/exact     : {len(mst_cands)}")

    if not candidates:
        print("\nNothing to add — all matched tokens already in lexicon.xml")
        return

    div = tree.xpath("//tei:div[@type='lexicon']", namespaces=NS)
    if not div:
        print("[ERROR] <div type='lexicon'> not found in lexicon.xml", file=sys.stderr)
        sys.exit(1)
    div = div[0]

    div.append(etree.Comment(
        " ══ Auto-generated entries (Phase 4) — assign <pos> and verify ══ "
    ))

    added_imn = 0
    added_mst = 0

    for rec in (sorted(imn_cands.values(), key=lambda r: r["lemma"]) +
                sorted(mst_cands.values(), key=lambda r: r["lemma"])):
        xml_id = rec["xml_id"]
        div.append(make_entry(
            xml_id     = xml_id,
            lemma      = rec["lemma"],
            def_ka     = rec["def_ka"],
            source     = rec["source"],
            tier       = rec["tier"],
            freq       = token_freq[xml_id],
            text_count = len(token_texts[xml_id]),
        ))
        if rec["tier"] == "imnaishvili":
            added_imn += 1
        else:
            added_mst += 1

    # Corpus source notes on existing corpus-sourced entries
    corpus_noted = 0
    for entry in tree.xpath("//tei:entry", namespaces=NS):
        xml_id = entry.get(f"{{{XML_NS}}}id", "")
        if xml_id not in corpus_ids:
            continue
        if entry.xpath("tei:note[@type='source']", namespaces=NS):
            continue
        entry.append(make_corpus_note())
        corpus_noted += 1

    # Write — pretty_print works correctly because remove_blank_text=True was used
    tree.write(str(LEXICON_XML), encoding="UTF-8",
               xml_declaration=True, pretty_print=True)

    total_added = added_imn + added_mst
    print(f"\n── Results ──────────────────────────────────────────────────────")
    print(f"  New entries added   : {total_added}")
    print(f"    Imnaishvili       : {added_imn}  (high confidence)")
    print(f"    Rukhadze          : {added_mst}  (marked unverified)")
    print(f"  Corpus notes added  : {corpus_noted}")
    print(f"  Total entries now   : {len(existing_ids) + total_added}")

    print(f"\n── Top 20 added (by corpus frequency) ───────────────────────────")
    for r in sorted(candidates.values(),
                    key=lambda r: -token_freq[r["xml_id"]])[:20]:
        fq = token_freq[r["xml_id"]]
        tx = len(token_texts[r["xml_id"]])
        print(f"  {r['lemma']:<30} {r['xml_id']:<35} "
              f"freq={fq:>4}  texts={tx:>2}  [{r['tier']}]")

    print(f"\n  Updated: {LEXICON_XML}")
    print(f"─────────────────────────────────────────────────────────────────")
    print(f"\n[Phase 4 complete] — assign <pos>, then run phase2 → phase3.\n")


if __name__ == "__main__":
    main()
