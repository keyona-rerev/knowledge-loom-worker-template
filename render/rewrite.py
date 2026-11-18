import re, sys, os
# Deterministic rewrite to a FULLY self-contained document, FAIL-CLOSED (B1/B2):
# - requires a real <head> (case-insensitive); absent/malformed -> exit 2
# - known external font/logo refs -> inline data URIs from staged pristine assets
# - CSP injected as FIRST head child (combined enforcement: a model-authored
#   CSP can never loosen ours)
# - read-back verification: the written document MUST contain our CSP with
#   script-src 'none', else exit 3
# - residual fetchable external refs in src/href/url()/@import (any scheme:
#   http(s), file, protocol-relative, ws, ftp) -> exit 4. data: URIs and
#   namespace identifiers (xmlns) are not fetch positions.
p = sys.argv[1]
d = os.path.dirname(os.path.abspath(__file__))
css = open(os.path.join(d, 'assets/fonts-inline.css')).read()
logo = open(os.path.join(d, 'assets/logo.b64.txt')).read()
h = open(p).read()

CSP = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
       'img-src data:; style-src \'unsafe-inline\'; font-src data:; script-src \'none\'; '
       'connect-src \'none\'; form-action \'none\'">')

h = re.sub(r'(?is)<link\s+rel=["\']?preconnect["\']?[^>]*>', '', h)
h, n_font_links = re.subn(r'(?is)<link[^>]*fonts\.googleapis\.com/css2[^>]*>', '<style>' + css + '</style>', h)
h = re.sub(r'(?i)https://res\.cloudinary\.com/[^"\'\s)]*', logo, h)
# The client's own logo URL (any host), recorded by scripts/set-client-brand.py,
# is swapped for the same bundled logo. Exact string match only.
_lu = os.path.join(d, 'assets/logo-url.txt')
if os.path.exists(_lu):
    _u = open(_lu).read().strip()
    if _u.startswith('https://'):
        h = h.replace(_u, logo)

# Quote-aware tag scanner (G3): a fake "<head>" inside an ATTRIBUTE VALUE
# must never count as the injection point - the naive regex injected the CSP
# into an attribute, the substring read-back passed, and the REAL head got
# no CSP (inline scripts would run).
TAG = re.compile(r"(?s)<(?:[^>\"']|\"[^\"]*\"|'[^']*')*>")
def find_real_head(doc):
    for tm in TAG.finditer(doc):
        if re.match(r'(?i)<head(?:\s|>)', tm.group(0)):
            return tm
    return None

m = find_real_head(h)
if not m:
    print('REJECT: no <head> element; refusing to guess injection point', file=sys.stderr)
    sys.exit(2)
# Bundled fonts (pristine staged asset, data: URIs only) are always available by
# name, so a document that only names the font families renders with them and
# needs no external font reference. Added right after the CSP; the CSP stays
# the first child of the real head. No network, no new resource URL is allowed.
h = h[:m.end()] + CSP + ('' if n_font_links else '<style>' + css + '</style>') + h[m.end():]

# read-back verification of the actual written bytes
out = h
# Positional read-back (G3): the CSP must be the FIRST child of the REAL
# head in the actual written bytes - substring presence anywhere is not
# proof (a CSP string inside an attribute used to pass).
m3 = find_real_head(out)
if not m3 or out[m3.end():m3.end() + len(CSP)] != CSP or "script-src 'none'" not in CSP:
    print('REJECT: CSP verification failed on written document', file=sys.stderr)
    sys.exit(3)

# residual external fetch positions -> reject (B2)
# Scan copy with CSS escapes decoded (G3): an escaped fetch position like
# url(\68 ttp://evil) decodes to url(http://evil) - the raw-regex scan used
# to miss it. Decoding affects ONLY the scan; written bytes are unchanged.
def css_unescape(doc):
    return re.sub(r'\\([0-9a-fA-F]{1,6})\s?', lambda mm: chr(int(mm.group(1), 16)), doc)
scan = css_unescape(out)

# url() is an ALLOWLIST, not a pattern: only data: and fragment refs survive.
for um in re.finditer(r'(?i)url\(\s*(["\']?)(.*?)\1\s*\)', scan):
    tgt = um.group(2).strip().lower()
    if not (tgt.startswith('data:') or tgt.startswith('#')):
        print(f'REJECT: non-data url() fetch position: {um.group(0)[:80]!r}', file=sys.stderr)
        sys.exit(4)

patterns = [
    r'(?i)(?:src|href)\s*=\s*["\']\s*(?:https?:|file:|//|ftp:|wss?:)',
    r'(?i)(?:src|href)\s*=\s*(?!["\'\s>])(?:https?:|file:|//|ftp:|wss?:)',
    r'(?i)@import\s',
    r'(?is)<script[^>]*src\s*=',
    r'(?is)<form[^>]*action\s*=\s*["\'](?!["\'])',
    r'(?is)<form[^>]*action\s*=\s*(?!["\'\s>])',
    r'(?is)<meta[^>]*http-equiv\s*=\s*["\']?refresh',
    r'(?i)(?:poster|srcset|data)\s*=\s*["\']?\s*(?:https?:|file:|//|ftp:|wss?:)',
]
for pat in patterns:
    m2 = re.search(pat, scan)
    if m2:
        print(f'REJECT: residual external reference: {scan[max(0,m2.start()-60):m2.end()+60]!r}', file=sys.stderr)
        sys.exit(4)
open(p, 'w').write(out)
print('rewrite OK: self-contained, CSP verified, no residual external refs')
