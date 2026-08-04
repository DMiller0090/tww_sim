# Buying a saturating axis - WHERE to place the next pass, and the pool that lets you

**Answers:** My axis saturates and I have an hour to spend on it - which candidate do I buy next? Why
did ranking my candidates once and taking the top N cluster them? My alphabet has thousands of members,
so why is its most extreme member not in it?
**Status:** validated offline (session 98) on the flooded-Hyrule Tetra corner, gated in
[`tests/test_entry_ledger.py`](../../tests/test_entry_ledger.py).
**Source:** [`harness/tetrapush/entry_ledger.py`](../../harness/tetrapush/entry_ledger.py)
(`walk_bam`, `ledger_distance`, `spread_cameras`, `SPREAD_EXTREMES`).

[clip-draw-ledger.md](clip-draw-ledger.md) measures *what* predicts a pass's new draws on a camera-like
axis: its distance from the passes already bought, at purchase time. This page is the other half - how
to turn that into the next buy, and the two traps between the law and the spend.

## Rank once and you buy one place N times

The measured quantity is a property of the **ledger**, not of the candidate. So a selector that scores
every candidate against the ledger it opened with and takes the top N is scoring N-1 of them against a
ledger that will not exist by the time they run: the runners-up to the best candidate are its
neighbours, and neighbours are exactly what the law says do not pay.

The fix is one line of discipline rather than a better score - **pick one, add it to the bought set,
re-rank**. That is farthest-point traversal, and its distances fall as the channel fills, which is the
saturation curve arriving at the candidate axis itself:

| pick | walk BAM | BAM from the ledger |
|---|---|---|
| 1 | +714 | **520** |
| 2 | +458 | 256 |
| 3 | -46 | 156 |
| 4 | +322 | 128 |

Read the decay as the budget, not as a disappointment: an axis with six passes on it has already taken
the far half of its own channel, and the fifth buy is worth what the fourth distance says it is.

## The alphabet does not contain its own extreme

`deliverable_bytes` enumerates `range(0, 256, step)` and maps the two clamped bytes onto their
delivered values, so **every strided C-stick alphabet stops at byte 240**. Byte 254 is only reachable
from 255, which no stride past 2 emits.

That is invisible until distance is the thing being ranked, and then it is the whole first pick. The
channel's negative extreme `[1, 1]` (walk **-716**) *was* always in the pool - 0 clamps into 1, so the
stride emits it for free - and it was session 97's best pass at 78% new. Its mirror `[254, 254]` (walk
**+714**) had never appeared in any candidate list built on this corner, across every pass from session
95 on. It sits **520 BAM** from the bought set, against a best-ever-measured 312.

So `SPREAD_EXTREMES` is unioned into the pool explicitly, rather than by widening the stride: a finer
stride multiplies the candidates and interleaves them *between* the ones already held, which is more
tickets at shorter distances - the opposite of what a spread wants. The rule generalizes past this
axis: **when you start ranking on distance, check that the endpoints of the range are in the set you
are ranking**, because an enumeration written to be representative is usually not written to be
extremal.

## Aimability is a filter on the pick, not on the pool

A camera that cannot aim the scope is not a draw for it, but on this channel that is decided by a
*different* byte than the walk is ([clip-camera-supply.md](clip-camera-supply.md)): the walk trail is a
function of the first `WALK_CHANNEL` bytes and the aim frame reads a later one. So a walk pair chosen
for distance keeps a free knob, and the selector searches a tail byte nearest-neutral first, dropping a
walk trail only when no tail rescues it. Pick 4 above is `240,208,192` - a non-neutral tail, bought for
a walk position that a neutral tail could not have aimed.

## See also

- [clip-draw-ledger.md](clip-draw-ledger.md) - the law this page spends, and how to price a pass
  against the draws already held.
- [clip-camera-supply.md](clip-camera-supply.md) - how many cameras there are, and why the walk pair
  and the aim byte are independent knobs.
- [clip-search-budget.md](clip-search-budget.md) - what a pass of a given shape costs.
