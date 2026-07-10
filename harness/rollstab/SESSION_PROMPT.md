# Seam-clip session prompt (the standing instructions)

Tracked, durable, improvable. This file holds the STABLE instructions only. It asserts
NOTHING time-sensitive: current state (what is solved, what is open) lives in the
`## Status` section of `harness/rollstab/README.md` and the newest handoff, which are
authoritative. If this file and the README status ever disagree about state, the README
is right and this file is stale.

To start a session, paste this ONE line, the SAME every time:

    Read harness/rollstab/SESSION_PROMPT.md and follow it.

That is all that is needed. The default action is to continue the newest handoff's
"Next step". To steer somewhere else on a given session, add a goal after that line
(optional), e.g. "... This session's goal: <one line>."

---

OBJECTIVE (stable): given a fixed initial anchor state and a target seam, ONE-SHOT
compute the controller input sequence that clips Link through it, found ENTIRELY in
the sim, and DTM-verify it.

HARD CONSTRAINTS:
- Full search runs in < 2 minutes. No exceptions.
- Float-perfect: the shipped seq clips 0-ULP in the sim and reproduces live via a
  clean DTM (NEVER advancewith).
- PURE SIM, NO CALIBRATION. The search takes ONLY the static anchor (its seed.json)
  as input and produces the input sequence with no live-Dolphin round-trip in the
  loop. This was the ORIGINAL requirement.

STANDING PRINCIPLE ON CALIBRATION (this is why past sessions drifted):
  A live-calibration / teleport / position-feedback / per-move bias workaround VIOLATES
  the objective. Do NOT add one. If one still exists in the pipeline (e.g. a live
  calibration step), REMOVING it is the priority, not building on it. The root cause it
  papers over is the from-rest idle -> walk entry not being cold-start-faithful in the
  sim; the objective-compliant fix is to MODEL that entry from the anchor seed, not to
  seed it from a live run. Check the README ## Status for where this currently stands.

READ, IN THIS ORDER, before proposing anything or touching code:
  1. harness/rollstab/README.md: the pipeline, run protocol, verification, the
     ## Status section (current state), and the "Dead ends" list.
  2. harness/rollstab/ROADMAP.md: the multi-phase NORTH STAR (toward the Tetra seam
     clip) -- which phase is open and what its live-gated "done" is.
  3. The newest _notes/seam-clip-live-validation-handoff-*.md: this session's starting
     point and next step.
  4. knowledge/strategy/seam-clip-solver.md: why the acceptance region is f32 DUST and
     every candidate must be tested exactly, not against a fitted ribbon.
  5. knowledge/history/seam-clip-dead-ends.md: the full RULED-OUT ledger (sessions 4-9).
Then restate, before editing anything: (a) current state in one paragraph, (b) the
specific goal for THIS session, (c) your plan. If the session message names no goal,
the goal IS the newest handoff's "Next step"; if there is no handoff yet, ask.

DO NOT REOPEN SOLVED WORK. The README ## Status says what is already bit-exact / shipped
/ found-routinely. Do not rewrite the sim model, the solver acceptance test, or the
collision/cut models without a state-level reason. If you believe the frontier is
somewhere other than what the Status + handoff say, state why BEFORE starting.

METHOD REFERENCE (for HOW to be fast + exact, a pattern to absorb, not code to reuse):
tww_sim/land/plan_land/_freeze/roll.py, the SOLVED 1D freeze search. Its pattern is a
cheap monotone predictor (pos_cap) + subtree prune + exact bit-confirm, no table, no
calibration. Any search work must follow that pattern; brute-force sweeping is the
known-slow path that blows the 2-minute budget.

IF YOU MUST CHANGE THE SIM, research in priority order:
  A. Decomp (src/d/, Link's actor + camera are complete): ground truth.
  B. Dolphin breakpoints / ASM / RAM: only if decomp is insufficient.
  C. Guess-and-check / derivation from samples: only if A and B fail, and CONSULT
     DERECK FIRST.
After any 0-ULP sim fix, add a live-data-backed regression test:
  1. memory-capture a live input sequence (xyz, anim frame, facing, proc, ...);
  2. write a sim unit test seeded from that captured source of truth;
  3. enforce 0-ULP on ALL frames.
If unsolved at session end, create the test anyway and let it flag RED.

RESPECT THE DEAD-END LEDGER (knowledge/history/seam-clip-dead-ends.md + README "Dead
ends" + the newest handoff). Do not re-run a ruled-out approach without NEW evidence;
if tempted, first state what changed. When you rule a NEW approach out, APPEND it to
knowledge/history/seam-clip-dead-ends.md. That is what keeps the ledger alive.

STALL RULE: if you get stuck, or are about to spend real effort outside the handoff's
plan, surface it before continuing.

Savestate slot 5 = kaze flat room for roll clips.

When you hit a Dolphin / lookup gotcha with no existing doc, document it (whichever
fits: ../tools/DOLPHIN_CONTROL.md, KB, or memory) before moving on.

END OF SESSION:
  1. If seam-clip behavior changed, update the README ## Status section (a pre-commit
     gate enforces this on any commit touching harness/rollstab/*.py).
  2. Write a handoff using harness/rollstab/HANDOFF_TEMPLATE.md.
  3. Commit. Push to GH only if Dereck asks.

---

FUTURE-WORK NOTES (not this session's scope; here so architecture leaves room. Do NOT
build these until asked):
- Mid-walk sword unsheathe/draw as a transient (its own anim + per-frame displacement),
  not the current static drawn/sheathed flag.
- Body-lean physics: daPy_lk_c::jointBeforeCB body-lean on the MOMI (thigh) joints
  (local_38 = (0, m3516/m3518, m351A) via mDoMtx_QuatConcat) + waist ground-tilt + a
  CLOTCH foot-plant translate; lean angles from velocity-change/turn (~ -8192 * lateral
  accel * factor), clamped +-0x1000 (~22.5 deg).
