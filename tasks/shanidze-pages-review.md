# Shanidze 1959 edition — page ranges per catalog text (for review)

**Source:** the edition's own Table of Contents in `shanidze.pdf`, printed
pp. 05–09 (liturgical order, PDF pp. 4–8) cross-checked against the
alphabetical-by-author TOC (printed pp. 010–011, PDF pp. 9–10) and the Russian
*Содержание* (PDF pp. 11–12). Start pages are from the TOC; **end page = (next
reading's start − 1)**.

**Not yet applied** to `tei/catalog.xml` — this is for your approval first.

## Proposed catalog encoding (parallel to the existing `<locus>`)

```xml
<msDesc>
  <msIdentifier><idno type="witness">N35</idno></msIdentifier>
  <locus from="31r" to="41v">ff. 31r–41v</locus>
</msDesc>
<bibl type="edition" corresp="#shanidze1959">
  <citedRange unit="page" from="24" to="30"/>
</bibl>
```

## Mapping table

| # | catalog event | Shanidze № | pages | cross-check / note |
|--:|---------------|:----------:|:-----:|--------------------|
| 1 | mrav-kharbeba-1 | 1 | 3–7 | |
| 2 | mrav-kharbeba-2 | 2 | 8–15 | |
| 3 | mrav-kharbeba-3 | 3 | 16–23 | |
| 4 | mrav-antipater | 4 | 24–30 | ✓ existing pb 24–30 |
| 5 | mrav-shoba-athanasi | 5 | 31–39 | |
| 6 | mrav-shoba-prokle | 6 | 40–45 | ✓ existing pb 41–45 |
| 7 | mrav-shoba-epiphane | 7 | 46–54 | |
| 8 | mrav-iakob-apostle | 8 | 55–57 | ✓ existing pb 56–57 |
| 9 | mrav-stepane-martyrdom | 9 | 58–62 | ✓ existing pb 58–62 |
| 10 | mrav-stepane-inventio | 10 | 63–69 | ✓ existing pb 64–69 |
| 11 | mrav-basil-1 | 11 | 70–71 | ✓ existing pb 71 |
| 12 | mrav-basil-2 | 12 | 72–73 | ✓ existing pb 73 |
| 13 | mrav-natlisgheba-1 | 13 | 74–75 | existing pb 75–76 (reading runs into p.76) |
| 14 | mrav-natlisgheba-2 | 14 | 76–78 | |
| 15 | mrav-natlisgheba-3 | 15 | 79–82 | |
| 16 | mrav-natlisgheba-kyrile | 16 | 83–89 | ✓ existing pb 84–89 |
| 17 | mrav-migeba-hesychios | 17 | 90–93 | ✓ existing pb 91–93 |
| 18 | mrav-migeba-timote | 18 | 94–99 | |
| 19 | mrav-markhva-chrysostom | 19 | 100–111 | |
| 20 | mrav-markhva-ephrem | 20 | 112–114 | |
| 21 | mrav-forty-martyrs | 21 | 115–123 | |
| 22 | mrav-lazare | 22 | 124–131 | |
| 23 | mrav-bzoba-severian | 23 | 132–140 | |
| 24 | mrav-bzoba-iohannes | 24 | 141–148 | |
| 25 | mrav-bzoba-meletios | 25 | 149–150 | |
| 26 | mrav-holymonday | 26 | 151 | 75-folio lacuna follows in the ms |
| 27 | mrav-aghdgoma-meletios | 27 | 152–154 | |
| 28 | mrav-aghdgoma-kyrile | 28 | 155–170 | |
| 29 | mrav-toma-chrysostom | 29 | 171–176 | New Sunday I |
| 30 | mrav-new-sunday | 30 | 177–178 | New Sunday II |
| 31 | mrav-amaghleba | 31 | 179–180 | |
| 32 | mrav-sulthmofenoba-1 | 32 | 181–184 | Pentecost I (მარტჳლია) |
| 33 | mrav-sulthmofenoba-2 | 33 | 185–189 | Pentecost II (მარტჳლია) |
| — | *(John-Baptist Nativity reading)* | 33a | 190 | **no catalog file** |
| 34 | mrav-feristsvaleba | 34 | 191–198 | |
| 35 | mrav-dormition-1 | 35 | 199–201 | |
| 36 | mrav-dormition-2 | 36 | 202–205 | |
| 37 | mrav-john-baptist-decollatio | 37 | 206–211 | TOC distinguishes the two (catalog folios were identical) |
| 38 | mrav-john-baptist-decollatio-2 | 38 | 212–215 | " |
| 39 | mrav-nativity-theotokos | 38a | 216 | unnumbered commemoration |
| 40 | mrav-enkenia-1 | 39 | 217–224 | |
| 41 | mrav-enkenia-2 | 40 | 225–231 | |
| 42 | mrav-exaltation-cross | 41 | 232–236 | |
| 43 | mrav-cross-vision | 42 | 237–242 | |
| 44 | mrav-nails-inventio | 43 | 243–244 | |
| 45 | mrav-peter-martyrdom | 44 | 245–249 | |
| 46 | mrav-paul-martyrdom | 45 | 250–254 | |
| 47 | mrav-martyrs-chrysostom | 46 | 255–256 | TOC distinguishes the three (catalog folios were identical) |
| 48 | mrav-martyrs-chrysostom-2 | 47 | 257–259 | " |
| 49 | mrav-martyrs-chrysostom-3 | 48 | 260–262 | " |
| 50 | mrav-departed-ephrem | 49 | 263–265 | |
| 51 | mrav-sinai-fathers | 50 | 266–279 | **same work as #52 — duplicate?** |
| 52 | mrav-sinai-fathers-amonios | 50 | 266–279 | **same work as #51 — duplicate?** |
| 53 | mrav-colophon-makari | — | 280–281 | appendix (colophon) |
| 54 | mrav-bound-ioane-zosime | — | 282 | appendix |
| 55 | mrav-ioane-zosime | — | 283–284 | appendix (praise of Georgian); Shanidze study begins p.285 |

## Flags / decisions needed

1. **Duplicate pair** — `mrav-sinai-fathers` and `mrav-sinai-fathers-amonios`
   both map to Shanidze №50 (Amonios, *Lives of the Sinai–Raithu Fathers*,
   p.266). They share ms folios in the catalog too. One is likely redundant.
   Which is canonical?
2. **Boundary ±1** — where one reading ends mid-page and the next begins on the
   same page, the computed end page can be one too low (e.g. natlisgheba-1 runs
   into p.76). Exact end pages are only knowable from the edition body; these
   ranges are correct at the start and ±1 at the end.
3. **Appendix items** (colophon-makari 280, bound-ioane-zosime 282,
   ioane-zosime 283) are post-corpus. Include their edition pages, or leave `—`?
4. **Catalog ms folios look like placeholders** — many `<locus>` ranges are
   regular ~12-folio blocks that disagree with the edition's proportions
   (e.g. basil-1 has 12 folios but only 2 edition pages). Worth a separate
   verification pass; the Shanidze pages here are the firmer datum.

---

# Folio audit (decision #4) — catalog `<locus>` vs. real `<pb ed="#S">` in texts

Compared each catalog `<locus from/to>` against the first/last manuscript folio
(`<pb ed="#S" n="...">`) actually present in the text file.

**Result: 52 of 55 differ.** Only `mrav-kharbeba-1` and `-2` match.

**Conclusion:** the catalog loci are placeholder estimates (regular ~10-folio
blocks that increment mechanically); the **text files hold the real folios** and
should become the source of truth. Reassuringly, the real folios line up with
the Shanidze pages just added (e.g. antipater real 24r–30v ≈ Shanidze 24–30).

Example divergences (catalog → real text folios):
- mrav-antipater 31r–41v → **24r–30v**
- mrav-shoba-athanasi 42r–56v → **31r–40r**
- mrav-stepane-inventio 103r–112v → **60r–67r**
- mrav-aghdgoma-kyrile 300r–309v → **148r–162v**

**But a few text files themselves still carry placeholder-looking folios** (their
`<pb ed="#S">` matches the catalog estimate, not real data) — these need OCR
verification against the manuscript images:
- `mrav-nativity-theotokos` — single pb `407r` (looks copied from catalog)
- `mrav-peter-martyrdom` — `463r–463v` (vs neighbour paul-martyrdom real 240r–244r)
- `mrav-shoba-prokle` — `16r–45r` (16r overlaps earlier texts — stray pb?)
- `mrav-holymonday` — **no `<pb ed="#S">` at all**

**Proposed follow-up (separate pass):** regenerate every catalog `<locus>` from
the real first/last folio in each text file, then OCR-verify the ~4 text files
above. Not done here — this review turn only added the Shanidze edition pages.

---

# Folio rebuild — APPLIED (this session)

Catalog `<locus>` values regenerated from the real `<pb ed="#S">` folios
in each text file. 51 events updated; 55 Shanidze `<bibl type="edition">`
citations left untouched; file well-formed, no new RNG errors.

## Loci changed (old → new)

| event | old (placeholder) | new (from text) |
|-------|------------------|-----------------|
| mrav-kharbeba-2 | 6v-15r | 6v-15r |
| mrav-kharbeba-3 | 23r-30v | 15v-23r |
| mrav-antipater | 31r-41v | 24r-30v |
| mrav-shoba-athanasi | 42r-56v | 31r-40r |
| mrav-shoba-epiphane | 69r-81v | 45v-53v |
| mrav-iakob-apostle | 82r-88v | 54v-56r |
| mrav-stepane-martyrdom | 89r-102v | 56v-59v |
| mrav-stepane-inventio | 103r-112v | 60r-67r |
| mrav-basil-1 | 113r-124v | 67v-68v |
| mrav-basil-2 | 125r-134v | 69r-70r |
| mrav-natlisgheba-1 | 135r-148v | 71r-72v |
| mrav-natlisgheba-2 | 149r-161v | 73r-74v |
| mrav-natlisgheba-3 | 162r-172v | 75r-77v |
| mrav-natlisgheba-kyrile | 173r-182v | 78r-84v |
| mrav-migeba-hesychios | 183r-194v | 85r-87v |
| mrav-migeba-timote | 195r-204v | 88r-93r |
| mrav-markhva-ephrem | 217r-226v | 107r-109r |
| mrav-forty-martyrs | 227r-238v | 110r-119v |
| mrav-lazare | 239r-250v | 120r-127r |
| mrav-bzoba-severian | 251r-261v | 127v-136r |
| mrav-bzoba-iohannes | 262r-271v | 136v-143r |
| mrav-bzoba-meletios | 272r-279v | 143v-144v |
| mrav-aghdgoma-meletios | 290r-299v | 145r-147v |
| mrav-aghdgoma-kyrile | 300r-309v | 148r-162v |
| mrav-toma-chrysostom | 310r-319v | 163r-168v |
| mrav-new-sunday | 320r-329v | 169r-170v |
| mrav-amaghleba | 330r-341v | 171r-173r |
| mrav-sulthmofenoba-1 | 342r-352v | 172r-175r |
| mrav-sulthmofenoba-2 | 353r-362v | 176r-180v |
| mrav-feristsvaleba | 363r-374v | 181v-188v |
| mrav-dormition-1 | 375r-386v | 189r-192r |
| mrav-dormition-2 | 387r-396v | 192v-195v |
| mrav-john-baptist-decollatio | 397r-406v | 196r-202v |
| mrav-john-baptist-decollatio-2 | 397r-406v | 203r-206r |
| mrav-enkenia-1 | 417r-426v | 206v-214r |
| mrav-enkenia-2 | 427r-436v | 214v-220r |
| mrav-exaltation-cross | 437r-447v | 221r-225r |
| mrav-cross-vision | 448r-455v | 225v-232r |
| mrav-nails-inventio | 456r-462v | 233r-234r |
| mrav-paul-martyrdom | 472r-480v | 240r-244r |
| mrav-martyrs-chrysostom | 481r-492v | 245r-246v |
| mrav-martyrs-chrysostom-2 | 481r-492v | 247r-250r |
| mrav-martyrs-chrysostom-3 | 481r-492v | 250v-252v |
| mrav-departed-ephrem | 493r-502v | 254r-255v |
| mrav-sinai-fathers | 503r-512v | 254r-255v |
| mrav-sinai-fathers-amonios | 503r-512v | 256r-273r |
| mrav-colophon-makari | 312v-312v | 274r-312v |
| mrav-bound-ioane-zosime | - | 312v-312v |
| mrav-ioane-zosime | - | 312v-312v |
| mrav-markhva-chrysostom | 205r-216v | 94r–103r (well-formed only) |

## Flagged — text files whose own folios need OCR verification

These were **not** rebuilt (catalog locus left as-is) or need cleanup:

- **mrav-holymonday** — no `<pb ed="#S">` at all; catalog locus unchanged.
- **mrav-nativity-theotokos** — single `<pb n="407r">`, looks copied from the old catalog estimate; locus unchanged.
- **mrav-peter-martyrdom** — folios `463r–463v` (neighbours sit near 240r; Shanidze p.245–249); locus unchanged.
- **mrav-shoba-prokle** — folios `16r–45r` (16r overlaps earlier texts, stray pb); locus unchanged.
- **mrav-markhva-chrysostom** — 3 side-less `<pb>` ids (`102`, `103`, `105`) in the text need a r/v side; locus set from well-formed folios only (94r–103r).
