# Cap-entry is a stick decode at the untarget frames - and every herd converts

**Answers:** What decides whether a herd ends mid-backslide (walk starts ~-25.7, burns frames
converting) or at cap (walk starts ~+18.5-19.0, direction free)? Do I need the camera slew to
reach the cap-entry regime? Which rungs can convert, and does converting move Tetra? Why is a
mid-backslide herd's at-cap walk direction-locked, and what does that make the real cost model?
**Status:** validated offline (session 167) on the wired-camera native stack: 49/49 ladder rungs
convert with Tetra's frozen point `_bits`-identical (`_notes/s167_rung06/s167_conv_survey.py`);
the rung06 landing that used it sits at 3.6e-4 u banded (walk 5, total 97). Not yet live/DTM-
confirmed.
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
that axis. Velocity direction at cap turns rate-limited, so short walks cannot spend the turn:
at rung06 the walk-3/4 cones stop 11-38 u short of every banked station, while walk 5 reaches
a 137-deg station 88 u out to under 1 u (the turn completes over distance). The honest walk
bound for a station at distance d and turn theta is therefore NOT `ceil(d / 19)` - straight-line
pricing admits 95/96-total rows whose turns are unreachable at their walk length. Price a
station by the measured cone (a 30 s 2-seg sweep per herd), not the disc.

One more free turning row: the herd's LAST row is still in the input pipe when the herd ends
(delay), so it acts on the first walk step - hand it to the walk optimizer (it is priced in the
herd already). At rung06 that row moved the walk-5 cone edge from 5.7 u off the station family
to 0.8 u.

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
