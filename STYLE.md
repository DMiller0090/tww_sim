# Comment, Commit & Naming Style

Follow this so new code reads like the surrounding tww_sim code — terse, factual, about the
*why* — not like generated boilerplate. The codebase's value is its decomp-grounded physics
rationale; comment to preserve that, not to narrate the obvious.

---

## 1. Mechanics

- Python `#` line comments for inline rationale. **Module/class/function docstrings (triple-quoted)
  are the right home for longer "what this is / how to use it" prose** — they are not gated and
  match the existing files (see `tww_sim/swim/sim.py`, `tests/golden_harness.py`).
- 4-space indent; ~100-char lines (`.editorconfig` enforces). Wrap long `#` comments across lines.
- No new copyright/header banners on files.

## 2. Long comment? Promote it to the knowledge base

A comment that needs more than ~2 lines is usually explaining *mechanics or a derivation*, not a
local *why*. Prefer to move that explanation into the knowledge base (the owning page under
`knowledge/`; start at `knowledge/README.md`) and leave a one-line pointer in the code:

```python
# release uses the looped SWIMWAIT frame, not a raw add; see knowledge/mechanics/neutral.md
```

- **Why:** code stays scannable; the mechanics live in one discoverable, cross-referenced place;
  the same explanation stops drifting across several files; the knowledge base stays the single
  source of truth.
- **Trade-off:** a pointer is less immediate than an inline paragraph and can drift. Mitigate by
  pointing at a *specific section* (not just a file), keeping genuinely-local one-line gotchas
  inline, and treating the knowledge base as authoritative — if the code and a doc disagree, the
  doc wins and the code gets fixed. A tight multi-line inline comment is still fine for an invariant
  a reader MUST see at that exact line (e.g. an f32 op-order caveat).

The pre-commit gate flags added `#` blocks over two lines as a nudge to apply this rule — promote
to the knowledge base, tighten to one line, or (rarely) bypass with `git commit --no-verify`.

## 3. Voice & tone

- **Explain *why*, or a non-obvious *consequence* — not the obvious *what*.** Good:
  `# x598 scramble amplifies the sub-ULP oldframe error ~600x`. Bad: `# loop over the frames`.
- **State facts, present tense, declaratively.** Describe how the game/code behaves.
- **Cite the ground truth** for physics claims where it helps (a `knowledge/` page, a decomp
  file/line, or a Claude memory).
- **No emoji. No decorative dividers / ASCII art. No restating the function name.**

## 4. Boilerplate tells to avoid

These read as machine-generated; don't write them:

- ❌ Change-log / conversational comments: `# Added this to fix the bug`, `# NEW:`, `# Updated to...`.
  Comments describe the code as it *is*; version control records history.
- ❌ Restating code in prose: `# set foo to true`, `# increment the counter`, `# return the result`.
- ❌ Tutorial padding: `# First, we...`, `# Next, ...`, `# Finally, ...`, `# Note that this is
  important because...`.
- ❌ Hedging / filler: `# this should probably work`, `# basically`, `# essentially`.
- ❌ Manufactured `@param`/`@return` doc-blocks on trivial functions. A short one-line docstring or
  a `# NOTE:` above a tricky function is the norm here.
- ❌ Over-explaining self-evident code to look thorough. When in doubt, write less.

## 5. Tag markers

Use this small, consistent set verbatim — uppercase tag, colon, space:

| Tag | Use |
|-----|-----|
| `# TODO:` | Known future work. Optionally scoped: `# TODO(planner):`. |
| `# FIXME:` | Known-wrong code that works for now. |
| `# HACK:` | Deliberate ugly workaround. |
| `# NOTE:` | Subtle precondition / ordering / x598-sensitivity caveat the reader must know. |
| `# WARNING:` | Stronger caveat. |
| `# XXX:` | Rare; "this is suspect". |

Don't invent new tags (`# REVIEW:`, `# IMPORTANT:`).

## 6. Commits, branches, PRs

- **Commit / PR subject:** `Component: Imperative, sentence-case summary` — e.g.
  `Tests: Vendor cold-start slate and load it by path`, `Repo: Reorganize into shareable package`.
  The component is the area (`Sim`, `Planner`, `Tests`, `Docs`, `Repo`, `Harness`). No
  Conventional-Commits `feat:`/`fix:` prefixes; no trailing period; no co-author trailers. Bodies
  are optional — add one only when the *why* is non-obvious; keep it to a few sentences, never a
  line-by-line restatement of the diff.
- **Branch names:** `author/topic-in-kebab-case`, e.g. `dmiller/repo-reorg`. No ticket numbers.

---

### One-line summary

Write terse, present-tense `#` comments that explain *why* not *what*; put longer mechanics in the
knowledge base with a one-line pointer; use `TODO/FIXME/HACK/NOTE/WARNING` verbatim; never leave
change-log narration or restate-the-code filler.
