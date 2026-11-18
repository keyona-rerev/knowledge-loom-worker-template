#!/usr/bin/env python3
"""set-client-brand.py - bundle ONE client's logo and fonts into this worker copy.

The renderer is offline: it can only use the logo and fonts bundled in
render/assets, pinned by render/assets.sha256. Run this ONCE on the client's
worker copy (on the installer's computer), then commit the result.

Usage:
  python3 scripts/set-client-brand.py --logo-url https://.../logo.png \
      --font "Playfair Display:700" --font "Lato:400,700"
  (or --logo path/to/logo.png for a local file)

  --logo-url  The client's logo URL - the SAME URL entered in Visual Studio.
              It is downloaded once, bundled, and recorded so the renderer
              swaps that exact URL for the bundled file.
  --logo      A local logo file instead (PNG, JPEG, WebP or SVG).
  --font   A Google Fonts family and its weights. Repeat for each family.
           Use the SAME family names the client enters in Visual Studio.
           Omit --font to keep the fonts already bundled.

Rules this keeps:
  - Every asset is a data: URI. Nothing is fetched at render time.
  - assets.sha256 is regenerated, so render.sh's integrity check passes.
  - The renderer swaps the recorded logo URL (and any res.cloudinary.com URL)
    for this bundled logo, so the logo works with no network at render time.
"""
import argparse, base64, hashlib, os, re, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "render", "assets")
MANIFEST = os.path.join(ROOT, "render", "assets.sha256")
# A desktop Chrome user agent makes Google Fonts answer with woff2 files.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def logo_mime(b: bytes) -> str:
    if b.startswith(PNG_MAGIC): return "image/png"
    if b[:3] == b"\xff\xd8\xff": return "image/jpeg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "image/webp"
    head = b[:512].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in b[:2048].lower()): return "image/svg+xml"
    sys.exit("logo must be a PNG, JPEG, WebP or SVG file")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse_font(spec: str):
    m = re.fullmatch(r"\s*([A-Za-z0-9 ]+?)\s*:\s*([0-9]{3}(?:\s*,\s*[0-9]{3})*)\s*", spec)
    if not m:
        sys.exit(f"bad --font {spec!r}: use \"Family Name:400,700\"")
    weights = sorted({int(w) for w in m.group(2).split(",")})
    return m.group(1), weights


def build_font_css(specs):
    blocks = []
    for family, weights in (parse_font(s) for s in specs):
        q = urllib.parse.quote(family) + ":wght@" + ";".join(str(w) for w in weights)
        css = fetch(f"https://fonts.googleapis.com/css2?family={q}&display=swap").decode("utf-8")
        urls = re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)", css)
        if not urls:
            sys.exit(f"Google Fonts returned no woff2 files for {family!r}. Check the name at fonts.google.com.")
        for u in urls:
            data = base64.b64encode(fetch(u)).decode("ascii")
            css = css.replace(f"url({u})", f"url(data:font/woff2;base64,{data})")
        blocks.append(css)
        print(f"font: {family} {weights} -> {len(urls)} files inlined")
    out = "\n".join(blocks)
    if re.search(r"url\((?!data:)", out):
        sys.exit("font css still has a non-data url(); refusing to write it")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--logo")
    g.add_argument("--logo-url")
    ap.add_argument("--font", action="append", default=[])
    a = ap.parse_args()

    if a.logo_url:
        if not a.logo_url.startswith("https://"):
            sys.exit("--logo-url must start with https://")
        logo = fetch(a.logo_url.strip())
    else:
        logo = open(a.logo, "rb").read()
    mime = logo_mime(logo)
    if len(logo) > 2 * 1024 * 1024:
        sys.exit("logo is over 2 MB; export a smaller file")

    font_css = build_font_css(a.font) if a.font else None

    open(os.path.join(ASSETS, "logo.png"), "wb").write(logo)  # original bytes, any format
    open(os.path.join(ASSETS, "logo.b64.txt"), "w").write(f"data:{mime};base64," + base64.b64encode(logo).decode("ascii"))
    open(os.path.join(ASSETS, "logo-url.txt"), "w").write((a.logo_url or "").strip() + "\n")
    print(f"logo: {len(logo)} bytes bundled")
    if font_css is not None:
        open(os.path.join(ASSETS, "fonts-inline.css"), "w").write(font_css)

    lines = []
    for name in ("fonts-inline.css", "logo.b64.txt", "logo-url.txt"):
        h = hashlib.sha256(open(os.path.join(ASSETS, name), "rb").read()).hexdigest()
        lines.append(f"{h}  {name}")
    open(MANIFEST, "w").write("\n".join(lines) + "\n")
    print("assets.sha256 regenerated. Commit render/ to the client's worker repo.")


if __name__ == "__main__":
    main()
