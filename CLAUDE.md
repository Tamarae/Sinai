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

---

## Project-Specific Conventions (Sinai Mravaltavi)

### Python / Build
- `render(template, dest, root=..., active=..., **ctx)` — always pass both `root` and `active`
- `root=""` for top-level pages; `root="../"` for one level deep (`texts/`, `lexicon/`, etc.); `root="../../"` for individual text pages
- NS dict in all parsers: `{"tei": "http://www.tei-c.org/ns/1.0", "xml": "http://www.w3.org/XML/1998/namespace"}`
- Never use `{% set active = "..." %}` inside templates — it overrides `build.py` context

### TEI Encoding
- Critical apparatus: `<app>`, `<lem>`, `<rdg wit="#N35">` / `<rdg wit="#N50">` — never footnotes
- Witness sigla: `#N35`, `#N50` (matching `xml:id` in catalog) — never `#S`
- Folio boundaries: `<milestone unit="folio" n="32r" ed="#N35"/>`
- Asomtavruli initials: `<hi rend="initial">Ⴀ</hi>`
- Always declare `xmlns="http://www.tei-c.org/ns/1.0"` and `xml:id` on root element
- Georgian has no grammatical gender — never use `<gen>` in lexicon entries

### Lexicon XML
- Entry IDs: `xml:id="lex-{georgian-romanized}"`, e.g. `lex-angelozi`
- Greek: `<cit type="translation" xml:lang="grc"><quote>...</quote></cit>`
- OLiA: `<xr type="lod"><ref target="http://purl.org/olia/olia.owl#...">...</ref></xr>`
- `source="imnaishvili-1975"` vs `source="corpus"` (attested but not in Imnaishvili)
- POS abbreviations: nouns use `სახ.` not `საბ.`

### IIIF @facs URL Formula
- `f.Nr = (N-1)×2 + 3`
- `f.Nv = (N-1)×2 + 4`
- Only 1r (0003) and 1v (0004) are currently correct in mrav-kharbeba-1.xml

### Key Principle
- **Always fix TEI XML source files, never build output HTML** — Jinja2 regenerates HTML on every build
