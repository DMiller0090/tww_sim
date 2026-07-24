# Tetra-push session prompt (the standing instructions)

Tracked, durable, improvable. This file holds the STABLE instructions only. It asserts NOTHING
time-sensitive: current state (what is done, what is open) lives in the `## Plan / status` section of
`harness/tetrapush/README.md` and the newest handoff, which are authoritative. If this file and the
README status ever disagree about state, the README is right and this file is stale.

To start a session, paste this ONE line, the SAME every time:

    Read harness/tetrapush/SESSION_PROMPT.md and follow it.

That is all that is needed. The default action is to continue the newest handoff's "Next step". To
steer somewhere else on a given session, add a goal after that line, e.g.
"... This session's goal: <one line>."

---

OBJECTIVE (stable): from **savestate slot 2** (mid-playback of the real any% TAS DTM
`28_Courtyard_TetraPush`), compute the input sequence that herds **Tetra** into a viable seam-clip
position (a genuine coord in `_generated/tetra_placements.tsv`), found ENTIRELY in the coupled sim and
DTM-verified. This is a ONE-TIME sequence for the real run, not a generalized solver, so a >2-minute
search is fine. Two milestones, in order:
  1. the sim reproduces the ~45 hand-performed push frames after state 2 **bit-exact** (Link + Tetra);
  2. the planner: state-2 config to the input sequence that lands Tetra on a genuine coord AND sets up
     the matching final roll entry (the two are coupled; there is runway from state 2 to steer both).
     The objective is **FRAME-MINIMAL -- the OPTIMAL, better-than-human solution** (`[[tetrapush-frame-minimal]]`):
     fewest total frames, the recorded human TAS a lower bound to BEAT, not the proc-9 slide and not
     a mere replica of the human cadence.

HARD RULES:
- **0-ULP is the bar**, validated against a locked live capture, never offline plausibility.
- **Decomp-first** (`[[decomp-first-not-brute-force]]`): read `tww/src/d/actor/d_a_player_main.cpp` /
  the JP `framework.map` for exact thresholds before live-bisecting. Breakpoint the JP address, not the
  US decomp comment (`[[jp-vs-us-decomp-addresses]]`).
- **When live disagrees with the sim, DIFF per-frame (BOTH actors), never guess inputs**
  (`[[tetra-clip-solved-live]]`). Log the movie per frame; the divergence frame names the bug.
- **No calibration / no live-feedback in the loop.** The planner takes only the static state-2 seed;
  pure sim, DTM-verified out of band.

READ, IN THIS ORDER, before proposing anything or touching code:
  1. `harness/tetrapush/README.md`: the setup, the push mechanic, the untarget-brakeslide decomp
     recipe, the addresses, and the `## Plan / status` (current state).
  2. The newest `_notes/tetrapush-handoff-*.md`: this session's starting point and next step.
  3. Memories: `[[courtyard-tetra-push]]` (this work), then `[[tetra-push-model]]`,
     `[[cc-push-stepper]]`, `[[tetra-follow-model]]`, `[[tetra-clip-solved-live]]`,
     `[[turnaround-clip-followenabled]]`.
Then restate, before editing anything: (a) current state in one paragraph, (b) the specific goal for
THIS session, (c) your plan. If the session message names no goal, the goal IS the newest handoff's
"Next step".

THE CURRENT BLOCKER (model gap): read it off the README `## Plan / status` -- the newest `[~]`/`[ ]`
box IS the live blocker (this file stays stable and never names a specific one, since the blocker moves
every session). Whatever it is: model it **decomp-first**, and keep every already-bit-exact land tech
unchanged (`tests/test_land_goldens.py` must stay green).

METHOD REFERENCE (how to be fast + exact, a pattern to absorb): the seam-clip `solver` /
`tww_sim/land/plan_land` (a cheap monotone predictor + subtree prune + exact bit-confirm, no table, no
calibration). Brute-force sweeping is the known-slow path.

TOOLING: `capture_push.py` (ground truth from slot 2 to `fixtures/courtyard_push_state2.json`),
`find_tetra.py` (live Tetra locator via the DMC walk). The coupled dynamics reuse
`harness/rollstab/cc_stepper` + `tww_sim/core/{cc_push,npc_zl1}` + `tww_sim/land`.

LIVE SETUP: slot 2 = the courtyard push mid-DTM, in the pipe-enabled research build
(`Dolphin-Zelda-TAS-Edition/.../Release`; `harness/dolphin_env.ensure_running` launches + boots it if
down). Never drive two Dolphins at once. Read `../tools/DOLPHIN_CONTROL.md` before touching Dolphin.
When you hit a Dolphin/lookup gotcha with no existing doc, document it before moving on.

END OF SESSION:
  1. Update the README `## Plan / status` section.
  2. Write a handoff using `harness/tetrapush/HANDOFF_TEMPLATE.md` to
     `_notes/tetrapush-handoff-<date>-sessionN.md`.
  3. Commit. Push to GH only if Dereck asks.
