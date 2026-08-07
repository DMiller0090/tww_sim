# The frame I was told to find was on the other addend

**Answers:** My frame-minimal objective is a COST and I have spent four sessions attacking one term of
it - which term did I never vary? Where did my walk-frame floor come from, and was it ever measured?
Why does gridding the reachable hull report `no leverage` at a budget that turns out to be productive?
Can a shorter walk reach a clip, and how would I tell the difference between "it cannot" and "I looked
wrong"?
**Status:** validated offline (session 104) on the flooded-Hyrule Tetra corner - 211 placements and 1130
walkable stations at `plan_cost` 21 (8 of 8 independently re-derived, deepest +0.339905) and 56 at
`plan_cost` 20 (6 of 6), against a floor of +0.1150; 19 refused. Gated in
[`tests/test_walk_budget.py`](../../tests/test_walk_budget.py) (14 + 1 slow).
**Source:** [`harness/tetrapush/entry_fan.py`](../../harness/tetrapush/entry_fan.py) (`plan_cost`,
`plan_frames`, `iter_fan2`'s ``j1``), [`harness/tetrapush/entry_reach.py`](../../harness/tetrapush/entry_reach.py)
(`FLOOR_FRAMES`, `MEASURE_FAN`, `measure`, `hull_scan`) and `_notes/s104_*.py`.

## The cost has two addends and only one was ever searched

`entry_fan.plan_cost` is `plan_frames + thrust + 4`. The objective
([`tetrapush-frame-minimal`](../../harness/tetrapush/objective.py)) is stated as a frame COST, and the
standing ask was a specific number - 21 against a delivered 23. Sessions 100-103 read that ask as a
THRUST and spent four passes on it, ending in a refusal with a mechanism and no knob
([mechanics/cut-frame-co-swing.md](../mechanics/cut-frame-co-swing.md): the cut-frame Co swing is
+8.9252 at thrust 13 against -1.2850 at 15, aim-invariant, and no search axis moves an animation
constant).

`plan_frames` is the other addend and nothing had varied it downward. Session 100 tested walk **5**
(more) and recorded that it did not help. Nobody tested **2** or **3**.

## The walk floor was inherited, not measured

`entry_reach.FLOOR_FRAMES = 4` is documented as *the delivered clip's plan length* - which is what it is,
and which is not the same thing as a floor. Two artifacts kept it in place:

- The pinned hull fixture holds a hull at **4 only**, so every reachability query at another budget
  raised rather than answered.
- `MEASURE_FAN` sweeps ``j1=(2, 3, 4)``. Since `plan_frames` is ``base + j1 + j2`` with ``j2 >= 1``, its
  shortest representable plan is **3 frames**, and asking it for budget 2 returns **0 endpoints**. That
  reads as "a 2-frame plan does not exist" and it is an alphabet artifact: `iter_fan2` accepts ``j1=1``
  (``for j in range(1, max(j1) + 1)``), so ``base_frames=(0,), j1=(1,), j2max=1`` is a real two-stick
  plan carrying the ordinary junction prunes.

Widening ``j1`` also grows the **4**-frame hull by **4.8x in area** (1688 -> 8074 u², with all 616 pinned
vertices contained), so every `outside the hull` prune taken since the fixture was pinned was over-tight.
Only outside is a claim ([clip-station-reachability.md](clip-station-reachability.md)), so the direction
of that error is: negatives were called too early, never too late.

## The 2-frame cloud is bounded by physics, not by the alphabet

Worth knowing before spending a pass refining sticks. Measured over the only 2-frame plan shape:

| stride | sticks | endpoints | hull area | extent moved |
|---|---|---|---|---|
| 8 | 583 | 139 213 | 123.8 u² | - |
| 2 | 3355 | 1 577 346 | 129.7 u² | 0.1 u |

A 5.75x finer alphabet buys **+4.8%** of area and 0.1 u of extent, and the nearest genuine entry stayed
**2.218 u** outside either. Two frames at the speedF cap is about 34 u of travel with a bounded turn; that
is the bound. Refining sticks does not move it, so a genuine row outside the cloud stays outside.

## Gridding the hull with her FROZEN is the trap

The first pass at this asked `entry_reach.hull_scan` over the 2-frame cloud and got ``n_leverage 0`` at
every one of the 22 aimable cells, ``|resid|min`` 2.6e-2 against a razor band of ~1e-4. That is not a
statement about the budget. `hull_scan` grids **Link's entry with the pushed actor at one placement**, and
a 2-frame entry sits ~40 u from where a 4-frame plan puts her, so she is out of Co range on the cut frame
and the field is a no-push plateau. Same cloud, same thrust, same facing, one cell:

| her placement | leverage | \|resid\|min |
|---|---|---|
| the console placement | **0** / 492 | 3.29e-01 |
| a productive placement | **293** / 492 | 3.50e-03 |

**Her placement is the switch, so it is the swept axis and never the frozen one.** This is
[clip-station-reachability.md](clip-station-reachability.md)'s scope error with the roles exchanged: there
the BAND was measured outside the candidate set, here the CANDIDATE was measured at a placement the budget
does not imply. And a 1.5 u grid steps straight over a ~1e-4 u dust ribbon in any case, which is why the
resolution that answers this is `locus_scan`'s ~1e-5 walk along the locus and not a finer grid.

## What the corner actually allows

Her placement swept over a ±170 u / 4 u grid about the brace, entries gridded at 1.0 u inside the 2-frame
cloud, locus walked at ~1e-5, thrust **15** (the delivered thrust, with the good swing):

| cell | placements with leverage | LIVE | closest \|resid\| |
|---|---|---|---|
| 2551 | 275 / 1539 | **116** | 8.29e-05 |
| 2552 | 275 / 1539 | **53** | 6.62e-04 |
| 2553 | 272 / 1539 | **42** | 4.16e-04 |

**211 placements carry live walkable dust at `plan_cost` 21**, 1130 walkable stations in total. Eight
re-derived from the station coordinates alone pass every independent check - the engine's genuine flag AND
`geometry_tetra.genuine_clip` on the post-CrrPos endpoint, containment in the FINE 2-frame cloud,
`is_walkable`, `placeable`, and depth over the floor - at `|resid|` down to 2.1e-07. The deepest reads
**+0.339905**, which is deeper than the console-delivered 4-frame clip's +0.2533.

So the corner was never the constraint at 21. The refused thrust and the unmeasured walk were being read as
the same question.

## The ladder stops where the swing says it does

Holding the walk at 2 and stepping the thrust down instead:

| `plan_cost` | thrust | live placements | verified | deepest | `cut_frame_swing` |
|---|---|---|---|---|---|
| 21 | 15 | **211** | 8 / 8 | **+0.339905** | -1.2850 |
| 20 | 14 | **56** | 6 / 6 | **+0.207886** | +1.8547 |
| 19 | 13 | **0** | - | none (nearest \|resid\| 1.6e-03) | +8.9252 |

The two addends are interchangeable in the ARITHMETIC and not in the physics, and this is the number that
says so: shortening the walk starts the roll earlier without re-phasing it, so it moves the whole
roll-and-cut in time and cannot rescue the floor thrust. `cut_frame_swing` still orders the rungs.
So `plan_cost` **20** is the measured floor of this corner, and 19 is refused for the reason
[mechanics/cut-frame-co-swing.md](../mechanics/cut-frame-co-swing.md) already gave.

## The short walk moves HER placement outward, which is where the next frames are

`plan_cost` counts from the ARRIVAL, so a shorter walk is only a real saving if the herd does not hand the
frames back placing her somewhere new. Measured as a distance-to-corner delta against the console
placement's 137.2560625336703 u (POSITIVE = she has less distance to be herded):

| `plan_cost` | herd delta range | placements needing LESS herd |
|---|---|---|
| 21 | -50.6 .. **+64.6 u** | **163** of 211 |
| 20 | -16.2 .. **+69.4 u** | **46** of 56 |

The sign is the finding: most viable short-walk placements sit FARTHER from the corner than the console
one, so the walk frames are not paid back at the herd and there is plausibly more to take. **It is a
distance and never a frame count** - converting it owes the herd search, and the herd has its own floor.

## What a station inside the cloud is, and is not

A live station is dust at an entry a two-frame plan can **reach**. It is not dust at an entry a two-frame
plan **lands on**: the fan's entries are discrete (two sticks in the whole plan) and the genuine set is a
~1e-4 u ribbon, so delivery still owes a 2-frame plan whose own predicted entry coincides with a station,
then `entry_search.confirm_entry`, then `cross_engine` at 0 ULP, then the DTM. That is the same gap the
4-frame delivery closed, one budget down, and the entry density at stride 1 is ample for it.

## A shorter walk lowers the CREDIT by exactly what it saves (session 113)

The obvious next step off this page is a `plan_frames`-1 hunt for `plan_cost` **19**, on the reading
that it buys one frame everywhere. It does not, and the arithmetic is exact rather than empirical.
`cloud_land.FREE_REACH` -- the station gap an arrival owes nothing for -- is `WALK_CAP * WALK_FRAMES`,
DERIVED from the very budget the hunt was run at (`station_map` re-checks it and raises otherwise). So
a cost-19 row is hunted at a 1-frame walk and credits 17 u instead of 34, and the whole-candidate bound
`plan_cost + arrival_frames(d_station)` moves by

    min(1, max(0, FREE_REACH - d_station) / WALK_CAP)

-- a full frame only when the arrival already sits inside **17 u**, sliding to **exactly zero** at 34 and
staying there. Checked against the live numbers: at the best in-band arrival measured anywhere
(``d_station`` 58.2, [the-short-atom-is-a-point.md](the-short-atom-is-a-point.md)) cost-19 and cost-20
score **21.424 frames each**, to three decimals.

The rule that generalises: **a budget cut that also cuts a credit derived from that budget is not a
saving until the credited term is slack.** Rank the halves in order -- solve the arrival first, and the
cost-19 hunt becomes worth its full frame; run it first and it is worth nothing at all.

## The transferable rule

**When the objective is a cost, enumerate its addends before searching any of them, and check which floors
were measured and which were inherited from the thing you are trying to beat.** A floor copied off the
current best is not a bound - it is the current best, wearing a constant's name. The tell here was in the
symbol itself: `FLOOR_FRAMES` said *floor* and its own comment said *the delivered clip's plan length*.
