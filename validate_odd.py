#!/usr/bin/env python3
"""
Validate all TEI files against the project ODD-generated schema.
Run: python3 validate_odd.py

Requires: lxml
The .rng file must already exist (generate from sinai-odd.xml via Roma or teitoodd).
If no .rng exists yet, the script reports instructions and exits cleanly.
"""
import sys
from pathlib import Path
from lxml import etree

RNG_PATH = Path("tei/sinai-mravaltavi.rng")
TEXT_DIR = Path("tei/texts")
LEXICON  = Path("tei/lexicon.xml")

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace"
}

def validate_against_rng(files: list[Path], rng: etree.RelaxNG) -> dict:
    results = {}
    for f in files:
        try:
            doc = etree.parse(str(f))
            valid = rng.validate(doc)
            errors = [str(e) for e in rng.error_log]
            results[f] = {"valid": valid, "errors": errors}
        except etree.XMLSyntaxError as e:
            results[f] = {"valid": False, "errors": [f"XML syntax error: {e}"]}
    return results

def check_dangling_lemmas(text_files: list[Path], lexicon_path: Path) -> list[str]:
    """Cross-file check: every lemma="#lex-X" must exist in lexicon.xml"""
    lex_tree = etree.parse(str(lexicon_path))
    known_ids = set(
        e.get("{http://www.w3.org/XML/1998/namespace}id")
        for e in lex_tree.findall(".//tei:entry", NS)
        if e.get("{http://www.w3.org/XML/1998/namespace}id")
    )
    issues = []
    for f in text_files:
        try:
            doc = etree.parse(str(f))
            for w in doc.findall(".//tei:w[@lemma]", NS):
                lemma = w.get("lemma", "").lstrip("#")
                if lemma and lemma not in known_ids:
                    issues.append(f"{f.name}: lemma '{lemma}' not in lexicon.xml")
        except etree.XMLSyntaxError:
            pass
    return issues

def main():
    text_files = sorted(TEXT_DIR.glob("*.xml"))
    all_files  = text_files + ([LEXICON] if LEXICON.exists() else [])

    # 1. XML well-formedness check (always runs)
    print("\n[1] XML well-formedness")
    any_broken = False
    for f in all_files:
        try:
            etree.parse(str(f))
            print(f"  OK  {f}")
        except etree.XMLSyntaxError as e:
            print(f"  FAIL {f}: {e}")
            any_broken = True
    if any_broken:
        print("\nFix XML errors before schema validation.")
        sys.exit(1)

    # 2. RelaxNG validation (requires generated .rng)
    print("\n[2] RelaxNG schema validation")
    if not RNG_PATH.exists():
        print(f"  No .rng found at {RNG_PATH}.")
        print("  Generate it from tei/sinai-odd.xml via:")
        print("    https://roma.tei-c.org  (upload sinai-odd.xml, download .rng)")
        print("    or: teitoodd --schema=relaxng tei/sinai-odd.xml tei/sinai-mravaltavi.rng")
    else:
        try:
            rng = etree.RelaxNG(etree.parse(str(RNG_PATH)))
        except etree.RelaxNGParseError as e:
            print(f"  FAIL could not parse {RNG_PATH}: {e}")
            print("  The .rng file is malformed — regenerate it from tei/sinai-odd.xml.")
        else:
            results = validate_against_rng(all_files, rng)
            for f, r in results.items():
                status = "OK  " if r["valid"] else "FAIL"
                print(f"  {status} {f}")
                for err in r["errors"][:5]:  # cap at 5 per file
                    print(f"       {err}")

    # 3. Cross-file lemma check (always runs)
    print("\n[3] Dangling lemma references")
    if LEXICON.exists():
        issues = check_dangling_lemmas(text_files, LEXICON)
        if issues:
            for i in issues:
                print(f"  WARN {i}")
        else:
            print("  OK  all lemma references resolve")
    else:
        print("  SKIP lexicon.xml not found")

    print()

if __name__ == "__main__":
    main()
