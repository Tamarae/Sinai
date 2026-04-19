#!/usr/bin/env python3
"""
Phase 4 cleanup — fixes three issues introduced by phase4_update_lexicon.py:

1. <pos>&lt;!-- assign manually --&gt;</pos>  →  <pos/>  (lxml escaped the comment)
2. xml:id="lex-tsinatsarmetqueli-tsinaistsarmetqueli-tsinarmetqueli"
                              →  xml:id="lex-tsinatsarmetqueli"
3. Duplicate source labels in <xr type="source"> ref text (deduplication)

Run ONCE from project root:
  python3 scripts/phase4_cleanup.py
"""

import re
from pathlib import Path
from lxml import etree

ROOT        = Path(__file__).resolve().parent.parent
LEXICON_XML = ROOT / "tei" / "lexicon.xml"

NS     = {"tei": "http://www.tei-c.org/ns/1.0",
          "xml": "http://www.w3.org/XML/1998/namespace"}
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

PLACEHOLDER = "<!-- assign manually -->"
LONG_ID     = "lex-tsinatsarmetqueli-tsinaistsarmetqueli-tsinarmetqueli"
SHORT_ID    = "lex-tsinatsarmetqueli"


def dedup_label(text: str) -> str:
    """Remove duplicate semicolon-separated parts from source label."""
    parts = [p.strip() for p in text.split(";")]
    seen  = []
    for p in parts:
        if p and p not in seen:
            seen.append(p)
    return "; ".join(seen)


def main():
    print("\n[Phase 4 cleanup]\n")

    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(LEXICON_XML), parser)

    fixed_pos    = 0
    fixed_id     = 0
    fixed_source = 0

    for entry in tree.xpath("//tei:entry", namespaces=NS):
        xml_id = entry.get(f"{{{XML_NS}}}id", "")

        # ── Fix 1: empty <pos> elements with escaped placeholder ─────────────
        for pos in entry.xpath("tei:gramGrp/tei:pos", namespaces=NS):
            if pos.text and PLACEHOLDER in pos.text:
                pos.text = None   # leave empty — editor sees <pos/>
                fixed_pos += 1

        # ── Fix 2: rename long xml:id ─────────────────────────────────────────
        if xml_id == LONG_ID:
            entry.set(f"{{{XML_NS}}}id", SHORT_ID)
            fixed_id += 1
            print(f"  Renamed: {LONG_ID}")
            print(f"       →   {SHORT_ID}")

        # ── Fix 3: deduplicate source labels in <xr type="source"> ───────────
        for xr in entry.xpath("tei:xr[@type='source']", namespaces=NS):
            for ref in xr.xpath("tei:ref", namespaces=NS):
                if ref.text and ";" in ref.text:
                    cleaned = dedup_label(ref.text)
                    if cleaned != ref.text:
                        ref.text  = cleaned
                        fixed_source += 1

        # ── Fix 3b: deduplicate source= attribute on <entry> ─────────────────
        src_attr = entry.get("source", "")
        if src_attr:
            # Remove duplicate pipe-separated segments
            parts = src_attr.split("|")
            seen  = []
            for p in parts:
                if p and p not in seen:
                    seen.append(p)
            cleaned = "|".join(seen)
            if cleaned != src_attr:
                entry.set("source", cleaned)
                fixed_source += 1

    tree.write(
        str(LEXICON_XML),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
    )

    print(f"\n── Fixed ─────────────────────────────────────────────────────────")
    print(f"  <pos> placeholders cleared  : {fixed_pos}")
    print(f"  Long xml:id renamed         : {fixed_id}")
    print(f"  Duplicate source labels     : {fixed_source}")
    print(f"\n  Saved: {LEXICON_XML}")

    # ── Validate ──────────────────────────────────────────────────────────────
    tree2   = etree.parse(str(LEXICON_XML))
    entries = tree2.xpath(
        "//tei:entry",
        namespaces={"tei": "http://www.tei-c.org/ns/1.0"}
    )
    print(f"  Validation: OK — {len(entries)} entries\n")
    print("[Phase 4 cleanup complete]\n")


if __name__ == "__main__":
    main()
