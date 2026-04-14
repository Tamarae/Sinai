import re
from lxml import etree

def is_asomtavruli_single(text):
    if text and len(text.strip()) == 1:
        char = text.strip()
        return '\u10a0' <= char <= '\u10ff'
    return False

tree = etree.parse('tei/texts/mrav-kharbeba-2.xml')
root = tree.getroot()
ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

token_occurrences = []
for p in root.xpath('//tei:p[@xml:id]', namespaces=ns):
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

print(f'Total token occurrences: {len(token_occurrences)}')
unique_tokens = set(t[0] for t in token_occurrences)
print(f'Unique tokens: {len(unique_tokens)}')
print(list(unique_tokens)[:20])