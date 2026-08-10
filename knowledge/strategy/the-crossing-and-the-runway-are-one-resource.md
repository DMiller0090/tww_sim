# The crossing and the runway are one resource: why the last herd cycle cannot also be the terminal

**Answers:** My terminal solve says which pair clips and my herd's last cycle lands nowhere near it -
is that a ranking problem or a structural one? What must the SECOND-to-last cycle hand over? Is that
requirement a constant of the problem, or does it move when I change the terminal? Can I move the
entry band by cutting the roll earlier (pressing B sooner)? How do I make a razor-scale terminal
predicate cheap enough to rank a whole beam on?
**Status:** MEASURED (session 126) on the flooded-Hyrule Tetra corner at facing 40835, over **20592
full-circle rolls** fired from 3 banked cycle-2 endpoints (48 armed junction endpoints each, every herd
prune off). 51 rolls carry her across the approach line; 12366 leave the pusher at or beyond the entry
band's near edge (1866 inside it); **zero do both** - the deepest crossing roll ends at runway 89.
RE-MEASURED session 146 with the model's own follow guard respected (218880 rolls off 8 cycle-2 exits),
which SHARPENED the structure and moved the number: a band-keeping roll inside the domain reaches `l0`
**-123.48**, i.e. it loses crossing rather than buying any, and the instrument that buys it is the
**junction** (in-domain by construction, up to **+89.71 u**, best absolute `l0` **-30.75** over the whole
banked cycle-2 population - 58 exits, 309500 endpoints, 0 guard trips). The old +80.4 exchange rate was read at states the sim does not model -
migrated to
[../history/the-crossing-bar-was-read-past-the-follow-guard.md](../history/the-crossing-bar-was-read-past-the-follow-guard.md).
**Source:** [`harness/tetrapush/handoff.py`](../../harness/tetrapush/handoff.py) (`resid_window`,
`entry_roots`, `endpoint`, `crossing_bar`), the beam keep in
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`extend_cycle`'s
`handoff_keep`), bank `fixtures/courtyard_crossing_bar.json`, gate
[`tests/test_handoff.py`](../../tests/test_handoff.py) (14); continues
[the-razor-is-on-the-pusher-not-the-pushed.md](the-razor-is-on-the-pusher-not-the-pushed.md).

---

## The last cycle is asked for two things and can pay for one

Chaining a herd back to a solved terminal (see the page above) leaves the last cycle holding two
requirements at once:

* **the crossing** - the pushed actor must end on the genuine side of the clip roll's approach line
  (`l0 > 0`; the genuine set is entirely one side of it);
* **the runway** - the pusher must end 190-320 u back along that line, because that is where the entry
  curve lives.

Both are properties of the same roll, and a roll is a single ~205 u atom in a chosen direction. The
mechanism that couples them is the plow itself: carrying the pushed actor sideways across the line
means rolling THROUGH her, and a roll that goes through her carries the pusher just as far past the
corner. Measured over the full aim circle, per band of where the roll left the pusher:

| pusher's final runway | rolls | best crossing gained | runway spent |
|---|---|---|---|
| -50 .. 0 | 1956 | **+177.6 u** | 425 - 503 |
| 0 .. 50 | 1599 | **+196.2 u** | 375 - 453 |
| 50 .. 100 | 1800 | +174.3 u | 325 - 403 |
| 100 .. 150 | 1263 | +129.8 u | 275 - 353 |
| **190 .. 320 (the entry band)** | 1866 | **+80.4 u** | 105 - 263 |
| 320 .. 900 | 10500 | +80.2 u | past the corner |

Below ~100 u of runway the plow engages and the crossing more than doubles; the knee is sharp (at
runway 89 the best crossing is `+12.9`, at runway 107 it is `-30.8`). Past ~150 u the table above reads
a flat **+80.0..+80.4 u across six hundred units of runway**, and that plateau is where the whole thing
went wrong: it is read at states the model does not simulate. Every roll in those rows ends with the
pusher past `FOLLOW_ENGAGE_DIST`, where `FreeRun` stops modelling her at all - see
[a-bound-read-past-the-guard-is-not-a-bound.md](a-bound-read-past-the-guard-is-not-a-bound.md) for the
check and the corrected numbers.

## So the requirement belongs to the cycle before, and the JUNCTION is what pays it

