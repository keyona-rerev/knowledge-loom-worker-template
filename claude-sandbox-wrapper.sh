#!/usr/bin/env bash
# claude-sandbox-wrapper.sh - TRUSTED host-side interposition executable for
# the pinned claude-code-action's supported input path_to_claude_code_executable.
# The Agent SDK spawns THIS script; it re-execs the real Claude Code CLI inside
# an enforced child namespace (docker on the runner, bwrap for local proofs):
#   - explicit env allowlist (OAuth + nothing else by default)
#   - NO GITHUB_* file commands, NO ACTIONS_* runtime/cache/results/OIDC vars
#   - fresh pid/mount namespace + fresh /proc, non-root uid, scratch HOME
#   - read-only /src (repo + input_snapshot), writable ONLY the dedicated out dir
# NOTE: /tmp noexec for the real bun-compiled CLI is NOT proven by the fake
# CLI; compatibility is deferred to the real-binary proof, never assumed.
# Stdio passes through untouched, so the SDK control protocol and the message
# stream (the host-captured transcript) are unaffected.
set -euo pipefail
MODEL_WORKDIR="${MODEL_WORKDIR:?trusted caller must set the dedicated out dir}"
MODEL_SRC_DIR="${MODEL_SRC_DIR:-$PWD}"
CLAUDE_BIN="${CLAUDE_BIN:-/usr/local/bin/claude}"
BACKEND="${SANDBOX_BACKEND:-docker}"
# Explicit child-env allowlist. Additions require review sign-off.
ALLOW_ENV=(CLAUDE_CODE_OAUTH_TOKEN)
if [ "$BACKEND" = "docker" ]; then
  args=( run --rm -i --init
    --network "${MODEL_NETWORK:-bridge}"
    --cap-drop ALL --security-opt no-new-privileges --pids-limit 512
    --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m
    --tmpfs /home/claude:rw,nosuid,size=128m
    --user 1000:1000 -e HOME=/home/claude
    -v "$MODEL_SRC_DIR:/src:ro" -v "$MODEL_WORKDIR:/work:rw" -w /src )
  # QA only: a host-provided CLI (fake) can be ro-mounted over the image path.
  if [ -n "${CLAUDE_BIN_HOST:-}" ]; then args+=( -v "$CLAUDE_BIN_HOST:/opt/claude:ro" ); fi
  for v in "${ALLOW_ENV[@]}"; do [ -n "${!v:-}" ] && args+=( -e "$v" ); done
  exec docker "${args[@]}" "${CLAUDE_RUNNER_IMAGE:?image ref required}" "$CLAUDE_BIN" "$@"
else
  # bwrap: identical isolation semantics for local/offline proofs.
  args=( --unshare-user --unshare-pid --die-with-parent --new-session
    --proc /proc --dev /dev
    --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 --ro-bind /bin /bin --ro-bind /sbin /sbin
    --ro-bind "$MODEL_SRC_DIR" /src
    --bind "$MODEL_WORKDIR" /work
    --tmpfs /home/claude --tmpfs /tmp
    --clearenv --setenv HOME /home/claude --setenv PATH /usr/local/bin:/usr/bin:/bin
    --chdir /src --uid 1000 --gid 1000 )
  if [ -n "${CLAUDE_BIN_HOST:-}" ]; then args+=( --ro-bind "$CLAUDE_BIN_HOST" /opt/claude ); fi
  for v in "${ALLOW_ENV[@]}"; do [ -n "${!v:-}" ] && args+=( --setenv "$v" "${!v}" ); done
  exec bwrap "${args[@]}" "$CLAUDE_BIN" "$@"
fi
