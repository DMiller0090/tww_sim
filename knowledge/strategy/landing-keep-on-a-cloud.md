# A last-cycle keep cannot move a floor it only reorders

**Answers:** The chain's landing floor sits ~6 u outside the placement band -- if I rank the last cycle's
endpoints on the landing they actually reach, does the floor move? Why did shifting the target by "the"
escape residual make things worse? What is the cheap predictor for a landing, when the target set is a
cloud rather than a thread?
**Status:** structural + MEASURED (session 107) on the flooded-Hyrule Tetra corner, gated in
[`tests/test_cloud_land.py`](../../tests/test_cloud_land.py); the session-106 floor it starts from is in
[`herd-price-of-a-placement.md`](herd-price-of-a-placement.md).
**Source:** [`harness/tetrapush/cloud_land.py`](../../harness/tetrapush/cloud_land.py) (`atom_cloud`,
`cloud_landing`, `residual_fan`, `predict_bound`),
[`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py) (`extend_cycle`'s
``cloud_keep``, `escape_probe`, `roll_probe`).

## Where a keep sits decides whether it can change anything

Session 106 ended pointing at a specific tool: the last cycle's endpoint keep is blind to the landing
(`full_herd.escape_probe` ranks against `objective.placement_thread`'s fit, which a 2D row cloud makes
fiction), so the ~6 u floor it reported was the CUT's rather than the population's. The tool is worth
building and it is built -- but it does not, on its own, move a floor, and the reason is where in the
stage it sits.

`extend_cycle` makes three cuts per cycle, in this order: the junction stage (``jn_keep``), the roll
stage's aim and camera-target cuts (``aim_keep`` / ``tcs_keep``), and only then the ENDPOINT keep. On the
LAST cycle nothing follows the endpoint keep except the escape itself. So an endpoint keep reorders the
final list and reports a better-chosen best; the SET it chooses from was already fixed by the two cuts
upstream. If every survivor lands ~6 u out, ranking them honestly names the least-bad one and changes
the floor by nothing.

That is why the honest scorer and the keep are different jobs:

| | what it is for | cost |
|---|---|---|
| enumerate at the survivors (`cloud_landing`) | the QUOTE -- what a candidate really lands, exactly | ~28 s an endpoint |
| rank the survivors (``cloud_keep``) | reporting the best of a fixed set; no floor movement | ~28 s an endpoint |
| score the AIMS (`predict_bound` in `roll_probe`) | the only cut that changes which endpoints exist | microseconds an aim |

The third is the one with authority, and it is the reason the predictor exists: a per-aim cut cannot
afford an enumeration, and `roll_probe` fires every aim anyway.

## The measurement that settles it, and the reason a blind keep still beat a blind non-keep

Run the last cycle with the keeps OFF (beam 64, nothing thread-ranked) and enumerate at every survivor:
**3 of 30 fire**, and the population's floor is **8.919 u at total 99** where the session-106 run's
landing-blind CUT reached **5.933 at 99**. Removing a blind keep made the answer worse, which only sounds
paradoxical until the refusal is diagnosed rather than counted (`away_walk.fires_census`): on all four
non-firing survivors sampled, **`l_ok` refuses all 672 variants** -- the L would act with Tetra in the
front cone, the clause `snap_reach` already showed the camera channel cannot buy.

So `escape_keep`'s real contribution was never its rank. It was that probing the escape at all keeps
endpoints that CAN escape, and a rank that is fiction still rides on top of a filter that is not. The
lesson generalises past this search: before replacing a proxy-ranked keep, ask what its probe was
filtering as a side effect, because that part may be doing the work.

And with both results in hand the last cycle is not where the frames are: its endpoint pool is 90%
escape-less and its best landing is 6-9 u out either way. The lever is upstream -- the cycle-2 beam that
every round has iterated off, chosen with no landing measure at all.

## The residual is a fan, so the predictor is a fan crossed with the rows

Session 106 measured the escape's residual as a 2D fan: over 1345 firing variants it spans along
-31..+23 and lateral **+13.8..+52**, never below +13.8 -- the atom always pushes Tetra lateral-positive,
so the herd has to deliver her ~14 u lateral-LOW of a row. Two things follow, and the first was already
paid for.

**A fan cannot stand in for its own member.** Shifting the target rows by the measured fast residual
(`aim.handoff_rows`, session 106 rounds 2-3) dropped all 33 roll survivors under a frame budget and,
uncapped, filled the beam with endpoints that convert WORSE (7.8-33.8 u where the unshifted run reached
5.93). A point-shift steers the rank toward whatever converts well for THAT point, which is not the same
set as converts well for the fan.

**So the prediction is a minimum over the fan.** `cloud_land.predict_bound` crosses the fan with the
rows and takes the cheapest whole candidate:

    bound = herd frames + the atom's own LOG length + the row's plan_cost
            + remaining_frames(distance from the shifted landing to that row)

Every term is load-bearing. The atom's LOG is what a delivery replays, not its `freeze_f` (session 105's
off-by-three -- the banked plan is 101 frames, not 98). The row's own `plan_cost` belongs inside because
the rows are 19-23 frames apart (session 104), so a landing 6 u from a cheap row beats one 1 u from an
expensive one. And the miss is priced at [`PUSH_CEILING`](../reference/constants.md), which makes the
exchange rate explicit: ~6 u of landing is ~0.5 frames, so a fast wide atom legitimately out-ranks a slow
exact one -- the trade a miss-only rank gets backwards by 14 frames.

## The fan's SIGN is band-local, so "the atom always pushes her lateral-positive" is not a law

Session 106 measured the fan at its own round-1 endpoints and found lateral **+13.8..+52**, never
negative, and read that as a property of the escape: the atom pushes her lateral-positive, so the herd
must deliver her ~14 u lateral-LOW of a row. Measured again at session 107's endpoints -- the two firing
cycle-3 survivors of round 4, same herd line, same code -- the fan spans lateral **-74.5..-1.9** and
along **+14.7..+72.3**. The sign is reversed.

Both measurements are right about their own states, and neither is a law. It follows from the dependence
`away_walk.probe` already documents: `rotate_side` decides which way Link steps before the slam, so the
residual's lateral tracks his offset from Tetra at **-0.53 u per u**, and which side of her a family of
endpoints sits on decides the sign of the whole fan. A herd instruction derived from one band ("deliver
her lateral-low") is therefore exactly backwards for the other.

This is the strongest available argument for `residual_fan` taking its endpoints as an argument and for
never caching a fan: measure it on the band being searched, every time.

## The predictor is optimistic, and it has to be Newtoned before it is quoted

`predict_bound` is a LOWER bound in the same family as `objective.plan_bound`'s `h`, and it is optimistic
for a specific reason: it assumes every fan member is reachable from the state being scored, and the
residual depends on that state -- its lateral tracks Link's offset from Tetra at **-0.53 u per u**
(`away_walk.probe`). A fan measured at unlike states predicts badly, in the direction that flatters.

So the division of labour is the one this repo keeps re-learning
(the banded-depth proxy taught it on the razor): the predictor
sizes the CUT, the enumeration makes the CLAIM. Measure the fan on the band being searched
(`residual_fan` takes the endpoints, it does not carry a constant), cut aims with it, then enumerate at
the survivors before quoting a landing or deciding where to look next.

## What a capped landing run may not do

The enumeration is ~28 s an endpoint, so a survivor pool of hundreds is hours, and a cap is often right.
A capped run must SAY how many survivors it never enumerated (``cloud_cap`` prints it, and unprobed
survivors keep an infinite bound and a `None` miss rather than a default). A silent truncation reads as
"measured the population" -- which is the exact error session 106 found one level up, and the reason its
~6 u floor needed re-measuring at all.
