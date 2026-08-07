# The short atom is a rigid throw: the arrival set is a POINT until frame 8

**Answers:** I widened `exit_arc` to ninety degrees and my arrival did not move a single unit -- is the
arc broken? What are the three tail frames between my 94 and my 97 actually buying? Why does every
relocation axis I sweep trade the two halves against each other instead of solving them? Where do I
read an endpoint's arrival floor -- is `d_station` beside the best landing the same number?
**Status:** MEASURED (session 113) on the flooded-Hyrule Tetra corner, against the session-111 cycle-3
beam (`_generated/s106/s111_c3_beam.json`) at node 1 (herd 68) on controlled relocation beds -- 2508
and 2489 variants (768 / 752 firing and settled) at two endpoints 45 u apart, a ~21.2k-variant arc
pass at three cells, and 170 relocation cells over three axes. Drivers
`_notes/s113_{arrival_surface,arrival_front,sep_curve}.py`, dumps `_generated/s106/s113_*.json`.
**Source:** [`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`escape_atom`'s
input recipe, `tail_variant`, `fires`),
[`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py) (`atom_cloud`, `exit_arc`,
`station_gap`, `arrival_frames`, `FREE_REACH`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`CO_RADII_BAR`).

---

[the-arrival-is-payable.md](the-arrival-is-payable.md) gave the atom a TAIL and said the arrival is an
axis at last. [the-offset-cannot-pay-both.md](the-offset-cannot-pay-both.md) then measured that the
landing and the arrival want Link's offset 22-25 u apart, and that at c3 node 1 the in-band 94 and the
paid 97 are the SAME CELL differing only in the atom's log -- **5 frames against 8**. This page says
what those three frames are, and it is not travel.

## The arrival set at atom <= 7 is a point, and at atom 8 it is a room

Enumerate one endpoint's whole atom grid -- flip bearing x rotate offset x turnaround x side x exit
bearing x tail -- keep the firing SETTLED variants, group by log length, and report the EXTENT of
Link's end positions rather than the best one. Two endpoints, 45 u apart, both at node 1:

| atom | variants | blob along | blob lat | area |
|------|----------|------------|----------|------|
| 5 | 40 / 80 | 1.1 u / 2.0 u | 1.1 u / 12.6 u | ~1 / ~25 u2 |
| 6 | 30 / 30 | 4.3 u / 4.2 u | 3.8 u / 3.8 u | ~16 u2 |
| 7 | 30 / 30 | 8.6 u / 9.8 u | 5.4 u / 6.0 u | ~50 u2 |
| **8** | 40 / 52 | **111.3 u / 116.4 u** | **93.6 u / 92.9 u** | **~10^4 u2** |
| 9 | 90 / 91 | 141 u / 148 u | 117 u / 116 u | ~1.6x10^4 u2 |

At a 5-frame atom, forty distinct knob combinations put Link inside a **1.1 x 1.1 u box**. The whole
knob grid is one arrival. At frame 8 the area jumps by two to three orders of magnitude and the blob
first CONTAINS the station cluster (along 804.7-818.7, lat +12.1..+35.5) -- which is exactly the frame
`arrival_frames` first reads 0 (``d_station`` 10.9 at the first endpoint), and exactly the banked 97.

How TIGHT the point is belongs to the posture, not to the log length: taken at the beam nodes' own
positions the same extent runs from 0.05 x 0.36 u to 14.87 x 47.77 u at comparable lengths, tracking
how many variants survive `fires` -- so read it at the endpoint in hand
([the-endpoint-is-four-numbers.md](the-endpoint-is-four-numbers.md), which also uses the rigidity to
SOLVE the endpoint rather than sweep for it).

The reason is in `escape_atom`'s own recipe: the atom is [optional turnaround] -> L-conversion (2
frames) -> rotate -> backwards slam -> hold the exit stick. That is 4-5 PRESCRIBED inputs, and the
frames after them start on ~25.7 u/frame of untarget-flip momentum that one stick cannot turn. The
knobs exist from frame 1 and their effect does not: it takes until frame 8 for the choices to separate
the trajectories at all.

## Which is why the exit arc is worth exactly zero at a short atom

`exit_arc` is the arrival's own knob and [the-offset-cannot-pay-both.md](the-offset-cannot-pay-both.md)
measured it moving ``d_station`` 59.8 -> 17.6 -- at atom 12-15. At atom <= 6 it moves NOTHING. Three
cells at node 1 (da +40, offsets -13.06 / -11.56 / -10.06), the standing bearing pair against a
34-bearing +-90 deg arc:

| cell | variants, pair -> arc | best arrival | best landing (and its gap) |
|------|----------------------|--------------|----------------------------|
| off -13.06 | 1242 -> 21114 | 43.9 -> **43.9** | 0.685 u @ 73.3 -> **0.685 u @ 73.3** |
| off -10.06 | 1248 -> 21216 | 46.9 -> **46.9** | 1.160 u @ 63.5 -> **1.160 u @ 63.5** |

