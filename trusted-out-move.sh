#!/usr/bin/env bash
# trusted-out-move.sh - move output.json from the dedicated out dir into the
# trusted workspace location, accepting ONLY the canonical regular file.
# Fail-closed: ANY other entry in the out dir (symlink, hardlink, dir,
# traversal-named file) rejects the whole move. Size-bounded.
set -euo pipefail
OUT_DIR="$1"; DEST="$2"
SRC="$OUT_DIR/output.json"
[ -d "$OUT_DIR" ] || { echo "out dir absent"; exit 1; }
[ -e "$SRC" ] || { echo "output.json absent"; exit 1; }
[ -L "$SRC" ] && { echo "output.json is a symlink - refused"; exit 1; }
[ -f "$SRC" ] || { echo "output.json is not a regular file - refused"; exit 1; }
[ -r "$SRC" ] || { echo "output.json exists but is not readable - honest failure"; exit 1; }
[ "$(realpath -m "$SRC")" = "$(realpath -m "$OUT_DIR")/output.json" ] || { echo "output.json realpath mismatch - refused"; exit 1; }
[ "$(stat -c %h "$SRC")" = "1" ] || { echo "output.json hardlink count > 1 - refused"; exit 1; }
[ "$(stat -c %s "$SRC")" -le 4194304 ] || { echo "output.json size out of bounds"; exit 1; }
# Reject if anything besides output.json exists in the dedicated out dir.
EXTRA=$(find "$OUT_DIR" -mindepth 1 ! -name output.json -print -quit)
[ -z "$EXTRA" ] || { echo "unexpected entry in out dir: $EXTRA - refused"; exit 1; }
mv "$SRC" "$DEST"
