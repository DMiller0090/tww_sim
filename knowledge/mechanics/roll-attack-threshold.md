# The A-press is only a roll above a stick threshold

**Answers:** Why did my A-press not roll on console when the sim rolled? What deflection does a roll
need? What does the game do with an A-press that is too shallow? Which searches owe this gate?
**Status:** validated live, from both sides. One console delivery pressed A at stick magnitude
0.5705 and Link did not roll (`fixtures/courtyard_attack_gate_s88_console.json`); another at 0.889
rolled (`fixtures/courtyard_entry_s86_console.json`). The value between them is the shipped HIO
constant, not a fit. Gate: `tests/test_attack_threshold.py`.
**Source:** `daPy_lk_c::setDoStatusBasic` (`d_a_player_main.cpp:2220` ATTACK, `:2218` PUT_AWAY),
`checkNextActionFromButton` (`:4318` -> `procFrontRoll_init`), `daPy_HIO_basic_c0::m`
(`d_a_player_HIO_data.inc:4`, `field_0x1C`).
Code: [`tww_sim/land/hio.py`](../../tww_sim/land/hio.py) (`ATTACK_MSD_MIN`),
[`tww_sim/land/state.py`](../../tww_sim/land/state.py) (the dispatch + `attack_blocked`), and the
native twin `_anmc.pyx` (both of its dispatch sites).

---

## The gate

An A-press does not reach `procFrontRoll_init` directly. It reaches it only through a **do-status**,
and `setDoStatusBasic` decides that status from the stick:

    fVar1 = mBasic.field_0x1C                                  # 0.75; * mMove.field_0x80 (0.5) if heavy
    ...
    else if (mStickDistance > fVar1)   dComIfGp_setDoStatus(dActStts_ATTACK_e);      # :2220

and `checkNextActionFromButton` turns **only** `dActStts_ATTACK_e` into a roll (`:4318`). So the roll
needs three things, not two: a grounded locomoting proc (`MOVE`/`ATN_MOVE`), L off, **and
`mStickDistance > 0.75`**.

At or below 0.75 the same press takes the branch above it and becomes `dActStts_PUT_AWAY_e` (`:2218`)
- Link **sheathes the sword** and keeps walking. Nothing rolls, nothing is pushed.

| deflection | status | proc |
|-----------|--------|------|
| `msd > 0.75` | `dActStts_ATTACK_e` | `FRONT_ROLL` |
| `msd <= 0.75` | `dActStts_PUT_AWAY_e` | the walk continues, sword goes away |
| L held, stick off-forward | `dActStts_JUMP_e` | sidehop / backflip |

The threshold cuts **between two deliverable byte pairs** - `(181,157)` decodes to 0.749943 and
`(74,102)` to 0.750400 - so it is a real edge in the input alphabet. No byte pair decodes to exactly
0.75, so the strictness of `>` is taken from the decomp and cannot be settled by delivery.

## What the model does with a refused press

The sheathe is not modelled (it is a proc of its own). `LandState` latches
**`attack_blocked`** instead, the same way a wall-suppressed roll latches `sidle_blocked`: the roll
does not fire, the flag is sticky, and a planner rejects the input stream rather than believing a
roll happened. Both dispatch sites of the native `LandCore` carry the same gate, or the search and
its own reference disagree about which candidates exist.

## Why a search owes it, and what it cost

The 0.05 floor in the model is the **locomotion** test (`msd > 0.05` = "is the stick pushed at all"),
which appears all over `checkNextMode`. Using it for the roll made every aim look rollable, and an
aim's magnitude is otherwise irrelevant to a roll: the roll's speed comes from the pre-roll `speedF`
and `_roll_init` snaps facing to the latched target whatever the deflection. That is exactly why the
alphabet was widened to the whole decoded-angle grid and why the mistake survived: it is true about
the roll and false about **getting** the roll. See
[../history/aim-alphabet-whole-grid.md](../history/aim-alphabet-whole-grid.md).

Consequence for the Courtyard entry search: the aim alphabet's atom is a decoded angle, represented
by the first byte pair in grid order, which is typically a shallow interior one. Filtered to pairs
that dispatch (`two_roll.roll_aim_fan`) the seam window's alphabet goes 81 aims / 49 decoded angles
-> **60 / 45**, and the angle 40834 drops out entirely because **no** byte pair reaching it clears
0.75.

**And that costs the search nothing, which session 89 had to re-run a pass to find out.** The
physical atom is not the angle, it is the **sine-table cell** ([clip-entry-search.md](../strategy/clip-entry-search.md)):
40834 and 40841 are both cell 2552, so dropping the angle only moves the cell's representative -
from `(95,168)` msd 0.5705, which sheathes, to `(82,186)` msd 0.9817, which rolls. Re-run with the
gate actually reaching the pass, the population is the same 81 scorings at the same entries and
residuals, **0 of them carry an unrollable aim** (against 57), all 55 draws confirm, and the frame
floor is back at **4**. Session 88's "36 of the 55 are dead" was a property of the PINNED ROW - the
list had been re-confirmed against the old representative - and not of the candidates.

**Rule:** an input the search emits must be checked against the dispatch it assumes, not only against
the physics that follows it. `confirm_entry` "confirms with a real A-press" - and confirmed 36
unrollable candidates, because the engine it replays on shared the missing gate.

## See also

- [land-movement.md](land-movement.md) - the land index; the roll's own physics.
- [../strategy/search-prune-the-dispatch.md](../strategy/search-prune-the-dispatch.md) - the prune a
  planner owes at the dispatch frame.
- [../reference/constants.md](../reference/constants.md) - the canonical value.
- [../history/aim-alphabet-whole-grid.md](../history/aim-alphabet-whole-grid.md) - the overturned
  "every aim in the window fires the roll".
