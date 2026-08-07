# The separation is not a suffix: it is the same resource as the momentum and the facing

**Answers:** My specification wants 92-157 u of separation where every beam node sits at 38-75 -- can I
just hold a stick at the endpoint and buy the difference? What does a unit of separation actually cost,
and is the 25.727 u/frame cap the right price? Why does my escape atom fire NOTHING from a deeper
endpoint when the shallow one fires thousands? Is my per-aim cut looking at Link's arrival at all?
**Status:** MEASURED (session 115) on the flooded-Hyrule Tetra corner, against the session-111 cycle-3
beam (`_generated/s106/s111_c3_beam.json`): a 16-bearing x 4-magnitude prologue grid x k = 0..8 at all
64 nodes, the atom enumerated at every selected endpoint and at every node's own control, and the
refusals attributed by `away_walk.fires_census`. Drivers `_notes/s115_{recede,screen_ab}.py`, dumps
`_generated/s106/s115_*.json`.
**Source:** [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`escape_atom`,
`fires`, `fires_census`, `snaps_at`, `snap_csangle`, `_SNAP_KEEP_SPEED`, `_cone_margin`),
[`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py) (`residual_fan`'s throw,
`predict_bound`, `herd_stations`, `arrival_frames`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`roll_probe`'s ``stations``
and ``sep``, `CO_RADII_BAR`).

---

[the-endpoint-is-four-numbers.md](the-endpoint-is-four-numbers.md) ended session 114 with one term
unpaid: a specification that pays both delivery predicates needs **92.5-156.8 u** between Link and
Tetra, every node of the beam sits at **38.09-75.25 u**, and the gap was priced at Link's endpoint
speed -- cap **25.727 u/frame**, so 0.67 frames for the cheapest specification and 3.68 for the solved
one. That price was arithmetic: no session had ever run the frames.

They are runnable, and unlike the other three relocation beds this one is not a fiction -- k frames of
holding a stick at the herd endpoint is an ordinary plan suffix that costs k frames. So run them.

## The separation moves, at a third of the quoted rate

Sweeping the prologue as a grid (16 bearings on the 0x1000 grid x magnitudes 0.06/0.2/0.5/1.0, each an
existing recipe primitive) rather than as named sticks, at every node:

| | measured |
|---|---|
| best sustained separation rate | **+8.3 .. +10.6 u/frame** |
| the price session 114 quoted | 25.727 u/frame (Link's endpoint speedF) |
| node 8 | sep **58.52 -> 129.88 u** over 8 frames |
| node 0 | sep **58.48 -> 124.87 u** over 8 frames |
| Tetra's own displacement | stops at **k = 2-3** and never resumes |

So the depth the specification asks for is inside 3-8 frames at every node, and the freeze the whole
decoupling rests on is real -- measured from Tetra's own displacement, never inferred from
`CO_RADII_BAR` (``centre_feet`` reads an ANIMATED centre and oscillates with the pose, so one frame
over the bar is not a freeze).

The rate is a third of the quoted cap for a reason worth keeping: **at the herd endpoint Link is
CLOSING, not receding.** His speedF is the untarget backslide's -25.4, but its along-component points
DOWN-line at ~+12 u/frame -- he is still chasing her. The separating prologue has to reverse that
first, so the 25.727 belongs to a direction he is not travelling in.

## And every unit of it is paid for out of the atom

Enumerating the escape atom at each selected endpoint (`cloud_land.cloud_landing`, 672-4704 variants):

| endpoint | separation | variants firing |
|---|---|---|
| node 8 control | 58.52 | **56 / 720** |
| node 0 control | 58.48 | **1888 / 2640** |
| node 1 control | 59.41 | **1964 / 4038** |
| every deep prologue (nodes 0, 1, 8; k = 2..6) | 72.7 .. 114.6 | **0** |

A zero is not a diagnosis, and the positive controls are why this one is worth reading
(`[[infeasible-needs-proof]]`). `away_walk.fires_census` attributes it: **``l_ok`` fails on 672 of 672**
at every receded endpoint, and at node 0's momentum-preserving pick it is the **SOLE** failing clause on
all 672 -- fix it and every variant fires.

## Why: one resource, spent three ways

The atom is written for the untarget EBS posture -- Link FACING AWAY from Tetra with backslide momentum
-- and its `l_ok` clause is exactly the statement that the L may not act with her in the +-90 deg cone.
The prologue destroys that posture, and the chain is measured end to end at node 8's best cone-clear
cell (bearing 0x8000, msd 0.50, k = 3):

1. turning Link costs the EBS: speedF **-25.45 -> -11.43**;
2. and the turnaround -- the atom's only facing lever -- requires the EBS be PRESERVED
   (`away_walk._SNAP_KEEP_SPEED` = -24.5). Measured: `snap_csangle` finds a window at **every** control
   (34816 / 34304 / 31232 at nodes 8 / 0 / 1) and **None at every receded endpoint**, at all three. The
   lever is gone by construction, not by bad luck;
3. so the atom's own first frame turns him in: cone margin **+3.51 deg -> -37.64 deg**, and -71 deg by
   the frame the L acts. ``turnaround_first=True`` changes nothing (identical facing 25265, because the
   ESS cannot snap without the speed).

**Separation, momentum and facing are one resource.** A prologue that buys the first spends the other
two, which is why the deep cells fire nothing and why the cone-clear ones -- clear at the prologue's own
last frame -- fire nothing either.

### What this retires

The separation cannot be appended to a herd, at 25.727 u/frame or at any rate. It is a **herd-shaped**
quantity: the only stage that can deliver depth AND leave the EBS posture intact is the last roll
itself, so it belongs in the cut that chooses endpoints, not in a suffix. `roll_probe` reports ``sep``
for that reason and does not rank on it: an endpoint keep that maximised depth would select for states
that cannot fire.

## What the beam actually owes, and the cut that could not see it

Enumerating the atom at every node's own endpoint -- the first time the beam has been priced by
enumeration rather than by specification -- says that **29 of the 64 nodes fire at all**, and that the
two halves' floors are held by DISJOINT sets of them:

| | nodes | what the other half reads |
|---|---|---|
| arrival already free (``arr_frames`` 0) | **2** | landings **25.40 .. 40.02 u** out |
| landing inside the 1.0 u band | **3** | arrivals owe **7.38 .. 8.37** frames (``d_station`` 159.5-176.3 u) |
| both (``joint``) | **0** | -- |

The correlation across the beam is only **-0.089** over the 29, so this is not a smooth trade to be
optimised along -- it is the session-113 bind ("each half is solved, never together") reproduced on
DELIVERED endpoints instead of relocated cells, with the two floors held by different nodes entirely.
The best bound anywhere on the beam is node 0's **93.95** (total 92.00, landing 25.400 u, arrival free),
and a bound is not a delivery.

And the census over all 64 names the single biggest obstacle, which is not the separation at all:
**``l_ok`` is the SOLE failing clause on 7349 variants (63% of all sole refusals**, against ``dips``
4117 / 35%), and it is the sole blocker at **19 of the 35 nodes that fire nothing whatsoever**. The
camera supply that answers it (`away_walk.snap_reach`, `full_herd.derived_target_css`) has been the
standing side-item since session 112; this measurement promotes it to the main one.

That makes the blindness expensive: `cloud_land.predict_bound` -- the per-aim screen inside
`full_herd.roll_probe`, the cut that decides which endpoints a last cycle may choose between -- priced
only the LANDING. The arrival entered at the survivors (`cloud_landing`, session 110) and never at the
screen, so the set it chose from was fixed with no reference to whether Link could reach the stations
his row's `plan_cost` was measured at. It is the session-107 failure mode one stage earlier: a winner
that scores well and delivers nothing ([delivery-is-two-predicates.md](delivery-is-two-predicates.md)).

**The fix is session 114's own finding.** The throw -- Link's displacement over the atom -- is rigid per
(node, log length), so `residual_fan` carries it per member and `predict_bound` places Link's arrival at
``link + throw`` and prices `arrival_frames` beside the landing miss. Measured against scoring the SAME
enumeration both ways (`_notes/s115_screen_ab.py`, so the comparison costs one rollout set, not two):

| | measured over the 29 firing nodes |
|---|---|
| the old key UNDERSTATES its own pick by | **+0.00 .. +9.23 frames, median +6.51** -- the arrival it never priced |
| the ROW the landing is priced against moves at | **9 of 29** endpoints |
| top-8 ENDPOINT ranking | **identical** (8/8 overlap) |
| what the new key's pick gains, both priced honestly | **+0.00 .. +0.28 frames** (median +0.00) |

Read that honestly: on THIS beam the joint screen does not change which endpoints survive, and the
frames it wins are inside a rounding. What it removes is a **median 6.51-frame fiction** in the number
the search reports -- a landing-only bound of 93 is really 99.5 against a banked 101, which is the
difference between "comfortably ahead" and "level" -- and it fixes WHICH ROW a third of the beam is
aimed at, which is what the next stage inherits. The cut moving is a thing to re-measure on a beam that
was cut with it, not a claim this measurement makes.

Per the standing rule, this predictor still only sizes the cut -- `cloud_landing` at the survivors makes
the claim (`[[banded-proxy-needs-its-newton]]`).

## Reading

- [the-endpoint-is-four-numbers.md](the-endpoint-is-four-numbers.md) -- where the specification and its
  92.5-156.8 u separation come from, and the 25.727 u/frame price this page measures.
- [the-short-atom-is-a-point.md](the-short-atom-is-a-point.md) -- the rigidity that makes the throw a
  table column rather than a steering channel.
- [the-arrival-is-payable.md](the-arrival-is-payable.md) -- the atom's TAIL, which is the other end of
  the same axis: it moves the arrival AFTER the atom, where this page is about before it.
- [delivery-is-two-predicates.md](delivery-is-two-predicates.md) -- why half a candidate scores well
  and delivers nothing.
