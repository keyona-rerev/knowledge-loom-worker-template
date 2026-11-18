#!/usr/bin/env bash
# Worker-side visual render step prototype (v4). The model never sees or
# chooses any of this; it only wrote the input html via its Write tool.
#
# Boundary: bubblewrap ONLY (v4: the non-bwrap fallback is DELETED - no
# bwrap means HARD FAILURE rc47, never a weaker sandbox). user+net+mount+
# pid+ipc namespaces, a minimal READ-ONLY rootfs (/usr /lib /lib64 /opt
# /etc/fonts), one writable bind (the jail), env scrubbed. No host
# filesystem (repo, .git, HOME, /tmp, secrets) exists inside. No network
# (netns). Chrome's own sandbox is off inside (--no-sandbox); the bwrap
# namespaces are the boundary. The runner MUST have bubblewrap installed.
set -uo pipefail
HTML_IN="$1"; OUT="$2"; W="${3:-1200}"; H="${4:-627}"
MAX_HTML=262144; MAX_PNG=4194304; TIMEOUT_S=45
CHROME=/opt/google/chrome/chrome
command -v bwrap >/dev/null || { echo "FAIL: bubblewrap not installed; refusing to render without the namespace boundary"; exit 47; }
SIZE=$(stat -c%s "$HTML_IN" 2>/dev/null || echo 0)
[ "$SIZE" -gt 0 ] || { echo "REJECT: missing/empty input"; exit 41; }
[ "$SIZE" -le "$MAX_HTML" ] || { echo "REJECT: input oversize ($SIZE > $MAX_HTML)"; exit 42; }
D="$(dirname "$(readlink -f "$0")")"
# Trusted assets: verified against a manifest before use. In the worker these
# are re-fetched from a PINNED trusted blob AFTER the model step, then
# verified against a manifest committed outside the model's write scope.
( cd "$D/assets" && sha256sum -c "$D/assets.sha256" >/dev/null 2>&1 ) || { echo "REJECT: asset integrity failure"; exit 46; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp "$HTML_IN" "$TMP/in.html"
python3 "$D/rewrite.py" "$TMP/in.html" >/dev/null || { echo "REJECT: rewrite failed"; exit 43; }
CHROME_FLAGS=(--headless=new --no-sandbox --disable-gpu --disable-extensions
  --disable-dev-shm-usage --no-first-run "--user-data-dir=/render/profile" --disable-quic
  --proxy-server=127.0.0.1:1 "--proxy-bypass-list=<-loopback>"
  "--host-resolver-rules=MAP * ~NOTFOUND"
  "--window-size=$W,$H" "--screenshot=/render/out.png" "file:///render/in.html")
env -i bwrap --unshare-all --die-with-parent \
  --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 --ro-bind /opt /opt \
  --ro-bind /etc/fonts /etc/fonts \
  --tmpfs /tmp --bind "$TMP" /render --proc /proc --dev /dev \
  --setenv HOME /render --setenv PATH /usr/bin:/bin --chdir /render \
  timeout "$TIMEOUT_S" "$CHROME" "${CHROME_FLAGS[@]}" 2>/dev/null
rc=$?
[ $rc -eq 0 ] || { echo "FAIL: chrome exit $rc (124=timeout)"; exit $rc; }
PSIZE=$(stat -c%s "$TMP/out.png" 2>/dev/null || echo 0)
[ "$PSIZE" -gt 0 ] || { echo "FAIL: empty png"; exit 44; }
[ "$PSIZE" -le "$MAX_PNG" ] || { echo "FAIL: png oversize ($PSIZE > $MAX_PNG)"; exit 45; }
python3 "$D/pngcheck.py" "$TMP/out.png" "$W" "$H" || { echo "REJECT: png failed decode validation"; exit 48; }
cp "$TMP/out.png" "$OUT"; echo "OK png=$PSIZE"
