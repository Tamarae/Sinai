# Claude Code — Global Workflow Instructions

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review `tasks/lessons.md` at session start for relevant project context

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

---

## Task Management

1. **Plan First** — Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan** — Check in before starting implementation
3. **Track Progress** — Mark items complete as you go
4. **Explain Changes** — High-level summary at each step
5. **Document Results** — Add review section to `tasks/todo.md`
6. **Capture Lessons** — Update `tasks/lessons.md` after any correction

---

## Core Principles

- **Simplicity First** — Make every change as simple as possible. Minimal impact on code.
- **No Laziness** — Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact** — Changes should only touch what's necessary. Avoid introducing bugs.

---

## Output Rules (this project)

- **Full files only** — no placeholders, no patches, no `# ... rest of code ...`
- When any file is modified, output the complete file from top to bottom
- Never truncate long code blocks
- **Always fix TEI XML source files, never build output HTML** — Jinja2 regenerates HTML on every build

---

## Project-Specific Conventions (Sinai Mravaltavi 864)

### Python / Build

- `render(template, dest, root=..., active=..., **ctx)` — always pass both `root` and `active`
- `root=""` for top-level pages; `root="../"` for one level deep (`texts/`, `lexicon/`, `bibliography/`, `research/`); `root="../../"` for individual text pages (`texts/mrav-*.html`)
- NS dict in ALL parsers and scripts — both keys required:
  ```python
  NS = {"tei": "http://www.tei-c.org/ns/1.0", "xml": "http://www.w3.org/XML/1998/namespace"}
  ```
- Never use `{% set active = "..." %}` inside templates — it overrides `build.py` context
- Build flags: `--texts`, `--lexicon`, `--bibliography`, `--index`

### TEI Encoding — Witness and Apparatus

The project has **one manuscript witness**: S (`xml:id="S"`), Sin. geo. №32-57-33,
864 CE. N35 is the Library of Congress item number — never use it as a siglum.

- **Always** `wit="#S"` — never `wit="#N35"` or `wit="#N50"`
- Apparatus model — single witness:
  ```xml
  <app>
    <lem resp="#shanidze">{Shanidze's reading}</lem>
    <rdg wit="#S" type="{type}">{manuscript reading}</rdg>
  </app>
  ```
- `<lem>` carries `resp="#shanidze"` and **no** `@wit`
- `<rdg>` carries `wit="#S"` and **no** `@resp`
- Allowed `@type` values on `<rdg>`:
  `orthographic` | `correction` | `omission` | `addition` | `lacuna` | `abbreviation` | `confirmation`

### TEI Encoding — Folio Breaks

Use `<pb>`, not `<milestone>`:

```xml
<pb n="3r" facs="{facs-url}" ed="#S"/>
```

Insert **before** the first word on each folio. `@facs` is required — never omit it.

**facs URL formula** (Library of Congress IIIF):
- Recto (Nr): image index = `(N−1)×2 + 3`
- Verso (Nv): image index = `(N−1)×2 + 4`

```
https://tile.loc.gov/image-services/iiif/service:gmd:gmd1:g1034:g1034m:sinai0{item}:f.{index}{side}/full/800,/0/default.jpg
```

Example — folio 5r: index = (5−1)×2+3 = 11 → `f.11r`

> Folio labels from 3v onward require OCR verification. Do not invent labels.

### TEI Encoding — Paragraphs and Initials

```xml
<p xml:id="{slug}-p1">
  <hi rend="initial">Ⴀ</hi>სე ვყოთ...
</p>
```

- `xml:id` pattern: `{text-slug}-p{n}`, e.g. `mrav-kharbeba-2-p1`
- `<hi rend="initial">` wraps exactly one Asomtavruli letter; rest of word follows with no space
- Paragraphs reflect manuscript rhetorical units (Asomtavruli initials), not Shanidze print lines

### Lexicon XML

- Entry IDs: `xml:id="lex-{georgian-romanized}"` — romanize lowercase, hyphens for spaces
  - Romanization: ა→a, ბ→b, გ→g, დ→d, ე→e, ვ→v, ზ→z, თ→t, ი→i, კ→k, ლ→l, მ→m,
    ნ→n, ო→o, პ→p, ჟ→zh, რ→r, ს→s, ტ→t, უ→u, ფ→p, ქ→k, ღ→gh, ყ→q, შ→sh,
    ჩ→ch, ც→ts, ძ→dz, წ→ts, ჭ→ch, ხ→kh, ჯ→j, ჰ→h
- Georgian has **no grammatical gender** — never use `<gen>`. `<gramGrp>` contains `<pos>` only
- POS values: use full English terms (`noun`, `verb`, `adjective`, etc.) in `<pos>`
- Source attribution: `source="imnaishvili-1975"` (in Imnaishvili) vs `source="corpus"` (attested only)
- Greek equivalents:
  ```xml
  <cit type="translation" xml:lang="grc"><quote>...</quote></cit>
  ```
  Use Greek script, not transliteration. First cit = primary, second = alternate. Omit if unknown.
- OLiA:
  ```xml
  <xr type="lod"><ref target="http://purl.org/olia/olia.owl#CommonNoun">noun</ref></xr>
  ```
- BOG link: `corresp="bog:{id}"` on `<entry>` — omit entirely if ID unknown, never guess

### Lexicon Tagging (`<w lemma>`)

- Tag **every occurrence** of a matching word, not just the first per paragraph
- Tag inside `<lem>` only — **never inside `<rdg>`**
- Do not double-wrap words already in `<w lemma="...">`
- Do not tag single-letter Asomtavruli initials in `<hi rend="initial">`
- Do not tag proper names unless they have a `lex-` entry in `lexicon.xml`
- Surface form goes inside `<w>`, normalized headword goes in `@lemma`:
  ```xml
  <w lemma="#lex-angelozi">ანგელოსი</w>
  ```
- After any tagging pass, verify with XPath: `//tei:rdg//tei:w` must return empty

### Lexicon Workflow (per new text)

Prompt files live in `prompts/` — paste into Claude Code, substitute `[TEXTID]`:

1. **`prompts/lexicon-candidate-extraction.md`** — reads text + lexicon + Imnaishvili,
   produces candidate entries and tagging targets. Writes nothing to disk.
2. Review candidates in Claude.ai (editorial judgment, Greek/OLiA fill-in).
   Paste approved entries into `tei/lexicon.xml`.
3. **`prompts/lexicon-autotagging.md`** — wraps matching tokens with `<w lemma>`,
   runs `python3 build.py --texts --lexicon`, verifies attestation counts.

### Validation

After any structural change, run a quick lxml check:

```python
from lxml import etree
NS = {"tei": "http://www.tei-c.org/ns/1.0", "xml": "http://www.w3.org/XML/1998/namespace"}
tree = etree.parse("tei/texts/mrav-{slug}.xml")
root = tree.getroot()
# rdg missing @type
bad_rdg = [r for r in root.findall(".//tei:rdg", NS) if r.get("type") is None]
# pb missing @facs
bad_pb = [pb for pb in root.findall(".//tei:pb", NS) if pb.get("facs") is None]
# w inside rdg (forbidden)
bad_w = root.findall(".//tei:rdg//tei:w", NS)
print(f"rdg missing @type: {len(bad_rdg)} | pb missing @facs: {len(bad_pb)} | w in rdg: {len(bad_w)}")
```

All three counts must be 0 before committing.