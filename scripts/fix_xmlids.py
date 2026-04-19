#!/usr/bin/env python3
"""
scripts/fix_xmlids.py — Align TEI file xml:ids with catalog.xml

For each <event> in catalog.xml:
  1. Reads the <note type="file"> to find the actual XML file
  2. Compares the file's root xml:id against the catalog event xml:id
  3. If they differ:
     a. Updates the root <TEI xml:id="..."> attribute
     b. Updates any <p xml:id="OLD_PREFIX-..."> to use the new prefix
     c. Writes the file back

After running this script, re-run the full pipeline:
  python3 scripts/phase0_build_lookups.py
  python3 scripts/phase0b_expand_paradigms.py
  python3 scripts/phase1_tokenize.py
  python3 scripts/phase2_match.py
  python3 scripts/phase3_oov.py
  python3 scripts/phase5_inject_w.py

Run from project root:
  python3 scripts/fix_xmlids.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

from lxml import etree

ROOT       = Path(__file__).resolve().parent.parent
CATALOG    = ROOT / "tei" / "catalog.xml"
TEXTS_DIR  = ROOT / "tei" / "texts"

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def parse_catalog(path: Path) -> dict[str, Path]:
    """
    Returns { catalog_event_id : absolute_Path_to_xml_file }
    by reading every <event xml:id="..."> and its <note type="file"> child.
    """
    tree   = etree.parse(str(path))
    result = {}

    for event in tree.xpath("//tei:event", namespaces=NS):
        event_id = event.get(XML_ID, "")
        if not event_id:
            continue
        note = event.xpath("tei:note[@type='file']", namespaces=NS)
        if not note:
            continue
        file_rel = (note[0].text or "").strip()
        if not file_rel:
            continue
        abs_path = ROOT / file_rel
        result[event_id] = abs_path

    return result


def fix_file(catalog_id: str, xml_path: Path, dry_run: bool) -> bool:
    """
    Read xml_path, compare root xml:id to catalog_id.
    If different, rename root xml:id and all paragraph xml:ids
    that start with the old prefix.
    Returns True if changes were made (or would be made in dry-run).
    """
    if not xml_path.exists():
        print(f"  [MISSING] {xml_path.name}")
        return False

    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(xml_path), parser)
    root   = tree.getroot()

    old_id = root.get(XML_ID, "")
    if old_id == catalog_id:
        return False   # already correct

    print(f"  FIX  {xml_path.name}")
    print(f"       xml:id  '{old_id}'  →  '{catalog_id}'")

    if dry_run:
        # Count paragraph ids that would be renamed
        paras_to_fix = []
        for p in root.iter(f"{{{NS['tei']}}}p"):
            p_id = p.get(XML_ID, "")
            if p_id.startswith(old_id + "-") or p_id.startswith(old_id + "_"):
                paras_to_fix.append(p_id)
        if paras_to_fix:
            print(f"       {len(paras_to_fix)} paragraph id(s) would be renamed")
        return True

    # ── Apply fixes ───────────────────────────────────────────────────────────
    # 1. Root xml:id
    root.set(XML_ID, catalog_id)

    # 2. Paragraph xml:ids with old prefix
    para_count = 0
    for p in root.iter(f"{{{NS['tei']}}}p"):
        p_id = p.get(XML_ID, "")
        if p_id.startswith(old_id + "-"):
            new_p_id = catalog_id + p_id[len(old_id):]
            p.set(XML_ID, new_p_id)
            para_count += 1
        elif p_id.startswith(old_id + "_"):
            new_p_id = catalog_id + p_id[len(old_id):]
            p.set(XML_ID, new_p_id)
            para_count += 1

    if para_count:
        print(f"       {para_count} paragraph id(s) renamed")

    # 3. Write back
    tree.write(str(xml_path), encoding="UTF-8",
               xml_declaration=True, pretty_print=False)
    return True


def main():
    ap = argparse.ArgumentParser(description="Fix TEI xml:ids to match catalog")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would change without modifying files")
    args = ap.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n[fix_xmlids] Aligning TEI xml:ids with catalog ({mode})\n")

    if not CATALOG.exists():
        print(f"[ERROR] {CATALOG} not found", file=sys.stderr)
        sys.exit(1)

    catalog_map = parse_catalog(CATALOG)
    print(f"  Catalog events with file paths: {len(catalog_map)}\n")

    fixed     = 0
    already_ok = 0
    missing   = 0

    for catalog_id, xml_path in sorted(catalog_map.items()):
        if not xml_path.exists():
            print(f"  [MISSING] {xml_path.name}  (catalog id: {catalog_id})")
            missing += 1
            continue

        changed = fix_file(catalog_id, xml_path, args.dry_run)
        if changed:
            fixed += 1
        else:
            already_ok += 1

    print(f"\n── Summary ──────────────────────────────────────────────────────")
    print(f"  Already correct : {already_ok}")
    print(f"  Fixed           : {fixed}")
    print(f"  Missing files   : {missing}")
    if args.dry_run:
        print(f"\n  DRY RUN — no files modified.")
        print(f"  Re-run without --dry-run to apply.")
    else:
        print(f"\n  Done. Now re-run the pipeline:")
        print(f"    python3 scripts/phase1_tokenize.py")
        print(f"    python3 scripts/phase2_match.py")
        print(f"    python3 scripts/phase3_oov.py")
        print(f"    python3 scripts/phase5_inject_w.py --dry-run")
        print(f"    python3 scripts/phase5_inject_w.py")
    print(f"─────────────────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
