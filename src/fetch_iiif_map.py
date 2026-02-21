#!/usr/bin/env python3
"""
Fetch LoC IIIF manifest for N35 (00279386887-ms) and build folio→facs map.

Usage:
    python3 src/fetch_iiif_map.py                # assume folio 1r = sp=1 (offset=0)
    python3 src/fetch_iiif_map.py --offset 3     # folio 1r = sp=4 (3 pre-ms images)
    python3 src/fetch_iiif_map.py --inspect      # print thumb URLs for sp=1..8 to check

offset = number of non-manuscript images at the *start* of the reel (target cards, title pages).
If folio 1r is at sp=K, then --offset is K-1.

Output:
    tei/n35_facs_map.json
"""
import json
import sys
import urllib.request
from pathlib import Path

MANIFEST_URL = "https://www.loc.gov/item/00279386887-ms/manifest.json"
IMAGE_SERVICE_BASE = (
    "https://tile.loc.gov/image-services/iiif/"
    "service:amed:amedmonastery:00279386887-ms"
)
VIEWER_BASE = "https://www.loc.gov/resource/amedmonastery.00279386887-ms/"
TOTAL_IMAGES = 282          # confirmed from LoC item page
OUT_PATH = Path("tei/n35_facs_map.json")


def service_url(sp_1based: int) -> str:
    """IIIF image service root URL for a given 1-based sequence number."""
    return f"{IMAGE_SERVICE_BASE}:{sp_1based:04d}"


def fetch_manifest() -> dict | None:
    req = urllib.request.Request(
        MANIFEST_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; SinaiMravaltaviEdition/1.0) Python/3"
            ),
            "Accept": "application/json, application/ld+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  Manifest fetch failed: {e}")
        return None


def build_folio_pairs(offset: int, total: int = TOTAL_IMAGES) -> list[tuple[str, int]]:
    """
    Return [(folio_label, sp_1based), ...].
    offset: number of pre-manuscript images (0-indexed count before folio 1r).
    Folio 1r starts at sp = offset + 1.
    """
    pairs = []
    folio_n = 1
    sp = offset + 1          # 1-based
    while sp <= total:
        pairs.append((f"{folio_n}r", sp))
        sp += 1
        if sp <= total:
            pairs.append((f"{folio_n}v", sp))
            sp += 1
        folio_n += 1
    return pairs


def inspect_mode():
    """Print thumb URLs for sp=1..8 so the user can check for target cards."""
    print("Thumb URLs for manual inspection (open in browser):\n")
    for sp in range(1, 9):
        thumb = f"{service_url(sp)}/full/pct:12.5/0/default.jpg"
        viewer = f"{VIEWER_BASE}?sp={sp}"
        print(f"  sp={sp:3d}  viewer: {viewer}")
        print(f"          thumb:  {thumb}\n")


def main():
    args = sys.argv[1:]

    if "--inspect" in args:
        inspect_mode()
        return

    offset = 0
    if "--offset" in args:
        idx = args.index("--offset")
        try:
            offset = int(args[idx + 1])
        except (IndexError, ValueError):
            print("ERROR: --offset requires an integer argument")
            sys.exit(1)

    print(f"Building folio map: offset={offset} → folio 1r = sp={offset + 1}")
    print(f"Trying to fetch manifest from {MANIFEST_URL} ...")
    manifest = fetch_manifest()

    # Extract canvas service URLs from manifest if available
    canvas_services: dict[int, str] = {}   # sp_1based → service @id
    if manifest:
        sequences = manifest.get("sequences", [])
        canvases = sequences[0].get("canvases", []) if sequences else []
        print(f"  Manifest OK — {len(canvases)} canvases")
        for i, canvas in enumerate(canvases):
            sp = i + 1
            try:
                svc = canvas["images"][0]["resource"]["service"]["@id"]
                canvas_services[sp] = svc
            except (KeyError, IndexError):
                pass
    else:
        print("  Using URL-pattern fallback (manifest unavailable)")

    # Build the map
    pairs = build_folio_pairs(offset=offset)
    folio_map: dict[str, dict] = {}

    for folio_label, sp in pairs:
        svc = canvas_services.get(sp) or service_url(sp)
        folio_map[folio_label] = {
            "facs": svc,
            "sp": sp,
            "tile_url": f"{svc}/full/full/0/default.jpg",
            "thumb_url": f"{svc}/full/pct:12.5/0/default.jpg",
            "viewer_url": f"{VIEWER_BASE}?sp={sp}",
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(folio_map, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {len(folio_map)} entries to {OUT_PATH}")
    print("\nFirst 8 folios:")
    for label in list(folio_map)[:8]:
        e = folio_map[label]
        print(f"  {label:5s} → sp={e['sp']:3d}  {e['viewer_url']}")

    print("\nTo verify alignment, open the viewer_url values above in your browser.")
    print("If 1r is at sp=K, re-run with:  python3 src/fetch_iiif_map.py --offset $((K-1))")


if __name__ == "__main__":
    main()