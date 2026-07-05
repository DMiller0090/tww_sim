#!/usr/bin/env bash
# Tracked pre-commit gate: keeps the knowledge base structurally sound and non-stale.
# Runs the fast, deterministic KB doc tests (structure/link hygiene + Source-path staleness)
# whenever a commit touches KB pages OR code (a code rename can orphan a doc's Source: ref).
#
# Fast (~0.3s), no Dolphin, no LLM. Bypass a genuine exception with: git commit --no-verify
set -uo pipefail
root="$(git rev-parse --show-toplevel)"

# Only run when the commit could affect the KB: any knowledge/ page, the KB tests, or any .py
# (code moves are what break Source: references).
staged="$(git diff --cached --name-only)"
if ! echo "$staged" | grep -qE '^(knowledge/|tests/test_kb_|.+\.py$)'; then
  exit 0
fi

cd "$root" || exit 0
if ! command -v python >/dev/null 2>&1; then
  echo "[kb-doc-gate] python not found; skipping (install python to enable the KB gate)." >&2
  exit 0
fi

out="$(python -m pytest tests/test_kb_hygiene.py tests/test_kb_links.py -q 2>&1)"
status=$?
if [ "$status" -eq 5 ]; then
  # pytest exit 5 = no tests collected (e.g. pytest missing / not a test env) -> don't block.
  echo "[kb-doc-gate] KB tests not collected; skipping (is pytest installed?)." >&2
  exit 0
fi
if [ "$status" -ne 0 ]; then
  echo "" >&2
  echo "[kb-doc-gate] Knowledge-base doc gate FAILED — fix before committing (or --no-verify):" >&2
  echo "$out" >&2
  exit 1
fi
exit 0