The structure holds and the instrument is not the roll. Re-measured with the guard respected (session
146, 8 cycle-2 exits x 48 junction endpoints x the full aim circle):

| instrument | best `l0` reached | in the domain? |
|---|---|---|
| a band-keeping roll | **-123.48** | yes - and it LOSES crossing |
| a deep-plow roll (any runway) | +128.87 | yes - it spends the runway, per the table above |
| **the junction alone** | **-30.75** (buying +2.46..**+89.71** u, median +53.79) | yes, 0 trips over 309500 endpoints |

So the condition on the handoff one cycle earlier is real, but it is set by what a JUNCTION can carry,
and the best any junction in the banked cycle-2 population reaches is `l0` **-30.75** against the
`l0 > 0` a genuine terminal needs. That is the honest statement of what is left: **30.75 u**, on the
one axis the terminal box cannot see
([the-box-cannot-see-the-lateral.md](the-box-cannot-see-the-lateral.md)) - not "the last cycle is badly
ranked" but "the last cycle is being asked to pay a bill that was run up before it started".

And it is a requirement on the whole cycle, not on its aim. Re-opening each banked cycle-2 terminal as
its PRE-ROLL endpoint (the split is recoverable exactly from the input log, and verified by re-firing
it 0-ULP) and sweeping the full aim circle from there, with the junction left exactly as it is, moves
the handoff by **-10.3 to +18.2 u** and reaches `-159.4` at best. The roll is the wrong knob: it buys
~+89-118 u of crossing off that state whatever it is aimed at. The crossing has to come from the
JUNCTION - where the pusher repositions without a 400 u commitment - which is the same conclusion an
earlier session reached about the lateral one cycle down.

## And the handoff's own `l0` does not predict what its junction can carry

This is the trap that makes the requirement awkward to breed against, and it is now population-complete
rather than anecdotal (session 146, all 58 arming exits): the crossing a junction buys spans
**+2.46 .. +89.71 u** and it is ANTI-correlated with where its parent starts. The best exit by `l0`
(-69.66) has a junction worth only **+11.0 u**; the biggest junction gain, **+89.71 u**, sits on an exit
at `l0` -193.73, and only **2 of 58** exits reach past -50 at all.

So a keep on the handoff's own `l0` - which is what five sessions of breeding ranked on - selects for
the wrong half of the sum. What has to be kept is `l0 + (what this exit's junction can carry)`, and the
second term costs one junction beam per exit and no aim sweep at all, so it is affordable at the cut
that decides which exits exist.

The alternative shape, and its price: let the last roll plow her across (it reaches +196 u) and accept
that it parks the pusher at runway -48..89, then walk him back. Measured on every crossing roll, the
pusher lands **112-238 u** from the nearest genuine entry (median 217), i.e. **7-14 frames** of retreat
at the walk cap, before any turn to the roll's facing. The banked cycle-3 beam's best is 73.7 u, so
neither route is free; the difference is that the first one has somewhere to spend the search.

## A bar belongs to its terminal, and it re-derives without firing a roll

Whatever the bar's value, it is a max over a roll population read in ONE frame, so it is a property of
that terminal and not of the problem. It outlived its thrust: the number below was measured at facing
40835 / thrust 14 and kept being printed beside thrust-11 screens two sessions after the plan moved
there. (The values in this section are the out-of-domain ones and are kept only because the
re-projection METHOD is what licenses reading any bar in another frame -
`fixtures/courtyard_crossing_bar.json` still holds them; the crossing numbers to use are the in-domain
table above.)

It needs no re-run to correct. `l0` and `runway` are affine projections of banked WORLD positions -
`tetra_lateral` is a dot against `pf.q` about `pf.brace` - and the census stores every roll's two XZ
pairs, so all 20592 rolls re-read in any frame exactly. The re-projection returns **-80.44** at the
frame it was measured in, and that is what licenses reading it anywhere else:

| terminal | `cut_step` | bar | best band-keeping roll |
|---|---|---|---|
| facing 40835, thrust 14 | 16 | **-80.44** | runway 240.1, `l0` -80.2 |
| facing 40600, thrust 11 | 13 | -76.87 | runway 234.6, `l0` -76.6 |
| facing 40660, thrust 11 | 13 | **-77.83** | runway 234.6, `l0` -76.6 |

