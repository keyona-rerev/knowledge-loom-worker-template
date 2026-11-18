# knowledge-loom-worker template

Claude Code worker for Prismm Knowledge Loom draft generation. Runs on the
owner's Claude subscription via claude-code-action + CLAUDE_CODE_OAUTH_TOKEN.
Dispatched via signed repository_dispatch from the loom's Supabase functions.
No client data in logs: prompts come from the queue snapshot, never workflow input.

Draft images: the same worker writes the graphic's HTML and renders the PNG
in a bubblewrap sandbox (render/), on the same subscription. No API key.

New client? Follow CLIENT_INSTALL.md: each client gets a private copy of this
worker on their own GitHub account, signed in with their own Claude Pro plan.
