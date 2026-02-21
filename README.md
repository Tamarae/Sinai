# სინური მრავალთავი 864 წლისა — ციფრული სამეცნიერო გამოცემა

**Sinai Mravaltavi of 864 — Level-4 Digital Scholarly Edition**

ილიას სახელმწიფო უნივერსიტეტი · ლინგვისტურ კვლევათა ინსტიტუტი

---

## პროექტის სტრუქტურა

```
mravaltavi/
├── tei/
│   ├── catalog.xml          ← კორპუსის კატალოგი (მასტერ-ინდექსი)
│   ├── lexicon.xml          ← ლექსიკონი (TEI <dictionary>)
│   ├── research.xml         ← სამეცნიერო სტატია
│   └── texts/
│       ├── mrav-kharbeba-1.xml
│       ├── mrav-kharbeba-2.xml
│       └── ...              ← ერთი XML ფაილი თითო ტექსტზე (~45 ფაილი)
│
├── templates/
│   ├── base.html            ← Jinja2 ბაზა (ნავ., ფუტ., CSS variables)
│   ├── index.html           ← მთავარი გვერდი
│   ├── manuscripts.html     ← ხელნაწერები
│   ├── about.html           ← პროექტის შესახებ
│   ├── texts/
│   │   ├── index.html       ← ტექსტების ბრაუზერი (კალენდ. + თემ.)
│   │   └── text.html        ← ერთი ტექსტი + კრიტ. აპარატი
│   ├── lexicon/
│   │   └── index.html       ← ლექსიკონი
│   └── research/
│       └── index.html       ← კვლევა
│
├── src/
│   ├── catalog_parser.py    ← catalog.xml → Python objects
│   ├── text_parser.py       ← mrav-*.xml → TextData + apparatus HTML
│   └── lexicon_parser.py    ← lexicon.xml → LexiconData
│
├── static/                  ← CSS, JS, images (GitHub Pages-ზე)
├── build/                   ← გენერირებული HTML (git-ignored)
│
├── build.py                 ← მთავარი build სკრიპტი
├── requirements.txt
└── README.md
```

## Build

```bash
pip install -r requirements.txt

# სრული build
python build.py

# ნაწილობრივი
python build.py --texts      # ტექსტების გვერდები
python build.py --lexicon    # ლექსიკონი
python build.py --index      # ინდექსი + ნავ.
```

## TEI ფაილების სტრუქტურა

### catalog.xml
კატალოგი კორპუსის სტრუქტურის შესახებ:
- `<listWit>` — ხელნაწერების მეტადატა (N35, N50)
- `<listPerson type="authors">` — ავტორების authority list (VIAF id-ებით)
- `<taxonomy xml:id="feasts">` — ლიტ. კალენდრის taxonomy
- `<taxonomy xml:id="genres">` — ჟანრების taxonomy
- `<listEvent>` — ყველა ტექსტი `@xml:id`, `@corresp` (feast), `@type` (genre)

### tei/texts/mrav-*.xml
ინდივიდუალური ტექსტები:
- `<listWit>` `<witness xml:id="N35">` / `<witness xml:id="N50">`
- `<text><body><div type="text">` — ტექსტი
- `<pb n="1r" wit="#N35"/>` — ფოლიო მილესტოუნები
- `<app><lem wit="#N35">…</lem><rdg wit="#N50" type="orthographic">…</rdg></app>`

### lexicon.xml
TEI `<dictionary>` სტრუქტურა:
- `<entry xml:id="mrav-angelozi" corresp="bog:angelozi">`
- `<form type="lemma"><orth>ანგელოზი</orth></form>`
- `<gramGrp><pos>noun</pos></gramGrp>`
- `<sense n="1"><def xml:lang="ka">…</def></sense>`
- `<cit type="translation"><quote xml:lang="grc">ἄγγελος</quote><ref target="https://logeion…"/></cit>`
- `<cit type="example"><quote>…</quote><bibl>…</bibl></cit>`
- `<xr type="lod"><ref target="http://purl.org/olia/…"/></xr>`
- `<xr type="source"><ref target="#mrav-kharbeba-1">ხარება I</ref></xr>`

## კრიტ. აპარატის ვარიანტების ტიპები (`@type` on `<rdg>`)

| type | label | CSS class |
|------|-------|-----------|
| `orthographic` | მართლ. | `rdg-orth` (blue) |
| `grammatical`  | გრამ.  | `rdg-gram` (green) |
| `lexical`      | ლექ.   | `rdg-lex`  (amber) |
| `omission`     | გამოტ. | `rdg-om`   (grey) |
| `addition`     | დამ.   | `rdg-add`  (purple) |

## სტატუსები

- `done` — კოდირება დასრულებულია
- `encoding-in-progress` — კოდირება მიმდინარეობს
- `planned` — დაგეგმილია

## ლიცენზია

CC BY-NC-SA 4.0 · © 2026 ილიას სახ. უნივ.
