#!/usr/bin/env bash
# render-visual.sh - draft-visual render DRIVER (model job, post-claude step).
# Extracts the html from output.json under the exact {visual_type, html}
# contract, then hands it to render/render.sh - the REVIEWED v4 hardened
# renderer (bwrap-only, fail-closed rc47 when bubblewrap is absent, full
# user+net+mount+pid+ipc namespaces, minimal ro rootfs, asset manifest,
# self-containment rewrite with enforced CSP, full PNG decode validation).
# Canvas size comes ONLY from mode.json (trusted claim context), never from
# model output. Any contract breach is a named exit, never a degraded render.
set -euo pipefail
OUT_JSON="$1"      # output.json (model-written, data only)
MODE_JSON="$2"     # mode.json from scripts/select-mode.py (trusted)
PNG_OUT="$3"       # destination png path
B64_OUT="$4"       # destination base64 path
D="$(dirname "$(readlink -f "$0")")"

W=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["canvas"]["w"])' "$MODE_JSON")
H=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["canvas"]["h"])' "$MODE_JSON")

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
python3 - "$OUT_JSON" "$TMP/visual.html" <<'PY'
import json, sys
o = json.load(open(sys.argv[1]))
if not isinstance(o, dict) or not isinstance(o.get("text"), str):
    sys.exit("output.json is not {\"text\": ...}")
try:
    inner = json.loads(o["text"])
except Exception:
    sys.exit("output text is not parseable JSON")
if not isinstance(inner, dict) or set(inner.keys()) != {"visual_type", "html"}:
    sys.exit("visual output keys must be exactly visual_type + html")
if not isinstance(inner["visual_type"], str) or not inner["visual_type"].strip():
    sys.exit("visual_type missing")
if not isinstance(inner["html"], str) or len(inner["html"]) < 20:
    sys.exit("html missing or implausibly small")
open(sys.argv[2], "w").write(inner["html"])
PY

# Reviewed v4 renderer, verbatim. Exit codes: 41 missing/empty, 42 oversize,
# 43 rewrite/egress reject, 44/45 png bounds, 46 asset integrity, 47 no bwrap
# (HARD FAIL - no fallback sandbox exists), 48 png decode/dims.
bash "$D/../render/render.sh" "$TMP/visual.html" "$PNG_OUT" "$W" "$H"
base64 -w0 "$PNG_OUT" > "$B64_OUT"
echo "render: ok ${W}x${H} png_bytes=$(stat -c%s "$PNG_OUT")"
