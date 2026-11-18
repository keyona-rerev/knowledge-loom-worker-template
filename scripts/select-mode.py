#!/usr/bin/env python3
# select-mode.py - TRUSTED-side run-mode selection (verify-claim job).
# Fixed allowlist, fails closed. For draft-visual jobs it also binds the
# render canvas from the CLAIM CONTEXT (input_snapshot.context.canvas) -
# never from anything the model later writes. Emits mode.json.
import json, os, sys

snap = json.load(open("input_snapshot.json"))
mode = "default"
canvas = None
if isinstance(snap, dict) and snap.get("kind") == "interactive":
    ik = snap.get("interactiveKind")
    if ik == "discover-sources":
        mode = "discover"
    elif ik == "draft-visual":
        mode = "visual"
        ctx = snap.get("context") or {}
        c = ctx.get("canvas") or {}
        w, h = c.get("w"), c.get("h")
        # Fail closed: a visual job without a claim-context canvas cannot run.
        if not (isinstance(w, int) and isinstance(h, int) and 100 <= w <= 4096 and 100 <= h <= 4096):
            sys.exit("visual job without a valid claim-context canvas")
        if not ctx.get("visual_id") or not ctx.get("source_hash"):
            sys.exit("visual job without bound visual_id/source_hash in claim context")
        canvas = {"w": w, "h": h}
with open("mode.json", "w") as f:
    json.dump({"mode": mode, "canvas": canvas}, f)
with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    f.write("mode=" + mode + "\n")
print(f"mode={mode}" + (f" canvas={canvas['w']}x{canvas['h']}" if canvas else ""))
