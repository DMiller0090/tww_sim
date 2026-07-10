#!/usr/bin/env bash
# Tracked pre-commit gate: seam-clip behavior changes must update the status doc.
#
# The `## Status` section of harness/rollstab/README.md is the single source of truth for
# current seam-clip state (what is solved / open / blocked). It drifts silently when the
# solver code changes without it, which is what made past sessions reopen solved work. So:
# if a commit stages any harness/rollstab/*.py but NOT harness/rollstab/README.md, block.
#
# Scoped by staged path -> fires ONLY on seam-clip solver commits, nothing else.
# Bypass a genuine exception (e.g. a pure refactor) with: git commit --no-verify
set -uo pipefail

staged="$(git diff --cached --name-only)"

if echo "$staged" | grep -qE '^harness/rollstab/.*\.py$'; then
  if ! echo "$staged" | grep -qE '^harness/rollstab/README\.md$'; then
    echo "" >&2
    echo "[rollstab-status] Seam-clip code changed but harness/rollstab/README.md is not in this commit." >&2
    echo "[rollstab-status] Update its '## Status' section (current state / what's solved / open), re-stage it," >&2
    echo "[rollstab-status] and commit again. Genuine exception (pure refactor): git commit --no-verify." >&2
    exit 1
  fi
fi
exit 0
