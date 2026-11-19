#!/usr/bin/env python3
"""render-welcome.py - welcome-video render DRIVER (model job, post-claude step).

TRUSTED CODE builds every slide. The model never writes HTML for this job:
it returns only words (output.json -> {"text": JSON{subject, preheader, intro,
expect, slides}}). This script:
  1. validates that word contract strictly (exact keys, types, lengths),
  2. HTML-escapes every string into a FIXED slide template whose colors and
     font names come ONLY from the digest-verified claim snapshot
     (input_snapshot.json -> context.brand), never from model output,
  3. renders each slide with the reviewed sandboxed renderer render/render.sh
     (bwrap, no network, CSP, asset manifest, PNG decode validation),
  4. stitches the PNGs into an MP4 (H.264, yuv420p, faststart) and a small
     GIF preview with ffmpeg, then writes base64 copies for the sealed bundle.

Usage: render-welcome.py OUTPUT_JSON SNAPSHOT_JSON OUT_DIR
Writes OUT_DIR/welcome.mp4(.b64) and OUT_DIR/welcome.gif(.b64).
Any contract breach is a named non-zero exit, never a degraded render.
"""
import base64, html, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, "..", "render", "render.sh")
LOGO_URL_FILE = os.path.join(HERE, "..", "render", "assets", "logo-url.txt")

FFMPEG = os.environ.get("FFMPEG_BIN") or "ffmpeg"  # pinned binary set by the workflow
SLIDE_SECONDS = 4.0
FADE = 0.4
MAX_MP4 = 8 * 1024 * 1024
MAX_GIF = 3 * 1024 * 1024
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
FONT = re.compile(r"^[A-Za-z0-9 ]{1,40}$")

LIMITS = {"subject": 90, "preheader": 140, "intro": 700}
EXPECT_MIN, EXPECT_MAX, EXPECT_LEN = 3, 5, 160
SLIDES_N, HEAD_LEN, SUB_LEN = 5, 70, 160


def die(code, msg):
    print(f"REJECT: {msg}", file=sys.stderr)
    sys.exit(code)


def load_script(path):
    try:
        o = json.load(open(path))
    except Exception:
        die(61, "output.json is not JSON")
    if not isinstance(o, dict) or set(o.keys()) != {"text"} or not isinstance(o["text"], str):
        die(61, 'output.json must be exactly {"text": "<minified JSON>"}')
    try:
        s = json.loads(o["text"])
    except Exception:
        die(62, "output text is not parseable JSON")
    validate_script(s)
    return s


def validate_script(s):
    keys = {"subject", "preheader", "intro", "expect", "slides"}
    if not isinstance(s, dict) or set(s.keys()) != keys:
        die(63, f"welcome script keys must be exactly {sorted(keys)}")
    for k, n in LIMITS.items():
        if not isinstance(s[k], str) or not s[k].strip() or len(s[k]) > n:
            die(64, f"{k} must be a non-empty string of at most {n} chars")
    e = s["expect"]
    if not isinstance(e, list) or not (EXPECT_MIN <= len(e) <= EXPECT_MAX) or \
            not all(isinstance(x, str) and x.strip() and len(x) <= EXPECT_LEN for x in e):
        die(65, f"expect must be {EXPECT_MIN}-{EXPECT_MAX} strings of at most {EXPECT_LEN} chars")
    sl = s["slides"]
    if not isinstance(sl, list) or len(sl) != SLIDES_N:
        die(66, f"slides must be exactly {SLIDES_N} entries")
    for x in sl:
        if not isinstance(x, dict) or set(x.keys()) != {"headline", "sub"}:
            die(66, "each slide must be exactly {headline, sub}")
        if not isinstance(x["headline"], str) or not x["headline"].strip() or len(x["headline"]) > HEAD_LEN:
            die(66, f"slide headline must be 1-{HEAD_LEN} chars")
        if not isinstance(x["sub"], str) or len(x["sub"]) > SUB_LEN:
            die(66, f"slide sub must be at most {SUB_LEN} chars")


def load_brand(snapshot_path):
    snap = json.load(open(snapshot_path))
    ctx = (snap or {}).get("context") or {}
    c = ctx.get("canvas") or {}
    w, h = c.get("w"), c.get("h")
    if not (isinstance(w, int) and isinstance(h, int) and 320 <= w <= 1920 and 180 <= h <= 1080):
        die(67, "welcome job without a valid claim-context canvas")
    b = ctx.get("brand") or {}
    out = {"w": w, "h": h}
    for k, default in (("background", "#111827"), ("accent", "#3B82F6"),
                       ("highlight", "#A855F7"), ("sparing_accent", "#F59E0B")):
        v = b.get(k)
        out[k] = v if isinstance(v, str) and HEX.match(v) else default
    for k, default in (("display_font", "Inter"), ("body_font", "Inter")):
        v = b.get(k)
        out[k] = v if isinstance(v, str) and FONT.match(v) else default
    name = b.get("business_name")
    out["business_name"] = name.strip()[:60] if isinstance(name, str) and name.strip() else ""
    return out


