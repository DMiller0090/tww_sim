#!/usr/bin/env bash
# Tracked pre-commit gate: keeps the tww_sim SOURCE tree on-structure (companion to kb-doc-gate.sh).
# Runs the fast, deterministic code-hygiene tests (no stale superswim.* refs; no oversized module)
# whenever a commit touches tracked tww_sim/**.py or .pyx.
#
# Fast (~0.1s), no Dolphin, no LLM. Bypass a genuine exception with: git commit --no-verify
set -uo pipefail
root="$(git rev-parse --show-toplevel)"

# Only run when the commit touches tww_sim source (where the two drift modes live).
staged="$(git diff --cached --name-only)"
if ! echo "$staged" | grep -qE '^tww_sim/.+\.(py|pyx)$'; then
  exit 0
fi

cd "$root" || exit 0
if ! command -v python >/dev/null 2>&1; then
  echo "[code-hygiene] python not found; skipping (install python to enable the gate)." >&2
  exit 0
fi

out="$(python -m pytest tests/test_code_hygiene.py::test_no_stale_package_refs tests/test_code_hygiene.py::test_no_oversized_modules -q 2>&1)"
status=$?
if [ "$status" -eq 5 ]; then
  echo "[code-hygiene] tests not collected; skipping (is pytest installed?)." >&2
  exit 0
fi
if [ "$status" -ne 0 ]; then
  echo "" >&2
  echo "[code-hygiene] Code hygiene gate FAILED - fix before committing (or --no-verify):" >&2
  echo "$out" >&2
  exit 1
fi
exit 0
