# A bound read past the model's own guard is not a bound

**Answers:** My sim warns that it stops being faithful past some threshold and my search maximises a
quantity anyway - what is that maximum worth? How do I check whether a banked bound was measured
inside the model, without re-running the census it came from? My crossing budget says one cycle back
has to hand over X - how do I tell whether X is physics or an artefact of a state the sim never
simulated? What buys the same quantity inside the domain?
**Status:** measured session 146, and it corrects a bound the endgame had rested on since session 126.
Computed on the banked census itself with no re-simulation: **all 2339 of its band-keeping rolls end
with the pusher past `FOLLOW_ENGAGE_DIST`**, and the roll that SET the bar ends **402.9 u** away, 173 u
past it. Re-swept inside the domain over 8 cycle-2 exits, 384 junction endpoints and 218880 rolls
(`_notes/s146_bar_domain.py`): a band-keeping roll that never trips the guard reaches `l0` **-123.48**
where the bar claims -80.44, and the instrument that does buy crossing in-domain is the **junction**:
population-complete over the banked cycle-2 beam (58 exits, **309500 endpoints, 0 guard trips**) it buys
**+2.46 .. +89.71 u** (median +53.79) and reaches `l0` **-30.75** at best.
**Source:** [`harness/tetrapush/from_f0.py`](../../harness/tetrapush/from_f0.py) (`FreeRun.step`'s
follow guard, `_follow_warned`), [`tww_sim/core/npc_zl1.py`](../../tww_sim/core/npc_zl1.py)
(`FOLLOW_ENGAGE_DIST`, `Zl1FollowState`), the bound it corrects in
[`handoff.py`](../../harness/tetrapush/handoff.py) (`crossing_bar`, bank
`fixtures/courtyard_crossing_bar.json`). Probe `_notes/s146_bar_domain.py`; artefacts
`_generated/s106/s146_bar_domain{,_jn}.json`. Migrated claim:
[../history/the-crossing-bar-was-read-past-the-follow-guard.md](../history/the-crossing-bar-was-read-past-the-follow-guard.md).

---

## The shape of the mistake

A coupled sim usually models one actor well and the other only in the regime the captures cover. Here
the pushed actor is carried as a plow target: her position moves when the pusher's collision cylinder
ejects her, and `FreeRun` says so out loud - past `FOLLOW_ENGAGE_DIST` she enters a follow state "which
this stt-3 plow model does NOT cover; the sim is no longer faithful from this frame on".

A search then maximises something over a full aim circle with the herd prunes off. Nothing stops it
choosing a member whose rollout left the domain, because the guard is a *warning*, not a prune - and
every probe in this repo runs under `simplefilter('ignore')`. So the maximum is taken over a population
the search cannot see the edge of, and the winner is disproportionately likely to be past it: the
members that leave the domain are exactly the ones that stop paying the physical cost the domain
imposes.

That is what happened. The bar was `max l0` over rolls that keep the pusher in the entry band, and the
member that set it rolls 400 u away from her - which is precisely why it keeps its runway.

## Checking it costs nothing, because the census stores positions

A banked census of world positions can be re-interrogated for domain membership without re-running
anything, and the check is one-sided in the useful direction:

> **end distance > threshold ⇒ the guard fired.** The guard fires on ANY frame, so a final separation
> past the threshold proves the rollout left the domain. The converse proves nothing - a rollout can
> leave and come back - so a member that passes this needs the real flag.

Applied to the 20592-roll census the bar was read from:

| population | best `l0` | end separation of that member |
|---|---|---|
| all rolls, any runway | **+35.48** | 84.4 u (in the domain; runway 6.64) |
| all rolls, in the entry band - **THE BANKED BAR** | -80.18 | **402.9 u (out of the domain)** |
| in the band AND end separation <= threshold | **none exists** | - |

**Not one of the 2339 band-keeping rolls in the census stays inside the model.** So the bar is not a
statement about a state a plan can continue from: by the frame it is read at, the pushed actor has been
standing still in the model for many frames while live she is following, and where she actually is at
the next stage's entry was never measured. The arithmetic was right; the state was not continuable.

## What the same quantity is worth inside the domain

Re-swept with the guard flag read per rollout rather than ignored - 8 cycle-2 exits, 48 junction
endpoints each, the full aim circle:

| instrument | best `l0` reached | domain |
|---|---|---|
| the junction alone (walking, still in contact) | **-30.75**, buying up to +89.71 u | in, **0 of 309500 endpoints** trip the guard |
| a roll, any runway, guard ignored | +128.87 | out |
| a roll, any runway, guard respected | +128.87 | in (the deep plow; it lands the pusher at low runway) |
| a roll that keeps the entry band, guard ignored | -26.55 | out |
| a roll that keeps the entry band, guard respected | **-123.48** | in |

98.8% of the full-circle rolls trip the guard, and respecting it costs **96.93 u** of apparent crossing
inside the band. So the corrected reading of the same structure is sharper than the original: a
band-keeping roll does not buy crossing at all, it LOSES it, and the crossing that does exist in-domain
is bought either by the deep plow (which spends the runway - see
[the-crossing-and-the-runway-are-one-resource.md](the-crossing-and-the-runway-are-one-resource.md)) or
by the JUNCTION, which is in-domain by construction because the pusher stays in contact while he walks.

## The three ways out, and which one is a measurement

1. **Model the missing regime.** The follow state machine already exists and is gated 0-ULP against a
   live capture (`Zl1FollowState`, [`tests/test_tetra_follow.py`](../../tests/test_tetra_follow.py));
   it was simply never wired into the coupled courtyard step, which carries her as a bare f32 point.
   Wiring it turns the whole >threshold population from unsimulated into measured - and the crossing
   there could move either way, since a following actor walks TOWARD the pusher.
2. **Stay inside the domain and re-price the requirement**, which is the table above.
3. **Quote the out-of-domain number anyway.** That is the defect, and it survived twenty sessions
   because the bound was re-projected, re-gated and re-banked without anyone asking what state it was
   read at (`[[infeasible-needs-proof]]`'s mirror image: a bound is as unproven as a refusal).

Only (1) and (2) are measurements. A guard that fires and is ignored is a search running with its eyes
shut over exactly the region it likes best.

## The rule

**Any bound quoted from a search over a coupled sim owes the fraction of its population that stayed
inside the model, and the same bound restricted to that fraction.** Cheap to produce - the flag is
already there and the positions are already banked - and the difference is not a rounding: here it is
96.93 u on a 80.44 u number, and the sign of the answer changes.