**The shorter roll's bar is HARDER, by 2.6 u, at exactly the terminal that saved 3.35 frames** - which
is the direction to expect and the reason to measure it rather than carry the number forward. The
crossing plateau moves with it and keeps its shape (`+80.0..+80.4` becomes `+77.5..+77.8` across six
hundred units of runway), and the structural claim survives whole: 67 rolls cross instead of 51, and
every one of them still leaves the pusher at runway <= 89, so **zero still do both**.

Two things follow for anything that quotes it. The bar is **flat in where the band's near edge is
drawn** - swept over near edges 130..220 it does not move a digit, because the roll that sets it sits
~75 u inside the band - so the runway floor and the bar are independent knobs and the session-136 floor
move cannot have touched it. And an unmeasured terminal has **no bar**: `handoff.crossing_bar(pf)`
returns `None` rather than a neighbour's number, since a plausible bar with no population behind it is
the defect, not the fallback.

## Cutting the roll earlier does not move the band

The obvious lever - fire the cut sooner, so the roll is shorter and the entry can sit closer to the
corner - does not work, and the reason is the corner itself. The cut lands at `thrust + 2` frames, and
thrust is just the B-press frame, a free input. Swept 6..16 at a real crossing endpoint:

| thrust | cut frame | genuine entries | runway band |
|---|---|---|---|
| 6 - 8 | 8 - 10 | 0 | none at any rung 30-400 |
| 9 | 11 | 1 | 200 |
| 10 - 11 | 12 - 13 | 1 - 3 | 220 - 260 |
| 14 | 16 | 4 | 180 - 290 |
| 15 | 17 | 4 | 200 - 270 |

The band's lower edge never leaves ~180-220 whatever the cut timing, because the pusher must travel far
enough to REACH the corner and brace against it before the cut; the extra roll frames are absorbed by
the brace, which is the same attractor that makes the cut-frame overlap a property of the corner rather
than of the handoff.

**Read the zeros as scoped, not as refusals** ([history/thrust-13-refused-by-geometry.md](../history/thrust-13-refused-by-geometry.md)
is this exact mistake, one axis over): the sweep is ONE pushed-actor position, ONE facing, lean 0, rungs
30-400. The facing was solved at thrust 14 and the facing window is about one value wide, so a thrust
whose row reads 0 has most likely had its window move rather than vanish. And a roll of `cut_step` N
travels 26N u, so the family where the cut fires as the pusher ARRIVES rather than after sliding sits
near 26N - which is 286 u at thrust 9 (inside the sweep) but 416 u at thrust 14 (past its ceiling). Any
claim about a thrust owes its own facing sweep and a ceiling past 26N.

What thrust does buy is **frames**: the clip roll costs `cut_step` frames, so thrust 9 is **5 frames
cheaper than thrust 14** and still genuine. On the same endpoint that is a bound of 92.50 against
97.35 - the cheapest single knob measured in this shape.

## Making the predicate cheap enough to rank on

A terminal predicate is only useful as a rank if a beam can afford it, and the razor solve as first
written costs ~19 s per endpoint (27 approach rungs x a 28001-sample lateral scan). Two economies take
it to ~1.5 s, and neither weakens it:

* **The residual is one number outside contact.** A roll that never reaches the pushed actor runs the
  same trajectory whatever the pusher's lateral offset is, so its residual is *bit-identical* over all
  but a few units of the span. A coarse pass finds that window by difference - no threshold, no tuned
  width - and the fine scan runs only inside it. The fine samples are taken on the full span's own
  lattice, so the two paths evaluate the same positions and return the same brackets **exactly**.
  Measured windows are 7-25 u of a 140 u span.
* **The bisected roots are a bound; the band walk is the claim.** Whether a sign change actually clips
  takes an 8001-sample f32 walk around it; every genuine entry is a root, so the distance to the
  nearest ROOT can only understate what a herd must close. That is what a prune needs. It is not a
  clip: at one rung of a real endpoint the root curve has 2 members and the genuine curve has none, so
  a quoted plan owes the walk ([[banded-proxy-needs-its-newton]]).

With those, a herd endpoint prices in frames as `frames + gap / walk cap + cut_step`, admissible on
every term - and the cheap half comes first: the pushed actor's offset SIGN refuses an endpoint on one
dot product, which is 112 of 127 banked endpoints before any razor work.