def is_dark(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 0.5


def logo_src():
    # Only the exact URL the worker recorded at connect-install. render/rewrite.py
    # swaps exactly this string for the bundled, manifest-verified logo. Anything
    # else would be an external reference and the renderer would refuse it.
    try:
        u = open(LOGO_URL_FILE).read().strip()
    except OSError:
        return None
    return u if u.startswith("https://") and '"' not in u and "<" not in u else None


def slide_html(brand, slide, idx, total, logo):
    e = html.escape
    dark = is_dark(brand["background"])
    text = "#FFFFFF" if dark else "#111111"
    muted = "rgba(255,255,255,0.78)" if dark else "rgba(17,17,17,0.72)"
    dots = "".join(
        f'<span style="display:inline-block;width:12px;height:12px;border-radius:6px;margin-left:10px;'
        f'background:{brand["sparing_accent"] if i == idx else muted};opacity:{1 if i == idx else 0.35}"></span>'
        for i in range(total))
    logo_tag = (f'<img src="{e(logo)}" alt="" style="position:absolute;left:64px;bottom:40px;height:96px;'
                f'max-width:360px;object-fit:contain">') if logo else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
html,body{{margin:0;padding:0;width:{brand["w"]}px;height:{brand["h"]}px;overflow:hidden}}
body{{background:{brand["background"]};background-image:radial-gradient(circle at 85% 15%,{brand["accent"]}33,transparent 55%);
position:relative;font-family:'{brand["body_font"]}',system-ui,sans-serif;color:{text}}}
.bar{{position:absolute;left:72px;top:96px;width:96px;height:10px;border-radius:5px;background:{brand["accent"]}}}
.txt{{position:absolute;left:72px;right:120px;top:140px}}
.h{{font-family:'{brand["display_font"]}',system-ui,sans-serif;
font-weight:700;font-size:72px;line-height:1.08;letter-spacing:-0.5px}}
.s{{margin-top:36px;max-width:1000px;font-size:34px;line-height:1.35;color:{muted}}}
.dots{{position:absolute;right:72px;bottom:80px}}
</style></head><body>
<div class="bar"></div>
<div class="txt"><div class="h">{e(slide["headline"])}</div>
<div class="s">{e(slide["sub"])}</div></div>
{logo_tag}
<div class="dots">{dots}</div>
</body></html>"""


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print((r.stdout + r.stderr)[-800:], file=sys.stderr)
    return r.returncode


def main():
    if len(sys.argv) != 4:
        die(60, "usage: render-welcome.py OUTPUT_JSON SNAPSHOT_JSON OUT_DIR")
    script = load_script(sys.argv[1])
    brand = load_brand(sys.argv[2])
    out_dir = sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    logo = logo_src()
    tmp = tempfile.mkdtemp()
    pngs = []
    for i, slide in enumerate(script["slides"]):
        hp = os.path.join(tmp, f"s{i}.html")
        pp = os.path.join(tmp, f"s{i}.png")
        open(hp, "w").write(slide_html(brand, slide, i, len(script["slides"]), logo))
        rc = run(["bash", RENDER, hp, pp, str(brand["w"]), str(brand["h"])])
        if rc != 0:
            die(70, f"sandboxed renderer refused slide {i + 1} (rc {rc})")
        pngs.append(pp)

    # MP4: each slide held SLIDE_SECONDS with a short fade in/out, concatenated.
    args = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
    for p in pngs:
        args += ["-loop", "1", "-t", str(SLIDE_SECONDS), "-framerate", "30", "-i", p]
    parts = "".join(
        f"[{i}:v]fade=t=in:st=0:d={FADE},fade=t=out:st={SLIDE_SECONDS - FADE}:d={FADE},format=yuv420p[v{i}];"
        for i in range(len(pngs)))
    chain = "".join(f"[v{i}]" for i in range(len(pngs))) + f"concat=n={len(pngs)}:v=1:a=0[out]"
    mp4 = os.path.join(out_dir, "welcome.mp4")
    if run(args + ["-filter_complex", parts + chain, "-map", "[out]", "-c:v", "libx264",
                   "-preset", "medium", "-crf", "26", "-pix_fmt", "yuv420p", "-r", "30",
                   "-movflags", "+faststart", mp4]) != 0:
        die(71, "ffmpeg mp4 encode failed")

    # GIF preview: the same slides, no fades, 640px wide, palette-optimized.
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for p in pngs:
            f.write(f"file '{p}'\nduration 2.5\n")
        f.write(f"file '{pngs[-1]}'\n")
    gif = os.path.join(out_dir, "welcome.gif")
    if run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
            "-vf", "scale=640:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse",
            "-loop", "0", gif]) != 0:
        die(72, "ffmpeg gif encode failed")

    mb, gb = open(mp4, "rb").read(), open(gif, "rb").read()
    if not (0 < len(mb) <= MAX_MP4) or mb[4:8] != b"ftyp":
        die(73, f"mp4 failed bounds/signature check ({len(mb)} bytes)")
    if not (0 < len(gb) <= MAX_GIF) or gb[:6] not in (b"GIF89a", b"GIF87a"):
        die(74, f"gif failed bounds/signature check ({len(gb)} bytes)")
    open(mp4 + ".b64", "w").write(base64.b64encode(mb).decode("ascii"))
    open(gif + ".b64", "w").write(base64.b64encode(gb).decode("ascii"))
    print(f"welcome render: ok slides={len(pngs)} {brand['w']}x{brand['h']} mp4_bytes={len(mb)} gif_bytes={len(gb)}"
          f" logo={'yes' if logo else 'no'}")


if __name__ == "__main__":
    main()
