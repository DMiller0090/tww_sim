# The "83% of draws are dead" share was measured from one Newton seed (sessions 81-93)

**status: historical** - superseded by
[../strategy/clip-band-per-lean.md](../strategy/clip-band-per-lean.md) (session 94). Kept because the
*shape* of the finding was right and load-bearing for a dozen sessions, and because the way it was wrong
is the reusable lesson.

**What was claimed (session 81, carried to session 93).** The acceptance band is a jagged function of the
roll's body lean, and a large share of the leans a real walk-in arrives at have **nothing genuine at any
entry on the locus at all**. Measured over one reference pass: ~2000 distinct leans across 43596
candidates, **83% of the pass's draws dead**, its 72 "near-misses" really 6. Session 93 then applied the
same reading to cell 2553 - 180 candidates inside `BAND_PROBE`, 0 converted - and concluded that every
one of them "lands at a lean whose band has no usable width", which closed the last cell of the
exit-angle axis that a 4-frame plan can reach.

**What stands.** The band really is a function of the lean as well as the facing, thrust and momentum,
and it really is jagged rather than signed: at a fixed configuration, widths measured across the fan's
leans run from 0.0 to ~5.9e-5 with no monotone structure. Scoring a whole pass at one configuration's
lean-0 band overstates `E[hits]`, and every near-miss must be priced at its own lean's band. All of that
is why `BandTable` exists and none of it moved.

**What was wrong, and it was the measurement rather than the mechanism.** "Nothing genuine at any entry
on the locus" was never measured over the locus. `configuration_band` Newtons the entry to the residual
zero **from a seed**, and `BandTable` handed it one seed for every key - the single global `ref_entry`.
The locus moves with the lean, so that seed can be on the curve at lean 0 and off it entirely at another
lean, and the function then reports `no leverage` or `no genuine on the residual zero` about a station
while the caller records it about the configuration. Exactly the defect fixed at the *qualification* in
session 90 (`escalate` -> `locus_scan`) and session 92 (`curve` -> `curve_scan`), one level down in the
ranking, untouched by both.

**The correction, measured (session 94).** With a seed ladder - the global ref, then the configuration's
own qualified station, then `locus_scan`/`curve_scan` from it - cell 2553 / thrust 15 goes from **0 of its
24 heaviest fan leans usable to 20 of 24**; re-running session 93's own frame-floor pass over the *same*
779130 candidates turns "180 dead-tail, 0 near, E[hits] 0.000" into **34 near-misses and E[hits] 0.079**;
and **10360 of the 15968 rows** in the band cache were negatives of the one-seed kind. The tell that
settles it needs no argument: asked for the band at the configuration of the clip that was delivered to
console and worked (facing 40841, thrust 15, lean 64761), the one-seed table answers `no genuine on the
residual zero`.

**The lesson.** A dead band is silent by construction - `genuine` comes from the sweep, so no clip is
ever suppressed and nothing looks broken; the pass just reports zero near-misses and zero expected hits
for a configuration that has both, which reads as "stop buying density here". So when a scope-level
verdict gets escalated because it was argued from one station, **ask the same question of every ranking
input that shares the machinery** - the fix does not propagate on its own, and the artifact that caches
the old answers will keep serving them past the patch.

## See also

- [../strategy/clip-band-per-lean.md](../strategy/clip-band-per-lean.md) - the current truth: the
  ladder, its order-independence, the cache hygiene, and why width ranks and never filters.
- [entry-search-one-seed-negative.md](entry-search-one-seed-negative.md) - the same defect one level up,
  at the qualification, and the half of the facing window it hid.
- [../strategy/clip-lottery-draws.md](../strategy/clip-lottery-draws.md) - the draw accounting the dead
  share belongs to.
