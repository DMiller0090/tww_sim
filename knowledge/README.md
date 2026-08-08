# tww_sim knowledge base

The retrieval-first knowledge base for TWW player physics - **superswimming** (swim) and **land**
movement - plus strategy, the shared engine, and the sim/planner model. **Start here** - find your
question below, follow the link, read one small page.

## How this is organized

Knowledge is split by **layer** - different kinds of fact with different lifespans:

| Layer | What | Lifespan |
|-------|------|----------|
| [`mechanics/`](mechanics/) | Game truth - formulas, constants, decomp-grounded behavior | timeless |
| [`strategy/`](strategy/) | TAS heuristics - reboost, dips, phase ordering | evolves |
| [`model/`](model/) | How the sim/planner implements it - engine (FP, anim), swim, land | tracks code |
| [`reference/`](reference/) | [Constants](reference/constants.md), [addresses](reference/addresses.md), [glossary](reference/glossary.md), [commands](reference/commands.md), [data](reference/data.md) | lookup |
| [`history/`](history/) | Provenance, dead ends, superseded conclusions, open questions | frozen |

**`history/` is not current truth** - its pages carry a `status: historical` banner. When you grep
for an answer, prefer the mechanics/strategy/model/reference pages; only read history for "how did we
get here" or provenance. Every page opens with an **`Answers:` / `Status:` / `Source:`** header so
you can triage in one glance.

## Question index

### Basics
- **What is superswimming / potential vs true speed?** → [mechanics/overview.md](mechanics/overview.md)
- **What does <term> mean?** (csangle, ESS, head-bob, x598, …) → [reference/glossary.md](reference/glossary.md)
- **What is the value of <constant>?** → [reference/constants.md](reference/constants.md) (NPC/actor Co-push + Zl1 look values: [reference/constants-npc.md](reference/constants-npc.md))
- **How do I run the sim / planner / a live test?** → [reference/commands.md](reference/commands.md)

### Charging, ESS, neutral, decay
- **How fast does charging build speed / what's the gain formula?** → [mechanics/charging.md](mechanics/charging.md)
- **What is ESS / what stick values / why is diagonal more efficient?** → [mechanics/ess.md](mechanics/ess.md)
- **How much speed do I lose for a given stick value?** (continuous decay law) → [mechanics/decay-curve.md](mechanics/decay-curve.md)
- **What does neutral do / is it really −2 / what's the exit-release speed?** → [mechanics/neutral.md](mechanics/neutral.md)
- **How does the animation cycle / head-bob drag / true displacement work?** → [mechanics/animation.md](mechanics/animation.md)

