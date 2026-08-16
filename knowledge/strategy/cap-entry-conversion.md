# Cap-entry is a stick decode at the untarget frames - and every herd converts

**Answers:** What decides whether a herd ends mid-backslide (walk starts ~-25.7, burns frames
converting) or at cap (walk starts ~+18.5-19.0, direction free)? Do I need the camera slew to
reach the cap-entry regime? Which rungs can convert, and does converting move Tetra? Why is a
mid-backslide herd's at-cap walk direction-locked, and what does that make the real cost model?
**Status:** validated offline (session 167) on the wired-camera native stack: 49/49 ladder rungs
convert with Tetra's frozen point `_bits`-identical (`_notes/s167_rung06/s167_conv_survey.py`);
LIVE-confirmed s168c/d (the conversion caps at +18.861622 on console, raw-vs-delivered
bit-identical, and a converted-herd + turning-row + walk + cut pick verified ALL-BIT-EXACT through
the cut). Reach numbers below are the s169 WALLED fixed-stack measurements; every unwalled cone
number is historical ([../history/the-unwalled-cone-edge-priced-the-w05-ladder.md](../history/the-unwalled-cone-edge-priced-the-w05-ladder.md)).
**Source:** s166 handoff (the rung05 camera-slew route), s167 stage A4/conv-survey; the untarget
tier itself is [../mechanics/brakeslide-ebs.md](../mechanics/brakeslide-ebs.md) +
`harness/tetrapush/README.md` (proc-9 ATN_ACTOR model, sessions 3-10).

---

## The regime is a decode, not a herd property

The herd's final roll exits through the 2-frame proc-9 untarget tier, and what the exit does with
the momentum is a function of the **stick decode on the untarget frames** (the herd's last two
rows for an end-of-herd untarget). The banked logs all carry `(128, 110)` there - a slight
camera-relative down - and at the natural camera that decode backslides: speedF flips to ~-25.7
and the walk must spend the L-flip and its brake frames converting. That is the whole
"31 of 46 herds end mid-backslide" penalty the fan's reach model carried.

Session 165/166 found the other regime at rung05 by rotating the camera under that fixed stick
(cs >= ~0xa5d7 at the decode converts). Session 167 found the direct knob: **replace the untarget
rows' stick with camera-forward (`128, 255`) and the exit converts on every herd** - walk starts
at +18.86..+19.00 already at cap, no L spent, natural camera, no slew. The rung05 camera-slew
route was the indirect spelling of this decode; the converting cone is ~+-40 deg of the roll
facing (measured at rung06: X in 32..224 at Y >= ~160 all convert).

## Converting is Tetra-free

The untarget rows act after the plow and after her point has settled: overriding them leaves her
frozen point `_bits`-identical on **all 49 rungs** (and the 18 naturally-at-cap rungs go
+18.5 -> +19.0 under the same rows). The rung06 stage-A2 "camera-coupling" reading - single-frame
substick slews at f54-70 moving her 0.2-1.3 u - was the *natural* `(128,110)` decode changing
under the rotated camera at those same untarget frames, not a plow effect. Pin the untarget
decode explicitly and the camera axis decouples from her entirely.

## What cap-entry does NOT buy: the turn

A converted walk starts at cap **along the roll facing**, and every herd's final roll faces
Tetra, while the entry strips stand between the herd end and her at bearings ~100-137 deg off
that axis. Velocity direction at cap turns rate-limited, so short walks cannot spend the turn.
The honest walk bound for a station at distance d and turn theta is therefore NOT `ceil(d / 19)`
- straight-line pricing admits 95/96-total rows whose turns are unreachable at their walk length.
Price a station by the measured cone ON THE WALLED ENGINE (a ~10 min aimed 2-seg beam per item,
`_notes/s169_queue/s169_reprobe.py`), not the disc: the s169 ladder sweep measured **w05
unreachable ladder-wide** (rung06-w05 10.15 u short at every turning-row variant, rung08/rung10-w05
41.13/33.79 u, rung05-w06 43.47 u, rung05-w07 10.80 u, rung04 no stations at all), and the alive
set is **rung06-w06 (2.31 u to a t14 station, total 98)**, **rung06-w07 (0.01 u, in-contact rows,
total 99)** and marginally rung08-w06 (6.61 u, total 99).

One more free turning row: the herd's LAST row is still in the input pipe when the herd ends
(delay), so it acts on the first walk step - and **the production fan cannot enumerate this axis**
(its pre-frames are the walk's own split), so a fan launch must BAKE a measured variant into the
herd log (`log[nh-1]`), gated the usual way (at-cap + Tetra `_bits` vs the natural herd). It is
worth ~14.6 u of reach at rung06-w06: the canonical `(128,255)` conversion reaches 16.93 u from
the t14 stations where the best measured variant `(56,160)` reaches 2.31 u - every plain-converted
fan run before s169 was structurally reach-starved, so their zeros are re-run queues, not evidence.

## What this retires

- The mid-backslide reach penalty (`kept_edge_reach`'s conversion-limited clouds) as a pricing
  input for herd-END walks: with the untarget rows pinned forward, every herd's walk starts at
  cap. (The measured-edge lesson still applies to any OTHER mid-backslide start.)
- The rung05-only framing of the camera-slew conversion: the s166 "cap-entry regime is
  herd-specific, cs >= ~0xa5d7" window was rung05's spelling of the decode cone under its own
  camera; rung06's reachable cs range never converts under `(128,110)` yet converts everywhere
  under a forward stick.

## See also

- [clip-camera-axis.md](clip-camera-axis.md) - the camera as a free input channel; the walk/aim
  halves of csangle.
- [../mechanics/brakeslide-ebs.md](../mechanics/brakeslide-ebs.md) - the ATN tier the backslide
  regime runs.
- [../model/admitting-draws.md](../model/admitting-draws.md) - the draw tables the re-pricing
  runs over.
