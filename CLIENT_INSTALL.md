# Client install: the AI worker on the client's own accounts

The installer follows the setup wizard, not this file:
https://insight-forge-setup-wizard.netlify.app (steps 20-25 and 29 cover
this worker). This file is the reference for what those steps do.

Each client gets a private copy of this worker on the client's own GitHub
account, signed in with the client's own Claude Pro plan. Drafts and images
are written by Claude Code on that plan. Nothing runs on ReRev's accounts. No
AI API key is used anywhere.

## What the installer does (wizard steps)

1. **Copy** this repo to the client's GitHub as `insightforge-worker`
   (Private), with GitHub's import page.
2. **Claude sign-in (the client):** `claude setup-token`. The client signs in
   with their own Claude Pro account. The token lasts one year (Anthropic's
   authentication guide, checked Nov 17, 2026).
3. **Two setup tokens**, made in the client's accounts:
   - GitHub fine-grained token on `insightforge-worker` only: Contents RW,
     Secrets RW, Actions R. It also serves as the app's wake-up token.
   - Supabase access token.
4. **Three repo secrets:** `CLAUDE_CODE_OAUTH_TOKEN`, `SETUP_GH_TOKEN`,
   `SUPABASE_ACCESS_TOKEN`.
5. **Connect button:** Actions > connect-install > Run workflow, with the
   project ref, logo URL and two fonts. It:
   - bundles the logo and fonts for the offline image renderer
     (`scripts/set-client-brand.py`) and commits `render/`,
   - generates every shared secret inside the run (masked, never shown),
   - stores the worker-side secrets here: `DISPATCH_SECRET`, `WORKER_SECRET`,
     `SUPABASE_FN_BASE`, `CLAIM_SEAL_KEY`, `CLAIM_SEAL_PUBLIC_KEY`,
     `CLAIM_SEAL_PRIVATE_KEY`,
   - stores the app-side secrets in the client's Supabase: `DISPATCHER_SECRET`,
     `DISPATCH_SECRET`, `WORKER_SECRET`, `DISPATCH_GITHUB_TOKEN`, `WORKER_REPO`,
     `WORKER_TOKEN_EXPIRES_AT`, `TENANT_USER_ID` (looked up: the one login),
     `VISUALS_ENABLED=true`.
   Re-running is safe: it regenerates both sides together.
6. **Budget cap:** GitHub Actions budget $0 with stop-usage on. Measured
   Nov 17: about 2 cents of compute per draft, inside the $12/month included.

## Yearly renewal

The client repeats `claude setup-token`. Paste the new token over
`CLAUDE_CODE_OAUTH_TOKEN`, renew the setup tokens if they expired, and run
connect-install again with the new date.

## Without the button (manual fallback)

`scripts/make-client-secrets.sh` writes the same secrets to a git-ignored
`client-secrets/` folder. Set them with `gh secret set` and
`npx supabase secrets set` using the names in step 5.

## Terms note

Anthropic's terms allow a person to sign in to the unmodified Claude Code app
with their own subscription. Here, each client runs Claude Code on their own
plan, on their own GitHub - the closest fit to "ordinary, individual usage".
Anthropic has not published a statement about a CI worker for a content
pipeline specifically. Sources: setup-wizard/SUBSCRIPTION_BUILD.md in
keyona-rerev/knowledge-loom-prismm.