### Turnaround & arrow
- **How do turnaround frames work? What's the angle threshold?** → 45° off straight-back (`0x6000` = 135°) → [mechanics/turnaround.md](mechanics/turnaround.md)
- **How do you reorient the charge axis?** → [turnaround.md#reorienting-the-charge-axis-turnaround-chains](mechanics/turnaround.md#reorienting-the-charge-axis-turnaround-chains)
- **What is arrow swimming / charge-rate loss / tip-over / spin-up?** → [mechanics/arrow.md](mechanics/arrow.md)
- **Does arrow swimming actually save time?** → **no** (exhaustive offline sweep, 0 wins; best case loses +4 fr) → [arrow.md#does-arrow-swimming-save-time--no-offline-exhaustive](mechanics/arrow.md#does-arrow-swimming-save-time--no-offline-exhaustive)

### Strobo & reboost
- **What is the stroboscopic effect / at what speeds?** → ≈ −794 / ≈ −1630 (air-dependent) → [mechanics/strobo.md](mechanics/strobo.md)
- **Does reboost save time? How big / when? Why does fixed cadence lose?** → [strategy/reboost.md](strategy/reboost.md)

### Pumps & dips
- **What is an ESS pump / the 1-frame entry tax / the x598 scramble?** → [mechanics/pumps.md](mechanics/pumps.md)
- **What is a neutral dip and when does it help?** → [strategy/neutral-dip.md](strategy/neutral-dip.md)
- **What order do the swim phases go in?** → [strategy/phase-ordering.md](strategy/phase-ordering.md)

### Camera
- **How does camera yaw affect movement / the steering law / fine steering?** → [mechanics/camera.md](mechanics/camera.md)
- **What drives csangle on LAND (manual camera, C-stick, L-blips)?** → [mechanics/land-camera.md](mechanics/land-camera.md)

### Culling / rendering
- **How does TWW decide what's drawn vs culled / the view frustum / FOV-near-far / per-actor cull box / why is the culling far ≠ render far / how do I view it live?** → [mechanics/culling.md](mechanics/culling.md)

### Collision geometry
- **How is stage/room collision stored in RAM (the DZB triangle mesh) / how do I reach it from a global / the vertex+triangle layout / ground vs wall vs roof / how do I view the live collision mesh in 3D?** → [mechanics/collision.md](mechanics/collision.md)
- **What happens each frame when Link walks/rolls INTO a wall (the CrrPos wall pass) / wall-hold / roll bonk vs grind / why A against a wall sidles instead of rolling / how does the sim run walls?** → [mechanics/wall-response.md](mechanics/wall-response.md)
- **Why do seam clips work (walking/rolling through a wall corner) / the float-precision root cause / why ≥~36 u + corner >90° + vertical walls / how do I predict one?** → [mechanics/seam-clip.md](mechanics/seam-clip.md)
- **How does an actor push Link (the Tetra "nudge") / cyl-cyl overlap + weight split / can it supply the extra displacement for a seam clip?** → [mechanics/actor-push.md](mechanics/actor-push.md)
- **How FAR can a push move an actor per frame / is `|speedF|/2` a hard bound / what does a plan pay to make the contact END shallow?** → the overlap halved per frame; 13.0 u/f is a steady state, and depth trades against distance → [mechanics/push-magnitude.md](mechanics/push-magnitude.md)
- **Where is the cylinder that pushes other actors (it is not Link's feet) / which lean tilts it and which frame's value does each term read / why does a roll off a curved approach push differently?** → [mechanics/link-co-centre.md](mechanics/link-co-centre.md)
- **When/how does Tetra follow Link (follow radius, speed), and when can Link lock onto / talk to her (the region a planner must avoid)?** → [mechanics/tetra-follow.md](mechanics/tetra-follow.md)
- **Where do Tetra's eyePos (the proc-9 re-aim target) and attention position (the camera's lock target) come from -- her look-at head chase, anims, hidden seed state?** → [mechanics/tetra-look.md](mechanics/tetra-look.md)
- **How does Link's own head turn toward a lock-on target (the m3564 setNeckAngle twist) / what moves mHeadTopPos / why does it feed back into facing through Tetra's look-at?** → [mechanics/link-head-look.md](mechanics/link-head-look.md)
- **How long does a lock-on keep driving the ATN_ACTOR procs after L is released / which check ends LOCK vs RELEASE / why does the roll still exit into the untarget brakeslide once the target is out of frame?** → [mechanics/attention-lock-lifetime.md](mechanics/attention-lock-lifetime.md)

### Ocean world, refills & routing
- **How is the sea laid out / why is only one island loaded / what's a sploosh zone / why route around quadrants?** → [mechanics/ocean-environment.md](mechanics/ocean-environment.md)
- **How do air refills work / why is touching land fatal / flat vs wavy / corner refills / the manual-refill workflow?** → [mechanics/air-refill.md](mechanics/air-refill.md)
- **How does the sim handle unmodeled world features (refills, sploosh) / the re-plan loop?** → [model/planner.md#unmodeled-world-features--the-re-plan-loop](model/planner.md#unmodeled-world-features--the-re-plan-loop)

### Land movement (walk, roll, turns, freeze)
- **Where do I find each land tech / the shared model (two angles, proc states, bit-exact status)?** → [mechanics/land-movement.md](mechanics/land-movement.md) (the land index)
- **How does walking accelerate / what are the two movement angles (facing vs travel) / the speedF foot-plant blend?** → [mechanics/walk-run.md](mechanics/walk-run.md)
- **Is there a walk-before-run speed plateau (~5.0)?** → no - full stick goes straight to the 17 cap (the "plateau" was a phantom front roll) → [walk-run.md#walk--run-acceleration-baseline](mechanics/walk-run.md#walk--run-acceleration-baseline)
- **What is a brakeslide / extended brakeslide (EBS) / why does ESS left-or-right hold speed almost forever / what is the wiggle EBS?** → is *facing* (not travel) relative to `csangle` → [mechanics/brakeslide-ebs.md](mechanics/brakeslide-ebs.md)
- **How does the 1-frame facing snap out of an EBS work / can the camera be steered to make it fire?** → the facing chase crossing TRAVEL, and NO: travel chases csangle, so the window is unreachable → [mechanics/ebs-turnaround.md](mechanics/ebs-turnaround.md)
- **How does the forward roll work / the 26 cap / chained + intermediate roll speeds / the frame-perfect roll-EBS?** → [mechanics/roll.md](mechanics/roll.md)
- **How EARLY can the B thrust fire out of a roll / does holding the stick during the roll open the cut window sooner / my frame-minimal search returned a provably LATE plan, what cost was it not counting?** → [mechanics/roll-cut-thrust-floor.md](mechanics/roll-cut-thrust-floor.md)
- **My A-press rolled in the sim and did NOT roll on console - what deflection does a roll need / what does the game do with a shallower press / which searches owe that gate?** → `mStickDistance > 0.75`, else it sheathes → [mechanics/roll-attack-threshold.md](mechanics/roll-attack-threshold.md)
- **What is the roll stab / the 49.22 single-frame lunge (CUT_F/CUT_A) that reaches a seam clip?** → [mechanics/roll-stab.md](mechanics/roll-stab.md)
- **How do the big-reversal ground turns work (WAIT_TURN pivot / MOVE_TURN turn-around / SLIP skid)?** → [mechanics/ground-turns.md](mechanics/ground-turns.md)
- **What are the targeted ballistic hops (sidehop / backflip) / the A=roll vs L+A=hop mapping / the ESS aim-turn?** → [mechanics/ballistic-hops.md](mechanics/ballistic-hops.md)
- **How do I stop Link at an exact position (the C-up SUBJECTIVITY freeze) / B-cancel / why isn't the re-walk cold?** → [mechanics/precise-stop.md](mechanics/precise-stop.md)
- **From a standstill, fastest way into a roll chain / why hold L on frame 1 / why the frame-6 roll caps at ~25.9?** → [strategy/roll-launch.md](strategy/roll-launch.md)
- **How do we plan and validate a roll-stab SEAM CLIP (dust acceptance, live calibration, the knobs)?** → [strategy/seam-clip-solver.md](strategy/seam-clip-solver.md)
- **The pushed actor is already placed and I can't move her - can I solve for Link's roll ENTRY instead? Which quantity is the razor / why does the PERPENDICULAR half of a placement miss decide it?** → [strategy/clip-entry-search.md](strategy/clip-entry-search.md)
- **My razor search returns "N near-misses, 0 genuine" - is it too small or aimed at nothing? What counts as ONE draw / why did 1.6x the candidates buy zero extra near-misses / which of my fan's prunes are physics?** → [strategy/clip-lottery-draws.md](strategy/clip-lottery-draws.md)
- **The clip works - now I need Link to exit the seam in a particular DIRECTION. Which quantity is the exit angle / can I steer where he cuts FROM / how wide is the facing window really, and how do I argue a facing is dead?** → [strategy/clip-exit-angle.md](strategy/clip-exit-angle.md)
- **My search found the target at a "nearby" entry and a huge pass at it returns nothing at all - is my REACHABLE SET the one I think it is? How do I price a lever in frames before believing it?** → [strategy/clip-exit-angle.md](strategy/clip-exit-angle.md#what-a-cell-costs-in-frames)
- **My pass says "N draws at a DEAD configuration, 0 near-misses, E[hits] 0" - is the cell dead or is my BAND measurement? Which entry lean does a band belong to / is a zero-width band a wall?** → [strategy/clip-band-per-lean.md](strategy/clip-band-per-lean.md)
- **My search has SATURATED - more candidates return the same closest approach bit for bit - what is left to buy? Is a camera slew free / which half of the camera was actually priced / how do I inject one into a stripped fan?** → [strategy/clip-camera-axis.md](strategy/clip-camera-axis.md)
- **My camera axis pays and does not saturate - how many draws are IN it? Is a C-stick that switches mid-plan more cameras / why did deduping my camera list collapse nothing / some cameras cannot aim my cell, is that the axis or my enumeration?** → [strategy/clip-camera-supply.md](strategy/clip-camera-supply.md)
- **My fan spends most of its frames re-walking paths it already walked - why, and how do I tell? How do I widen a pass past what its dedup key set fits in RAM? I bought 10x the prefix families and got 1.9x the draws - what did I widen into?** → [strategy/clip-search-budget.md](strategy/clip-search-budget.md)
- **My entry sweep is too slow for the resolution the razor needs - what is eating the time? Do I have to SIMULATE the roll to score it / when does a compiled context stop being reusable / how do I move the fan onto the native fleet?** → [strategy/clip-search-budget.md](strategy/clip-search-budget.md)
- **My best approach just improved 37x - is my axis converging, or did I enlarge a lottery? I have several axes priced on one scope, where does the clock go?** → [strategy/clip-search-budget.md](strategy/clip-search-budget.md#a-record-is-not-a-trend)
- **My new pass reports a better draw rate than the last one - is it finding NEW tickets or re-drawing the ones I hold? How do I tell a saturating axis before spending an hour on it / why does my axis stop paying long before its supply table runs out / is E[hits] really proportional to my draw count?** → [strategy/clip-draw-ledger.md](strategy/clip-draw-ledger.md)
- **My lottery estimate says E[hits] 1 and my search is still empty - bad luck, or a broken estimate? What exactly is the "hit" my E[hits] counts / a candidate scored a PERFECT ZERO gap and did not clip, how?** → [strategy/clip-band-transfer.md](strategy/clip-band-transfer.md)
- **My axis saturates and I have an hour to spend on it - WHICH candidate do I buy next? Why did ranking my candidates once and taking the top N cluster them / why is my alphabet's most extreme member not in my alphabet?** → [strategy/clip-camera-spread.md](strategy/clip-camera-spread.md)
- **Six passes in and still empty, with the estimate saying it should not be - what is left to be wrong? Were my BANDS measured in the set my CANDIDATES come from / why does my closest approach keep improving while nothing clips / how do I close a razor axis with a PROOF instead of a compute budget?** → [strategy/clip-station-reachability.md](strategy/clip-station-reachability.md)
- **My frame-minimal plan cuts provably LATE and the earliest thrust returns nothing - thin dust or geometry? How do I REFUSE a configuration in one call instead of buying another lottery / can moving the PUSHED ACTOR buy penetration / which clause of my acceptance test is actually failing?** → [strategy/clip-razor-depth.md](strategy/clip-razor-depth.md)
- **My sweep found a placement that clips - can the actor actually STAND there? Why does a position seeded INSIDE a wall push perfectly happily instead of being ejected / which of my search's axes is missing a deliverability filter?** → [model/placement-standability.md](model/placement-standability.md)
- **Is the entry lean a lever on what happens LATE in a roll / why does sweeping it move my cut-frame result by nothing / how many frames does `m351C` survive?** → [mechanics/roll-lean-decay.md](mechanics/roll-lean-decay.md)
- **Sweeping the pushed actor's PLACEMENT changes nothing about my cut-frame contact / my search is FLAT in her position - why, and what axis is left?** → [mechanics/plow-ejection-equilibrium.md](mechanics/plow-ejection-equilibrium.md)
- **How much OVERLAP does my cut frame need and where must the pushed actor stand / why is a small aligned push worth more than a big crooked one / how do I rank a raw sweep row before solving the razor / which aim cell is cheapest?** → [model/required-cut-contact.md](model/required-cut-contact.md)
- **Why does the same corner clip on one thrust and refuse two frames earlier when it is the same animation / which frame of a roll can a cut collect a push on at all / why are placement, velocity, lean and aim ALL worth so little at the floor thrust?** → [mechanics/cut-frame-co-swing.md](mechanics/cut-frame-co-swing.md)
- **My frame-minimal objective is a COST and one term of it refuses - which addend did I never vary? Where did my walk-frame floor come from, and was it ever MEASURED? Why does gridding the reachable hull read `no leverage` at a budget that is actually productive / can a SHORTER walk reach a clip?** → [strategy/plan-cost-walk-budget.md](strategy/plan-cost-walk-budget.md)
- **I measured a saving in UNITS - what is it worth in FRAMES? What does my frame cost count FROM / can I just stop my delivered plan early or re-aim its ending / is my DEPTH ranking selecting the placements my objective wants?** → [strategy/herd-price-of-a-placement.md](strategy/herd-price-of-a-placement.md)
- **I ranked my last stage on the thing it actually delivers and the floor did not move - where does a keep have to SIT to change anything? Why did shifting my target by "the" measured residual make it worse / what is the cheap per-aim predictor when the target set is a CLOUD?** → [strategy/landing-keep-on-a-cloud.md](strategy/landing-keep-on-a-cloud.md)
- **My plan lands IN THE BAND at a winning total and still is not deliverable - what did the row's `plan_cost` assume about MY arrival? Why does `hull_scan` read `no leverage anywhere` here and leverage-without-dust there?** → [strategy/delivery-is-two-predicates.md](strategy/delivery-is-two-predicates.md)
- **My candidate's ARRIVAL is in the wrong place - is that the endpoint, or where I stopped measuring? What ends the escape atom, and what if I keep holding the exit stick? Why does an arrival 20 u from a station reach NOTHING / why do extra tail frames never improve my bound?** → [strategy/the-arrival-is-payable.md](strategy/the-arrival-is-payable.md)
- **I have swept every knob my escape has and the landing barely moves - is it a steering channel at all? Why is my frame-minimal miss always LATERAL / what exactly does the escape push her / why is a shorter herd not simply a cheaper plan?** → [strategy/the-landing-belongs-to-the-endpoint.md](strategy/the-landing-belongs-to-the-endpoint.md)
- **Straightening my push costs me atom frames - why? Why is my arrival free at a CROOKED endpoint and unpayable at an on-line one / what offset should my last cycle aim for / my cut finally produced on-line endpoints and they all read `nofire`, is that the grid or the physics?** → [strategy/the-offset-cannot-pay-both.md](strategy/the-offset-cannot-pay-both.md)
- **I widened my escape's exit arc to 90 degrees and the arrival did not move ONE unit - is the arc broken? What are the tail frames between my in-band total and my paid one actually buying / why does every relocation axis TRADE the two halves instead of solving them / is `d_station` beside my best landing the same as my arrival floor?** → [strategy/the-short-atom-is-a-point.md](strategy/the-short-atom-is-a-point.md)
- **My sweeps all TRADE the two predicates and none pays both - is that the physics or is my BASIS a dimension short? Once the escape is a rigid throw, where do I GET the endpoint from instead of gridding for it / why does a finite-difference Newton stall at its very first iterate here / what does the separation my specification needs actually COST in frames?** → [strategy/the-endpoint-is-four-numbers.md](strategy/the-endpoint-is-four-numbers.md)
- **My specification wants far more separation than any node has - can I just hold a stick at the endpoint and buy it? What does a unit of separation COST, and is the endpoint-speed cap the right price / why does my atom fire NOTHING from a deeper endpoint when the shallow one fires thousands / is my per-aim cut looking at Link's arrival at all?** → [strategy/the-separation-is-not-a-suffix.md](strategy/the-separation-is-not-a-suffix.md)
- **My census says ONE clause refuses most of my search - is that a wall or a rank that never asked for it? A previous session measured this camera unreachable, does that close it / why are two nodes of my beam, same endpoint and same roll, one firing and one dead / how do I tell a screen measuring the WRONG QUANTITY from one measuring a real limit?** → [strategy/the-camera-supplies-the-cone.md](strategy/the-camera-supplies-the-cone.md)
- **I fixed the screen that was refusing my search and the beam still does not improve - what did fixing it actually buy? Which slot of my mixed keep is earning its place / can a quantity a previous session retired as "the wrong question" still be the right RANK / how fine does my swept grid have to be?** → [strategy/the-screen-is-not-the-rank.md](strategy/the-screen-is-not-the-rank.md)
- **Every candidate on my beam owes the SAME arrival bill - is that geometry or is it my station list? How do I tell an arrival that is too FAR from one pointed the wrong WAY / why do extra tail frames make it WORSE / what does a knob grid that holds two values of an axis cost me?** → [strategy/the-exit-bearing-buys-the-arrival.md](strategy/the-exit-bearing-buys-the-arrival.md)
- **One half of my predictor's score never moves - is the term wrong or is my measured TABLE missing the column it reads? What does `dict.get(key, default)` cost on a measured record / a knob my library has had for eight sessions has never shown up in a result, is it worthless or unreachable / my honest table is now 400x bigger than the screen can afford, do I coarsen the grid?** → [strategy/the-fan-outlived-its-columns.md](strategy/the-fan-outlived-its-columns.md)
- **I plumbed a measured axis into my per-aim screen and the predicted bound moved by EXACTLY zero everywhere - is the plumbing broken? Why does my 75k-member table answer like a 3-member one / I fixed a 2x error, every rank moved, and the cut came out byte-identical - was the fix pointless / which of my two measures can even see a knob that pays late?** → [strategy/the-cheapest-atom-owns-the-screen.md](strategy/the-cheapest-atom-owns-the-screen.md)
- **My cheap screen and my exact keep rank the same candidates differently - which term does it? How do I predict "the cheapest variant that LANDS" instead of "the cheapest variant" / is a banded search always the slow one / what does a length restriction fix that a predicate does not?** → [strategy/minimise-subject-to-the-predicate.md](strategy/minimise-subject-to-the-predicate.md)
- **I fixed my screen's reduction and the ranking still did not improve - what else is wrong? Is my "optimistic by construction" predictor actually a bound / why does it call 24 of 27 endpoints deliverable where 6 deliver / is it the beam's rank, the screen, or the budget that drops my good endpoints?** → [strategy/the-fan-is-not-a-bound.md](strategy/the-fan-is-not-a-bound.md)
- **One clause of my acceptance refuses most of my variants - is relaxing it the next axis? Would a bigger budget revive the candidates that pass nothing / how do I price a quality bar in frames / why does "no upstream knob buys it back" not make a clause worth fixing?** → [strategy/the-dip-budget-is-not-the-lever.md](strategy/the-dip-budget-is-not-the-lever.md)
- **Half my beam is candidates that can never end a plan - is fixing the keep that admits them worth a session? Should my screen be a keep SHARE or a REQUIREMENT / how do I tell a calibration that transfers from one measured on a different quantity / what does an A/B buy me when both lanes tie?** → [strategy/the-shape-of-a-cut-is-not-its-answer.md](strategy/the-shape-of-a-cut-is-not-its-answer.md)
- **My last stage's endpoints all land PAST the target - should I re-cut the stage before it to hand off earlier? How do I test an upstream re-cut before paying an hour for it / why is my arrival free at one endpoint and 140 u away at the next / what does landing nearer the target actually buy?** → [strategy/the-handoff-along-was-already-spanned.md](strategy/the-handoff-along-was-already-spanned.md)
- **What is the separation between my two actors actually FOR? Why does every endpoint on my beam owe the same arrival bill wherever it lands / my search finally produced a DEEP endpoint and its escape fires nothing, is that the depth or the camera / is an irreducible bill a search failure or the room?** → [strategy/the-depth-the-room-asks-for.md](strategy/the-depth-the-room-asks-for.md)
- **My search's hits keep getting REJECTED by the confirm/replay step even though the state looks right - what prune am I missing? Which frame's proc does a queued button dispatch from?** → [strategy/search-prune-the-dispatch.md](strategy/search-prune-the-dispatch.md)
- **Every quantity my razor search sweeps came out console-exact and the trick still failed - what did I not price? Is a "measured constant" still constant at the frame that gets SCORED? When is a verdict undecidable rather than wrong?** → [strategy/razor-prices-every-term.md](strategy/razor-prices-every-term.md)
- **Which partial stick magnitudes are live-valid in a land plan / why NEVER emit Y 192–254?** → [mechanics/precise-stop.md](mechanics/precise-stop.md). NB: this live-valid *stick-input* band is a different thing from the sim's [`Y171` partial-magnitude *regime*](model/land-sim.md#partial-magnitude-regime-y171-msd052) - don't conflate "partial stick" with "partial regime".

### Model - engine (core)
- **Why f32/ctypes / op-order / `_F32_PI` / `cM_rad2s` truncation / the baked cos+sin tables / which matrix-quat ops are FMA-fused?** → [model/fp-faithfulness.md](model/fp-faithfulness.md)
- **How does the J3D anim runtime work / the 42-joint skeleton / Hermite keyframes / world-space foot FK / `PSMTXQuat` / how does the toe become `speedF`?** → [model/anim-engine.md](model/anim-engine.md)
- **Why must the euler→quat half-angle be sign-extended / why isn't a negated quaternion bit-equivalent?** → [model/euler-quat-signed-half.md](model/euler-quat-signed-half.md)
- **Why must an anim frame ctrl's rate be f32 / how can two rates that "are 1.1" advance to different frames / why does one ULP of anim frame matter?** → [model/anim-frame-is-f32.md](model/anim-frame-is-f32.md)
- **Which position/lean is the model POSED from (before or after `posMove`) / why does a proc-init frame draw upright / why do ULPs of base matter?** → [model/draw-base.md](model/draw-base.md)
- **Does a drawn sword change the walk anims (WALKS/DASHS) / which anims does `getAnmData` swap / why can that move `speedF`?** → [model/equipped-anim-set.md](model/equipped-anim-set.md)
- **Does the anim keep running while Link is STOPPED / why is a re-walk's first step tiny / when does a stop reset the walk phase / what does low health change?** → [model/wait-stop-pose.md](model/wait-stop-pose.md)

### Model - swim
- **Why f32 / the console cosine table / CHARGE_DISP_FACTOR / cold-start mRate?** → [model/swim-sim.md](model/swim-sim.md)
- **How does the planner search / why are mid-swim pumps off by default / the crossover decomposition / the speed-retention prune?** → [model/planner.md](model/planner.md)
- **What are the predict/ modules / the off-axis residual?** → [model/predictors.md](model/predictors.md)

### Model - land
- **How does the land sim accumulate position (f32) / the `Y171` partial regime / the 7 red ULP tests?** → [model/land-sim.md](model/land-sim.md)
- **How does floors mode follow a sloped floor (Phase G) / the zero atan cell / m35B8 / m35C4 (setStepsOffset) / field_0x030 / what does a floors anchor seed carry?** → [model/ground-model.md](model/ground-model.md)
- **How does the land planner reach a target (x,z) / the live-valid stick set / the C-up freeze to z=2000 / seam-clip vs RTA bars?** → [model/land-planner.md](model/land-planner.md)
- **How does the land SETUP FINDER work (human-consistent discrete moves → ranked input seqs) / why re-simulate instead of summing displacements / which moves are "blocks" / why isn't walking one?** → [model/land-setup-finder.md](model/land-setup-finder.md)
- **What are the targeted ballistic hops (sidehop / backflip) / the A=roll vs L+A=sidehop/backflip input mapping?** → [mechanics/ballistic-hops.md](mechanics/ballistic-hops.md)

### Provenance & open work
- **Was <bug> a physics issue or an artifact?** (bug#2, 554, off-axis, omega grid, cosine table) → [history/resolved-bugs.md](history/resolved-bugs.md)
- **What's still unresolved?** → [history/open-questions.md](history/open-questions.md)
- **Why run a search's fidelity gate BEFORE the search / how did a clip search end up aimed at a roll nobody performs?** → [history/entry-search-s79-superseded.md](history/entry-search-s79-superseded.md)
- **Why audit a search's own accounting before scaling its biggest cost / how did "the fan is the only budget" turn out to be wrong by 12x?** → [history/entry-search-s80-superseded.md](history/entry-search-s80-superseded.md)
- **I proved a prune was my own assumption, not physics - why isn't removing it a lever? Why price an axis before promoting it?** → [history/entry-search-s81-momentum-lever.md](history/entry-search-s81-momentum-lever.md)
- **My axis priced at exactly 8x - why is a perfectly integral multiplier a warning sign? How did sweeping a facing at 1 BAM measure the same configuration sixteen times?** → [history/entry-search-s81-camera-lever.md](history/entry-search-s81-camera-lever.md)
- **My model is live-gated 0 ULP and still wrong - how? Why record the REGIME a capture covers next to the claim it proves?** → [history/co-centre-body-chn-twist.md](history/co-centre-body-chn-twist.md)
- **I widened my search's input alphabet on a measurement and the console refused a third of it - why can a gate on the model prove nothing about a DISPATCH? What does a containment check actually promise?** → [history/aim-alphabet-whole-grid.md](history/aim-alphabet-whole-grid.md)
- **Two implementations of one quantity disagree and every capture I have is blind to it - how do I design the run that decides? Why can a code seam be a symptom rather than the bug?** → [history/co-centre-two-ports.md](history/co-centre-two-ports.md)
- **My dedup collapsed 137 objects into 49 and I read it as a discount - what was it actually telling me? Why is enumerating an input's PATHS the wrong axis?** → [history/entry-search-s95-segmented-cameras.md](history/entry-search-s95-segmented-cameras.md)

## Page template (for contributors)

```
# Title
**Answers:** <the questions this page answers, in plain language>
**Status:** validated | approximate | open  (+ how)
**Source:** decomp <file:line> · live <date> · History: <link>
---
<definition → formula → constants (LINK to reference/constants.md, don't restate) → validation>
## See also
```

Keep pages **small and single-topic** (one Read should answer the question). Put dated narrative and
superseded findings in `history/`, not in the truth pages. One canonical value per constant - link
to [constants.md](reference/constants.md) instead of restating numbers.

If a topic has an **unresolved verdict**, give it a short `## Open question - <current status>`
section *in the truth page* (state the current best answer + "unproven"), and link to `history/` for
the provenance. The definitive *current* answer must be reachable from the truth layer - not only
from a `status: historical` page. (Validated by the doc-eval: weak agents were told to prefer
non-history pages, so an answer that lives only in history is effectively hidden.)

The KB is regression-tested by a bounded weak-agent eval - the question bank + run protocol under
[`_eval/`](_eval/) (Tier-A retrieval / Tier-B comprehension, run by fanning out weak sub-agents;
agents must never read `_eval/` itself, the answer key).
