# The roll's body lean is written by its own dispatch frame, so it is an axis you choose

**Answers:** What body lean do I build a roll's razor schedule at - the walk's `m351C`, the herd's, or
something else? Why did a terminal that solved genuine stop clipping when I re-measured it? Is the
lean a constant of a corner or a knob? How do I keep a native fast path from handing me a stale field
as if it were a measurement?
**Status:** measured session 148 on the Courtyard ladder, by simulation rather than from the
docstring: a real `clip_roll.fire` roll's per-frame `_draw_lean` is reproduced exactly by
`entry_search.fast_schedule` seeded at the post-entry `m351C` and by no other seed. The stale-mirror
half is fixed and gated in
[`tests/test_freerun_native.py`](../../tests/test_freerun_native.py) (`m351C` and `draw_lean` added to
the 0-ULP allowlist). The claim this replaces is in
[history/the-delivered-lean-was-an-unsynced-mirror.md](../history/the-delivered-lean-was-an-unsynced-mirror.md).
**Source:** [`tww_sim/land/state.py`](../../tww_sim/land/state.py) (`_set_move_slant_angle`,
`_sync_from_core`), [`harness/tetrapush/from_f0.py`](../../harness/tetrapush/from_f0.py)
(`_step_native`), [`entry_search.py`](../../harness/tetrapush/entry_search.py) (`lean_at_roll`,
`fast_schedule`). Probes `_notes/s148_lean_census.py`, `_notes/s148_atom.py`.
Constants: [../reference/constants.md](../reference/constants.md).

---

## The seed is the post-ENTRY `m351C`, and the dispatch frame writes it

A roll is not a MOVE, so `_set_move_slant_angle` takes its decay branch every roll frame and the lean
runs down ([../mechanics/roll-lean-decay.md](../mechanics/roll-lean-decay.md)). What that page does not
say is where the roll *starts* from, and the answer is not the walk.

The A press acts a frame late, so the roll's **first frame is still MOVE** - and a MOVE frame above the
speed threshold WRITES `m351C` from the turn it is making. Measured on rung 3 of the Courtyard ladder,
walking in at `m351C` **0**:

| frame | proc | `m351C` in → out | `_draw_lean` |
|---|---|---|---|
| 1 | MOVE | 0 → **200** | 0 |
| 2 | FRONT_ROLL (entry) | 200 → **130** | 100 |
| 3 | FRONT_ROLL (schedule step 0) | 130 → 85 | **65** |

`fast_schedule` consumes its argument as the lean at **schedule step 0**, which is the roll's *third*
frame - the entry frame runs one full roll step before it
([`clip_roll`](../../harness/tetrapush/clip_roll.py): step `k` is roll frame `k + 2`). So the seed is
the value *after* the entry frame, which is exactly `lean_at_roll`'s own contract. Seeded at **130** the
analytic draws `[65, 42, 28, 18, 12]` reproduce the simulated roll frame for frame; seeded at the walk
end (0) they are all zero, and at 648 they read `[324, 211, 137, 89, 58]`.

**So the lean is a product of the roll's own dispatch - how far that one frame turns - not a property
of the corner, the herd, or the walk endpoint.** Two plans arriving at the same place with different
approach facings enter at different leans, and the same plan re-aimed enters at a different one:
across one at-cap cloud the dispatch wrote leans from -130 to +240.

That makes it an **axis**, and a live one, because
[clip-band-per-lean.md](clip-band-per-lean.md) measured the acceptance band as a *jagged* function of
lean - some carry the full band, some collapse to a single f32 value. "Barren at the lean this aim
happens to write" is therefore not "barren"
([seam-clip-solver.md](seam-clip-solver.md) - infeasibility needs proof). Fire the aim, read the
entry-frame `m351C`, solve **there**; and vary the approach when you want a different one.

## A field a fast path does not sync back reads as a measurement that never moved

The reason this went four sessions unnoticed is worth more than the number.

`from_f0._step_native` copied seven fields back from the native core and not `m351C`; the same hole was
in `LandState._sync_from_core`. The **physics never diverged** - the core's own `m351C` matches the
Python path bit-for-bit - and nothing inside the sim reads the mirror, because the core uses its own
copy. So the staleness is invisible until a *harness* script reads it. One did, across all 49 ladder
rungs, and got **one distinct value** - the state-2 seed - which was recorded as "the delivered lean"
and became the default every terminal was built at.

Two mechanical checks, both cheap:

- **Unanimity across objects that have no reason to agree is a tell, not a finding.** Forty-nine
  independent herds do not land on one `m351C`. This is
  [clip-lottery-draws.md](clip-lottery-draws.md)'s "print the IDENTITY of what you counted", asked of a
  constant instead of a draw.
- **A native gate that compares an allowlist can only find divergence in fields somebody listed.** The
  0-ULP gates were green throughout and were right to be. Sync every field a caller can *see*, not the
  ones the step happens to need, and put them in the allowlist - a field nobody listed is a field
  nobody can be wrong about out loud.

## See also

- [clip-band-per-lean.md](clip-band-per-lean.md) - why the band must be measured at the draw's own
  lean, and why one configuration's band overstates a population's.
- [../mechanics/roll-lean-decay.md](../mechanics/roll-lean-decay.md) - the decay itself, and the
  narrower claim it licenses (depth at a *solved* configuration barely moves).
- [dispatchable-is-not-clipping.md](dispatchable-is-not-clipping.md) - the terminal family this
  re-points, and the rule it already states about using a window one object away from where it was
  measured.
