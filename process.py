import re
from lxml import etree

def is_asomtavruli_single(text):
    if text and len(text.strip()) == 1:
        char = text.strip()
        return '\u10a0' <= char <= '\u10ff'
    return False

def normalize(word):
    if word.endswith('ის'):
        return word[:-2], 'genitive'
    elif word.endswith('ს'):
        return word[:-1], 'dative'
    elif word.endswith('ით'):
        return word[:-2], 'instrumental'
    elif word.endswith('ად'):
        return word[:-2], 'adverbial'
    elif word.endswith('ო'):
        return word[:-1], 'vocative'
    elif word.endswith('ი'):
        return word[:-1], 'nominative'
    else:
        return word, 'uninflected'

# Load lexicon
lexicon_tree = etree.parse('tei/lexicon.xml')
lexicon_root = lexicon_tree.getroot()
ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
lexicon_orths = set()
for orth in lexicon_root.xpath('//tei:orth[@xml:lang="ka"]', namespaces=ns):
    lexicon_orths.add(orth.text)

# Load imnaishvili
imna_tree = etree.parse('tei/imnaishvili-extracted.xml')
imna_root = imna_tree.getroot()
imna_entries = {}
for entry in imna_root.xpath('//tei:entry', namespaces=ns):
    orth = entry.xpath('.//tei:orth[@xml:lang="ka"]', namespaces=ns)[0].text
    sense = entry.xpath('.//tei:sense[1]', namespaces=ns)
    if sense:
        def_ka = sense[0].xpath('.//tei:def[@xml:lang="ka"]', namespaces=ns)
        def_en = sense[0].xpath('.//tei:def[@xml:lang="en"]', namespaces=ns)
        def_ka_text = def_ka[0].text if def_ka else ''
        def_en_text = def_en[0].text if def_en else ''
    else:
        def_ka_text = ''
        def_en_text = ''
    imna_entries[orth] = (def_ka_text, def_en_text)

# Extract tokens
text_tree = etree.parse('tei/texts/mrav-kharbeba-2.xml')
text_root = text_tree.getroot()

token_occurrences = []
for p in text_root.xpath('//tei:p[@xml:id]', namespaces=ns):
    pid = p.get('{http://www.w3.org/XML/1998/namespace}id')
    # Remove hi rend='initial' if single Asomtavruli
    for hi in p.xpath('.//tei:hi[@rend="initial"]', namespaces=ns):
        if is_asomtavruli_single(hi.text):
            hi.getparent().remove(hi)
    # Get text
    text = etree.tostring(p, method='text', encoding='unicode').strip()
    # Split on whitespace
    words = re.split(r'\s+', text)
    for word in words:
        word = word.strip('.,!?;:"')
        if word and not re.match(r'^[^\w]+$', word, re.UNICODE):
            token_occurrences.append((word, pid))

# Now, process
new_candidates = set()
already_in_lexicon = []
unknown = []

for surface, pid in token_occurrences:
    norm, case = normalize(surface)
    if norm in imna_entries and norm not in lexicon_orths:
        new_candidates.add(norm)
    elif norm in lexicon_orths:
        already_in_lexicon.append((surface, norm, pid))
    else:
        unknown.append((surface, pid))

# For new candidates, create entries
list_a = []
for lemma in sorted(new_candidates):
    def_ka, def_en = imna_entries[lemma]
    slug = re.sub(r'[^a-z0-9]+', '-', lemma.lower())
    if len(slug) > 1 and slug[-1] == '-':
        slug = slug[:-1]
    # Check collision
    existing_ids = [e.get('xml:id') for e in lexicon_root.xpath('//tei:entry', namespaces=ns)]
    if f'lex-{slug}' in existing_ids:
        slug += '-n'  # simple append
    entry = f'''<entry xml:id="lex-{slug}">
  <form type="lemma">
    <orth xml:lang="ka">{lemma}</orth>
  </form>
  <gramGrp>
    <pos><!-- TODO --></pos>
  </gramGrp>
  <sense n="1">
    <def xml:lang="en">{def_en}</def>
    <def xml:lang="ka">{def_ka}</def>
    <cit type="translation" xml:lang="grc">
      <quote><!-- TODO: Greek equivalent --></quote>
    </cit>
  </sense>
  <xr type="lod">
    <ref target=""><!-- TODO: OLiA URI --><!-- TODO: POS label --></ref>
  </xr>
  <xr type="source">
    <ref target="#mrav-kharbeba-2">mrav-kharbeba-2</ref>
  </xr>
</entry>'''
    list_a.append(entry)

# List B
list_b = []
for surface, lemma, pid in already_in_lexicon:
    list_b.append(f'{surface} | lex-{re.sub(r"[^a-z0-9]+", "-", lemma.lower())} | mrav-kharbeba-2-{pid}')

# List C
list_c = []
for surface, pid in unknown:
    list_c.append(f'{surface} | mrav-kharbeba-2-{pid}')

print("List A: New candidate entries")
for e in list_a:
    print(e)
    print()

print("List B: Already-in-lexicon words")
for l in list_b:
    print(l)

print("List C: Unknown tokens")
for u in list_c:
    print(u)

print(f"\nCandidates (List A): {len(list_a)} new entries")
print(f"Already tagged targets (List B): {len(list_b)} occurrences across {len(set(l.split(' | ')[1] for l in list_b))} unique lemmas")
print(f"Unknown tokens (List C): {len(list_c)} tokens for manual review")