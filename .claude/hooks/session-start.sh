#!/bin/bash
# VBT SessionStart hook. Two jobs, both so a fresh Claude Code (web) chat is ready with
# ZERO manual setup or pasting:
#   1. Inject the trunk workflow as session context (main is the one branch; sync first,
#      land back on main last) — the authoritative rule that stops parallel chats forking.
#   2. Install the Python deps the analysis/tests/CV pipeline needs (remote/web only;
#      idempotent + benefits from container-state caching).
# Synchronous (no async): guarantees the context + deps are present before the agent starts.
# stdout MUST be only the JSON below, so all install chatter is redirected away.
set -uo pipefail

# --- 2) deps: web/remote sessions start from a bare clone; install so tests/CV just run ---
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  {
    pip install -q -r "${CLAUDE_PROJECT_DIR:-.}/analysis/requirements.txt"
    pip install -q -r "${CLAUDE_PROJECT_DIR:-.}/analysis/requirements-video.txt"
  } >/dev/null 2>&1 || true
fi

# --- 1) workflow context: printed to stdout -> added to the session's context ---
cat <<'CTX'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"VBT branch workflow (authoritative, see CLAUDE.md > Branch & sync protocol): `main` is the ONE trunk and the GitHub default branch. FIRST ACTION this session: sync it -> `git fetch origin --prune && git checkout main && git pull --ff-only origin main`. If the platform dropped you on an auto-created claude/<slug> branch, rebase it onto origin/main (`git checkout -B <slug> origin/main`) or just work on main. Do routine work (data ingest, docs, small fixes) on main directly and push main; use a short-lived session/<topic> branch ONLY for larger/riskier work and merge it back to main the SAME session. LAST ACTION: land on main and push it — never end with work stranded on a side branch (that is what caused past dataset forks). Only ONE session edits dataset/ at a time; the ingest tools are idempotent (strip-by-set_id then rewrite), so re-running on latest main is the safe way to reconcile. Do NOT open PRs unless asked; do NOT put the model identifier in commits."}}
CTX
