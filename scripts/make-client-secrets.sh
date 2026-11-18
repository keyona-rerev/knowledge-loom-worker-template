#!/usr/bin/env bash
# make-client-secrets.sh - generate the shared secrets for ONE client install.
# Writes each value to client-secrets/<NAME> (git-ignored, mode 600). Prints
# names only, never values. See CLIENT_INSTALL.md step 3.
set -euo pipefail
cd "$(dirname "$0")/.."
D=client-secrets
mkdir -p "$D"; chmod 700 "$D"
grep -qx "client-secrets/" .gitignore 2>/dev/null || echo "client-secrets/" >> .gitignore
umask 077
rand() { openssl rand -hex 32 | tr -d '\n'; }
for n in DISPATCH_SECRET WORKER_SECRET DISPATCHER_SECRET CLAIM_SEAL_KEY; do
  [ -s "$D/$n" ] || { rand > "$D/$n"; echo "made $n"; }
done
if [ ! -s "$D/CLAIM_SEAL_PRIVATE_KEY" ]; then
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out "$D/CLAIM_SEAL_PRIVATE_KEY" 2>/dev/null
  openssl pkey -in "$D/CLAIM_SEAL_PRIVATE_KEY" -pubout -out "$D/CLAIM_SEAL_PUBLIC_KEY"
  echo "made CLAIM_SEAL_PRIVATE_KEY + CLAIM_SEAL_PUBLIC_KEY (RSA 4096)"
fi
echo "Done. Values are in $D/ - next: CLIENT_INSTALL.md step 4."
