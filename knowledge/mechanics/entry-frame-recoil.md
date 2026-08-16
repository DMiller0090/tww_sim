# The roll-dispatch frame recoils off Tetra - and the fan's entry prediction must model it

**Answers:** Why did a fan hit that swept genuine fail `confirm_entry` with every walk flag green
but `entry` off by 5-8 u? Is a "0 genuine" from a herd whose walk ends NEAR Tetra trustworthy?
What does the entry frame actually do when Link is still inside her Co disc, and whose pose does
its CC resolve use? Why did the same fan pass the console rediscovery 8/8 yet mint 4 fictional
genuine on rung06?
**Status:** proven 0-ULP offline (session 168) forward on 5 engine-measured plans off the
converted rung06-w05 herd plus cross-cell aim-independence; console-clip inertness engine-checked
(centre 184.5 u out, correction a no-op). Gated `tests/test_entry_recoil.py` against
`fixtures/courtyard_entry_recoil_s168.json`. Not yet live/DTM-confirmed.
**Source:** s167rung06 overnight post-mortem (`_notes/s168_queue/`), `harness/tetrapush/
overnight.py` (`entry_recoil`/`entry_corrected`/`tetra_corrected`), the push-pair law
`harness/tetrapush/from_f0.py` (`cc_push_pair`, session 27).

---

On the frame the roll dispatches, THREE things happen in an order that matters:

1. Link steps **one full roll step** - `nspeed * (sin, cos)(commanded facing)`, 26 u at the cap
   (`entry_search.roll_entry`, unchanged).
2. The CC pair resolves - **off Link's WALK-END exec Co centre** (the 1-frame pose lag: the
   dispatch frame's collision cylinder is still posed by the walk, not by the roll's first
   frame), at the walk-end positions.
3. The halves land: Link's recoil half is added to his **post-roll-step** position; Tetra's push
   half moves her frozen point. Both are `from_f0.cc_push_pair` halves (`dCcS::SetPosCorrect`,
   the 50/50 rank split) - measured 5.5-7.6 u each on the rung06 ground truths.

So the true entry is `roll_entry(walk, facing, nspeed) + link_half`, and the Tetra the razor must
sweep is `walk_end_tetra + tetra_half`. The recoil pair is a function of the CANDIDATE alone
(centre and Tetra, never the aim) - validated bit-identical across aim cells - so the fan computes
it once per key (`overnight.entry_recoil`), and the candidate key carries the walk-end exec centre
(`co_center_exec(init_frame=False)`, key = `(x, z, m351C, speedF, ccx, ccz, tx, tz)`): two plans
at one endpoint with different poses are different candidates.

**The regime split this explains:** the console arrival broke contact before the entry (centre
184.5 u from her), so every pre-s168 validation - the s163 console-w04 rediscovery, the banked
101, `verify-console` - ran where the recoil is exactly zero and never saw the gap. A cap-entry
converted herd walks TOWARD her stations, its entries land inside the 80 u Co disc
([../strategy/cap-entry-conversion.md](../strategy/cap-entry-conversion.md)), and there the
uncorrected prediction put every scored entry 5-8 u off reality: the s167rung06 overnight's 4
"genuine" were fictions of the wrong entry (their true timelines sweep ~0.86 u off the strip),
and its 16-h zero was NOT a statement about the item. **A pre-s168 zero on any in-contact item is
a queue to re-run, not evidence** - the same lesson class as the s160 containment gap
([../model/fan-containment-gap.md](../model/fan-containment-gap.md)).
