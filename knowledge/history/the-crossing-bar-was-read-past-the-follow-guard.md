# The crossing bar was read past the follow guard (sessions 126-145)

status: historical
**Superseded by:** [../strategy/a-bound-read-past-the-guard-is-not-a-bound.md](../strategy/a-bound-read-past-the-guard-is-not-a-bound.md)
(session 146). The structural half of the claim survives on
[../strategy/the-crossing-and-the-runway-are-one-resource.md](../strategy/the-crossing-and-the-runway-are-one-resource.md);
this page holds the part that did not.

---

## What was claimed

From session 126 to 145, the requirement on the second-to-last herd cycle was:

> A last roll that stays in the entry band buys **at most +80.4 u** of crossing, so **cycle 2 must
> leave the pushed actor at `l0 >= -80.4`**.

with a stated mechanism: "past ~150 u of runway the best crossing available stops moving at all -
+80.0 to +80.4 u across six hundred units of runway - because a roll that keeps its distance is not
plowing her; **that 80 u is what she covers on her own, following**."

The number was banked (`fixtures/courtyard_crossing_bar.json`), re-projected across terminals
(session 137, -76.87..-77.83 at thrust 11), gated, printed in `roll_probe`'s verbose screen report,
and used as the target of five sessions of `l0_keep` breeding (sessions 134-142).

## Why it does not hold

**The coupled courtyard model has no follow state at all.** `from_f0.FreeRun` carries the pushed actor
as a bare f32 point moved only by the collision push, and past `npc_zl1.FOLLOW_ENGAGE_DIST` it sets
`_follow_warned` and warns that live Tetra "would enter the stt-4 FOLLOW state, which this stt-3 plow
model does NOT cover; the sim is no longer faithful from this frame on". So the stated mechanism cannot
be what produced the plateau, and the frames the plateau is read at are frames the sim does not model.

Checked on the census the bar was read from, with no re-simulation (session 146 - the end separation is
stored, and end separation past the threshold proves the guard fired):

* the roll that SET the bar ends **402.9 u** from her, 173 u past the guard;
* **all 2339 band-keeping rolls in the census** end past it, so there is no in-domain member of the
  population the maximum was taken over;
* the only in-domain crossing in the census reaches `l0 +35.48` at runway **6.64** - the deep plow,
  which spends the runway exactly as the surviving structural claim says.

Re-measured with the guard respected, a band-keeping roll reaches `l0` **-123.48** rather than -80.44:
inside the domain such a roll does not buy crossing, it loses it.

## What replaced it

The junction, measured: it is in-domain by construction (the pusher stays in contact while he walks,
so he never leaves the threshold - **0 trips over 309500 endpoints** off the 58 banked cycle-2 exits that
arm one) and it buys **+2.46 .. +89.71 u** of crossing on its own, median +53.79 - more than the roll bar
it replaces ever claimed. Session 126 had already concluded "the crossing must come from the JUNCTION"
from the other direction (re-aiming a banked roll moves the handoff by only -10.3..+18.2 u) and never
measured what the junction was worth; the number that got carried forward was the roll's.

## The lesson worth keeping

A guard that warns rather than prunes is invisible to a search maximising over its population, and the
maximum lands past it preferentially - the members that leave the domain are the ones that stop paying
the cost the domain imposes. Any bound quoted off such a search owes the fraction of its population that
stayed inside the model, and the same bound restricted to it.