Seventeen times the rollouts, identical to the last digit printed. (A third cell, off -11.56, was run
only under the arc and reproduces `_notes/s112_honest_surface.py`'s independently measured landing
there -- 1.883 u at ``d_station`` 61.4 -- to the same digit.) The arc is a LONG-atom knob, and the
positive control is what makes that a claim rather than a count: the same call at the same endpoints
does move the arrival once the blob has opened.

## The throw is rigid, and it points OUT of the station band

Because the set is a point, the atom is a fixed DISPLACEMENT, and it is a large one: **(+53.9 along,
+60.8 lateral)** at the first endpoint and **(+60.1, +62.9)** at the second -- an 81-87 u throw at
~47 deg, held to within the blob's own 1-13 u width. Two consequences the earlier framing had
backwards:

* **Link does not have to travel to the stations -- he is already there.** At node 1's 94/97 cell he
  stands at along **808.58**, INSIDE the stations' own along band, and his gap is essentially pure
  lateral (-30.68 against +12.1..+35.5). The 5-frame atom FIXES the lateral (residual +3.18) and
  BREAKS the along, throwing him to 862.5 -- **43.8 u past** the band it started in.
* **So the three tail frames are an excursion, not a journey.** Frames 5-7 are Link leaving the
  station band on rails; frame 8 is the blob opening wide enough to come back. Nothing steers during
  them, which is why widening a knob cannot buy them and why they cost their face value in frames.

## The third relocation axis exists, and it trades like the other two

Every bed until now moved Link LATERALLY (the offset --
[the-landing-belongs-to-the-endpoint.md](the-landing-belongs-to-the-endpoint.md)) or moved BOTH actors
down-line (the placement --
[herd-price-of-a-placement.md](herd-price-of-a-placement.md)), and both hold the Link-Tetra SEPARATION
invariant by construction. Moving Link alone along the herd line is a real third axis and it moves the
arrival hard -- at node 1's cell, ``d_sep`` -45 takes the arrival floor **43.9 -> 23.1** -- because it
slides the rigid throw's landing point up-line into the station box.

What the arrival wants is Link's endpoint at ``station - throw`` ~ (753, -42) while the landing wants
Tetra on a row at along ~884 -- a separation of ~**130 u**, well past `full_herd.CO_RADII_BAR` **80**.
That bar turns out NOT to be the blocker: `fires` only needs the separation to PERSIST, so the atom
still fires at ``centre_feet`` up to **160** (30 short variants a cell), and past the bar Tetra simply
takes no push, which makes the landing the herd's problem alone and drives it nearly exact -- **0.163 u
from row 26** (cost 20) at d_along +58 / d_sep -80.

The axis is worth real frames and still does not pay. Swept over 80 priced cells (d_along +50..+64 x
d_sep -110..-15), deep separation takes the ARRIVAL floor from 43.9 to **2.6 u**, and the best joint
BOUND from session 112's paid 97.00 to **96.00** (d_along +58 / d_sep -80: in band at total 95.12 with
``d_station`` 48.9, owing 0.88 frames). But ``near`` and ``near_band`` never converge -- at every deep
cell the arrival-optimal member of the blob lands 28-36 u out while the landing-optimal member arrives
45-49 u from a station. The blob is small precisely because the atom is rigid, so its two extremes stay
30-45 u apart and no member is at both.

## Each half is already solved at a 5-frame atom. They are just never at the same endpoint

This is the bind in its final form, and it is not a shortage of frames. Over 90 relocation cells at
node 1 (d_along 0..+45 x offset -16..+8, standing pair, `len(log) <= 6`):

* the ARRIVAL floor is ``d_station`` **4.8 u** -- comfortably inside `cloud_land.FREE_REACH` 34 -- at
  a **5-frame** atom, total 94.00. Its landing is 35.9 u out.
* the LANDING floor is **0.685 u**, in band, also at a **5-frame** atom, total 94.00. Its arrival is
  58.2 u, owing 24.2 u = 1.42 frames.
* **no cell pays both.** Not one of the 170 cells across all three relocation axes.

The two floors sit 40 u apart down the herd line, and the rigid throw means the endpoint that puts
Link's point on the stations is the endpoint that leaves Tetra 40 u short of the rows. A 94 does not
need a better atom or a wider knob -- it needs an endpoint the throw maps ONTO the station box while
Tetra is already on a row, and no 2D slice of the relocation space contains one.

Session 114 found that endpoint by completing the basis: all three axes above hold **Tetra's lateral**
fixed, and moving it pays both halves at once --
[the-endpoint-is-four-numbers.md](the-endpoint-is-four-numbers.md).

## Read the arrival's own floor, not the landing's passenger

`_notes/s112_honest_surface.py`'s ``short`` field keeps the min-LANDING variant at ``len(log) <= 6``
and reports whatever ``d_station`` that variant carries. That number is not the cell's arrival floor
and is not close to it: at node 1's 94/97 cell ``short`` reads **73.3** where the same enumeration's
minimum is **43.9**. Rank the arrival on `station_gap` minimised over the settled firing short
variants (`_notes/s113_arrival_surface.py`'s ``near``), and pair it honestly -- ``near`` alone is free
to choose whichever row's stations sit nearest Link, so only ``near_band`` (landing already inside
`objective.PLACEMENT_BAND`) and ``paid`` (``arrival_frames == 0`` as well) can end a plan.
