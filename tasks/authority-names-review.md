# Imnaishvili name indexes → authority.xml (applied)

Encoded **Index I (persons)** and **Index II (geographic names)** from
`Imnaishvili_dictionary.xml` into `tei/authority.xml`.

## What was added
- **+180 `<person>`** and **+56 `<place>`** entries (now 197 persons / 65 places).
- Each new entry: `xml:id` (romanized, homonyms suffixed), `persName/placeName`
  (main + bare-form variants), `type` where the descriptor implied one,
  `<note type="description">` for the parenthetical, and the Shanidze page/line
  references kept **verbatim** in `<bibl type="attestation" corresp="#shanidze1959">`.
- 14 existing entries (დავით, ელია, იესუ, მარიამ, პავლე, პეტრე, …) received the
  Imnaishvili attestation as an added `<bibl>` — their VIAF/trilingual data untouched.
- Well-formed; no new RNG errors.

## Needs your editorial decision — homonyms colliding with an existing entry
These new entries share a name with one you already have. They were created as
**separate** ids (not merged), because only you can say which sense matches the
existing VIAF entry. Merge or link each pair as appropriate:

| new entry (Imnaishvili) | may correspond to existing |
|-------------------------|----------------------------|
| pers-gabriel-mtavarangelozi (გაბრიელ) | pers-gabriel |
| pers-gabriel-anderdzshi (გაბრიელ) | pers-gabriel |
| pers-iakob-mamatmtavari (იაკობ) | pers-iakob |
| pers-iakob-martali (იაკობ) | pers-iakob |
| pers-ieremia-tsinatsarmetqueli (იერემია) | pers-ieremia |
| pers-ieremia-tkhzul (იერემია) | pers-ieremia |
| pers-iesukriste (იესუ ქრისტე) | pers-iesu-kriste |
| pers-ioseb-iosep (იოსებ) | pers-ioseb |
| pers-ioseb-shuenieri (იოსებ) | pers-ioseb |
| pers-ioseb-hayleli (იოსებ) | pers-ioseb |
| pers-mariam (მარიამ) | pers-mariami |
| pers-mariam-moses (მარიამ) | pers-mariami |
| pers-mikael (მიქაელ) | pers-mikhael |
| pers-mikael-mghdeli (მიქაელ) | pers-mikhael |
| pers-mose-tsinatsarmetqueli (მოსე) | pers-mose |
| pers-mose-amba (მოსე) | pers-mose |
| pers-pavle-motsikuli (პავლე) | pers-pavle |
| pers-pavle-mamay (პავლე) | pers-pavle |
| pers-petre-motsikuli (პეტრე) | pers-petre |
| pers-petre-mamatmtavari (პეტრე) | pers-petre |
| pers-solomon (სოლომონ) | pers-solomoni |
| pers-solomon-mamasakhlisi (სოლომონ) | pers-solomoni |
| pers-solomon-monazoni (სოლომონ) | pers-solomoni |
| pers-kriste (ქრისტე) | pers-iesu-kriste |

## Not encoded into authority (by design)
- **Index III — peoples/ethnonyms** (63): demonyms/epithets (ბერძენი, ასური,
  ჰურია, ბოსტრელი…), many tied to a person. These are lexicon/epithet material,
  not persons or places. Recommend: lexicon, or a dedicated `<listNym>`.
- **Index IV — animals** (53) and **Index V — plants** (42): common nouns →
  they belong in the **lexicon**, not authority.

## Caveats
- Attestation strings are the OCR'd page/line lists verbatim; `.`-vs-`;` group
  boundaries occasionally merge (e.g. აგრიპა `247,…. 249,…`). Kept as-is rather
  than mis-splitting into wrong citedRanges — structure them in a later verified pass.
- Parenthetical content was stored whole as a description note; some parens hold
  name-variants (e.g. ალფიანე (აფიანე, აფინა)) rather than descriptors — review if needed.
