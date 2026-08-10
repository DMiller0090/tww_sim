# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""THE FULL HERD -- the 2-roll chain composed cycle-over-cycle to the genuine-coord cluster (s43).

Session 42 cleared Dereck's 2-roll bar (12.862 u/frame vs the human's 12.758). The unit that did it
-- junction (phase list, gated, armed) -> roll (fan aim, L pulse, computed C-stick slew) -- is
generic; this module CHAINS it N times, out to the ~967 u the genuine `tetra_placements` cluster
sits down-herd, and scores the endgame (how close Tetra lands to a genuine coord).

WHAT CYCLE 3+ NEEDS THAT CYCLE 2 DID NOT: EVERY ROLL MUST STEER ITS OWN CAMERA
------------------------------------------------------------------------------
`cycle2_chain` swept `target_cs` on roll 1 only; roll 2 ran with a frozen camera because nothing
came after it. In a chain, the roll of cycle k sets up the junction of cycle k+1 -- so every roll
sweeps a `target_cs`, and the grid is **derived from that roll's OWN entry csangle**
(`derived_target_css`), never the s42 winner's 38812 (`[[no-overtuned-constants]]`: the band is
entry-state-relative, ~+-300 BAM of post-roll EBS travel).

THE SEPARABILITY THAT MAKES IT AFFORDABLE (measured here, gated by `target_cs_is_exit_only`)
---------------------------------------------------------------------------------------------
With the aim fixed, `target_cs` changes NOTHING until the roll's exit: Tetra's position is
bit-identical every frame of the roll, as are the roll's speedF and locked facing; only the camera
state (and hence the post-exit EBS travel) differs. The main stick is already known inert inside a
roll (s41), and this is the C-stick counterpart. So a cycle's roll stage factors:

  stage R1  sweep the AIM (camera frozen) -- this alone decides the push -- and keep the best;
  stage R2  for each kept aim, sweep the derived `target_cs` grid, keeping the ones whose endpoint
            can actually be CONTINUED (`junction_quality`).

Without the factoring the cycle costs |aim| x |tcs| rollouts; with it, |aim| + keep x |tcs| -- and
the tcs values are pruned by the thing they exist for, the next junction. Cycle 1 gets the same
treatment (`cycle1_nodes`): 159 s -> 10 s for the identical 13.147 u/f best. Those probes are this
search's cheap monotone predictors; the exact bit-confirm is `confirm_plan` (the method reference in
SESSION_PROMPT: predictor + prune + exact confirm, no calibration).

TWO THINGS THIS SESSION HAD TO FIX BEFORE ANY OF IT SEARCHED CORRECTLY
-----------------------------------------------------------------------
  * **Clone independence** (a real harness bug, fixed in `tww_sim/land/state.py`): `LandState.clone`
    shared the mutable `AttentionLock` -- the machine that routes a roll exit to proc 9 vs 6 -- so
    branches corrupted each other AND their parent, permanently. Replaying one junction from a
    clone gave facing 16138, then 34819 after 25 unrelated sibling rollouts. Every beam here rests
    on clone isolation; gated by `tests/test_full_herd.py`.
  * **The endpoint keep must be ROLLABILITY, not flatness** (`roll_probe`). Flatness does not
    predict it: over three cycle-1 nodes, 32 / 43 / 71 of 400 endpoints were rollable, and on the
    first node none of the rollable ones were among the flattest. That single ranking choice was
    what made the cycle-2 stage report hundreds of valid endpoints and zero surviving rolls, four
    times over.

Pure stdlib, no Dolphin. CLI: ``python -m harness.tetrapush.full_herd {sep | box | plan | endgame}``.
The ``endgame`` command also runs the coupled-entry stage (milestone 2b). Session 46 quantified the
BARRIER against the decomp bar: the plow ejects Tetra by `CO_RADII_BAR - centre_feet`, so she is
FROZEN on her coord exactly when Link's exec Co-centre sits >= 80 u (`LINK_CO_R + TETRA_CO_R`) from
her. `separation_scan` reports `centre_feet`/`deficit`/`freeze_ok`; the s44 placement lands 15.4 u
below the bar (deep contact) so any step ejects her. The FIX is a GRAZING arrival (chain ranked to
place her at `centre_feet >= 80`, route a). ABOVE the bar 2b reduces to a Link-ONLY navigation to the
entry (Tetra untouched); `entry_targeting`'s down-herd push fan STALLS there (the EBS backslide
carries Link off the up-herd entry), so it stays as the in-band GUARD and `walk_to_entry` (session 47)
is the real navigation -- a `reach_precise` glide to `seeds.ENTRY_ROLL_POS` on the coupled run.

THE SECOND HALF OF THE BARRIER: ARRIVAL MOMENTUM, NOT JUST POSITION (session 47)
--------------------------------------------------------------------------------
The s46 `freeze_ok` (centre_feet >= 80) is POSITIONAL and necessary but NOT sufficient. `walk_to_entry`
run on a synthetic frozen arrival (`synthetic_frozen_arrival`, the `walk` CLI) shows the SAME freeze_ok
position walks CLEAN (Tetra bit-frozen) from a near-rest arrival but re-plows her ~59 u from a hot
down-herd EBS -- the ~5 frames it takes to bleed a -25.7 momentum off drift Link back below the bar,
and a turnaround does not rescue it (the snap preserves the -25.7). So route a's grazing chain must
deliver Link NEAR-REST / receding up-herd, not merely at centre_feet >= 80. The walk maneuver itself is
solved (Link reaches the entry to ~7 u clean); the open piece is the chain that arrives that way.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import objective as O
from harness.tetrapush import search as S
from harness.tetrapush import two_roll as T
from harness.tetrapush import roll_kernel as RK
from harness.tetrapush.reposition import AXIS_HERD, AXIS_PAIR, HerdLine, ESS_DOWN
from harness.tetrapush.steered_reposition import _bearing, _s16
from harness.tetrapush.tetra_plow import LINK_CO_R, TETRA_CO_R
from tww_sim.land.land import FRONT_ROLL
from tww_sim.land.constants import WAIT, FREE_WAIT
from tww_sim.land.plan_land._primitives import stick_for_bearing, world_angle_s16

# The clean-separation bar (s46): the plow depth is `CO_RADII_BAR - dist(exec_centre, Tetra_feet)`,
# so it ejects ZERO -- Tetra FROZEN -- once the exec centre sits >= 80 u away. See `_centre_feet`.
CO_RADII_BAR = LINK_CO_R + TETRA_CO_R

# The camera's slew authority over a roll's frames (~460-530 BAM/frame, `steered_reposition
# .camera_authority`) bounds the reachable band; 128 BAM resolves the ~+-300 BAM viable window.
TCS_SPAN = 1536
TCS_STEP = 128

# The LAST cycle's grid: one roll's MEASURED slew reach (-46.6..+40.7 deg over 112 arrivals), at the
# 512 step its snapping targets are 1-2 members wide in. Why it differs: `camera_probe_key`. 512 is
# MEASURED-right, not a compromise -- 128 buys 2.4x the population and 0.000 u (`escape_tcs_step_note`).
ESCAPE_TCS_SPAN = 0x2800
ESCAPE_TCS_STEP = 512


def escape_tcs_step_note():
    """**Why `ESCAPE_TCS_STEP` stays 512, and the reason not to re-run this sweep finer** (session 74).

    The snapping ``target_cs`` values are 1-2 members wide AT 512 BAM, so a finer step looks like free
    recall. Measured: a step of 128 grows the snapping population **2.4x** -- 63 -> 83 of 112 arrivals,
    84 -> **199** (arrival, tcs) pairs, 33927 -> **85192** firing atom variants, with 20 arrivals whose
    window is NARROWER than 512 BAM (all at -13.4..-21.1 deg) -- and it moves the frontier by
    **0.000 u**: pd **0.432** at 75 frames either way, `objective.verdict` True, best-by-bound
    **bit-identical** (75.12, jf 7 end 285, ``freeze_f`` 4, `aim.handoff_spec` True). Only 74 f moves at
    all, 24.680 -> 23.919, against a `objective.PLACEMENT_BAND` of 1.0, and `objective.replay_and_score`
    on the new winner returns the SAME plan `fixtures/courtyard_plan_s73.json` already holds.

    The cause is structural rather than a resolution accident: ``target_cs`` is EXIT-ONLY for Tetra
    (`target_cs_is_exit_only`), so over 161 targets x 112 arrivals her arrival along/lateral spread is
    **0.00 u**. A finer grid buys more camera states for the SAME arrivals, and what a plan can land at a
    given frame count is capped by the ARRIVAL (`away_walk.push_profile`'s ledger). More camera is not
    more placement.

    Returns the measurement as data, so a caller or gate can assert on it instead of on prose."""
    return dict(step=ESCAPE_TCS_STEP, finer=128, arrivals=(63, 83), arrivals_total=112,
                pairs=(84, 199), variants=(33927, 85192), narrow_window_arrivals=20,
                pd_at_75=(0.432, 0.432), pd_at_74=(24.680, 23.919), bound=(75.12, 75.12),
                arrival_spread=0.0)


def frame_in_model(run, walls=None):
    """**Both MODEL-BOUNDARY prunes, in one place** (`objective` rules 4 and 4b, session 60).

    Every search stage below used to test only the first half: `run._follow_warned`, Tetra past
    `FOLLOW_ENGAGE_DIST` where she self-locomotes in stt 4. Session 60 measured the second half and
    found it enforced NOWHERE -- the Courtyard `FreeRun` models no BG collision at all, so a plan is
    free to walk Link straight THROUGH the courtyard back wall (node 1's does, from plan frame 84,
    while the console has him braced at exactly `LINK_WALL_R`). Both are boundaries of what the
    forward model covers, not preferences, so they belong side by side and are checked together.

    This is a PRUNE, not a wall model: it keeps the search in the region where the missing
    `WallCorrect` cannot act. If a plan ever genuinely needs wall contact during the herd, this has
    to become a model -- widening the radius instead would only hide the infidelity again."""
    return (not run._follow_warned) and O.frame_is_wall_free(
        run.link.pos_x, run.link.pos_z, run.tx, run.tz, walls)


def derived_target_css(run, span=TCS_SPAN, step=TCS_STEP):
    """The per-cycle camera-slew grid, DERIVED from this roll's own entry csangle (never a constant
    carried between cycles -- the viable band is entry-state-relative, s42)."""
    cs0 = int(run.csangle)
    return tuple((cs0 + off) & 0xFFFF for off in range(-int(span), int(span) + 1, int(step)))


# --------------------------------------------------------------------------- the separability fact

def target_cs_is_exit_only(env, *, offsets=(1536, -1536), upto=24):
    """**The measured C-stick counterpart of s41's in-roll stick inertness**: during a roll, the
    camera target changes nothing but the camera. Replays one cycle-1 roll at the same aim under
    several `target_cs` values and reports the first frame at which ANY physics state diverges,
    together with whether Tetra ever moved differently and whether the roll's speedF/facing changed.

    Returns ``dict(ok, first_diverge, roll_frames, tetra_identical, roll_speedF, roll_facing)``;
    ``ok`` means the divergence is confined to the exit (no Tetra difference, same roll)."""
    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    fb = _bearing((base.link.pos_x, base.link.pos_z), (base.tx, base.tz))
    base.step(T._inp(fb, base.csangle, 1.0, buttons=S.PAD_L, triggerL=255))
    center = _bearing((base.link.pos_x, base.link.pos_z), (base.tx, base.tz))
    aim = T.roll_facing_fan(base, center, 0x2000, 8)[0][1]
    cs0 = int(base.csangle)

    def trace(tcs):
        r = base.clone()
        stream = T.roll_stream(aim, hold=1, a_hold=2, l_window=(5, 8))
        rows, roll = [], None
        for k in range(upto):
            r.step(dict(stream(k), substickX=T.slew_substick(r.csangle, tcs), substickY=0))
            if r.link.state == FRONT_ROLL and roll is None:
                roll = (r.link.speedF, r.link.facing)
            rows.append((r.link.state, r.link.facing, r.link.pos_x, r.link.pos_z, r.tx, r.tz))
        return rows, roll

    ref, roll_ref = trace(None)
    n_roll = sum(1 for row in ref if row[0] == FRONT_ROLL)
    first, tetra_same, roll_same = upto, True, True
    for off in offsets:
        rows, roll = trace((cs0 + off) & 0xFFFF)
        d = next((k for k, (a, b) in enumerate(zip(ref, rows)) if a != b), None)
        first = min(first, upto if d is None else d)
        tetra_same &= all(a[4:] == b[4:] for a, b in zip(ref, rows))
        roll_same &= (roll == roll_ref)
    return dict(ok=tetra_same and roll_same and first >= n_roll, first_diverge=first,
                roll_frames=n_roll, tetra_identical=tetra_same, roll_speedF=roll_ref[0],
                roll_facing=roll_ref[1])


# --------------------------------------------------------------------------- the cycle's roll stage

def pursuit_box(env, hl, margin=1.5):
    """**The PURSUIT REGIME, measured off the recorded window** -- not a tuned constant. Over his
    whole 2-roll push the human holds a strikingly tight geometry: Link stays 40-85 u BEHIND Tetra
    along the push axis, within ~12 u of the herd line laterally, and the bearing from Link to Tetra
    never leaves ~+-14 deg of the herd direction. That is what a plow-pursuit looks like; a state
    outside it cannot roll into her at all (measured: from a lat +43 / lead -17 endpoint, ZERO of
    the 95 full-circle roll aims survives the on-line prune).

    Returns the recorded bounds widened by ``margin`` -- ``dict(max_lat, lead_lo, lead_hi,
    max_delta)`` (delta in BAM). `human_in_box` gates that the human himself passes it."""
    rows = S.rollout_recorded(env, upto=45)['rows']
    hb = hl.bearing_bam()
    lats, leads, deltas = [], [], []
    for r in rows:
        lx, lz, tx, tz = r['link'][0], r['link'][-1], r['tetra'][0], r['tetra'][-1]
        lats.append(abs(hl.lateral(lx, lz) - hl.lateral(tx, tz)))
        leads.append(hl.lead(lx, lz, tx, tz))
        deltas.append(abs(_s16(_bearing((lx, lz), (tx, tz)) - hb)))
    return dict(max_lat=max(lats) * margin, lead_lo=min(leads) * margin,
                lead_hi=max(leads) / margin, max_delta=max(deltas) * margin)


def in_pursuit_box(run, hl, box, axis=AXIS_HERD):
    """Is this coupled state inside the measured pursuit regime (`pursuit_box`)?

    **``axis`` IS WHAT CAPPED THE PLAN (session 135), and it is one assumption, not a constant.**
    The three clauses say: Link is 26.8-127.8 u behind her, within 18.0 u of the push line, and
    bearing to her within 21.35 deg of it. Read on `AXIS_HERD` all three are measured against ONE
    fixed world direction, which also asserts that the direction he pushes IS the direction the herd
    wants. By the last two cycles that is false and load-bearing: session 134's band-keeping cycle-2
    beam (``l0`` -51.75, past the -80.4 bar) died here at generation 1 with separations 58.8 / 63.9 /
    64.6 u -- dead centre in the human's own recorded 40.4-85.2 u plow band -- against ``max_lat``
    17.99 (it read -35.5 / -49.2 / -58.6) and ``max_delta`` 21.35 deg (-37.1 / -49.6 / -66.5).
    Ordinary plow pairs pointing 37-67 deg off the herd line.

    On `AXIS_PAIR` the identical predicate is read about the pair's own push axis
    (`reposition.pair_line`), where ``lead`` is minus the separation and the lateral and bearing
    terms are zero by construction -- so it collapses to the human's measured SEPARATION band and
    costs one hypot. Nothing is widened and no constant is invented (`[[no-overtuned-constants]]`);
    the equality with the full three-clause form about `pair_line` is the gate, not a claim
    (`tests/test_free_axis.py`)."""
    lx, lz, tx, tz = run.link.pos_x, run.link.pos_z, run.tx, run.tz
    if axis == AXIS_PAIR:
        return -box['lead_hi'] <= math.hypot(lx - tx, lz - tz) <= -box['lead_lo']
    lead = hl.lead(lx, lz, tx, tz)
    if not (box['lead_lo'] <= lead <= box['lead_hi']):
        return False
    if abs(hl.lateral(lx, lz) - hl.lateral(tx, tz)) > box['max_lat']:
        return False
    return abs(_s16(_bearing((lx, lz), (tx, tz)) - hl.bearing_bam())) <= box['max_delta']


def human_in_box(env, hl, box=None, axis=AXIS_HERD):
    """Containment for the regime gate (`[[search-space-contains-human]]`): the recorded human must
    sit inside the pursuit box on EVERY frame of his window -- the box is read off him, so this
    asserts the margin logic never inverts. Returns ``dict(ok, outside)``.

    It is the containment test for ``axis`` too, and the one that says a freed direction is still HIS
    regime: on `AXIS_PAIR` the clauses that survive are the separation band, and his own separation
    never leaves 40.4-85.2 u."""
    box = pursuit_box(env, hl) if box is None else box
    hb = hl.bearing_bam()
    outside = []
    for r in S.rollout_recorded(env, upto=45)['rows']:
        lx, lz, tx, tz = r['link'][0], r['link'][-1], r['tetra'][0], r['tetra'][-1]
        if axis == AXIS_PAIR:
            if not (-box['lead_hi'] <= math.hypot(lx - tx, lz - tz) <= -box['lead_lo']):
                outside.append(r['f'])
            continue
        lead = hl.lead(lx, lz, tx, tz)
        lat = abs(hl.lateral(lx, lz) - hl.lateral(tx, tz))
        delta = abs(_s16(_bearing((lx, lz), (tx, tz)) - hb))
        if not (box['lead_lo'] <= lead <= box['lead_hi'] and lat <= box['max_lat']
                and delta <= box['max_delta']):
            outside.append(r['f'])
    return dict(ok=not outside, outside=outside)


def junction_alphabet(run, hl, *, ess_step=4, aim_step=64):
    """The junction's PER-FRAME input alphabet: the low-magnitude ESS sticks that steer the glide
    (`two_roll.ess_fan`), a coarse spread of full-magnitude aims (the human's f27 "pre-aim" is a
    full stick, (211,230), which no ESS fan contains), and -- always -- the TOWARD-TETRA full stick,
    which is the ARMING input (the proc-7 flip fires when a toward-Tetra stick acts under L, so
    without it in the alphabet every endpoint reads 'unarmed' forever). Each member is offered with
    and without L by `junction_beam`."""
    out = [b for _a, b in T.ess_fan()[::max(1, int(ess_step))]]
    out += [b for _w, b in T.roll_facing_fan(run, hl.bearing_bam(), 0x4000, int(aim_step))]
    tb = _bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz))
    out.append(stick_for_bearing(tb, run.csangle, msd=1.0))
    return out


def roll_probe(endpoint, hl, *, step=24, l_window=(4, 7), min_roll=20.0, half_window=0x2800,
               dead=None, corridor=None, target_along=None, thread=None, resid=None,
               fan_center=None, fan=None, rows=None, stations=None, pf=None, axis=AXIS_HERD,
               collect=None, terminal=None, terminal_sink=None):
    """**Is this junction endpoint ROLLABLE at all, how STRAIGHT can its roll be, where does it
    ARRIVE, and where would the ESCAPE land from it?** -- an aim sweep, returning
    ``dict(rate, off, off_rate, along, n, arrive, over, land, land_frames, land_off, land_over,
    fan_edge, fan_half)`` for the surviving rolls, or None if none survive.

    This is the endpoint keep's real criterion, because FLATNESS DOES NOT PREDICT IT. Measured over
    three cycle-1 nodes (400 endpoints probed each): 32 / 43 / 71 were rollable, and on the first
    node NONE of them were among the flattest (they sat at |lat| ~17) while on the other two the
    rollable ones were the flattest (|lat| 0.2-0.4). So a flatness keep silently empties the stage on
    some entry states and works on others -- which is exactly how the cycle-2 stage kept reporting
    hundreds of valid-looking endpoints and zero surviving rolls. Probe; do not rank by proxy.

    ``off`` (session 68) is the same lesson applied to SQUARENESS, and it is why the endpoint's own
    `aim.corridor_aim_error` is not what the keep should rank on: at a LONG junction (jf 10-12) the aim
    swings 5-8 deg per frame, so an endpoint measuring +1.12 deg fires a roll that leaves Tetra
    **37.6 u off the corridor** with Link 51 u off her lateral and a next junction that arms NOTHING.
    The sweep already fires every aim, so the straightness it can actually DELIVER (the corridor offset
    of the best surviving roll's endpoint, `objective.push_corridor`) costs nothing to report -- and
    unlike the entry aim it cannot lie. ``off_rate`` is the straightest roll's own down-herd rate, so a
    caller can see what the straightness costs in frames.

    ``target_along`` (session 70) is the SAME lesson applied to the third axis, ARRIVAL. A cycle's roll
    is a ~205 u atom that cannot stop short, so where a plan ENDS is decided by which endpoint it rolls
    from -- and nothing here ranked that: the s69 cycle-3 stage kept endpoints whose rolls landed Tetra
    at along **947** against a `aim.handoff_target` of **894**, 53 u past it, which is ~4 frames spent
    twice (bought going past, then paid back in lateral) and the whole of that run's 78-80 vs 75-frame
    overrun. The junction is the adjustable part (~13 u/frame of pursuit against the roll's fixed
    length), so the arrival is a property of the ENDPOINT -- exactly the shape ``off`` has. The sweep
    already fires every aim, so the along its rolls DELIVER costs nothing to report, and ``arrive`` is
    the smallest ``|delivered along - target_along|`` any surviving roll reaches (``over`` its signed
    value, + = past the target). ``along`` is the straightest roll's own delivered along.

    ``thread``/``resid`` (session 71) give the axis that SUBSUMES those two and corrects them:
    ``land`` = the smallest `aim.thread_miss` any surviving roll's ESCAPE would reach (the delivered
    Tetra plus the measured residual, against the target segment), with ``land_frames`` the
    `objective.thread_frames` at that roll and ``land_off``/``land_over`` its own squareness and
    arrival, so what the trade cost is legible.

    It is not a convenience combination of the other two. ``off`` rides
    `aim.handoff_corridor`, which is a line from the origin through ONE point (the thread's near end
    minus the residual), while the target is a SEGMENT whose lateral falls 0.215 u per u of along --
    78x the corridor's own slope. So the corridor's lateral ask is right only where the arrival is
    exactly on target: measured against what the escape actually needs, it is off by **1.33 u at
    along 900, 4.11 u at 912.7 and 10.18 u at 949.5**, against a `objective.PLACEMENT_BAND` of 1.0.
    Every arrival the last cycle chooses between is past the target (the roll is a ~223 u atom that
    cannot stop short), so ``off`` was scoring exactly the arrivals it cannot score. ``land`` computes
    the landing point and measures it against the segment, so it is exact given the residual -- the
    same shift `aim.handoff_rows` made on the RANK side in session 70, here on the KEEP side.

    ``fan``/``rows`` (session 107) are ``thread``/``resid``'s CLOUD form, and they exist because the two
    inputs that axis takes are both wrong once the target set is a row cloud: ``resid`` is one member of
    a FAN (session 106 measured the residual spanning lateral +13.8..+52, and a point-shift of the target
    measurably steers the rank toward endpoints the fan converts BADLY), and ``thread`` is a fit through
    a ~170 u-wide cloud. Given a measured fan (`cloud_land.residual_fan`) and the rows, ``cloud_bound``
    is the cheapest whole candidate any surviving roll could reach -- herd + the atom's log + the row's
    `plan_cost` + the remaining miss at `objective.PUSH_CEILING`, minimised over fan x rows
    (`cloud_land.predict_bound`) -- with ``cloud_miss``/``cloud_row`` its landing and target.

    This is the position that MATTERS for a landing, which is the session-107 finding: an endpoint keep
    on the last cycle only reorders a set that this sweep and the junction cut already fixed, so ranking
    it honestly names the least-bad survivor without changing the floor. The per-aim cut is where the set
    is decided, and it cannot afford the ~28 s enumeration -- hence a predictor here and the enumeration
    (`cloud_land.cloud_landing`) at the survivors. Optimistic by construction, so it sizes the cut and
    never makes the claim.

    ``stations`` (session 115) is the OTHER half of that same cut, and until it existed this screen
    scored half a candidate: ``cloud_bound`` priced the landing alone, so the set of endpoints the last
    cycle may choose from was fixed with no reference to whether Link's own arrival could ever reach
    the stations his row's `plan_cost` was measured at. Enumerated over the whole session-111 cycle-3
    beam the two halves are ANTI-CORRELATED -- node 0 lands 25.4 u out with its arrival already free
    (``d_station`` 23.4, inside `cloud_land.FREE_REACH`), node 3 lands 4.7 u out with its stations
    136.8 u away and owing 6.05 frames -- so a landing-only screen keeps precisely the endpoints whose
    other half cannot be paid. Given a `cloud_land.herd_stations` map and a fan carrying the THROW
    (session 114's rigid Link displacement, `cloud_land.residual_fan`), the predictor prices both
    (`cloud_land.predict_bound`), and ``cloud_d_station``/``cloud_arr`` report the arrival it chose.

    ``pf`` (session 134) is the axis the ENDGAME is denominated in, brought forward to the cut that
    decides which endpoints exist. A `handoff.PairFrame` here reports ``l0_max`` -- the largest
    `handoff.tetra_lateral` any surviving roll DELIVERS, her offset from the clip roll's approach
    line, where the genuine side is positive. Session 126 measured the whole remaining gap in this
    one number: the last roll buys at most **+80.4 u** of crossing while keeping Link's runway band,
    so cycle 2 must hand over ``l0 >= -80.4`` against the -149..-264 the banked beam delivers. That
    bar belongs to the TERMINAL it was measured at, not to the problem -- a shorter roll carries her
    less far, and at the thrust-11 family it is **-76.87 .. -77.83** (s137). Read it through
    `handoff.crossing_bar(pf)`, which returns the bar for the frame in play or ``None``. It is
    ONE DOT PRODUCT on the delivered Tetra -- free beside the rollout that already happened -- where
    the endpoint keep it complements (`extend_cycle`'s ``handoff_keep``) costs ~1.5 s a survivor and,
    per session 107's standing warning, can only reorder the set this screen already fixed.
    ``l0_off``/``l0_along`` are the delivering roll's own squareness and arrival, so what the
    crossing costs on the other axes is legible rather than inferred.

    ``sep`` -- Link's separation from Tetra ALONG the herd line (``-lead``, so + = he is behind her) --
    rides along free because the sweep already computes the metrics, and it is reported rather than
    ranked on. Session 115 measured why it may not be a keep of its own: the specification wants
    92.5-157 u where the beam sits at 38-75, but appending frames to buy it at the endpoint kills the
    atom outright (0 of 672 variants fire at every deep prologue against controls firing 56-1964,
    attributed by `away_walk.fires_census` to ``l_ok`` on all 672), so depth is worth having only when
    the HERD produces it and only through the arrival it buys -- which is what ``stations`` prices.

    ``fan_center`` (session 71) is WHERE the sweep points, and it is the difference between a screen
    that answers and one that does not. The default fan is +-0x2800 (112.5 deg wide) about the HERD
    bearing thinned by ``step``, and 95-99% of every aim in it dies ``followed`` -- Link past
    `FOLLOW_ENGAGE_DIST`, which a ~223 u roll does the instant it stops plowing her. Measured over the
    whole armed set of a real cycle-2 exit (33 surviving rolls of ~83k aims), the survivors occupy
    **18.5 deg** of that 112.5 herd-relative and **13.4 deg** relative to the bearing to TETRA, so the
    sweep spends ~85% of its rollouts where nothing can live. ``fan_center='tetra'`` re-centres it on
    the per-endpoint bearing to her -- the causal frame, since surviving IS keeping contact.

    That buys RESOLUTION at the same cost, and resolution is the thing the screen was short of: at the
    default ``step=24`` it is 3x coarser than `roll_candidates`, the stage it screens FOR, and on the
    band the plan needs (jf 6, 416 endpoints) it finds **2** rollable where ``step=8`` finds **20**,
    while it calls the jf-7 band DEAD where ``step=8`` finds 2 -- including that band's best predicted
    landing. Narrowed to `pursuit_box`'s measured ``max_delta`` (+-21.35 deg, the recorded regime, not
    a fitted number) the fan holds ~31 aims at ``step=8`` against ~27 at ``step=24`` over the wide one.
    Containment holds by measurement (`[[search-space-contains-human]]`): the human's own two rolls sit
    at +0.76 and +0.63 deg from the bearing to Tetra, and the widest survivor anywhere in the sweep at
    7.65 deg. The narrowing is also SELF-CHECKING rather than trusted
    (`[[oneshot-no-manual-tweaking]]`): ``fan_edge``/``fan_half`` report the furthest SURVIVING aim
    from the centre against the window it was given, so a caller or a gate can see whether the window
    is binding instead of assuming it is not.

    ``collect`` (session 71) is the sink for the JOINT distribution, because the three axes above are
    aggregated INDEPENDENTLY over the fan and a keep cannot read a pair off them: the roll that
    delivers ``off`` and the roll that delivers ``arrive`` are in general different aims, so
    "square AND arriving" is not expressible in the return value. Every surviving roll appends
    ``dict(along, lat, off, over, rate, link_lat, aim, want, jf)`` -- what a combined key has to be
    calibrated on (`junction_beam`'s ``collect`` has the same shape and the same reason).

    ``terminal`` (session 145) is the axis ``pf`` reports moved to the KEEP side, and it is here
    because reporting it was measurably not enough. ``l0_max`` and `handoff.probe`'s ``resid`` ranked
    five sessions of breeding, and session 144 measured the population that produced: of 49 rungs,
    4 satisfy the terminal's ``tetra_from_corner``, 0 its ``along``, 0 the seam's facing window, and
    none more than one at a time. A rank on a residual that cannot reach zero at that facing is a
    rank on one criterion, so it breeds one criterion. Given a `terminal_keep.TerminalKeep` the sweep
    REFUSES an aim failing any axis (``t_facing`` / ``t_l0`` / ``t_along`` / ``t_runway`` / ``t_tfc``
    in ``dead``) and ranks only what survives all of them, on the exact residual at the roll's own
    facing, lean and momentum (``t_resid``, ``t_n``, ``t_genuine``).

    ``t_l0`` (session 146) is the axis the box structurally could not test: ``along``, ``runway`` and
    ``tetra_from_corner`` are every one of them a projection on the roll direction, so all three are
    invariant to a lateral slide of both actors, and the family behind them is a ``side = 0`` slice.
    Her own offset from the approach line is where the banked population actually fails -- ~130 u
    against the 31.58 u session 145 read off ``tetra_from_corner`` -- and no choice of aim buys it,
    because it is a property of the delivered TETRA (see `terminal_keep.TerminalKeep.screen`).

    ``dead`` accumulates WHY each aim died. A stalled cycle is the recurring failure mode here, and
    "no aim rolled" is not a diagnosis -- talk-unsafe, never-rolled, weak (+5 not +26), off-line and
    wall are four different problems with four different fixes. With a ``terminal`` it also carries
    the CROSS-TAB ``<why>@seam``: how many aims that died a HERD death had already put their achieved
    facing inside the seam window. Session 144 predicted ``followed`` would be that counter (a roll
    aimed at the corner stops plowing her the moment it passes her) and predicting is not measuring;
    every death after ``no_roll`` has fired its roll, so the achieved facing is known exactly and the
    cross-tab needs no proxy for it.

    ``terminal_sink`` is the DIAGNOSIS beside the count, and it exists because "0 kept" is not a
    result any more than session 144's bare zeros were: it takes `terminal_keep.TerminalKeep.screen`
    for EVERY aim whose roll fired -- kept or dead, and carrying the herd ``dead_why`` -- so a sweep
    that keeps nothing still says by how much each axis missed and which one to steer. The roll entry
    is known the moment the roll appears, so a herd death downstream of it does not cost the
    measurement; only the exact residual (which needs a compiled ctx) is reserved for what the screen
    passes."""
    walls = O.courtyard_walls()
    dead = {} if dead is None else dead
    cor = O.push_corridor(hl) if corridor is None else corridor
    # the rows in herd coords ONCE, not per aim (the raw genuine-coord set carries only x/z)
    hrows = _CL().herd_rows(rows, hl) if (fan and rows) else None
    # ...and the stations likewise, so the arrival half costs the screen one min() per (member, row)
    hstat = _CL().herd_stations(stations, hl) if (fan and rows and stations) else None
    best = None
    if fan_center is None:
        center = hl.bearing_bam()
    elif fan_center == 'tetra':
        center = _bearing((endpoint['run'].link.pos_x, endpoint['run'].link.pos_z),
                          (endpoint['run'].tx, endpoint['run'].tz))
    else:
        center = int(fan_center)
    for (_want, aim) in T.roll_facing_fan(endpoint['run'], center, half_window, step):
        rr = endpoint['run'].clone()
        seg = T.roll_segment(rr, aim, target_cs=None, l_window=l_window)
        why = ('talk' if seg['talk_unsafe'] else
               'no_roll' if not seg['ok'] or seg['roll_speedF'] is None else
               'weak' if seg['roll_speedF'] < min_roll else
               'followed' if rr._follow_warned else
               'wall' if not O.frame_is_wall_free(rr.link.pos_x, rr.link.pos_z, rr.tx, rr.tz,
                                                 walls) else None)
        if why is None:
            m = T.metrics(rr, hl, endpoint['frames'] + seg['frames'])
            if not T.alive(m, axis=axis):
                why = 'offline'
        if why is not None:
            dead[why] = dead.get(why, 0) + 1
            if terminal is not None and seg.get('entry') is not None:
                # the cross-tab: a HERD death whose roll nevertheless aimed into the seam window
                if _TK().in_seam_window(seg['entry']['facing']):
                    dead[why + '@seam'] = dead.get(why + '@seam', 0) + 1
                if terminal_sink is not None:
                    terminal_sink.append(dict(terminal.screen(seg['entry']), dead_why=why,
                                              aim=aim, want=_want, jf=endpoint['jf']))
            continue
        # computed HERE, refused after ``collect``: a keep that drops an aim silently says how many
        # survived and not by how much the rest missed (`terminal_sink`, and the docstring's why)
        tk = None if terminal is None else terminal.score(seg['entry'])
        if tk is not None and terminal_sink is not None:
            terminal_sink.append(dict(tk, dead_why=None, aim=aim, want=_want, jf=endpoint['jf']))
        al = hl.along(rr.tx, rr.tz)
        lat = hl.lateral(rr.tx, rr.tz)
        off = cor['offset'](al, lat)
        over = None if target_along is None else al - float(target_along)
        land = lframes = None
        if thread is not None and resid is not None:
            from harness.tetrapush import aim as A      # deferred: `aim` reads `objective` back
            la, ll = al + resid[0], lat + resid[1]
            land = A.thread_miss(la, ll, thread)['miss']
            lframes = O.thread_frames(la, ll, thread)
        sep = -m['lead']                     # + = Link is BEHIND her, the pursuit side
        # the endgame's own axis, one dot product on the Tetra this roll delivered (s134)
        l0 = None if pf is None else _HO().tetra_lateral(pf, (rr.tx, rr.tz))
        cloud = None
        if fan and rows:
            # the CLOUD form of the same axis: cheapest whole candidate over fan x rows, microseconds
            # an aim -- the only landing measure this per-aim cut can afford. With ``stations`` it
            # prices the ARRIVAL beside it, off each member's own throw (s115).
            cloud = _CL().predict_bound(al, lat, endpoint['frames'] + seg['frames'], fan, hrows,
                                        link=((hl.along(rr.link.pos_x, rr.link.pos_z),
                                               hl.lateral(rr.link.pos_x, rr.link.pos_z))
                                              if hstat else None),
                                        stations=hstat)
        if collect is not None:
            row = dict(along=al, lat=lat, off=off, over=over, rate=m['per_frame'],
                       link_lat=m['lat'], sep=sep, aim=aim, want=_want, jf=endpoint['jf'],
                       land=land, land_frames=lframes, l0=l0, frames=m['frames'],
                       cloud_bound=(cloud['bound'] if cloud else None),
                       cloud_miss=(cloud['miss'] if cloud else None),
                       cloud_d_station=(cloud['d_station'] if cloud else None),
                       cloud_arr=(cloud['arr_frames'] if cloud else None))
            if tk is not None:                 # ABSENT, not None, when unasked: the row shape a
                row['terminal'] = dict(tk)     # caller banked before this axis existed is preserved
            collect.append(row)
        if tk is not None and not tk['ok']:
            dead[tk['why']] = dead.get(tk['why'], 0) + 1
            continue
        edge = abs(_s16(_want - center))
        if best is None:
            best = dict(rate=m['per_frame'], off=off, off_rate=m['per_frame'], along=al, n=1,
                        arrive=None if over is None else abs(over), over=over,
                        land=land, land_frames=lframes, land_off=off, land_over=over,
                        sep_max=sep, cloud_sep=sep,
                        l0_max=l0, l0_off=off, l0_along=al,
                        cloud_bound=(cloud['bound'] if cloud else None),
                        cloud_miss=(cloud['miss'] if cloud else None),
                        cloud_row=(cloud['row_idx'] if cloud else None),
                        cloud_d_station=(cloud['d_station'] if cloud else None),
                        cloud_arr=(cloud['arr_frames'] if cloud else None),
                        fan_edge=edge, fan_half=int(half_window))
            if tk is not None:                 # same discipline as the ``collect`` row above
                best.update(t_resid=tk['resid'], t_genuine=1 if tk['genuine'] else 0,
                            terminal=dict(tk))
            continue
        best['n'] += 1
        best['fan_edge'] = max(best['fan_edge'], edge)
        best['rate'] = max(best['rate'], m['per_frame'])
        best['sep_max'] = max(best['sep_max'], sep)
        if off < best['off']:
            best['off'], best['off_rate'], best['along'] = off, m['per_frame'], al
        if over is not None and abs(over) < best['arrive']:
            best['arrive'], best['over'] = abs(over), over
        if land is not None and land < best['land']:
            best['land'], best['land_frames'] = land, lframes
            best['land_off'], best['land_over'] = off, over
        if l0 is not None and l0 > best['l0_max']:
            best['l0_max'], best['l0_off'], best['l0_along'] = l0, off, al
        if cloud is not None and (best['cloud_bound'] is None
                                  or cloud['bound'] < best['cloud_bound']):
            best['cloud_bound'], best['cloud_miss'] = cloud['bound'], cloud['miss']
            best['cloud_row'] = cloud['row_idx']
            best['cloud_d_station'], best['cloud_arr'] = cloud['d_station'], cloud['arr_frames']
            best['cloud_sep'] = sep
        if tk is not None:
            best['t_genuine'] += 1 if tk['genuine'] else 0
            if abs(tk['resid']) < abs(best['t_resid']):
                best['t_resid'], best['terminal'] = tk['resid'], dict(tk)
    return best


def _CL():
    """`cloud_land`, imported on use. Deferred because it reads `away_walk` which reads this module
    back, and because a beam that asks for no landing measure should not pay for the module at all."""
    from harness.tetrapush import cloud_land as CL
    return CL


def _TK():
    """`terminal_keep`, imported on use -- same reason as `_HO`, and it reads `handoff` in turn."""
    from harness.tetrapush import terminal_keep as TK
    return TK


def _HO():
    """`handoff`, imported on use -- it compiles a coupled roll (`terminal.RollFrame`) on
    construction, which a beam that asks no terminal question should not pay for."""
    from harness.tetrapush import handoff as HO
    return HO


def _dedup_endpoints(ends):
    """Collapse endpoints that share BOTH the physics state and the pending delay-1 input. (The
    pending input must stay in the key: two endpoints identical in physics can differ in whether
    the roll-A fires the full 26 or the weak +5 -- the s42 arming lesson.)"""
    seen, out = set(), []
    for e in ends:
        r = e['run']
        last = e['log'][-1] if e['log'] else {}
        tag = (round(r.link.pos_x, 1), round(r.link.pos_z, 1), r.link.facing >> 5,
               round(r.link.speedF, 2), round(r.tx, 1), round(r.tz, 1),
               last.get('stickX'), last.get('stickY'), bool(last.get('triggerL')))
        if tag in seen:
            continue
        seen.add(tag)
        out.append(e)
    return out


#: BAM -> degrees, so a cone deficit and an aim error can be added as one scalar (`_armable_square`).
_BAM_DEG = 360.0 / 65536.0


def _cone_deficit(run):
    """How far Link's facing still is from leaving the +-90 deg talk/target cone, in BAM (0 = out).
    That cone is the gate on BOTH the talk-safe roll-A and the proc-7 arming flip
    (`two_roll.junction_gates`)."""
    tb = _bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz))
    return max(0, 0x4000 - abs(_s16(run.link.facing - tb)))


def _physics_tag(run):
    """A frontier candidate's PHYSICS identity -- `_state_tag`'s neighbourhood WITHOUT the pending
    input. The distinction is the whole of the session-68 frontier fix: children of one node differ
    ONLY in their pending input (the pipeline acts a frame late), so a frontier deduped by
    (physics, pending) can hold `beam` copies of one physics state."""
    return (round(run.link.pos_x, 1), round(run.link.pos_z, 1), run.link.facing >> 5,
            round(run.link.speedF, 2), run.link.state)


def _frontier_score(hl, pf=None):
    """The junction frontier's ranking: get Link's facing OUT of the +-90 deg talk/target cone
    first (that is the gate that blocks arming), then hug the herd line.

    ``pf`` (a `handoff.PairFrame`, session 135) replaces the second order with the axis the endgame
    is denominated in -- her ``l0``, one dot product. It goes with `AXIS_PAIR`: with the direction
    freed, "hug the herd line" has no customer left to serve, and the last two cycles are not
    herding. The cone order is untouched, because arming is what a junction is for.

    Ranking on |lat| ALONE is myopic in exactly the wrong direction -- the flattest states are the
    ones still facing Tetra, which can never arm, so they crowd out the productive branch. Measured:
    a beam of 16 then found ZERO endpoints where a beam of 12 found 162 (a wider beam finding
    strictly less is the tell).

    Kept as ONE SHARE of the frontier rather than the whole of it (session 68): on its own it is a
    greedy walk that maximises TURN RATE, and the turn is what swings Link's ~17 u exec-centre lead
    laterally -- so it degrades the push aim monotonically (kept aim -12 -> -20 -> -26 -> -34 -> -41
    over five generations off a real cycle-1 exit). See `junction_beam`."""
    if pf is not None:
        HO = _HO()

        def score_l0(n):
            r = n['run']
            return (_cone_deficit(r), -HO.tetra_lateral(pf, (r.tx, r.tz)))
        return score_l0

    def score(n):
        r = n['run']
        lat = abs(hl.lateral(r.link.pos_x, r.link.pos_z) - hl.lateral(r.tx, r.tz))
        return (_cone_deficit(r), lat)
    return score


def _armable_square(hl, corridor):
    """**The frontier's second and third orders (session 68): how close this state is to being an
    ARMED SQUARE one**, in degrees.

    The endpoint a cycle wants is out of the cone (so it can arm) AND square (so the roll it fires
    carries Tetra down the push corridor rather than across it -- `aim.corridor_aim_error`). Those
    two pull against each other frame by frame, and a lexicographic key starves whichever comes
    second: cone-first walks the aim out to -41 deg, |aim|-first never leaves the cone and finds
    **zero** armed endpoints. So one order is the aim alone and one is the SUM of the aim error and
    the cone deficit in degrees -- a single scalar that wants both at once, no weight to tune.

    Returns ``(aim_only, aim_plus_cone)`` as two key functions."""
    from harness.tetrapush import aim as A          # deferred: `aim` reads `objective` back

    def aim(n):
        v = A.corridor_aim_error(n['run'], hl, corridor)
        return 1e9 if v is None else abs(v)

    return aim, (lambda n: aim(n) + _cone_deficit(n['run']) * _BAM_DEG)


def _expand(run, letters):
    """**One junction node's children**: the shared frame once, then a run per pending letter.

    A generation expands each live node by its whole alphabet -- 274 children off one node at the
    shipped knobs -- and the obvious loop steps that same frame 274 times. It does not have to: at
    `input_delay=1` the delivered letter is buffered and cannot touch its own frame, so the children
    are one frame carrying 274 different pending inputs (`FreeRun.fork_pending`, which holds the
    proof and the gate). Measured on a real beam: all 274 land in one physics class and one csangle
    class, at every generation, and the stage is 53% `FreeRun.step`.

    A wired run keeps clone-and-step -- the delay buffer is `LandState`'s there, and the search this
    serves is native."""
    if run.native_step:
        return run.fork_pending(letters)
    out = []
    for d in letters:
        r = run.clone()
        r.step(d)
        out.append(r)
    return out


def _shared_frame(run, letter):
    """The frame a node's whole alphabet shares, stepped once -- what the SHARED prunes read.

    `junction_beam` kills most children on `followed` / `wall` / `outbox`, and all three read only
    Link's and Tetra's positions and the follow flag: fields of the shared frame, identical across
    the alphabet. So the verdict is the NODE's, and a node that fails it can be dropped whole
    without materialising a single child (~23k of 65k children a stage). Any letter serves, since
    the delivered one cannot touch its own frame -- see `_expand`."""
    if run.native_step:
        return run.fork_pending([letter])[0]
    r = run.clone()
    r.step(letter)
    return r


def junction_beam(node, hl, box, *, max_frames=12, beam=24, ess_step=1, aim_step=16,
                  keep=12, collect=None, dead=None, per_state=4, aim_share=True, corridor=None,
                  axis=AXIS_HERD, pf=None):
    """**The junction as a per-frame BEAM, not an enumerated family.** The atom is one frame's
    (stick, L): each generation extends every live node by the whole alphabet
    (`junction_alphabet`), prunes anything that leaves the pursuit box, dedups by state, and keeps
    ``beam``. Any node that also passes `two_roll.junction_gates` is collected as a usable endpoint.

    **THE FRONTIER WAS A GREEDY SINGLE-STATE WALK, AND THAT IS WHY EVERY ENDPOINT CAME OUT UNSQUARE
    (session 68).** A node's children all share IDENTICAL physics -- the input pipeline acts a frame
    late, so the stick delivered here does not move Link until the next generation -- and the frontier
    ranked them with a key computed on that shared physics, which TIES. A stable sort then filled all
    ``beam`` slots with pending-input variants of ONE state, so the beam walked a single trajectory and
    its "diversity" (636 / 2288 endpoints off a cycle-1 exit) was pending variants of one path. Worse,
    the single path it walked was `_frontier_score`'s fastest TURN out of the cone, and the turn is what
    rotates Link's ~17 u exec-centre lead: the kept aim degraded -12 -> -20 -> -26 -> -34 -> -41 over
    five generations, and every armed endpoint landed at -33..-36 deg off the push corridor. Two fixes,
    both keeps and neither a rank:

      * ``per_state`` caps the slots one PHYSICS state (`_physics_tag`) may take, so the frontier holds
        ``beam / per_state`` genuinely different states. The pending input still belongs in the dedup
        `ident` (the s42 arming lesson: two states identical in physics differ in whether the roll-A
        fires 26 or the weak 5), it just may no longer monopolise the beam.
      * ``aim_share`` adds the two `_armable_square` orders to the keep, so the branch that stays SQUARE
        while it turns survives the cut.

    Measured off the dumped s66 cycle-1 beam, squarest armed endpoint per exit, stock -> fixed:
    node 1 **-15.34 -> +0.03**, node 2 **-15.56 -> -1.90**, the human's own exit -2.98 -> +2.42 -- and
    it is FASTER (46 s -> 22 s at the same budget, the beam no longer re-expanding one state). Nodes 0
    and 3 stay at -33 / +29: squareness is a property of the cycle EXIT, and those two do not have it,
    which is exactly why it belongs in the cycle keep as well (`extend_cycle`).

    WHY, measured (from the human's own cycle-1 exit, 8 frames): the beam returns **432** distinct
    gate-passing in-box endpoints where `two_roll.junction_variants` returns **7**, at the SAME best
    flatness (min |lat| 7.26 either way). So the win is DIVERSITY, not a better single endpoint --
    which is what this stage needs, because roll survival off an endpoint is razor-thin (only a
    couple of the flattest endpoints yield any alive roll at all, and two endpoints identical in
    physics can differ purely in their pending delay-1 input).

    (An earlier reading here -- "the single-stick family cannot express the reposition at all" --
    was an artifact of the `LandState.clone` attention-sharing bug, and is retracted; his junction
    does use three distinct sticks, but the family sweeps enough sticks to reach the same box.)"""
    live = [dict(run=node['run'], log=node['log'], jf=0)]
    ends = []
    walls = O.courtyard_walls()
    dead = {} if dead is None else dead
    cor = O.push_corridor(hl) if corridor is None else corridor
    aim_only, aim_cone = _armable_square(hl, cor)
    for _f in range(int(max_frames)):
        nxt, seen = [], set()
        for nd in live:
            # the alphabet is state-dependent (the arming stick aims at Tetra from HERE)
            letters = [dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                            triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL, substickY=0)
                       for (sx, sy) in junction_alphabet(nd['run'], hl, ess_step=ess_step,
                                                         aim_step=aim_step)
                       for l in (0, 1)]
            if not letters:
                continue
            # the prunes below are the SHARED frame's, so they are decided once for the node and a
            # dead one costs no children at all (`_shared_frame`)
            probe = _shared_frame(nd['run'], letters[0])
            # counted separately on purpose: "the beam emptied" is only diagnosable if the
            # regime, the walls and the posture box are distinguishable afterwards.
            why = ('followed' if probe._follow_warned else
                   'wall' if not O.frame_is_wall_free(probe.link.pos_x, probe.link.pos_z,
                                                      probe.tx, probe.tz, walls) else
                   'outbox' if not in_pursuit_box(probe, hl, box, axis) else None)
            if why is not None:
                dead[why] = dead.get(why, 0) + len(letters)
                continue
            for d, r in zip(letters, _expand(nd['run'], letters)):
                sx, sy, l = d['stickX'], d['stickY'], 1 if d['triggerL'] else 0
                jf = nd['jf'] + 1
                tag = (round(r.link.pos_x, 1), round(r.link.pos_z, 1), r.link.facing >> 5,
                       round(r.link.speedF, 2), r.link.state, sx, sy, l)
                if tag in seen:
                    continue
                seen.add(tag)
                cand = dict(run=r, log=nd['log'] + [d], jf=jf)
                nxt.append(cand)
                why = T.junction_gates(r, hl, node['frames'] + jf, axis=axis)
                dead[why or 'ENDPOINT'] = dead.get(why or 'ENDPOINT', 0) + 1
                if why is None:
                    e = dict(cand)
                    e['m'] = T.metrics(r, hl, node['frames'] + jf)
                    e['frames'] = node['frames'] + jf
                    e['jv'] = dict(kind='beam', phases=T._fit_phases(e['log'][-jf:]))
                    ends.append(e)
                    if collect is not None:
                        collect.append(e)
        # the frontier keep: shares by turn-out-of-the-cone AND by squareness, capped per physics
        # state so no single state can take the whole beam (see the docstring -- session 68)
        if not nxt:
            break
        orders = [sorted(nxt, key=_frontier_score(hl, pf))]
        if aim_share:
            orders.append(sorted(nxt, key=aim_only))
            orders.append(sorted(nxt, key=aim_cone))
        live = _mixed_beam(orders, beam,
                           ident=lambda n: (_physics_tag(n['run']),
                                            n['log'][-1]['stickX'], n['log'][-1]['stickY'],
                                            bool(n['log'][-1]['triggerL'])),
                           group=lambda n: _physics_tag(n['run']), per_group=per_state)
    # MIXED keep (the s42 lesson): half by flatness, half by shortness -- neither ranking alone
    # keeps the survivors. `extend_cycle` re-keeps by ROLLABILITY, which is stronger than both.
    ends.sort(key=lambda e: (abs(e['m']['lat']), e['jf']))
    flat = ends[:int(keep) - int(keep) // 2]
    rest = [e for e in ends if e not in flat]
    rest.sort(key=lambda e: (e['jf'], abs(e['m']['lat'])))
    return flat + rest[:int(keep) // 2]


def junction_quality(run, hl, box, *, frames=6, sticks=None, axis=AXIS_HERD):
    """**The cheap CONTINUABILITY predictor** for a post-roll endpoint -- the thing that ranks a
    `target_cs`, which exists only to set up the next junction.

    It is EXACT PHYSICS, not a proxy: a `FreeRun` step is ~0.3 ms, so simply gliding the endpoint
    forward a few frames on each of a couple of representative ESS sticks costs ~5 ms, and it
    answers the only question that matters -- does this camera target leave a glide that STAYS in
    the pursuit box (`pursuit_box`) long enough for a junction to work? Scored ``(-frames_in_box,
    |lat|)``, lower is better; None if no representative glide survives even two frames.

    (A straight-line analytic projection was tried first and is wrong: through the junction Link is
    still in CONTACT with Tetra -- dist ~59 < 80 -- so he keeps push-gliding her and the relative
    lead barely moves, which a free-flight projection misses by ~25 u/frame. The lateral term it got
    right; the along term it did not. Running the real steps is both cheaper to trust and fast.)

    The full `junction_beam` is the expensive exact stage that runs only on the kept targets."""
    sticks = sticks or (ESS_DOWN, (111, 111), (145, 146))
    walls = O.courtyard_walls()
    best = None
    for st in sticks:
        r = run.clone()
        inbox = 0
        for _ in range(int(frames)):
            r.step(dict(stickX=st[0], stickY=st[1], buttons=0, triggerL=0,
                        substickX=T.CSTICK_NEUTRAL, substickY=0))
            if not frame_in_model(r, walls) or not in_pursuit_box(r, hl, box, axis):
                break
            inbox += 1
        if inbox < 2:
            continue
        lat = abs(hl.lateral(r.link.pos_x, r.link.pos_z) - hl.lateral(r.tx, r.tz))
        score = (-inbox, lat)
        if best is None or score < best:
            best = score
    return best


def junction_square_probe(node, hl, box, corridor, *, max_frames=8, beam=16, ess_step=2,
                          aim_step=32, cap=60, step=24, per_state=4):
    """**How SQUARE a roll this exit's junction can still deliver** -- the exit-level counterpart of
    `roll_probe`, and the keep the cycle-1 stage was missing (session 69).

    Session 68 ended at "squareness is a property of the cycle EXIT, and that is one stage further
    up". Measured, it is, and by two orders of magnitude on exits the frame bound cannot tell apart:
    every cycle-1 exit scores `plan_bound` **71.90-71.97**, the five the old ``tcs_keep=3`` stage kept
    deliver corridor offsets of **141.83 / 27.81 / 14.67 / none / none**, the best on the whole camera
    grid delivers **11.20**, and the HUMAN's own exit -- the same roll one camera target away, Tetra
    bit-identical and his facing within 4 BAM -- delivers **1.34**. Nothing upstream of a probe sees
    that: the exits are bound-tied, so the cut that picks among them is `roll_candidates`'
    ``tcs_keep``, ranked by `junction_quality` (frames in the box), which is blind to the aim.

    So run the junction for real, at a coarse budget, and report the smallest corridor offset any
    surviving roll through it DELIVERS -- `roll_probe`'s ``off``, never an endpoint's own entry aim
    (session 68: at jf 10-12 the aim swings 5-8 deg per frame and a +1.12 deg endpoint fired a roll
    landing 37.6 u off). ~15-25 s per exit against cycle 1's 21 unique ones -- **308 s**, which is a
    keep the stage can afford once per solve but not one every caller should pay (`cycle1_nodes`).

    **THE POOL IS THE MEASUREMENT THAT MAKES IT HONEST** (`_probe_pool`, ``spread=False``). Which
    endpoints get probed decides the answer, and both single pools lie in opposite directions -- on
    three real exits, prefix-only reads ``1.34 / none / 27.02`` and squarest-only reads
    ``none / 141.83 / 14.67``. The mix of both, **uncapped by physics state**, is >= each of them
    everywhere and finds strictly more rollable endpoints than either (12 against 9 on one exit). The
    per-state cap `_probe_pool` applies by default is the one thing that must NOT be reused here: it
    reproduces the s68 stall (one pending each of mostly-uncontinuable states -- ``none`` where the
    uncapped mix reads 1.34).

    Returns ``dict(off, rate, jf, aim, n_ends, n_pool, n_roll)``, or None when no roll survives (an
    exit that cannot roll at all is not an exit -- it ranks last, it does not rank infinitely square).
    ``max_frames``/``beam``/``cap``/``step`` are budget knobs, deliberately coarser than the real
    stage's: this ranks exits against each other, and `extend_cycle` re-searches the winner in full."""
    got = []
    junction_beam(node, hl, box, max_frames=max_frames, beam=beam, ess_step=ess_step,
                  aim_step=aim_step, keep=1, collect=got, per_state=per_state, aim_share=True,
                  corridor=corridor)
    uniq = _dedup_endpoints(got)
    sq_key, _ = _armable_square(hl, corridor)
    pool = _probe_pool(uniq, int(cap), sq_key, spread=False)
    best, n_roll = None, 0
    for e in pool:
        p = roll_probe(e, hl, step=step, corridor=corridor)
        if p is None:
            continue
        n_roll += 1
        if best is None or p['off'] < best[0]['off']:
            best = (p, e)
    if best is None:
        return None
    p, e = best
    from harness.tetrapush import aim as A          # deferred: `aim` reads `objective` back
    return dict(off=p['off'], rate=p['off_rate'], jf=e['jf'], n=p['n'],
                aim=A.corridor_aim_error(e['run'], hl, corridor),
                n_ends=len(uniq), n_pool=len(pool), n_roll=n_roll)


#: **The CALIBRATED cheap `junction_square_probe` budget** (session 70): 1/8 the full probe's cost
#: (~2.7 s against ~21 s) and, measured, a detector with no false positives -- see `square_probe_key`.
CHEAP_PROBE = dict(max_frames=5, beam=8, ess_step=3, aim_step=48, cap=12, step=48, per_state=2)


def square_probe_key(hl, box, corridor, budget=None):
    """**The cheap `junction_square_probe` as a mid-chain tcs KEEP** (session 70) -- the calibrated
    answer to "what should `roll_candidates`' ``tcs_keep`` rank on at cycles >= 2", and it is a probe
    rather than a proxy because every proxy was measured WORSE than the stock key.

    Session 69 left the tcs cut ranked by `junction_quality` (frames in the pursuit box) at every
    cycle, which is blind to the aim: on cycle 1's 25-exit grid it keeps 141.83 / 27.81 / 14.67 u of
    deliverable corridor offset where the grid holds 11.20. The handoff's proposal was to make that
    glide report the AIM it reaches instead. Measured on the same grid -- 25 exits, every one fully
    probed, so the calibration is exact -- an aim key is not merely no better, it is WORSE:

        key                                keep 3 delivers      the best exit's rank
        (-inbox, |lat|)   [stock]                  14.67 u                        5
        (-inbox, glide |aim|)                     116.93 u                        7
        (-inbox, glide |aim| + cone)              116.93 u                        4
        (-inbox, exit |aim|)                         NONE                        19
        exit |aim| alone                             NONE                        19
        the CHEAP probe (~2.7 s)                   11.20 u                        1
        the FULL probe (~21 s)                     11.20 u                        1

    The reason is structural and it is the s68 lesson again: the exits with the SMALLEST aim error are
    the ones whose junction arms NOTHING (|aim| 1.26-2.05 deg, zero rollable endpoints), so an aim key
    ranks the dead ones first. Squareness that a roll can actually deliver is not visible in any
    cheap scalar; it has to be rolled for.

    What IS affordable is the same probe at a coarser budget (`CHEAP_PROBE`). Coarseness costs RECALL,
    not precision: on the grid it scores only 2 of the 6 armable exits, but both are real and they are
    the full probe's **#1 and #3** -- and it returns None (never a wrong number) on the rest, including
    every exit the full probe also calls unrollable. So it belongs in a MIXED keep with the stock
    quality order (`_mixed_beam`), never as the whole rank: where it answers, take it; where it does
    not, the stage is exactly what it was.

    Returns a callable ``node -> off or None`` for `roll_candidates`' ``tcs_probe``."""
    kw = dict(CHEAP_PROBE if budget is None else budget)

    def key(node):
        p = junction_square_probe(node, hl, box, corridor, **kw)
        return None if p is None else p['off']

    return key


def landing_key(hl, thread, resid=None, escape_frames=4):
    """**The LAST cycle's tcs key: where the ESCAPE would land her from this exit** (session 70).

    `junction_quality` asks whether the NEXT junction can continue from a roll's exit -- and the last
    cycle has no next junction, so on the final cycle the stock tcs cut ranks the camera targets by a
    quantity that has no bearing on anything (`extend_cycle` already turns the gate off with
    ``require_quality=False``; the ORDER was left ranked by it anyway). The last cycle's exit IS the
    handoff state: what it is worth is what the escape lands from it.

    So rank it by `objective.thread_frames` of `aim.landing_miss`'s landing point -- the exit's position
    plus the escape's MEASURED residual, priced in the frames that landing still costs. Exact given the
    residual, free to compute (no rollout), and the same prediction `escape_probe` then confirms with
    the real atom on the survivors: the cheap-predictor / exact-confirm shape the rest of this search
    uses. Without a residual it degrades to the exit's own position, which is `rank_key`'s ``'thread'``.

    Returns a callable ``node -> frames`` for `roll_candidates`' ``tcs_key``."""
    from harness.tetrapush import aim as A          # deferred: `aim` reads `objective` back

    def key(node):
        run = node['run']
        a, l = hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz)
        if resid is not None:
            lm = A.landing_miss(run, hl, thread, resid)
            a, l = lm['along'], lm['lat']
        return node['frames'] + int(escape_frames) + O.thread_frames(a, l, thread)

    return key


def camera_probe_key():
    """**The LAST cycle's camera cut had no term for the escape's own CAMERA requirement, and that
    requirement is what every atom number in this work was quietly assuming** (session 73).

    The atom's turnaround needs the csangle inside its snap window, and its own C-stick is neutral, so
    it cannot slew there (`away_walk.snap_bill`: 15-38 deg at ~470 BAM/frame is 6-15 frames against
    `objective.TIMELOSS_BUDGET` 2). The one channel that can pay is the LAST ROLL's ``target_cs``, idle
    for the roll's whole duration -- and until this key existed nothing in the search asked it to. The
    atom instead COMMANDED the window (`away_walk.escape_atom`'s old default), 91-114 deg off the live
    csangle, so from session 65 to 72 the frontier was conditional on a camera leg no roll could deliver.

    So this reports what the arrival still OWES: 0 when its own live csangle already snaps (nothing to
    pay -- the roll delivered it), else the BAM to the nearest window member, None when the terminal has
    no window at all. Measured over 112 real arrivals against the widened grid (`ESCAPE_TCS_SPAN`), 63
    reach a bill of 0 inside their own roll's slew, and the frontier at those is REPLAY-FAITHFUL and
    strictly better than the commanded one it replaces: **75 frames, pd 0.432 u, `objective.verdict`
    True**, against s72's commanded-csangle 1.644 u at the same 75.

    Wired as a `roll_candidates` ``tcs_probe`` -- a KEEP share, never an order or a filter -- and that is
    calibrated, not stylistic. Swept over 16 arrivals x 41 camera targets (656 cells), **274 fire** at
    the live csangle and only **12 snap**; all 12 of those fire (snap ⇒ fires, no exceptions) but **262
    firing cells do not snap**, because a camera steer also moves the arrival's own EBS facing, so a
    non-snapping target can put Tetra out of the front cone by itself -- measured, the 75-frame winner
    fires with ``turnaround_first=False``. As a filter the bill would therefore throw away 96% of the
    firing states. As a KEEP OF 3 it is the best cheap term measured: it retains a BEST-bound firing cell
    for **13 of the 14** arrivals that have one, at median **0.00** and max 2.44 frames of bound loss,
    where a keep of 3 by the front-cone margin retains one for 7 (widest-first) or 3 (narrowest-first)
    and loses 7 / 11 arrivals outright. The cone cannot screen this at all: the frontier cell's own
    margin is **5.2 deg**, below the DEAD cells' median of 11.1. Costs one frame per candidate.

    **KEEP THIS SHARE, and not for the reason it was added** (session 117, and the reason `lok_probe_key`
    below does not replace it). Session 77 proved the snap itself undeliverable and session 116 showed
    this key had been RANKING the cut on it blindly -- both true, and both about whether an atom FIRES.
    Asked the other question, on the whole swept camera axis (551 priced states over 23 rolls,
    `_notes/s117_camera_axis.py`), the same bill is the best VALUE order measured: it retains the roll's
    swept-optimum bound at **14 of 23** rolls at mean **+0.14** frames of loss, where `landing_key` --
    the last cycle's own order -- retains **9** at **+0.53**. A key can be the wrong screen and the right
    rank; the s116 retirement is evidence about the first only.

    Returns a callable ``node -> bam or None`` for `roll_candidates`' ``tcs_probe``."""
    from harness.tetrapush import away_walk as AW    # deferred: `away_walk` imports this module

    def probe(node):
        b = AW.snap_bill(node['run'])
        return None if b['bam'] is None else abs(int(b['bam']))

    return probe


def lok_probe_key(hl):
    """**The LAST cycle's camera keep, on the clause that actually refuses -- ``l_ok``** (session 116,
    and the correction of `camera_probe_key`'s quantity, not of its shape).

    Session 73 established that the escape's camera requirement belongs in this cut and wired
    `camera_probe_key` to carry it, ranked on the SNAP bill. Session 77 then measured that the snap is
    not deliverable -- over a roll's whole reachable camera set ``want - travel`` has an 87 deg hole
    exactly where the snapping band sits -- and the conclusion drawn was that the camera cannot pay.
    Half of that is right: the snap cannot be bought (0-6 reachable states of ~110 over the whole
    session-111 beam). But the snap is not what the frame owes. What ``l_ok`` needs is only that the L
    does not act with Tetra in the cone (`away_walk.escape_atom`'s s75 note), and THAT the camera
    supplies at **1-68 of the same ~110 states, in all 16 families of the beam, on the search's own
    `ESCAPE_TCS_STEP` 512 grid**. So the supply was there the whole time and nothing asked for it: the
    rank picked a ``target_cs`` blind to it, and at 19 of the 35 nodes that fire nothing it picked one
    that refuses -- while a SIBLING node of the same family, same endpoint, same aim, differing only in
    this camera, fires. Enumerated at the 7 families those 19 sit in, re-firing the roll at a clearing
    target takes every one of them from **0 of 672** variants to **238-624**.

    BINARY, and that is measured rather than modest. The margin at the L frame predicts how MANY
    variants fire (within a family, monotone over 18 enumerated states) but NOT what they are worth:
    node 16's widest margin (47.9 deg, 1507 firing) bounds 94.78 while its narrowest (30.1, 1494)
    bounds 94.76, and node 52's widest (68.2, 3622 firing) bounds 98.72 against 98.41 for a narrower
    one. So an ordering by margin would be a preference nothing measured -- every clearing target ties
    at 0.0 and the stable sort leaves `landing_key`'s own order to separate them.

    A KEEP SHARE by default, and ``lok_require`` (`extend_cycle`) is the same predicate as a
    REQUIREMENT (`as_requirement`). The share was chosen on the s73 calibration -- a camera term as a
    filter throws away firing states (there, 96% of them) -- plus session 116's second argument from
    ``dips`` refusing the other half whatever the camera does, and session 121 measured that clause to
    decide NO endpoint (at the 30 dead endpoints of the census it is the sole refusal on 0 of 200038
    variants while ``l_ok`` is sole on 55754, and no dip budget revives one) --
    `knowledge/strategy/the-dip-budget-is-not-the-lever.md`. Costs two steps per candidate.

    **AND THE s73 CALIBRATION IS ABOUT THE SNAP BILL, NOT ABOUT THIS PREDICATE -- BUT THE SHAPE STILL
    DOES NOT MOVE THE ANSWER** (session 122, both halves measured). 96% of the firing cells fail the
    BILL, where this one is exact (above) and every state it drops fires nothing: over the 165-survivor
    population's 33 R2 cells (`_notes/s122_shape_preflight.py`, an emulation self-checked to reproduce
    the banked keep at 33 of 33) the share spends **54 of its 99 slots** on states that cannot fire
    while the requirement returns **63 slots, all firing**, 25 of them targets the share never kept --
    and the 8 cells it empties all sit at a pre-roll node that keeps live cells on another aim, so it
    drops **zero junction nodes**. Re-cut whole (`_notes/s122_recut_c3.py`, the s119 pair lane with
    this one knob) the requirement beam is what that predicts -- **63 of 63 terminals clear, 50 of 50
    probed FIRE** against the share's 27 of 47, in-band **2 -> 6**, deliverers **1 -> 4**, 34 endpoints
    the share never reached, 0 disagreements at the 23 shared, 20% less wall clock -- and the best
    DELIVERED is **105.00 at the same endpoint**, unmoved. So the share is not kept for the s73 reason
    (retired) but because the shapes tie on the answer, and default-off leaves every banked beam's
    provenance intact; a NEW cut should prefer ``lok_require``.
    `knowledge/strategy/the-shape-of-a-cut-is-not-its-answer.md`.

    **AND IT IS EXACT AS A SCREEN AND INERT AS AN ORDER** (session 117, both measured, and the
    distinction is the whole reason this coexists with `camera_probe_key` rather than replacing it).
    At the two rolls whose EVERY reachable camera state was priced -- 225 of them -- this predicate is
    perfect: **107 of 107 clearing states fire and 118 of 118 non-clearing states fire nothing**, no
    false positive and no false negative. But being binary it ties every clearing target at 0.0, so over
    a set that is entirely clearing it supplies no ordering at all and the slot collapses onto
    `landing_key`'s: swept whole, this order retains the roll's optimum at **10 of 23** rolls at mean
    **+0.53** frames, indistinguishable from `landing_key` alone (9, +0.53), while the snap bill above
    reaches 14 at +0.14. The share earns its place on the FULL graded set, where it decides whether an
    endpoint exists at all -- not on the axis it has already let through
    (`knowledge/strategy/the-screen-is-not-the-rank.md`).

    Returns a callable ``node -> 0.0 (clears) | None (does not)``."""
    from harness.tetrapush import away_walk as AW    # deferred: `away_walk` imports this module

    def probe(node):
        return 0.0 if AW.lok_clear(node['run'], hl)['clear'] else None

    return probe


def as_requirement(probe):
    """**A ``tcs_probe`` read as a ``tcs_require`` -- the SAME predicate in the other shape** (session
    122), so that a shape A/B differs in the shape alone and never in what is being asked.

    A probe reports ``None`` for a camera target it refuses and a sortable for one it accepts; as a
    share that refusal only sinks the target to the back of one order of several, where as a
    requirement it drops the target before the keep. Both shapes are worth having and which one is
    right is a MEASUREMENT, not a preference -- see `lok_probe_key`'s ``lok_require``.

    Returns a callable ``node -> bool`` for `roll_candidates`' ``tcs_require``."""
    return lambda node: probe(node) is not None


def roll_candidates(node, hl, box, *, half_window=0x2800, step=8, l_windows=((4, 7), (5, 8)),
                    aim_keep=3, min_roll=20.0, tcs_keep=3, target_css=None,
                    fan_center=None, require_quality=True, key=None, mixed_aims=True,
                    tcs_key=None, tcs_probe=None, tcs_require=None, corridor=None,
                    tcs_span=None, tcs_step=None, env=None, twin=None, shared_body=None,
                    axis=AXIS_HERD):
    """The cycle's ROLL stage from a junction endpoint, factored by the separability above.

    R1: sweep the reachable aim fan (camera frozen) x the L windows, prune talk-unsafe / weak /
    off-line / wall-touching, keep ``aim_keep`` of them -- by ``key`` (`rank_key` -- the frame bound by
    default, the s43 herd rate if asked) MIXED with two geometric orders when ``mixed_aims``
    (`_mixed_beam`): |Link - Tetra lateral| and distance off `objective.push_corridor`.

    **What the fan actually contains, and where it is lost** (session 63, measured -- and the mixed keep
    here is NOT what recovers it): widened past `aim_keep`, the cycle-2 fan holds endpoints 7.0 u off
    the push corridor only 0.12 frames behind the -40.5 u one the bound picks. Those reach this stage
    and are kept by it; they die at `require_quality` below, because putting Tetra on the corridor
    requires LINK 50-58 u off her lateral (the plow ejects her AWAY from his centre, so the two are
    ANTI-CORRELATED inside a roll) and the next junction cannot continue from there. So a mid-chain keep
    over roll endpoints -- at this cut or at the beam's -- cannot help, and both were measured inert
    (the beam one returned the same 9 cycle-2 survivors, all 44.9-59.0 u off). The lateral has to be
    corrected in the JUNCTION, where Link repositions without a 400 u commitment. This keep stays
    because it is correct where it does fire (the LAST cycle, whose `require_quality` is off).
    R2: re-run each kept aim over the DERIVED `target_cs` grid and keep the ``tcs_keep`` camera
    targets whose endpoint the NEXT junction can actually continue from, ranked by
    `junction_quality` -- a tcs that strands the plan is worthless however fast the roll was.

    ``tcs_key`` / ``tcs_probe`` (session 70) are what that cut ranks on when `junction_quality` is not
    the right question, and each is measured rather than assumed:
      * ``tcs_key`` REPLACES the order (a callable ``node -> sortable``). The LAST cycle wants
        `landing_key`, because its exit is the handoff and there is no next junction to strand.
      * ``tcs_probe`` ADDS a keep share (a callable ``node -> off or None``), for mid-chain cycles where
        continuability IS the question but the aim also has to survive: `square_probe_key`, the cheap
        `junction_square_probe`. Its calibration -- and the measurement that every CHEAP AIM KEY IS
        WORSE THAN THE STOCK ONE -- is in that docstring. A SEQUENCE of probes gives a share each
        (session 116): the last cycle's camera answers to two independent customers, the snap bill
        (`camera_probe_key`) and the escape's ``l_ok`` cone (`lok_probe_key`), and neither order
        contains the other -- the snap is reachable at 0-6 of ~110 camera states where the cone clears
        at 1-68.
      * ``tcs_require`` (session 122) is the OTHER shape of the same question -- a callable ``node ->
        bool`` that drops a camera target before the keep instead of sinking it in one order. A share
        cannot spend more than its slot; a requirement decides the whole cut, so it belongs only to a
        predicate measured EXACT at deciding whether the state can fire at all. Its calibration -- and
        the measurement that the last cycle's ``l_ok`` cone is such a predicate where the snap bill is
        not -- is in `lok_probe_key`.

    ``tcs_span`` / ``tcs_step`` (session 73) widen the grid `derived_target_css` builds, which the LAST
    cycle needs and the shipped `TCS_SPAN` cannot supply: the escape atom's turnaround wants the camera
    inside its snap window, 15-38 deg off the arrival's own csangle, and +-1536 BAM is +-8.4. The
    values for that cycle are `ESCAPE_TCS_SPAN` / `ESCAPE_TCS_STEP`, the roll's own measured slew reach
    (see those constants); mid-chain the defaults are unchanged.

    ``env`` / ``twin`` (session 129) run R1 on `roll_kernel`'s fan instead of one wired
    `roll_segment` per aim. It is the screen's own economy made explicit: the fan is where 84% of a
    stage goes (s126), every run it makes is DISCARDED (only ``(want, aim, lw)`` survives the cut),
    and the csangle a roll commits does not depend on the aim -- so a fan of ~90 aims pays for one
    camera and ~90 native rollouts. Pass ``env`` to have the twin built per node
    (`roll_kernel.node_twin`), or ``twin`` directly if the caller already holds one.

    ``shared_body`` (session 130; defaults to on whenever ``env``/``twin`` is passed) runs R2 off
    `roll_kernel.SharedBody` -- one wired roll per aim, then a camera walk and an exit tail per
    camera target, instead of ~25 whole wired rolls. R2 could not take the fan for the reason the
    s129 box gives (its survivors ARE their runs: the candidate carries one forward and
    `junction_quality` steps it), and it does not need to: `target_cs_is_exit_only` says the
    targets share the roll itself, so what is re-run is only the ~5 frames after it, and what comes
    out is a genuine wired run. Reaching for the fan here instead would have been the wrong lever
    twice over -- a native endpoint cannot be stepped by `junction_quality` (measured s130: the
    camera does not stop the moment the C-stick centres, so the glide off a frozen-csangle endpoint
    differs), and fanning over targets costs a camera trace per target, which is more than the
    rollout it replaces.

    Both are gated stage-for-stage against the wired path, and independently, in
    `tests/test_fan_stage.py`; the records themselves are gated in `tests/test_roll_kernel.py` and
    `tests/test_tcs_kernel.py`.

    Returns the surviving post-roll nodes (each ``dict(run, log, frames, m, knobs, quality)``)."""
    out = []
    r1 = []
    walls = O.courtyard_walls()
    use_shared = (env is not None or twin is not None) if shared_body is None else bool(shared_body)
    key = rank_key() if key is None else key
    center = hl.bearing_bam() if fan_center is None else int(fan_center)
    fan = T.roll_facing_fan(node['run'], center, half_window, step)
    if twin is None and env is not None:
        twin = RK.node_twin(env, node['log'], check=node['run'])
    if twin is not None:
        # fan per L WINDOW, then walked in the wired path's (aim, lw) order -- the keep below is a
        # STABLE sort, so order decides ties: knowledge/strategy/a-screen-needs-a-record-not-a-run.md
        aims = [a for _w, a in fan]
        per_lw = [RK.roll_fan(node['run'], aims, l_window=lw, target_cs=None, fast=twin)
                  for lw in l_windows]
        for i, (want, aim) in enumerate(fan):
            for lw, recs in zip(l_windows, per_lw):
                rec = recs[i]
                if rec['talk_unsafe'] or not rec['ok'] or rec['roll_speedF'] is None \
                        or rec['roll_speedF'] < min_roll:
                    continue
                rv = RK.RecordRun(rec)
                fr = node['frames'] + rec['frames']
                m = T.metrics(rv, hl, fr)
                if not T.alive(m, axis=axis) or not frame_in_model(rv, walls):
                    continue
                r1.append(dict(k=key(rv, fr, m), want=want, aim=aim, lw=lw, m=m,
                               along=hl.along(rv.tx, rv.tz), lat=hl.lateral(rv.tx, rv.tz)))
    else:
        for (want, aim) in fan:
            for lw in l_windows:
                rr = node['run'].clone()
                seg = T.roll_segment(rr, aim, target_cs=None, l_window=lw)
                if seg['talk_unsafe'] or not seg['ok'] or seg['roll_speedF'] is None \
                        or seg['roll_speedF'] < min_roll:
                    continue
                fr = node['frames'] + seg['frames']
                m = T.metrics(rr, hl, fr)
                if not T.alive(m, axis=axis) or not frame_in_model(rr, walls):
                    continue
                r1.append(dict(k=key(rr, fr, m), want=want, aim=aim, lw=lw, m=m,
                               along=hl.along(rr.tx, rr.tz), lat=hl.lateral(rr.tx, rr.tz)))
    r1.sort(key=lambda t: t['k'])
    # the mixed aim keep, and where it does and does not fire: see the docstring
    if mixed_aims and len(r1) > int(aim_keep):
        # the line this keep rides: the caller's (`aim.handoff_corridor`), else the coord one -- s69
        # wired the handoff line into every mid-chain aim keep and this one was still reading direct
        cor = O.push_corridor(hl) if corridor is None else corridor
        r1 = _mixed_beam([r1,
                          sorted(r1, key=lambda t: abs(t['m']['lat'])),          # push squareness
                          sorted(r1, key=lambda t: cor['offset'](t['along'], t['lat']))],
                         int(aim_keep), ident=lambda t: (t['want'], tuple(t['lw'])))
    for t in r1[:int(aim_keep)]:
        want, aim, lw = t['want'], t['aim'], t['lw']
        css = (derived_target_css(node['run'],
                                  span=TCS_SPAN if tcs_span is None else int(tcs_span),
                                  step=TCS_STEP if tcs_step is None else int(tcs_step))
               if target_css is None else target_css)
        graded = []
        # R2 off the shared roll body: one wired roll, then a camera per target and its exit tail
        body = RK.SharedBody(node['run'], aim, l_window=lw) if use_shared else None
        walk = RK.camera_walks(body, css) if body is not None and body.ok else None
        for tcs in css:
            log = list(node['log'])
            if walk is not None:
                seg, rr = RK.tcs_segment(body, walk, tcs, log=log)
            else:
                rr = node['run'].clone()
                seg = T.roll_segment(rr, aim, target_cs=tcs, l_window=lw, log=log)
            if seg['talk_unsafe'] or not seg['ok'] or seg['roll_speedF'] is None \
                    or seg['roll_speedF'] < min_roll:
                continue
            fr = node['frames'] + seg['frames']
            m = T.metrics(rr, hl, fr)
            if not T.alive(m, axis=axis) or not frame_in_model(rr, walls):
                continue
            cand = dict(run=rr, log=log, frames=fr, m=m, quality=None,
                        knobs=dict(roll_bam=want, aim=aim, l_window=lw, target_cs=tcs,
                                   roll_speedF=seg['roll_speedF'], jframes=node['jf'],
                                   junction=node['jv']['kind'], phases=node['jv']['phases']))
            if tcs_require is not None and not tcs_require(cand):
                continue                          # this camera target cannot fire -- the OTHER shape
            q = junction_quality(rr, hl, box, axis=axis)
            if q is None and require_quality:     # this camera target strands the plan next cycle
                continue                          # (a TERMINAL roll has no next cycle to strand)
            cand['quality'] = q
            graded.append((q, cand))
        if tcs_key is not None:
            graded.sort(key=lambda t: tcs_key(t[1]))
        else:
            # unscored (quality None) only occurs on a terminal roll -- rank those by `key`
            graded.sort(key=lambda t: t[0] if t[0] is not None
                        else (0, key(t[1]['run'], t[1]['frames'], t[1]['m'])))
        if tcs_probe is not None and len(graded) > int(tcs_keep):
            # a share by what the exit's junction can still DELIVER -- a keep, so the order above is
            # untouched and the probe can only ADD; several probes, several shares (see the docstring)
            probes = [tcs_probe] if callable(tcs_probe) else list(tcs_probe)
            orders = [[n for _q, n in graded]]
            for pr in probes:
                orders.append([n for _v, n in sorted(((pr(n), n) for _q, n in graded),
                                                     key=lambda t: (t[0] is None, t[0] or 0.0))])
            out.extend(_mixed_beam(orders, int(tcs_keep),
                                   ident=lambda n: _state_tag(n['run'])))
        else:
            out.extend(n for _q, n in graded[:int(tcs_keep)])
    return out


# --------------------------------------------------------------------------- the N-cycle chain

def rank_key(rank='bound', placements=None, hl=None, resid=None):
    """**The beam's ordering, ASCENDING every way** (lower is better) -- built here so every stage
    ranks the same way and the choice is a measured one rather than a habit.

    ``'bound'`` (the session-60 default) is `objective.plan_bound`: frames spent plus the fewest that
    could still land the coord. Ranking on it is frame-minimal by construction, and it counts LATERAL
    drift, because the distance to a coord is a distance and not a down-herd projection.

    ``'thread'`` (session 62) is `objective.thread_cost`, and it is the one for the LAST cycle and
    the terminal: it counts along and lateral at the rates the plow achieves on each, so it can see
    what `'bound'` measurably cannot -- that the human's on-thread endpoint and the search's 39.9 u
    off-thread one are not the same plan four frames from the end. Needs ``hl``.

    ``'rate'`` is the s43 herd rate (`-u/frame`), kept selectable so the difference is measurable
    instead of asserted -- it was the rank that produced the 868 u / 69 f chain whose 28 u lateral
    offset the endgame then could not pay for.

    ``resid`` (session 70) ranks against the state the HERD must deliver rather than against the coord
    the ESCAPE lands on: the placement rows translated up-herd by the escape's measured residual
    (`aim.handoff_rows`). It is the rank-side twin of `aim.handoff_corridor` and of
    ``arrive_keep``/`roll_probe`'s ``arrive``, and it matters most under ``'thread'``, whose 47.6 u of
    along slack otherwise SWALLOWS an overshoot whole -- the s69 cycle-3 endpoints landed at along 947,
    inside the real thread's 937.5..984.1 and therefore free, while against the shifted thread
    (893.9..940.5) they are past its far end and priced. Never passed to the admissible ``budget``
    CUT, which keeps ranking on the coord (`extend_cycle`): the shifted target is the more pessimistic
    of the two, and a prune must stay optimistic."""
    if rank == 'rate':
        return lambda run, frames, m: -m['per_frame']
    rows = placements if placements is not None else seeds.load_placements()[0]
    if resid is not None:
        from harness.tetrapush import aim as A      # deferred: `aim` reads `objective` back
        if hl is None:
            raise ValueError("resid shifts the rows in HERD coordinates -- it needs the HerdLine")
        rows = A.handoff_rows(rows, hl, resid)
    if rank == 'bound':
        return lambda run, frames, m: O.plan_bound(frames, _placement_dist(run, rows))
    if rank != 'thread':
        raise ValueError("rank must be 'bound', 'thread' or 'rate', not %r" % (rank,))
    if hl is None:
        raise ValueError("rank 'thread' needs the HerdLine (it is a herd-frame metric)")
    th = O.placement_thread(hl, rows)
    return lambda run, frames, m: O.thread_cost(
        frames, hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz), th,
        ready=_terminal_ready(run)['ready'])


def _budget_cut(nodes, key, budget, label='', verbose=False):
    """Drop nodes whose `objective.plan_bound` already exceeds the frame budget -- a SOUND prune (the
    bound is admissible, so such a node cannot finish in time whatever follows it). Never silent:
    it says how many it dropped, since a stage that empties itself here is a finding."""
    if budget is None:
        return nodes
    kept = [n for n in nodes if key(n['run'], n['frames'], n['m']) <= float(budget)]
    if verbose and len(kept) != len(nodes):
        print("    (budget %g: dropped %d of %d %s -- bound already over)"
              % (budget, len(nodes) - len(kept), len(nodes), label))
    return kept


def _mixed_beam(orders, beam, ident=None, group=None, per_group=None):
    """Cut a beam by SEVERAL orders at once, an equal share of the slots each, deduped by ``ident``
    across all of them -- the same shape as `junction_beam`'s flat/short keep, one stage up.

    ``group``/``per_group`` cap how many members of ONE group may take slots. Without it a beam whose
    members TIE fills every slot with variants of a single state, which is not a hypothetical: it is
    what `junction_beam`'s frontier did for twenty-five sessions (session 68 -- see its docstring),
    because the input pipeline acts a frame late so all of a node's children share identical physics
    and every rank ties across them.

    A keep, never a rank: whatever is best by the first order is still kept, so this can only ADD
    alternatives. That is the point -- see `objective.push_corridor`. Session 61 measured that ranking
    a mid-chain beam on the lateral throws away the branch that comes back, and session 63 measured
    that keeping only the frame bound leaves the corridor branch out of the beam entirely (the cycle-2
    endpoint kept sat 45 u off the corridor while one 4.8 u of along behind it sat 7 u off).

    Used at BOTH cuts, which matters: applying it only to the cycle beam is measurably INERT, because
    `roll_candidates`' ``aim_keep`` cut has already thrown the diverse aims away (session 63 -- the
    re-solve came back byte-identical, same 9 survivors, corridor offsets 44.9-59.0). A keep can only
    preserve what reaches it."""
    ident = (lambda n: _state_tag(n['run'])) if ident is None else ident
    seen, out, used = set(), [], {}

    def _take(n):
        t = ident(n)
        if t in seen:
            return False
        if group is not None and per_group is not None:
            g = group(n)
            if used.get(g, 0) >= int(per_group):
                return False
            used[g] = used.get(g, 0) + 1
        seen.add(t)
        out.append(n)
        return True

    per = max(1, int(beam) // max(1, len(orders)))
    for i, order in enumerate(orders):
        room = int(beam) - len(out) if i == len(orders) - 1 else per
        taken = 0
        for n in order:
            if taken >= room or len(out) >= int(beam):
                break
            if _take(n):
                taken += 1
    # any slots the later orders could not fill go back to the first (the rank)
    for n in orders[0]:
        if len(out) >= int(beam):
            break
        _take(n)
    return out


def _state_tag(run):
    """Beam dedup key: the coupled state at a cycle boundary, coarse enough to collapse duplicates
    and fine enough to keep genuinely different plans (the same granularity the junction stage
    uses)."""
    return (round(run.link.pos_x, 1), round(run.link.pos_z, 1), run.link.facing >> 5,
            round(run.link.speedF, 2), round(run.tx, 1), round(run.tz, 1), int(run.csangle) >> 5)


def _probe_pool(ends, cap, sq_key=None, tag=None, spread=True, jf_spread=False, l0_key=None):
    """**Which endpoints get roll-probed when there are more than ``cap`` of them.**

    `extend_cycle` takes the first ``cap`` of `junction_beam`'s return, and session 70 measured that
    this is a FLATNESS prefix and not the generation prefix the session-68 note here claimed: with
    ``keep`` unbounded the beam returns its endpoints sorted by ``(|Link - Tetra lateral|, jf)``, so
    the 250 probed off a real cycle-2 exit were **entirely jf 8 and jf 10** out of 4622 spread over
    jf 5..12. ``jf_spread`` is the fix -- a share of the pool that walks the junction-frame bands
    round-robin, so every band gets probed rather than whichever one happens to be flattest.

    It matters because the junction frame IS the arrival: the roll's length is fixed (~223 u off that
    exit) while the junction pushes ~11-12 u/frame, so off that node jf 6 lands Tetra at along 887 and
    jf 12 at 947 against a `aim.handoff_target` of 894. The flattest-250 pool contained no endpoint
    whose roll could arrive on target, so ``arrive_keep`` had exactly two arrivals to choose between
    (947.40 / 949.50, both ~53 u past) and came out byte-identical to the stage without it -- while a
    band-spread pool finds a rollable jf-6 endpoint delivering **886.81, i.e. 7.07 u from the target**.
    Flatness not predicting rollability is `roll_probe`'s own founding measurement; this is the same
    lesson applied to WHICH endpoints get probed at all.

    Session 68's own measurement of the cap stands: off cycle-1 node 1 the fixed frontier returns 4158
    armed endpoints of which **932 are within 5 deg** of the push corridor, and every one of them is
    past index 250 (the 250 probed are all -15.5..-15.8; the square ones sit at junction frame 10+).

    And it measured that closing that gap COSTS MORE THAN IT BUYS, which is why ``sq_key`` is opt-in.
    Spending a share of the pool on squareness -- with or without spreading it over the distinct
    physics states -- took cycle 2 from **8 survivors to ZERO**, twice. The rollable-AND-continuable
    endpoints are concentrated in the few early states, and only some PENDING inputs of those states
    roll at all (the s42 arming lesson), so a pool spread over 45 states holds one pending each of
    mostly-uncontinuable ones: 250 consecutive endpoints yield 6 rollable whose rolls pass
    `junction_quality`, while the spread pool yields 7 rollable whose rolls (the square ones included)
    strand the next junction -- confirmed against the REAL next junction, which arms 0 endpoints from
    the +1.12 deg endpoint's roll.

    So the prefix stays the default and the square share is a knob (`extend_cycle`'s ``square_pool``).
    The conclusion the numbers point at is not a better cut here: squareness that survives to a
    continuable roll is a property of the cycle EXIT, and that is one stage further up.

    ``l0_key`` (session 134) is a share by the axis the ENDGAME is denominated in -- her offset from
    the clip roll's approach line (`handoff.tetra_lateral`) at the endpoint, descending. Both orders
    above are blind to it, and the cap makes that decisive rather than cosmetic: a real cycle-1
    parent yields **4292** unique endpoints of which **250 (5.8%)** are screened at all, chosen by
    flatness and junction-frame band. Measured over the eight banked parents, the screened
    population's best DELIVERED ``l0`` is **-90.39** against a beam that hands over **-183.41**, so
    what the stage produces and what its cuts keep differ by 93 u on the one number session 126
    reduced the whole endgame to. This is the earliest place that axis can be asked for, and it is
    free -- one dot product per endpoint, no rollout.

    An endpoint's own ``l0`` is NOT a predictor of what its roll delivers (session 126's trap: two
    cycle-2 nodes at an identical -183.41 reach -27.10 and +19.65), which is exactly why it is a
    share and never the order: it buys the screen a look at the endpoints the other two orders
    structurally never show it, and `roll_probe` then decides.

    ``spread=False`` is that one stage up (`junction_square_probe`, session 69): the same prefix +
    squareness mix with NO per-state cap. Where this function's job is to pick endpoints to CARRY, the
    probe's job is to score an exit, and there the cap is what lies -- measured on three real exits,
    the uncapped mix reads ``1.34 / 141.83 / 14.67`` where the capped one reads
    ``none / 141.83 / 25.89``, and it finds strictly more rollable endpoints (12 against 9). Both
    single pools are worse than the mix in one direction or the other (prefix-only
    ``1.34 / none / 27.02``, squarest-only ``none / 141.83 / 14.67``)."""
    ends = list(ends)
    if len(ends) <= int(cap) or (sq_key is None and not jf_spread and l0_key is None):
        return ends[:int(cap)]
    orders = [ends]
    if sq_key is not None:
        orders.append(sorted(ends, key=sq_key))
    if l0_key is not None:
        orders.append(sorted(ends, key=l0_key))
    if jf_spread:
        # the junction-frame bands, round-robin: the i-th of every jf before the (i+1)-th of any
        seen = {}
        rank = {}
        for e in ends:
            jf = e['jf']
            rank[id(e)] = seen.get(jf, 0)
            seen[jf] = rank[id(e)] + 1
        orders.append(sorted(ends, key=lambda e: (rank[id(e)], e['jf'])))
    if not spread or sq_key is None:
        # the per-state cap belongs to the SQUARENESS share (s68's measurement); band coverage on its
        # own must not inherit it -- it would hand back one pending variant per state (session 70)
        return _mixed_beam(orders, int(cap), ident=id)
    tag = (lambda e: _physics_tag(e['run'])) if tag is None else tag
    nstates = len({tag(e) for e in ends})
    return _mixed_beam(orders, int(cap), ident=id,
                       group=tag, per_group=max(1, int(cap) // max(1, nstates)))


def extend_cycle(nodes, hl, box, *, jn_keep=6, jn_beam=24, ess_step=1, aim_step=16,
                 max_frames=12, beam=8, aim_keep=3, half_window=0x2800, step=8,
                 probe_cap=250, probe_step=24, rank='bound', budget=None, placements=None,
                 require_quality=True, glide_keep=False, escape_keep=False, corridor_keep=True,
                 align_keep=True, per_state=4, aim_share=True, square_keep=True,
                 square_pool=False, corridor=None, arrive_keep=False, target_along=None,
                 resid=None, tcs_landing=False, tcs_square=False, land_keep=False,
                 probe_contact=False, probe_half=None, escape_flip=None, escape_rots=None,
                 escape_rank=None, tcs_escape=False, lok_require=False, cloud_keep=False,
                 cloud_flip=None,
                 cloud_rots=None, cloud_cap=None, cloud_fan=None, cloud_stations=None,
                 cloud_exit_runs=None, cloud_exit_step=None, cloud_exit_half=None,
                 delivered_keep=False, handoff_keep=False, handoff_pf=None, handoff_rungs=None,
                 handoff_roots=True, handoff_sign=True, l0_keep=False, free_axis=False,
                 terminal=None, terminal_sink=None, env=None, verbose=False):
    """One chained cycle applied to a whole beam: the junction stage (`junction_beam`), whose
    endpoints are kept by ROLLABILITY (`roll_probe` -- not flatness, which measurably selects
    unrollable states), followed by the roll stage (`roll_candidates`), deduped by state and cut to
    ``beam`` by ``rank`` (`rank_key`; the frame bound by default).

    ``budget`` (frames) drops any survivor whose `objective.plan_bound` is already over it --
    admissible, so nothing solvable is lost (`_budget_cut`).

    ``require_quality`` must be **False for the LAST cycle of a chain**: `junction_quality` asks
    whether the next junction could continue from this roll's endpoint, and the last cycle has no next
    junction -- only the terminal glide, which needs contact and the regime, not a junction posture.
    Session 61 measured what leaving it True costs: from the cycle-2 beam it produced **zero** cycle-3
    survivors (the s43 chain "stalling"), where False produces **7**, at 69-70 frames and
    `plan_bound` 74.4-74.7 -- inside the 75-frame budget.

    ``corridor_keep`` / ``align_keep`` (session 63) make the cut a MIXED keep (`_mixed_beam`) over
    three orders -- ``rank``, distance off the push corridor (`objective.push_corridor`), and
    |Link - Tetra lateral| (``metrics['lat']``, the push's squareness). Both are keeps and never ranks:
    whatever is best by ``rank`` is still kept, which is what session 61's warning requires (the
    mid-chain lateral OSCILLATES, so the branch that comes back must stay in). Note that the same
    diversity has to be applied at `roll_candidates`' ``aim_keep`` cut to have any effect -- keeping it
    here alone was measured INERT.

    Measured reason, in one line each. CORRIDOR: the rank cannot see a lateral excursion whose bill
    arrives two cycles later -- at the cycle-2 stage the beam kept an endpoint **45.5 u** off the
    corridor and `plan_bound` ranked it BEST (72.94) while a **7.0 u**-off endpoint sat 0.12 frames
    behind, and that excursion then cost 21.5 u of sideways push (~1.7 frames) in the last roll and the
    terminal (`objective.push_budget`). ALIGNMENT: what a terminal recovers is monotone in it, measured
    on the three cycle-3 endpoints whose terminals were actually run -- Link 16.6 u off Tetra's lateral
    recovered **39.0 u** of placement distance, 22.8 u off recovered 14.0, 47.0 u off recovered 7.6 --
    and the human himself never exceeds **12 u** (`pursuit_box`) where `two_roll.alive` admits 60.

    ``per_state`` / ``aim_share`` / ``square_keep`` (session 68) are the SQUARENESS keeps, one at each
    of the two cuts this stage makes. The first two are `junction_beam`'s frontier fix (its docstring
    has the measurement: the frontier was a greedy walk over ONE physics state whose kept aim degraded
    to -41 deg, and the fix takes the squarest armed endpoint from -15.3 to +0.03 off a real cycle-1
    exit). ``square_keep`` is this stage's own: `roll_probe`'s rate stays the RANK, and a share of
    ``jn_keep`` goes to the endpoints whose probed roll leaves Tetra CLOSEST TO THE CORRIDOR
    (`roll_probe`'s ``off``), because the rate does not predict the direction -- the squarest rollable
    endpoint measured 28th of 60 by rate, so a pure rate keep of 6 never sees it. Ranked on the roll's
    DELIVERED offset, not the endpoint's own `aim.corridor_aim_error`: keeping by the entry aim took
    cycle 2 from 8 survivors to ZERO, because at a long junction the aim swings 5-8 deg per frame and a
    +1.12 deg endpoint fires a roll landing 37.6 u off (see `roll_probe`). The cheap entry aim is still
    the right key one stage earlier, where nothing has been probed yet (`_probe_pool`).

    ``glide_keep`` (session 62) belongs with it, and for the same reason: on the LAST cycle the
    survivors are re-ranked by `glide_probe` -- what their terminal glide actually reaches -- rather
    than by where the roll left Tetra. Measured, the two disagree by two frames of finish (see
    `glide_probe`). It costs ~1 s per survivor, so it re-ranks the final list, never the aim fan.

    ``escape_keep`` (session 67) supersedes it on the last cycle, one stage further out: the terminal
    glide has NO authority over Tetra (`escape_probe` / `aim` -- the whole alphabet moves her
    identically for four frames), so what a last-cycle endpoint is worth is what its ESCAPE lands.
    The survivors are probed with the real atom and ranked by `aim.landing_miss`, with a share of the
    beam kept by that miss. It costs ~2-5 s per survivor and takes precedence over ``glide_keep``.

    ``arrive_keep`` / ``target_along`` (session 70) are the OVERSHOOT, the third axis of the same
    endpoint probe (`roll_probe`'s ``arrive``). The s69 cycle-3 stage kept endpoints landing at along
    947 against a `aim.handoff_target` of 894 and came out at 78-80 frames against a 75 budget; a roll
    is a ~205 u atom that cannot stop short, so the junction length is what decides arrival and the
    keep is where it belongs. ``resid`` (the escape's measured residual) points ``rank`` at the state
    the herd must DELIVER instead of at the coord itself (`rank_key`) -- the same shift, in the rank.
    ``arrive_keep`` also spreads the PROBE POOL over the junction-frame bands (`_probe_pool`'s
    ``jf_spread``), without which it has nothing to choose from: the pool is a FLATNESS prefix, so the
    250 probed of 4622 were all jf 8/10 and every arrival in them was ~53 u past the target.

    ``land_keep`` (session 71) is the endpoint keep's own version of that shift, and it is the axis
    that SUBSUMES ``square_keep`` and ``arrive_keep`` rather than a third share beside them: a share of
    ``jn_keep`` by the smallest escape LANDING any probed roll would reach (`roll_probe`'s ``land``,
    exact given ``resid``). The two it replaces are separately blind -- ``off`` rides a corridor line
    through ONE point, so past the target along its lateral ask is wrong by 4.11 u at +18.8 and 10.18 u
    at +55.6 against a 1.0 u `objective.PLACEMENT_BAND`, and every arrival a last cycle chooses between
    is past the target. Requires ``resid``; inert without it.

    ``probe_step`` / ``probe_contact`` (session 71) are the SCREEN's resolution and where it points, and
    they are one fix in two knobs (kept separable so the measurement can tell them apart). The screen
    ran 3x coarser than `roll_candidates`, the stage it screens for, over a fan 6x wider than any
    surviving roll occupies -- so on the band the plan needs it found 2 rollable endpoints of 416 and
    called the next band dead. ``probe_contact`` re-centres the fan on the bearing to Tetra and narrows
    it to `pursuit_box`'s measured ``max_delta``, which is what makes ``probe_step=8`` cost what
    ``probe_step=24`` cost before. `roll_probe`'s ``fan_center`` holds the measurement.

    ``probe_half`` (session 72) is the knob that makes the screen AFFORDABLE, and it exists because
    session 71's proposed two-stage screen (coarse ``step`` to find live endpoints, fine ``step`` on
    those) cannot work: per-endpoint survival is **ONE alphabet member wide** (measured over both
    full-resolution bands -- median 1 surviving aim, widest window 0.04 deg), so a ``[::step]``
    decimation finds ~1/step of the live endpoints however it is staged. Measured, ``probe_step=8``
    over the ``max_delta`` fan finds **21%** of the jf-7 band's live endpoints and **8%** of jf 6's,
    and what it drops is not tail: it loses jf 7's best escape bound (77.54 against **75.51**, i.e.
    2.0 frames) and jf 6's best landing (32.13 against **19.97 u**).

    The axis that works is the WIDTH at full resolution, because survival is razor-thin in aim but its
    LOCATION is not -- every survivor of both bands sits within **8.34 deg** of the bearing to Tetra,
    and the two bands' best arrivals on BOTH keys sit inside **2 deg** of it. So ``probe_half`` (BAM,
    with ``probe_step=1``) buys the frontier for less than the shipped screen costs: measured per
    endpoint, +-2 deg is **20 aims** and recovers both bands' best arrival, where ``max_delta`` at
    ``step=8`` is ~31-35 aims and does not. Containment is measured, not assumed
    (`[[search-space-contains-human]]`): the human's own two rolls sit at +0.76 and +0.63 deg from the
    bearing to her, and ``fan_edge`` reports the furthest SURVIVING aim so a binding window shows up
    (`roll_probe`). Recall of ENDPOINTS still falls with the width (+-2 deg holds 18% / 60%), so a
    wider setting is the thorough one: +-8 deg is 83 aims and 98-99%.

    ``cloud_keep`` / ``cloud_flip`` / ``cloud_rots`` (session 107) are ``escape_keep``'s MEASURED
    replacement, and they exist because session 106 measured that keep to be landing-blind: every rank
    in it (`escape_probe`'s ``miss`` and ``bound``, `away_walk.probe`'s ``thread``) reads
    `objective.placement_thread`'s FIT, and the frame-minimal target set is a ~170 u-wide 2D CLOUD of
    rows (session 105) through which a fit is fiction. So rounds 1-3 of the retargeted chain reported a
    ~6 u landing floor over the 6-8 endpoints their beams KEPT out of 18-33 survivors, and that floor
    was a property of the CUT. This keep ranks the survivors on `cloud_land.cloud_probe` -- the whole
    atom knob grid enumerated at each endpoint, priced as complete candidates (herd + the atom's own
    log + the row's `plan_cost` + the remaining miss at `objective.PUSH_CEILING`) -- with a share of the
    beam kept by the raw miss. It costs ~28 s per survivor, the same order as ``escape_keep``'s swept
    form, and supersedes ``escape_keep``/``glide_keep`` when on.

    ``cloud_fan`` is the half of that fix with authority, and the distinction is the session-107 finding:
    the keep above sits at the ENDPOINT of the last cycle, where the survivor set is already fixed by the
    junction cut, so however honestly it ranks it can only name the least-bad survivor. Handing a measured
    residual fan (`cloud_land.residual_fan`) here puts the same measure at the per-AIM screen instead --
    `roll_probe`'s ``cloud_bound``, a share of ``jn_keep`` by the cheapest whole candidate any surviving
    roll could reach over fan x rows -- which is the cut that decides which endpoints exist. Free per aim
    (a few thousand distances) against ~28 s for an enumeration, and OPTIMISTIC, so it sizes the cut while
    ``cloud_keep``'s enumeration makes the claim.

    ``cloud_stations`` / ``cloud_exit_runs`` (session 110) make that keep JOINT, and they are the fix for
    what killed the session-107 winner: a landing inside the band is half a candidate, because the clip
    also needs Link's ARRIVAL to reach the stations the row's `plan_cost` was priced at
    (`knowledge/strategy/delivery-is-two-predicates.md`). Given a `cloud_land.station_map` the keep
    prices `cloud_land.arrival_frames` beside the landing miss and reports ``joint`` -- the variant that
    owes NOTHING on either half -- and ``cloud_exit_runs`` gives it the axis to pay with: the atom's tail
    (`away_walk.escape_atom`'s ``exit_run``), which moves the arrival while Tetra stays frozen.

    ``cloud_stations`` now also reaches the per-aim SCREEN (session 115), and that is where it decides
    something rather than reorders: the keep above runs at the survivors, so until now the set they are
    drawn from was fixed by a `roll_probe` that priced only the landing. Enumerated over the whole
    session-111 cycle-3 beam the two halves are anti-correlated (node 0: landing 25.4 u out, arrival
    already free; node 3: landing 4.7 u, stations 136.8 u away), so a landing-only screen selects the
    endpoints whose arrival cannot be paid. It costs the screen one ``min()`` per (fan member, row) and
    needs a fan carrying the THROW (`cloud_land.residual_fan` with ``exit_runs``) -- which is now a
    REFUSAL rather than a default (session 119: the fan the s115-s117 cuts were handed carried it on
    0 of 178 members, so their screens priced Link's arrival at the roll terminal).

    ``cloud_exit_step`` / ``cloud_exit_half`` (session 119) are the last unplumbed axis, and they are
    the KEEP's half of it: `cloud_land.exit_arc` was built in session 110 and no enumeration could ask
    for it, since only `cloud_land.atom_cloud` took bearings. Session 118 swept it by hand at 14
    already-chosen endpoints for ~3 frames (delivered 106.45 -> 103.45, the beam's first ``joint``
    records), which is a measurement about ENDPOINTS THAT ALREADY EXISTED; this is what lets the cut
    that decides they exist see the same axis. The SCREEN's half arrives through ``cloud_fan`` instead
    (`cloud_land.residual_fan` with the same ``exit_step``), because a bearing list is meaningless
    beam-wide -- the arc's centres are measured from each endpoint's own position (`cloud_land._arc`).
    Default None = the standing pair, so a beam cut without them is byte-for-byte the s118 one; at
    `cloud_land.ARC_STEP` the enumeration is ~13x the pair per endpoint (measured 9.2 s -> 127.9 s at
    ``max_frames=18``), so a run that turns it on should size ``cloud_cap`` to match and say what it
    skipped.

    ``delivered_keep`` (session 120) is a share of the beam by the field the OBJECTIVE is denominated
    in, and it exists because every other cloud share reads ``cloud['best']`` -- the minimum-``bound``
    variant, which session 119 measured to be an ``n_atom`` = 3 member at 64 of 64 endpoints. ``bound``
    charges the atom 1:1 in frames and the miss it buys at `objective.PUSH_CEILING`, so the rank is
    structurally short-atom and a knob that pays late (the exit arc, whose frames land at tails 10-11)
    cannot appear in it at all. The DELIVERED figure has no such floor: ``in_band``/``joint`` are
    min-TOTAL among variants that satisfy a predicate rather than minima over an unconstrained fan
    (`cloud_land.cloud_landing`), so a node whose only deliverable variant is a 10-frame atom is
    rankable on it. Kept as a share and never as the rank, for `_mixed_beam`'s standing reason -- most
    nodes have no settled record at all, and a node without one is UNMEASURED, not refused, so it
    sorts last here and keeps its place in the other orders.

    ``handoff_keep`` (session 126) is what the ZERO-WALK-AWAY shape replaces that whole stack with,
    and the replacement is not a refinement of it -- it is a different question. Every keep above ranks
    a last-cycle endpoint by where TETRA ends up (the thread, the cloud, the row's stations), because
    the plan used to be "park her on a coord, walk away, roll back in". Session 123 deleted the walk-away
    and session 125 measured the consequence: her placement is free inside a wide band and **the razor
    is on LINK** -- 15 of 127 banked endpoints park her on the genuine side and ALL 15 admit a clip
    roll, while Link ends the last roll 73-171 u from the nearest genuine entry it needs. So this keep
    ranks on `handoff.endpoint`: her ``l0`` SIGN first (one dot product, which refuses 112 of 127
    before any razor work), then the distance from LINK to the genuine entry curve at her own Tetra,
    priced in frames as ``frames + gap/WALK_CAP + 16``. ~1.5 s per survivor at `handoff.RUNWAYS`,
    against ~28 s for a cloud enumeration, and it supersedes ``cloud_keep``/``escape_keep``/
    ``glide_keep`` when on. ``handoff_roots`` picks the admissible curve (`handoff.entry_roots`, the
    default) over the confirmed one (`handoff.entry_locus`, ~10x dearer); ``handoff_sign`` turns the
    empirical side prune off to re-measure it; ``handoff_pf`` passes a `handoff.PairFrame` at another
    facing/thrust/lean, which is not a detail -- the herd's own last-roll aims yield ZERO genuine and
    the clip roll must be aimed at the corner deliberately.

    Session 107's warning applies to it as it does to every keep here: it sits at the ENDPOINT, so it
    can only name the least-bad member of a survivor set the per-aim screen already fixed. What it
    can afford at the screen is the SIGN.

    ``l0_keep`` (session 134) is that warning acted on, and it is ``handoff_keep``'s axis moved to
    the two cuts UPSTREAM of it -- the probe pool (`_probe_pool`'s ``l0_key``) and the per-aim screen
    (`roll_probe`'s ``pf`` -> ``l0_max``). Session 126 reduced the whole remaining endgame to one
    number, ``l0 >= -80.4`` handed over by cycle 2, and measured cycle 2 handing over -183.41. What
    this stage's population actually reaches was never asked until now: screened over the eight
    banked cycle-1 parents it is **-90.39**, 10 u short of the bar and 93 u better than the beam
    keeps. So the gap was mostly a CUT, not a reachability -- the endpoints that cross are the ones
    riding 25-50 u off the push corridor at a positive lateral, and ``corridor_keep`` / ``square_keep``
    are the orders that refuse exactly those. Those keeps are not wrong; they are HERD constraints,
    and by the last two cycles there is no more herding to do (session 123 deleted the walk-away,
    session 125 moved the razor onto Link). Kept as a share for `_mixed_beam`'s standing reason, so
    whatever is best by ``rank`` still survives.

    ``free_axis`` (session 135) is the clause underneath all of that, and it is the measured CAP on
    the plan rather than another share. It swaps `in_pursuit_box`, `two_roll.alive` and
    `_frontier_score` from the herd line to the pair's own push axis (`reposition.AXIS_PAIR`) --
    every measured number kept, one assumption dropped. Session 134 got cycle 2 to ``l0`` -51.75 at
    52 frames, past the -80.4 bar the whole endgame was reduced to, and cycle 3 off those states
    returned ZERO survivors with every child ``outbox`` at generation 1: they fail ONLY the direction
    clauses, at separations 58.8-64.6 u that sit dead centre in the human's own recorded plow band.
    Freed, the same stage returns 21x more surviving rolls. It is a PRUNE, so unlike every keep here
    it changes what exists rather than what is chosen -- and it composes with ``l0_keep``, which is
    then what picks among the states the freed prune admits.

    Why it belongs at the screen and not only at the endpoint: ``l0`` is ONE DOT PRODUCT on a Tetra
    the rollout already produced, where `handoff.endpoint`'s locus solve is ~1.5 s a survivor. The
    axis is affordable exactly where the set is decided.

    ``terminal`` / ``terminal_sink`` (session 145) pass a `terminal_keep.TerminalKeep` straight
    through to `roll_probe`, and they exist because ``l0_keep`` and every rank before it were still
    RANKS. Session 144 measured the population five sessions of that produced: 4 of 49 rungs satisfy
    the terminal's ``tetra_from_corner``, 0 its ``along``, 0 the seam's facing window, none more than
    one at a time. Session 145 then measured what a re-point of the last cycle can recover, sweeping
    the FULL 2280-member alphabet from each rung's own last junction: 528 aims reach a live seam cell
    and **every one of them dies ``followed``**, missing ``along`` by >= 9.6 u, ``tetra_from_corner``
    by >= 34.1 u and the razor's ``lat`` by >= 10.6 u -- while ``runway`` is satisfied outright. So
    the keep here is not an optimisation of the last roll; it is the axis the CYCLES have to be bred
    against, which is the only thing that moves those three.

    It is a share at THREE cuts, and the third was measured to be load-bearing: a chained run with
    the pool and the screen alone handed over **-160.62** where the same stage's screened population
    reaches **-90.39**. The roll stage was exonerated -- re-opening each kept node at its own
    pre-roll endpoint, `roll_candidates` delivered exactly what that endpoint's screen promised
    (0.00 u lost at three of four, and one node BEAT its screen by 4.73 u on a wider fan) -- so what
    dropped the high-``l0`` survivors was the FINAL beam cut, which sorts on the frame rank and had
    no share for the axis. A keep that only reaches two of three cuts is a keep the third one
    undoes.

    ``escape_flip`` / ``escape_rots`` / ``escape_rank`` (session 72) pass the escape atom's two
    unswept knobs and its frames rank through ``escape_keep`` (`escape_probe`, `away_walk.probe`):
    where the conversion frames PUSH her, which on four real arrivals is worth landing 4.90 -> 0.33,
    4.99 -> 0.01 and 8.23 -> 0.00 u and the first `aim.handoff_spec` True. ~30 s per survivor at
    ``escape_flip=0x400`` with all four rotates, so a solve opts in on the last cycle.

    ``tcs_landing`` / ``tcs_square`` (session 70) are the CAMERA-target cut's two calibrated keys, one
    per kind of cycle: `landing_key` on the LAST one (its exit is the handoff, so rank it by where the
    escape lands, not by a next junction it does not have) and `square_probe_key` mid-chain (a keep
    share by what the exit's junction can still deliver). The second costs ~2.7 s per surviving
    (aim, tcs) pair, so it is opt-in; the first is free. See `square_probe_key` for the calibration,
    including the measurement that every CHEAP AIM key is worse than the stock one.

    ``tcs_escape`` (session 73) is the LAST cycle's camera cut re-aimed at the customer it never had:
    the escape atom's snap window. It widens the grid from `TCS_SPAN` (+-8.4 deg, the mid-chain
    junction's razor travel band) to `ESCAPE_TCS_SPAN` (the roll's own -46.6..+40.7 deg slew reach) and
    keeps a share by `camera_probe_key` -- what the arrival still OWES the atom. Without it the atom
    COMMANDED a csangle 91-114 deg off live and every landing since s65 was conditional on a leg no roll
    could pay; with it, 63 of 112 measured arrivals owe nothing, and the frontier there is both
    replay-faithful and better: **75 frames, pd 0.432 u, `objective.verdict` True** where the commanded
    frontier read 1.644 u at the same 75. Free (one frame per candidate), LAST cycle only -- mid-chain
    the widened band strands the next junction (s42).

    Every node carries its FULL delivered input log, so any survivor is replayable end-to-end on a
    fresh `FreeRun` (`confirm_plan`)."""
    out = []
    rows_j = placements if placements is not None else seeds.load_placements()[0]
    key = rank_key(rank, rows_j, hl, resid=resid)
    # the RANK may be the (inadmissible) thread cost, or shifted to the handoff by ``resid``; the hard
    # budget CUT is neither -- it stays the admissible coord-distance bound (see `rank_key`)
    cut = key if (rank == 'bound' and resid is None) else rank_key('bound', rows_j)
    # the line the keeps ride: to the nearest coord by default, `aim.handoff_corridor` from the chain
    cor_j = O.push_corridor(hl, rows_j) if corridor is None else corridor
    sq_key, _ = _armable_square(hl, cor_j)
    th_j = O.placement_thread(hl, rows_j)
    # the ENDPOINT keep's landing axis (s71): the target is a SEGMENT, not the corridor's one point
    th_land = th_j if (land_keep and resid is not None) else None
    # the SCREEN's fan (s71): re-centred on the bearing to Tetra and narrowed to the recorded regime,
    # which is where every surviving roll measurably lives -- see `roll_probe`'s ``fan_center``
    pkw = (dict(fan_center='tetra', half_window=int(box['max_delta'])) if probe_contact else {})
    if probe_half is not None:
        # ...and NARROWED at full resolution, which is the axis a decimated ``step`` cannot buy:
        # survival is one alphabet member wide, its location is not (see the docstring)
        pkw['half_window'] = int(probe_half)
    # the CAMERA-target cut's key: the landing on the last cycle, the cheap probe mid-chain (s70)
    tcs_key = (landing_key(hl, th_j, resid) if tcs_landing else None)
    tcs_probe = square_probe_key(hl, box, cor_j) if tcs_square else None
    # the endgame's frame, built ONCE if either customer wants it (the endpoint keep or the screen)
    pf_j = ((handoff_pf if handoff_pf is not None else _HO().PairFrame())
            if (handoff_keep or l0_keep or free_axis) else None)
    jaxis = AXIS_PAIR if free_axis else AXIS_HERD
    l0_key = ((lambda e: -_HO().tetra_lateral(pf_j, (e['run'].tx, e['run'].tz)))
              if l0_keep else None)
    tcs_require = None
    if tcs_escape:
        # the LAST cycle's camera has two customers the cut never priced: the escape's snap window
        # (s73) and the clause that actually refuses, its ``l_ok`` cone (s116). A keep share each.
        tcs_probe = [camera_probe_key(), lok_probe_key(hl)]
        if lok_require:
            # ...or the cone as a REQUIREMENT, the same predicate in the other shape (s122 -- see
            # `lok_probe_key`'s ``lok_require``). The snap bill keeps its share of what survives.
            tcs_probe, tcs_require = [camera_probe_key()], as_requirement(lok_probe_key(hl))
    jdead = {}
    for node in nodes:
        ends = junction_beam(node, hl, box, max_frames=max_frames, beam=jn_beam,
                             ess_step=ess_step, aim_step=aim_step, keep=10 ** 6, dead=jdead,
                             per_state=per_state, aim_share=aim_share, corridor=cor_j,
                             axis=jaxis, pf=(pf_j if free_axis else None))
        uniq = _dedup_endpoints(ends)
        if len(uniq) > int(probe_cap):
            # never a silent truncation: say what was dropped
            if verbose:
                print("    (probing %d of %d unique endpoints -- capped)"
                      % (probe_cap, len(uniq)))
            uniq = _probe_pool(uniq, probe_cap, sq_key if square_pool else None,
                               jf_spread=arrive_keep, l0_key=l0_key)
        rdead = {}
        scored = [(p, e) for p, e in ((roll_probe(e, hl, step=probe_step, dead=rdead,
                                                 corridor=cor_j, target_along=target_along,
                                                 thread=th_land, resid=resid,
                                                 fan=cloud_fan, rows=(rows_j if cloud_fan else None),
                                                 stations=cloud_stations,
                                                 pf=(pf_j if l0_keep else None), axis=jaxis,
                                                 terminal=terminal, terminal_sink=terminal_sink,
                                                 **pkw), e)
                                      for e in uniq) if p is not None]
        scored.sort(key=lambda t: -t[0]['rate'])
        orders = [[e for _p, e in scored]] if scored else []
        if square_keep and scored:
            # rollability stays the rank, a share goes to the straightness the roll DELIVERS
            # (`roll_probe`'s ``off``, never the endpoint's own aim -- see the docstring)
            orders.append([e for _p, e in sorted(scored, key=lambda t: t[0]['off'])])
        if arrive_keep and scored and target_along is not None:
            # ...and a share to the endpoints whose roll ARRIVES at the handoff target rather than
            # past it, which is the same probe's third axis (session 70 -- see `roll_probe`)
            orders.append([e for _p, e in sorted(scored, key=lambda t: (t[0]['arrive'] is None,
                                                                       t[0]['arrive'] or 0.0))])
        if th_land is not None and scored:
            # ...and a share by where the ESCAPE would land, which is the two axes above measured
            # against the real target segment instead of against a one-point line (session 71)
            orders.append([e for _p, e in sorted(scored, key=lambda t: (t[0]['land'] is None,
                                                                       t[0]['land'] or 0.0))])
        if cloud_fan and scored:
            # ...and a share by that axis measured against the CLOUD over the whole residual fan --
            # the cut that decides which endpoints exist, so it is the one worth a landing measure
            orders.append([e for _p, e in sorted(scored, key=lambda t: (t[0]['cloud_bound'] is None,
                                                                       t[0]['cloud_bound']
                                                                       or 0.0))])
        if l0_keep and scored:
            # ...and a share by how far ACROSS the clip roll's approach line the roll carries her --
            # the endgame's own axis, at the cut that decides which endpoints exist (s134)
            orders.append([e for _p, e in sorted(scored, key=lambda t: (t[0]['l0_max'] is None,
                                                                       -(t[0]['l0_max'] or 0.0)))])
        if len(orders) > 1:
            kept = _mixed_beam(orders, int(jn_keep),
                               ident=lambda e: (_physics_tag(e['run']), e['log'][-1]['stickX'],
                                                e['log'][-1]['stickY'],
                                                bool(e['log'][-1]['triggerL'])))
        else:
            kept = [e for _p, e in scored[:int(jn_keep)]]
        jdead['unrollable'] = jdead.get('unrollable', 0) + (len(uniq) - len(scored))
        for k, v in rdead.items():                     # WHY the aims died, not just how many
            jdead['aim_' + k] = jdead.get('aim_' + k, 0) + v
        if verbose and scored:
            # is the SCREEN's window binding? (`roll_probe`'s ``fan_edge`` -- never assume it is not)
            ed = max(p['fan_edge'] for p, _e in scored)
            print("    (%d of %d endpoints roll; furthest surviving aim %.2f deg of the %.2f deg "
                  "half-window)" % (len(scored), len(uniq), ed * _BAM_DEG,
                                    scored[0][0]['fan_half'] * _BAM_DEG))
            if l0_keep:
                # the SCREENED frontier the cut below chooses from, against THIS terminal's own bar
                # (s137): the bar moves with the terminal, so a literal here quotes the wrong one
                l0s = [p['l0_max'] for p, _e in scored if p['l0_max'] is not None]
                bar = _HO().crossing_bar(pf_j) if pf_j is not None else None
                print("    (screened l0 %+.2f .. %+.2f over %d endpoints; the bar cycle 2 must hand"
                      " over is %s)" % (min(l0s), max(l0s), len(l0s),
                                        ('%+.2f' % bar) if bar is not None
                                        else 'NOT MEASURED at this terminal') if l0s else
                      "    (screened l0: none)")
        for j in kept:
            for cand in roll_candidates(j, hl, box, aim_keep=aim_keep, half_window=half_window,
                                        step=step, key=key, require_quality=require_quality,
                                        tcs_key=tcs_key, tcs_probe=tcs_probe, axis=jaxis,
                                        tcs_require=tcs_require, corridor=cor_j, env=env,
                                        tcs_span=ESCAPE_TCS_SPAN if tcs_escape else None,
                                        tcs_step=ESCAPE_TCS_STEP if tcs_escape else None):
                cand['plan'] = list(node.get('plan', [])) + [cand['knobs']]
                out.append(cand)
    out = _budget_cut(out, cut, budget, 'roll survivors', verbose)
    if handoff_keep and out:
        # THE ZERO-WALK-AWAY SHAPE'S OWN KEEP -- see the docstring's ``handoff_keep``
        HO = _HO()
        pf = pf_j
        rungs = HO.RUNWAYS if handoff_rungs is None else tuple(handoff_rungs)
        for n in out:
            r = n['run']
            n['handoff'] = HO.endpoint(pf, (r.link.pos_x, r.link.pos_z), (r.tx, r.tz), n['frames'],
                                       runways=rungs, roots=handoff_roots,
                                       sign_prune=handoff_sign)
        # the tie-break is her SIGNED offset, descending: every refused endpoint scores ``inf``, and
        # among them the ones her last roll nearly carried across are the informative ones
        out.sort(key=lambda n: (n['handoff']['bound'], -n['handoff']['l0']))
        if verbose:
            on = [n for n in out if n['handoff']['onside']]
            live = [n for n in on if n['handoff']['n']]
            print("    (handoff-probed %d survivors: %d park her on the genuine side, %d of those"
                  " admit an entry curve; best bound %s = %s u of gap at %d herd frames)"
                  % (len(out), len(on), len(live),
                     ('%.2f' % out[0]['handoff']['bound']) if live else '--',
                     ('%.2f' % out[0]['handoff']['gap']) if live else '--',
                     out[0]['frames'] if live else -1))
    elif cloud_keep and out:
        # the landing MEASURED rather than predicted -- see the docstring's ``cloud_keep``
        CL = _CL()
        # a WALL-CLOCK budget, never a claim about the population: a capped run says what it skipped
        probed, skipped = out, 0
        if cloud_cap is not None and len(out) > int(cloud_cap):
            probed = sorted(out, key=lambda n: cut(n['run'], n['frames'], n['m']))[:int(cloud_cap)]
            skipped = len(out) - len(probed)
        for n in probed:
            n['cloud'] = CL.cloud_probe(n['run'], n['frames'], hl, rows_j,
                                        flip_step=(CL.FLIP_STEP if cloud_flip is None
                                                   else cloud_flip),
                                        rotate_offs=cloud_rots, stations=cloud_stations,
                                        exit_runs=(cloud_exit_runs or (0,)),
                                        exit_step=cloud_exit_step, exit_half=cloud_exit_half)
        # an unprobed survivor is UNMEASURED, not refused: infinite bound, and a None miss so the
        # share below cannot invent a landing for it
        for n in out:
            if 'cloud' not in n:
                n['cloud'] = dict(fires=False, bound=float('inf'), miss=None, total=None,
                                  frames=n['frames'], unprobed=True, in_band=None, joint=None)
        out.sort(key=lambda n: n['cloud']['bound'])
        if verbose:
            fired = [n for n in out if n['cloud']['fires']]
            solved = [n for n in fired if n['cloud']['in_band'] is not None]
            joint = [n for n in fired if n['cloud'].get('joint') is not None]
            if skipped:
                print("    (cloud keep CAPPED at %d: %d survivors were NOT enumerated -- the floor"
                      " below is the capped slice's, not the population's)" % (cloud_cap, skipped))
            dl = [d for n in fired for d in [CL.delivered(n['cloud'])] if d is not None]
            if dl:
                print("    (%d survivors carry a SETTLED record: best DELIVERED %.2f frames -- what"
                      " a replay pays, the field the objective is denominated in)"
                      % (len(dl), min(dl)))
            print("    (cloud-landed %d survivors: %d fire, %d land INSIDE the %.1f u band, %d pay"
                  " BOTH halves; best bound %.2f = %.3f u at total %.1f%s)"
                  % (len(out), len(fired), len(solved), O.PLACEMENT_BAND, len(joint),
                     fired[0]['cloud']['bound'] if fired else float('nan'),
                     fired[0]['cloud']['miss'] if fired else float('nan'),
                     fired[0]['cloud']['total'] if fired else float('nan'),
                     (', arrival %.1f u from its stations'
                      % fired[0]['cloud']['d_station']) if (fired and cloud_stations
                                                            and fired[0]['cloud'].get('d_station')
                                                            is not None) else ''))
    elif escape_keep and out:
        # the LAST cycle's endpoint is handed to the ESCAPE, and nothing between them has authority
        # (`escape_probe`) -- so rank it by what the escape lands, and keep a share by that miss.
        th = O.placement_thread(hl, rows_j)
        for n in out:
            n['escape'] = escape_probe(n['run'], n['frames'], hl, rows_j, th,
                                       atom_flip=escape_flip, atom_rots=escape_rots,
                                       atom_rank=escape_rank)
        out.sort(key=lambda n: n['escape']['bound'])
        if verbose:
            fired = [n for n in out if n['escape']['fires']]
            print("    (escape-probed %d survivors: %d fire; best lands %.2f u off the thread at "
                  "%d f (bound %.2f), worst firing %.2f u)"
                  % (len(out), len(fired),
                     fired[0]['escape']['miss'] if fired else float('nan'),
                     fired[0]['escape']['frames'] if fired else -1,
                     fired[0]['escape']['bound'] if fired else float('nan'),
                     fired[-1]['escape']['miss'] if fired else float('nan')))
    elif glide_keep and out:
        # the LAST cycle is keeping endpoints for a TERMINAL, so measure the terminal (`glide_probe`)
        th = O.placement_thread(hl, rows_j)
        for n in out:
            n['glide'] = glide_probe(n['run'], n['frames'], hl, rows_j, th)
        out.sort(key=lambda n: n['glide']['bound'])
        if verbose:
            print("    (glide-probed %d survivors: best hands the terminal bound %.2f, worst %.2f)"
                  % (len(out), out[0]['glide']['bound'], out[-1]['glide']['bound']))
    else:
        # the rank first, then continuability -- a faster cycle that strands the plan is worth less
        # than a marginally slower one the next junction can pick up (the s42 entry-state lesson).
        # ``quality`` is None under ``require_quality=False`` and a tuple otherwise, and a beam can
        # hold BOTH (the last cycle keeps unjudged rolls), so the tie-break must be None-safe.
        out.sort(key=lambda n: (key(n['run'], n['frames'], n['m']),
                                n.get('quality') is None, n.get('quality') or ()))

    def _off(n):
        return cor_j['offset'](hl.along(n['run'].tx, n['run'].tz),
                               hl.lateral(n['run'].tx, n['run'].tz))

    orders = [out]
    if corridor_keep and out:
        # a share of the beam by Tetra's distance off the push corridor -- see the docstring
        orders.append(sorted(out, key=_off))
    if align_keep and out:
        # ...and a share by Link's lateral offset from her, the axis that predicts a terminal
        orders.append(sorted(out, key=lambda n: abs(n['m']['lat'])))
    if l0_keep and out:
        # ...and a share by how far ACROSS the approach line the cycle actually left her, which the
        # frame rank cannot see and the endpoint keep alone does not survive (s134 -- the docstring)
        orders.append(sorted(out, key=lambda n: -_HO().tetra_lateral(pf_j, (n['run'].tx,
                                                                            n['run'].tz))))
    if handoff_keep and out:
        # ...and a share by the RAW gap, so an endpoint that reaches the entry curve is never cut by
        # the frame rank that averages a few units of it away against a whole herd's frames
        orders.append(sorted(out, key=lambda n: (n['handoff']['gap'], -n['handoff']['l0'])))
    if cloud_keep and out:
        # ...and a share by the MEASURED landing, kept on the raw miss so a band-reaching endpoint
        # is never cut by the frame rank that averages it away
        orders.append(sorted(out, key=lambda n: (n['cloud']['miss'] is None,
                                                 n['cloud']['miss'] or 0.0)))
        if delivered_keep:
            # ...and a share by what a REPLAY of this node pays -- see the docstring
            dlv = _CL().delivered
            orders.append(sorted(out, key=lambda n: (dlv(n['cloud']) is None,
                                                     dlv(n['cloud']) or 0.0)))
    elif escape_keep and out:
        # ...and a share by where the ESCAPE lands her, which is what ends the plan (session 67)
        orders.append(sorted(out, key=lambda n: (n['escape']['miss'] is None,
                                                 n['escape']['miss'] or 0.0)))
    beamed = _mixed_beam(orders, beam)
    if verbose:
        print("    -> %d roll survivors, %d after dedup/beam (junction dead: %s)"
              % (len(out), len(beamed), ' '.join('%s=%d' % kv for kv in sorted(jdead.items()))))
        if beamed:
            print("       kept: corridor off %s | Link-Tetra lat %s"
                  % (' '.join('%.1f' % _off(n) for n in beamed),
                     ' '.join('%+.1f' % n['m']['lat'] for n in beamed)))
    return beamed


def cycle1_nodes(env, hl, box, *, nflips=(1, 2, 3), flip_msd=1.0, half_window=0x2000, step=4,
                 l_windows=((5, 8), (4, 7), (6, 9)), aim_keep=4, beam=8,
                 tcs_keep=3, rank='bound', budget=None, placements=None,
                 square_keep=False, sq_cap=24, corridor=None, verbose=False, native=True):
    """Cycle 1 from state 2, FACTORED like every later cycle (`roll_candidates`) rather than as the
    s42 full aim x tcs cross product -- same search space, ~20x fewer rollouts (159 s -> 10 s for
    the identical 13.147 u/f best).

    At state 2 Tetra is ~122 deg BEHIND Link (out of the +-90 cone), so the L-held flip prologue
    re-targets straight into the proc-7 flip -- no turnaround is needed to start.

    **WHAT THIS STAGE ACTUALLY HAS TO CHOOSE, MEASURED (session 69): ONE ROLL AND ITS CAMERA.** The
    aim fan does not branch here -- of the whole ``half_window`` fan x three ``l_windows``, exactly
    **three** (aim, window) pairs survive the roll prunes and all three are the SAME aim (want 35324);
    the l-window decides only which frame the exit lands on (f20 / f21 / f22), and of those f20's whole
    tcs family fails `junction_quality`. So the entire cycle-1 candidate set is one roll swept over the
    25-value `derived_target_css` grid, and every one of them scores `plan_bound` **71.90** -- the rank
    cannot separate them at all.

    What separates them is the SQUARENESS their junction can still deliver, and it varies by two orders
    of magnitude across that bound-tied grid (`junction_square_probe`: 1.34 to 141.83 u, some none). The
    ``tcs_keep=3`` cut ranks them by `junction_quality`, which measures frames-in-the-box and is blind
    to the aim -- and it keeps the three worst-but-one (141.83 / 27.81 / 14.67, where the best is 11.20
    at quality rank 5).

    ``square_keep=True`` is the fix and it is **opt-in, because it costs 308 s**: enumerate the WHOLE
    surviving grid (pass ``tcs_keep`` large) and spend the keep on the probe -- a `_mixed_beam` share by
    the smallest corridor offset the exit's junction delivers, at most ``sq_cap`` exits probed. A SOLVE
    wants it (`chain_herd`'s ``c1_square``, default ON, where it is worth cycle 2's whole straightness:
    corridor offset 37.0 -> 8.97 u); a caller that just needs a cycle-1 node to build something else on
    does not, which is why the defaults here stay the cheap s43-s68 stage.

    A keep and never a rank, as always: whatever the frame bound likes best is still kept. And the
    probe never promotes an exit that cannot roll -- `junction_square_probe` returns None there, which
    sorts last rather than infinitely square.

    ``native`` (session 131, on by default) seeds the chain with a run whose camera is driven from
    the C core (`seeds.make_freerun(native=True)`), so every node the chain carries steps in C. It is
    ONE knob for the whole chain because a node's run is what the later stages step: the junction,
    `junction_quality`'s glides and the roll exit tails all inherit it. 0-ULP identical either way
    (`tests/test_native_camera.py`); False is the pre-s131 engine, and what a comparison runs."""
    dtm = seeds.dtm_input_at(env)
    key = rank_key(rank, placements, hl)
    cut = key if rank == 'bound' else rank_key('bound', placements)
    rows_c = placements if placements is not None else seeds.load_placements()[0]
    cor = O.push_corridor(hl, rows_c) if corridor is None else corridor
    out = []
    for nflip in nflips:
        base = seeds.make_freerun(env, native=native)
        base.pre_seed_input(dtm(0))
        blog = []
        fb = _bearing((base.link.pos_x, base.link.pos_z), (base.tx, base.tz))
        for _ in range(nflip):
            d = T._inp(fb, base.csangle, flip_msd, buttons=S.PAD_L, triggerL=255)
            blog.append(dict(d))
            base.step(d)
        center = _bearing((base.link.pos_x, base.link.pos_z), (base.tx, base.tz))
        # the prologue as a pseudo junction endpoint, so the roll stage is literally the same code
        node = dict(run=base, log=blog, frames=nflip, jf=nflip,
                    jv=dict(kind='prologue', phases=[]))
        cands = roll_candidates(node, hl, box, half_window=half_window, step=step,
                                l_windows=l_windows, aim_keep=aim_keep, fan_center=center,
                                tcs_keep=tcs_keep, key=key, corridor=cor, env=env)
        for c in cands:
            c['knobs']['nflip'] = nflip
            c['plan'] = [c['knobs']]
        if verbose:
            print("  nflip=%d: preroll %+.2f -> %d cycle-1 survivors"
                  % (nflip, base.link.speedF, len(cands)))
        out.extend(cands)
    out = _budget_cut(out, cut, budget, 'cycle-1 survivors', verbose)
    # the rank first, then continuability -- a faster cycle that strands the plan is worth less than
    # a marginally slower one the next junction can pick up (the s42 entry-state lesson).
    out.sort(key=lambda n: (key(n['run'], n['frames'], n['m']), n.get('quality')))
    seen, uniq = set(), []
    for n in out:
        t = _state_tag(n['run'])
        if t in seen:
            continue
        seen.add(t)
        uniq.append(n)
    if not square_keep or len(uniq) <= int(beam):
        return uniq[:int(beam)]
    # the squareness keep: probe what each exit's junction can still deliver (see the docstring)
    for n in uniq[:int(sq_cap)]:
        n['square'] = junction_square_probe(n, hl, box, cor)
    if verbose:
        got = [n for n in uniq[:int(sq_cap)] if n.get('square')]
        print("  square-probed %d of %d cycle-1 exits: %d roll, best off %s"
              % (min(len(uniq), int(sq_cap)), len(uniq), len(got),
                 '%.2f' % min(n['square']['off'] for n in got) if got else 'none'))
    sq = sorted(uniq, key=lambda n: (n.get('square') is None,
                                     (n.get('square') or {}).get('off', 0.0)))
    return _mixed_beam([uniq, sq], int(beam), ident=lambda n: _state_tag(n['run']))


def chain_herd(env, hl, *, ncycles=3, c1_beam=8, beam=8, jn_keep=6, aim_keep=3,
               c1_step=4, jn_beam=24, ess_step=1, nodes=None, box=None,
               rank='bound', last_rank='thread', budget=None, placements=None,
               corridor_keep=True, last_escape=True, per_state=4, aim_share=True,
               square_keep=True, c1_square=True, handoff=True, corridor=None,
               last_arrive=True, last_landing=True, mid_square=False, land_keep=False,
               probe_step=24, probe_contact=False, probe_half=None, escape_flip=None,
               escape_rots=None, escape_rank=None, last_camera=True, native=True, verbose=False):
    """**The full-herd chain**: cycle 1 from state 2 (`cycle1_nodes`), then ``ncycles - 1``
    applications of `extend_cycle`, every cycle sweeping its OWN derived `target_cs` grid.

    ``rank`` / ``budget`` are the objective (session 60): rank every beam by the admissible frame
    bound and drop anything that already cannot finish inside ``budget`` frames.

    ``corridor_keep`` (session 63) makes every cycle's cut a MIXED keep -- half by ``rank``, half by
    distance off the push corridor -- because a lateral excursion's bill arrives cycles after the rank
    that took it. See `extend_cycle` for the measurement.

    ``last_rank`` (session 62) is the LAST cycle's own rank, and it is deliberately a different one.
    Two measurements force the split. Mid-chain, Tetra's lateral OSCILLATES rather than accumulating
    (+5.8 after cycle 1, -39.9 after cycle 2, +8.9 after cycle 3): ranking an intermediate beam on it
    would have thrown away the survivor that came back, so cycles 1..N-1 stay on the pure frame
    `'bound'`. At the END it is the whole remaining gap -- the s61 solve finished 73 frames INSIDE
    budget and 31.4 u short purely because the last cycle and terminal traded lateral for along at
    par -- so the final cycle ranks on `'thread'` (`objective.thread_cost`), which prices them apart.

    ``last_escape`` (session 67, default ON) makes the last cycle's endpoint keep `escape_probe` --
    the real escape atom's landing miss -- instead of `glide_probe`'s terminal glide, because the
    glide was measured to have no authority over Tetra at all (`aim`). Set it False to reproduce the
    s62-s66 keep.

    ``c1_square`` (session 69, default ON) makes cycle 1 keep by what each exit's junction can still
    DELIVER (`cycle1_nodes`' ``square_keep``, ~308 s once). Cycle 1's candidates are bound-TIED, so the
    frame rank cannot choose between them at all and the old `junction_quality` cut was anti-correlated
    with squareness; turning this on took cycle 2 from **37.00 to 8.97 u** off the push corridor, Tetra's
    lateral from -32.10 to -3.65 and Link's lateral offset from her from +11.14 to -0.69, at a `plan_bound`
    of 72.69 against 72.81.

    ``handoff`` (session 69, default ON) points every mid-chain aim keep at `aim.handoff_corridor`
    rather than at `objective.push_corridor`: the state the chain must DELIVER is the coord minus the
    escape's measured ~44 u residual, and the two lines ask for aims ~0.56 deg apart at cycle-2 range
    -- the full width of the `aim.aim_window` the plan has to hit at the end. Pass ``corridor`` to
    supply a line directly (a dumped one, or a different ``feet`` depth). It also carries the measured
    residual into every cycle's RANK (`rank_key`'s ``resid``), so a beam is ordered by its distance to
    the state the herd must DELIVER rather than to the coord the escape lands on.

    ``last_arrive`` (session 70, default ON) prices the OVERSHOOT where it is decided: the last cycle's
    endpoint keep takes a share by what its roll ARRIVES at (`roll_probe`'s ``arrive``, against the
    corridor's own target). A roll is a ~205 u atom that cannot stop short, so the plan's finish is
    chosen when the endpoint is -- and the s69 run ended 53 u past the handoff target at 78-80 frames
    against a 75 budget with nothing shorter in the set.

    ``last_landing`` (session 70, default ON) fixes the CAMERA cut on the same cycle: its exit is the
    handoff, so rank the `target_cs` grid by where the escape would land from it (`landing_key`) instead
    of by whether a next junction -- which does not exist -- could continue. Free.
    ``mid_square`` (default OFF) is its mid-chain counterpart, the cheap `junction_square_probe` as a
    keep share (`square_probe_key`); it costs ~2.7 s per surviving (aim, tcs) pair, i.e. ~15 min a
    cycle, so a solve opts in. Its docstring holds the calibration, including the finding that every
    CHEAP AIM key -- the shape this was expected to take -- is measurably WORSE than the stock one.

    ``probe_step`` / ``probe_contact`` / ``probe_half`` / ``land_keep`` (sessions 71-72) are the
    endpoint SCREEN, forwarded to every cycle: where its fan points, how wide it is and at what
    resolution, plus the landing axis it keeps on. `extend_cycle` holds the measurement -- the short
    version is that the shipped screen (``probe_step=24``, the wide fan) misses the arriving band's
    best arrivals entirely, and the setting that finds them is ``probe_contact=True, probe_step=1``
    with a narrow ``probe_half``, which costs LESS per endpoint than the shipped one.
    ``escape_flip`` / ``escape_rots`` / ``escape_rank`` (session 72) sweep the escape atom's
    ``flip_bearing`` and ``rotate_off`` on the last cycle's keep and rank it in frames.

    ``last_camera`` (session 73, default ON) is what makes any of those numbers describe a REPLAYABLE
    plan. The escape atom needs the camera inside its turnaround's snap window and cannot slew there
    itself, so until now it simply COMMANDED the csangle -- 91-114 deg off the arrival's own -- and every
    landing from s65 to s72 was conditional on a camera leg no roll could pay. This turns the last
    cycle's camera cut into the payer: `ESCAPE_TCS_SPAN` (the roll's own measured slew reach) instead of
    the mid-chain `TCS_SPAN`, plus `camera_probe_key` as a keep share. Free, and the frontier it reaches
    is BETTER than the commanded one: **75 frames, pd 0.432 u, `objective.verdict` True**.

    Returns ``dict(beams, best, bar, box, corridor)`` -- the per-cycle beams (so a stalled cycle is
    diagnosable), the best final node, the human's 2-roll rate, the pursuit box and the line in force."""
    import time
    t0 = time.perf_counter()
    box = pursuit_box(env, hl) if box is None else box
    rows = placements if placements is not None else seeds.load_placements()[0]
    if corridor is None and handoff:
        from harness.tetrapush import aim as A       # deferred: `aim` reads `objective` back
        corridor = A.handoff_corridor(env, hl, O.placement_thread(hl, rows), rows=rows)
        if verbose:
            print("  corridor: %s target along %.1f lat %+.2f (escape residual %s)"
                  % ('handoff' if corridor['ok'] else 'COORD (the escape probe did not fire)',
                     corridor['target'][0], corridor['target'][1],
                     'none' if corridor['resid'] is None
                     else '%.1f u' % math.hypot(*corridor['resid'])))
    if nodes is None:
        # the cycle-1 exits are bound-TIED, so the camera target decides cycle 2's squareness: the
        # keep costs ~308 s and is worth corridor offset 37.0 -> 8.97 u (`cycle1_nodes`)
        nodes = cycle1_nodes(env, hl, box, step=c1_step, beam=c1_beam, aim_keep=aim_keep + 1,
                             rank=rank, budget=budget, placements=rows, corridor=corridor,
                             square_keep=c1_square, tcs_keep=(10 ** 6 if c1_square else 3),
                             native=native, verbose=verbose)
    beams = [nodes]
    if verbose and nodes:
        print("  cycle 1: %d nodes, best %.3f u/f, bound %.1f f (%.1f s)"
              % (len(nodes), nodes[0]['m']['per_frame'],
                 O.plan_bound(nodes[0]['frames'], _placement_dist(nodes[0]['run'], rows)),
                 time.perf_counter() - t0))
    for c in range(2, int(ncycles) + 1):
        t1 = time.perf_counter()
        nodes = extend_cycle(nodes, hl, box, jn_keep=jn_keep, jn_beam=jn_beam,
                             ess_step=ess_step, beam=beam, aim_keep=aim_keep,
                             # the LAST cycle hands off to the terminal glide, not to a junction:
                             # no continuability gate, the lateral rank, the glide keep
                             rank=(last_rank if c == int(ncycles) else rank),
                             budget=budget, placements=rows,
                             require_quality=(c < int(ncycles)),
                             glide_keep=(c == int(ncycles) and not last_escape),
                             escape_keep=(c == int(ncycles) and last_escape),
                             corridor_keep=corridor_keep, per_state=per_state,
                             aim_share=aim_share, square_keep=square_keep, corridor=corridor,
                             # the LAST cycle is the one that has to ARRIVE (`roll_probe`'s
                             # ``arrive``): its roll cannot stop short, so overshoot is priced here
                             arrive_keep=(c == int(ncycles) and last_arrive),
                             target_along=(corridor['target'][0]
                                           if (last_arrive and c == int(ncycles)
                                               and corridor is not None) else None),
                             resid=(corridor.get('resid') if corridor is not None else None),
                             # the camera cut: the landing on the last cycle (free), the cheap
                             # squareness probe mid-chain (opt-in, ~2.7 s per surviving pair)
                             tcs_landing=(c == int(ncycles) and last_landing),
                             tcs_square=(c < int(ncycles) and mid_square),
                             # ...and on the LAST cycle the camera's OTHER customer: the escape's snap
                             # window, which nothing paid for before s73 (`camera_probe_key`)
                             tcs_escape=(c == int(ncycles) and last_camera),
                             # the SCREEN (s71-s72) and the ESCAPE's atom knobs (s72), both opt-in
                             land_keep=land_keep, probe_step=probe_step,
                             probe_contact=probe_contact, probe_half=probe_half,
                             escape_flip=escape_flip, escape_rots=escape_rots,
                             escape_rank=escape_rank,
                             env=env, verbose=verbose)
        beams.append(nodes)
        if verbose and nodes:
            n = nodes[0]
            print("  cycle %d: %d nodes, best %.3f u/f, herd %.1f u in %d f, %.1f u from a coord "
                  "(bound %.1f f) (%.1f s)"
                  % (c, len(nodes), n['m']['per_frame'], n['m']['herd'], n['frames'],
                     _placement_dist(n['run'], rows),
                     O.plan_bound(n['frames'], _placement_dist(n['run'], rows)),
                     time.perf_counter() - t1))
        if not nodes:
            break
    return dict(beams=beams, best=(nodes[0] if nodes else None), box=box, corridor=corridor,
                bar=T.human_baseline(env, hl)['per_frame'])


# --------------------------------------------------------------------------- confirm / placement

def confirm_plan(env, hl, node, want_rolls=None):
    """**The winner-confirmation gate, generalized to N rolls** (`two_roll.confirm_chain` is the
    2-roll case): re-run the node's own delivered input log on a FRESH self-contained `FreeRun` and
    require the endpoint to be BIT-IDENTICAL to the search's node -- both actors' positions, Link's
    facing, csangle -- with every grounded A-press talk-safe and the whole log in the plow regime.

    The wall clearance (`objective`, rule 4) is measured here on EVERY frame with the exact metric,
    not the search's cell-bracketed prune: a stage prune only has to filter, but the confirm is what
    says a plan is deliverable, so it reports the binding margin and the frame it occurs on."""
    run = seeds.make_freerun(env)
    dtm = seeds.dtm_input_at(env)
    run.pre_seed_input(dtm(0))
    rolls, in_roll, talk_safe = 0, False, True
    worst_margin, worst_at = float('inf'), None
    for i, d in enumerate(node['log'], 1):
        if S.a_press_is_talk(run, d):
            talk_safe = False
        run.step(d)
        wm = O.wall_margin(run.link.pos_x, run.link.pos_z, run.tx, run.tz)['margin']
        if wm < worst_margin:
            worst_margin, worst_at = wm, i
        if run.link.state == FRONT_ROLL:
            if not in_roll:
                rolls += 1
            in_roll = True
        else:
            in_roll = False
    ref = node['run']
    bit_exact = (run.link.pos_x == ref.link.pos_x and run.link.pos_z == ref.link.pos_z
                 and run.link.facing == ref.link.facing and run.tx == ref.tx
                 and run.tz == ref.tz and int(run.csangle) == int(ref.csangle))
    frames = len(node['log'])
    herd = hl.along(run.tx, run.tz)
    wall_ok = worst_margin > 0.0
    ok = bit_exact and talk_safe and wall_ok and not run._follow_warned
    if want_rolls is not None:
        ok = ok and rolls == int(want_rolls)
    return dict(ok=ok, per_frame=herd / frames if frames else 0.0, frames=frames, rolls=rolls,
                herd=herd, talk_safe=talk_safe, bit_exact=bit_exact, wall_ok=wall_ok,
                wall_margin=worst_margin, wall_margin_at=worst_at)


def placement_report(node, placements=None):
    """How close this plan leaves Tetra to the ENDGAME target set: the nearest genuine
    `tetra_placements` coord and its distance, plus the remaining down-herd distance to the cluster
    centroid. The endgame proper (landing ON a coord with the matching final roll entry) is scored
    from here."""
    if placements is None:
        placements, _ = seeds.load_placements()
    tx, tz = node['run'].tx, node['run'].tz
    best = min(placements, key=lambda p: math.hypot(p['x'] - tx, p['z'] - tz))
    return dict(tetra=(tx, tz), nearest=best,
                dist=math.hypot(best['x'] - tx, best['z'] - tz))


def endgame_report(node, hl, placements=None):
    """**The COUPLED endgame metric** (SESSION_PROMPT milestone 2): the placement objective is not
    just "Tetra near a coord" -- the coord list is valid ONLY for a specific FINAL clip entry
    (`seeds.ENTRY_ROLL_POS/FACING`, the slot-7 turnaround-clip setup). So a plan is scored on BOTH
    halves of the joint target:

      * ``placement`` -- Tetra's distance to the nearest genuine coord (`placement_report`), the
        thing the terminal cycle drives to zero;
      * ``entry_dist`` / ``entry_dfacing`` -- how far Link's endpoint is from the entry the coord
        list assumes (position u + facing BAM). MEASURED, not yet solved: the plow leaves Link ~40-85
        u behind Tetra and near the herd line, while the entry sits up-herd and ~70 u off-line
        (`endgame_geom`), so reaching it is a SEPARATE reposition after the herd -- this quantifies
        that gap for the joint solve."""
    p = placement_report(node, placements)
    lx, lz = node['run'].link.pos_x, node['run'].link.pos_z
    erp = seeds.ENTRY_ROLL_POS
    return dict(placement=p, entry_dist=math.hypot(lx - erp[0], lz - erp[1]),
                entry_dfacing=_s16(node['run'].link.facing - seeds.ENTRY_ROLL_FACING),
                link=(lx, lz, node['run'].link.facing))


def _entry_cost(run):
    """Link's endpoint distance to the final-clip roll entry (`seeds.ENTRY_ROLL_POS`), the position
    the reposition drives to zero. Facing (`ENTRY_ROLL_FACING`) is scored separately -- the clip's
    own turnaround sets it -- so position is the reposition rank."""
    erp = seeds.ENTRY_ROLL_POS
    return math.hypot(run.link.pos_x - erp[0], run.link.pos_z - erp[1])


def _centre_feet(run):
    """Horizontal distance from Link's ANIMATED exec Co-centre (`_computed_center`, the value the
    console push `cc_push_pair` consumes) to Tetra's feet -- the quantity the plow depth is
    `CO_RADII_BAR - this`. It, NOT the feet-to-feet distance, decides whether a step ejects Tetra:
    once it is >= `CO_RADII_BAR` (80 u) the push is zero and she is frozen on her coord. The centre
    leads the feet by a pose-dependent ~17 u, so the feet can be well inside 80 while the centre is
    at the bar."""
    cx = run.co_center()
    return math.hypot(cx[0] - run.tx, cx[-1] - run.tz)


def _link_velocity(run):
    """Link's ground velocity (x, z) in u/frame. speedF integrates the position along the TRAVEL
    angle (`current.angle.y`), not the shape facing -- in the EBS backslide the two differ by
    0x8000, so it is `travel` that gives the direction Link actually moves."""
    th = run.link.travel * (2.0 * math.pi / 65536.0)
    return (run.link.speedF * math.sin(th), run.link.speedF * math.cos(th))


def _approach_rate(run):
    """Link's ground-velocity component TOWARD Tetra's feet (u/frame): +ve = closing (the plow
    re-fires as centre_feet drops below the bar), <= 0 = receding. This is the MOMENTUM half of the
    coupled-entry barrier (session 47): at the SAME `freeze_ok` position a near-rest/receding arrival
    (approach ~ 0) walks clean, but a hot down-herd EBS (approach ~ +25.6) re-plows Tetra tens of u
    before the walk can reverse it. `arrival_quality` gates on it."""
    vx, vz = _link_velocity(run)
    dx, dz = run.tx - run.link.pos_x, run.tz - run.link.pos_z
    d = math.hypot(dx, dz)
    if d < 1e-9:
        return 0.0
    return (vx * dx + vz * dz) / d


def arrival_quality(placed, hl, placements=None, *, band_tol=2.0, approach_tol=3.0):
    """**The CHEAP coupled-arrival gate** (milestone 2b, route a piece 1): does a placement satisfy
    BOTH arrival constraints the grazing chain must hit, so a chain candidate can be REJECTED before
    paying `walk_to_entry` (or the 800 s chain re-run)?

    The two halves (both decomp/live-grounded, sessions 46 + 47):
      * POSITION -- Tetra ON a genuine coord (`placement_dist <= band_tol`) at `freeze_ok`
        (`centre_feet >= CO_RADII_BAR`, so a separating step ejects zero); and
      * MOMENTUM -- Link near-rest / receding up-herd (`approach_rate <= approach_tol`), else the
        hot EBS re-plows her even from a freeze_ok position (the session-47 finding).

    Pure prediction off the placed state (no walk, no rollout), so it is a monotone PREDICTOR the
    exact `walk_to_entry`/`confirm_plan` bit-confirm sits behind (the method reference: cheap
    predictor + exact confirm, no calibration). Returns the measured fields + the `arrival_ok`
    verdict; `approach_tol` is a "few u/f", not a tuned magic constant -- the clean/hostile split is
    0 vs +25.6 u/f, a wide margin either side of it."""
    if placements is None:
        placements, _ = seeds.load_placements()
    run = placed['run']
    pd = _placement_dist(run, placements)
    cf = _centre_feet(run)
    ar = _approach_rate(run)
    freeze_ok = cf >= CO_RADII_BAR
    return dict(placement_dist=pd, centre_feet=cf, co_radii_bar=CO_RADII_BAR,
                deficit=max(0.0, CO_RADII_BAR - cf), freeze_ok=freeze_ok,
                speedF=run.link.speedF, approach_rate=ar, receding=ar <= 0.0,
                arrival_ok=freeze_ok and pd <= band_tol and ar <= approach_tol)


def place_on_thread(arrival, hl, placements=None, *, mags=(0.08, 0.15, 0.25), max_frames=18):
    """**The CLEAN grazing-arrival recipe** (milestone 2b, session 49): freeze Tetra ON the genuine
    thread by placing from an ON-LINE, near-REST arrival.

    Session 49 traced why the current terminal grazing lands 10.85 u off (not on) a coord even though
    it reaches `freeze_ok` + receding: the hot EBS glide (speedF ~ -23) overshoots DOWN-herd THROUGH
    Tetra, so the deep->freeze_ok separation ejects her ~10 u LATERALLY off the ~5e-4 u-thin thread
    (measured: from the on-coord frame NO separation direction -- neutral / up-push / ess -- keeps her
    within pd 9; all reach lat -9..-15 as centre_feet climbs past 80). The lateral drag IS the
    separation of a hot, off-center approach.

    The fix is geometric: if Link sits ON the herd line BEHIND Tetra (lateral-matched to the coord) at
    NEAR-REST, a single gentle down-line crawl-push ejects her ALONG the line -- so she freezes
    on-thread with ~0 lateral drift. Validated here: from a `synthetic_frozen_arrival(momentum='rest',
    lat_off=0)` seeded just below the bar, one msd~0.08-0.25 push down `hl.bearing_bam()` freezes Tetra
    at pd < 1 (lateral drift ~ 0.02 u), `arrival_ok` True. So route (a)'s chain/terminal must deliver
    Link on-line-behind + near-rest before the placing push (a decelerating, lateral-centered approach),
    NOT the sustained EBS glide -- that is the concrete next target.

    Sweeps the gentle push magnitude, keeps the min-pd freeze at `centre_feet >= CO_RADII_BAR`. Returns
    ``dict(run, log, frames, pd, centre_feet, lat_drift, approach, freeze_ok, arrival_ok, msd)``; `log`
    carries the arrival's log + the push (bit-confirmable only when the arrival is chain-reachable --
    a synthetic arrival does not replay, like `walk_to_entry`)."""
    if placements is None:
        placements, _ = seeds.load_placements()
    r0 = arrival['run']
    lat0 = hl.lateral(r0.tx, r0.tz)
    down = hl.bearing_bam()
    best = None
    for msd in mags:
        r = r0.clone()
        inputs = []
        for _f in range(int(max_frames)):
            sx, sy = stick_for_bearing(down, int(r.csangle), msd=msd)
            d = dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                     substickX=T.CSTICK_NEUTRAL, substickY=0)
            r.step(d)
            inputs.append(d)
            if r._follow_warned:
                break
            if _centre_feet(r) < CO_RADII_BAR:
                continue
            pd = _placement_dist(r, placements)
            cand = dict(run=r.clone(), inputs=list(inputs), pd=pd, msd=msd,
                        centre_feet=_centre_feet(r), lat_drift=hl.lateral(r.tx, r.tz) - lat0,
                        approach=_approach_rate(r))
            if best is None or pd < best['pd']:
                best = cand
            break                                          # first freeze on this glide is the graze
    if best is None:                                       # never froze (stayed deep or followed)
        best = dict(run=r0, inputs=[], pd=_placement_dist(r0, placements), msd=None,
                    centre_feet=_centre_feet(r0), lat_drift=0.0, approach=_approach_rate(r0))
    freeze_ok = best['centre_feet'] >= CO_RADII_BAR
    return dict(run=best['run'], log=list(arrival.get('log', [])) + best['inputs'],
                frames=arrival.get('frames', 0) + len(best['inputs']),
                pd=best['pd'], centre_feet=best['centre_feet'], lat_drift=best['lat_drift'],
                approach=best['approach'], msd=best['msd'], freeze_ok=freeze_ok,
                arrival_ok=freeze_ok and best['pd'] <= 2.0 and best['approach'] <= 3.0)


def separation_scan(placed, hl, placements=None, *, n_dirs=48):
    """**The coupled-entry BARRIER, quantified against the decomp bar** (milestone 2b): from a state
    where Tetra sits ON a genuine coord, report whether Link can leave for the entry without ejecting
    her, and -- when he cannot -- BY HOW MUCH the placement is too deep.

    The pivot (session 46): the plow depth is `CO_RADII_BAR - centre_feet` (`_centre_feet` = the exec
    Co-centre to Tetra), so a separating step ejects ZERO -- Tetra is FROZEN -- exactly when the
    placement's centre_feet >= `CO_RADII_BAR` (80 u, decomp-exact). `terminal_targeting` lands Tetra
    on a coord only at DEEP contact (centre_feet ~= 64.6 u, ~15 u below the bar), because the genuine
    coords form a THIN thread (session 26: ~46 u long, ~5e-4 u perpendicular) the plow can only reach
    by pushing INTO it; there every separation step ejects her off the thread. So the fix is a
    GRAZING arrival -- the chain/terminal ranked to reach the band with the placing push the LAST
    light touch, `centre_feet` up at the bar. Above the bar the coupling is BROKEN and 2b reduces to
    a Link-ONLY navigation to the entry (Tetra frozen); see `entry_targeting`.

    Returns the scan summary + the measured bar fields (`centre_feet`, `co_radii_bar`, `deficit`,
    `freeze_ok`); pure prediction, no state kept. `clean_separation` is retained (the strict
    one-step form); `freeze_ok` (`centre_feet >= bar`) is the actionable grazing target."""
    if placements is None:
        placements, _ = seeds.load_placements()

    def pdist(run):
        return min(math.hypot(p['x'] - run.tx, p['z'] - run.tz) for p in placements)

    r0 = placed['run']
    dist0 = math.hypot(r0.link.pos_x - r0.tx, r0.link.pos_z - r0.tz)
    cf0 = _centre_feet(r0)
    rows = []
    for (sx, sy) in _terminal_alphabet(r0, hl, n_dirs=n_dirs):
        for l in (0, 1):
            r = r0.clone()
            r.step(dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                        triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL, substickY=0))
            if r._follow_warned:
                continue
            rows.append((pdist(r), math.hypot(r.link.pos_x - r.tx, r.link.pos_z - r.tz),
                         _entry_cost(r)))
    rows.sort()
    best_pd = rows[0][0] if rows else None
    clean = [x for x in rows if x[0] <= 2.0 and x[1] > 80.0 and x[2] < _entry_cost(r0)]
    return dict(start_dist=dist0, start_entry=_entry_cost(r0), start_placement=pdist(r0),
                best_step_placement=best_pd, clean_separation=bool(clean),
                centre_feet=cf0, co_radii_bar=CO_RADII_BAR,
                deficit=max(0.0, CO_RADII_BAR - cf0), freeze_ok=cf0 >= CO_RADII_BAR,
                n_steps=len(rows))


def entry_targeting(placed, hl, placements=None, *, max_frames=40, beam=48, n_dirs=24,
                    band_tol=6.0, verbose=False):
    """**The coupled-entry reposition beam** (milestone 2b machinery): from a placement state, steer
    LINK back to the final-clip entry (`seeds.ENTRY_ROLL_POS`, ~174 u up-herd + 73 u lateral of the
    coord band) while Tetra stays ON a coord. Per-frame beam (atom = one `_terminal_alphabet`
    (stick, L)), pruned by the plow regime (`_follow_warned`: dist < 230 so Tetra will not FOLLOW)
    and the genuine band (`placement_dist <= band_tol`, which also holds her still -- once Link
    separates past dist 80, `cc_push_pair` ejects zero), ranked by `_entry_cost`, tracking the
    global closest-to-entry in-band state. Any survivor carries its FULL log, so `confirm_plan`
    replays the WHOLE state-2 -> placement -> reposition sequence 0-ULP.

    NOTE (`separation_scan`, session 46): from a DEEP-contact placement (`centre_feet` < the 80 u
    bar, the current terminal's output) this beam is BLOCKED at frame 0-1 -- separating ejects Tetra
    off the thin genuine thread. Above the bar (`freeze_ok`) Tetra is FROZEN and the coupling is
    broken, but this beam still STALLS there: its `_terminal_alphabet` is a down-herd PUSH fan, and
    Link leaves the placement in a hot EBS backslide (speedF ~-23) whose momentum carries him AWAY
    from the up-herd entry faster than a push-bearing stick can turn him (measured: greedy nav grows
    the entry gap). Above the bar 2b is a Link-ONLY navigation problem -- kill the backslide, walk to
    the entry, Tetra untouched -- so the correct tool is a WALK/EBS planner (`plan_land`), not this
    push fan. This beam remains the in-band GUARD (it proves Tetra holds); the navigation is the open
    milestone-2b piece once the chain arrives grazing (route a)."""
    if placements is None:
        placements, _ = seeds.load_placements()

    def pdist(run):
        return min(math.hypot(p['x'] - run.tx, p['z'] - run.tz) for p in placements)

    best = dict(run=placed['run'], log=placed['log'], frames=placed['frames'],
                cost=_entry_cost(placed['run']), pd=pdist(placed['run']),
                plan=placed.get('plan', []))
    live = [dict(run=placed['run'], log=placed['log'], frames=placed['frames'])]
    for _f in range(int(max_frames)):
        nxt, seen = [], set()
        for nd in live:
            for (sx, sy) in _terminal_alphabet(nd['run'], hl, n_dirs=n_dirs):
                for l in (0, 1):
                    r = nd['run'].clone()
                    d = dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                             triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL, substickY=0)
                    r.step(d)
                    if r._follow_warned:                       # dist > 230: Tetra would FOLLOW
                        continue
                    pd = pdist(r)
                    if pd > band_tol:                          # Tetra left the genuine band
                        continue
                    tag = (round(r.link.pos_x, 1), round(r.link.pos_z, 1),
                           r.link.facing >> 5, round(r.link.speedF, 2))
                    if tag in seen:
                        continue
                    seen.add(tag)
                    cost = _entry_cost(r)
                    cand = dict(run=r, log=nd['log'] + [d], frames=nd['frames'] + 1, cost=cost, pd=pd)
                    nxt.append(cand)
                    if cost < best['cost']:
                        best = dict(cand, plan=placed.get('plan', []))
        nxt.sort(key=lambda c: c['cost'])
        live = nxt[:int(beam)]
        if verbose:
            print("    f%2d: %3d live, best entry %.1f u (Tetra %.2f u from coord)"
                  % (_f, len(live), best['cost'], best['pd']))
        if not live:
            break
    return dict(best=best, dist=best['cost'], placement=best['pd'],
                entry_dfacing=_s16(best['run'].link.facing - seeds.ENTRY_ROLL_FACING))


def _neutral_input():
    return dict(stickX=128, stickY=128, buttons=0, triggerL=0,
                substickX=T.CSTICK_NEUTRAL, substickY=0)


def _at_rest(run):
    return run.link.state in (WAIT, FREE_WAIT) and abs(run.link.speedF) < 1e-6


_WALK_MAX_NSPEED = 17.0                                   # LandState.MAX_NSPEED (the walk speed cap)


def _glide_to_entry(run0, ex, ez, t0, k, min_crawl, max_walk, coast_max):
    """One proportional-speed glide toward the entry at controller gain ``k`` (the `reach_precise`
    inner loop, on the coupled run). Returns ``(best, max_td)`` where `best` is the min-resting-gap
    release (``dict(gap, n_walk, coast, run, inputs)``) or None, and `max_td` is Tetra's worst
    displacement seen (walk + every coast probe)."""
    def tdisp(run):
        return math.hypot(run.tx - t0[0], run.tz - t0[1])

    def entry_gap(run):
        return math.hypot(run.link.pos_x - ex, run.link.pos_z - ez)

    walk = run0.clone()
    walk_inputs = []
    max_td = tdisp(walk)
    best = None
    for n in range(1, int(max_walk) + 1):
        rem = entry_gap(walk)
        target_speed = min(max(k * rem, min_crawl), _WALK_MAX_NSPEED)
        # floor 0.051 sustains a sub-unit crawl (reach_precise): the first frame's remaining is large
        # so msd == 1.0 and the walk STARTS from rest fine; once moving, a low msd is sustainable.
        msd = min(max(math.sqrt(target_speed / _WALK_MAX_NSPEED), 0.051), 1.0)
        th = world_angle_s16(ex - walk.link.pos_x, ez - walk.link.pos_z)
        sx, sy = stick_for_bearing(th, walk.csangle, msd)
        d = dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                 substickX=T.CSTICK_NEUTRAL, substickY=0)
        walk.step(d)
        walk_inputs.append(d)
        max_td = max(max_td, tdisp(walk))
        if walk._follow_warned:                         # the walk itself left the plow regime
            break
        coast = walk.clone()
        cn, broke = 0, False
        for _ in range(int(coast_max)):
            coast.step(_neutral_input())
            cn += 1
            max_td = max(max_td, tdisp(coast))
            if coast._follow_warned:                    # coasting overshot the follow shell
                broke = True
                break
            if _at_rest(coast):
                break
        g = entry_gap(coast)
        if not broke and (best is None or g < best['gap']):
            best = dict(gap=g, n_walk=n, coast=cn, run=coast, inputs=list(walk_inputs))
        # stop once the crawl has clearly passed closest approach (the controller then orbits it)
        elif best is not None and n > best['n_walk'] + 12 and entry_gap(walk) > best['gap'] + 3.0:
            break
    return best, max_td


_WALK_GAINS = (0.5, 0.3, 0.2)                             # the proportional-glide gain sweep


def walk_to_entry(placed, hl, placements=None, *, max_walk=200, coast_max=40, gains=_WALK_GAINS,
                  min_crawl=0.043):
    """**Milestone-2b piece 2: the Link-ONLY WALK to the final-clip entry** (`seeds.ENTRY_ROLL_POS`),
    ABOVE the clean-separation bar where Tetra is frozen (session 47). This is the tool the s46
    reframe called for: above the bar the coupling is broken, so reaching the entry is standard land
    navigation, NOT the push fan that `entry_targeting` stalls on.

    Structure -- `reach_precise` on the coupled run: aim the live world-bearing to the entry each
    frame, scaling the walk deflection so the target speed tracks ``k * remaining`` (Link glides into
    a ~`min_crawl` u/frame crawl instead of overshooting the ~17 u full-deflection granularity), and
    per-frame clone + neutral-coast to the min RESTING entry gap (bit-exact mid-walk clone makes the
    O(n) release sweep identical to per-release re-simulation). The 2-frame input latency makes the
    approach overshoot at a gain-dependent speed, so the controller gain is SWEPT over `gains` and the
    best clean release kept (a search over the gain, not a per-case tuned constant). It runs on the
    `FreeRun` so the push coupling stays HONEST -- Tetra's displacement is MEASURED, not assumed zero
    -- and the plan bit-confirms via `confirm_plan`; every candidate is pruned by the FOLLOW regime
    (dist < 230, `_follow_warned`), so the walk never carries Link past the follow shell.

    THE MOMENTUM CAVEAT (the session-47 finding, why `freeze_ok` alone is not enough): the s46 bar is
    POSITIONAL and necessary but NOT sufficient. A hot down-herd EBS arrival (speedF ~ -25.7 pointing
    at Tetra) re-plows her 44-67 u before the walk can reverse it -- the ~5 frames it takes to bleed
    the momentum off drift Link back below the bar. Turning around first does not rescue it (the snap
    preserves the -25.7, still ~44 u of plow). So a CLEAN walk needs the grazing chain (route a,
    piece 1) to deliver Link NEAR-REST or already receding up-herd, not just at `centre_feet >= 80`.
    This planner REPORTS `max_tetra_disp` (Tetra's worst displacement over the whole walk+coast) and
    `clean` (< 1 u) so a hot arrival is flagged, never silently plowed.

    Returns ``dict(best, dist, run, log, frames, max_tetra_disp, clean, followed, entry_dfacing)`` --
    `log`/`frames` carry the FULL state-2 -> placement -> walk sequence for `confirm_plan` (only when
    the placement itself is chain-reachable; a synthetic placement does not replay). `entry_dfacing`
    is scored but not optimised -- the clip's own turnaround sets the entry facing (`_entry_cost`)."""
    ex, ez = seeds.ENTRY_ROLL_POS
    if placements is None:
        placements, _ = seeds.load_placements()
    run0 = placed['run']
    t0 = (run0.tx, run0.tz)
    best, max_td = None, math.hypot(run0.tx - t0[0], run0.tz - t0[1])
    for k in gains:
        b, td = _glide_to_entry(run0, ex, ez, t0, k, min_crawl, max_walk, coast_max)
        max_td = max(max_td, td)                          # every gain's plow counts toward the flag
        if b is not None and (best is None or b['gap'] < best['gap']):
            best = b
    if best is None:
        best = dict(gap=math.hypot(run0.link.pos_x - ex, run0.link.pos_z - ez),
                    n_walk=0, coast=0, run=run0, inputs=[])
    plan_log = (list(placed.get('log', [])) + best['inputs'][:best['n_walk']]
                + [_neutral_input()] * best['coast'])
    return dict(best=best, dist=best['gap'], run=best['run'], log=plan_log,
                frames=placed.get('frames', 0) + best['n_walk'] + best['coast'],
                max_tetra_disp=max_td, clean=max_td < 1.0,
                followed=best['run']._follow_warned,
                entry_dfacing=_s16(best['run'].link.facing - seeds.ENTRY_ROLL_FACING))


def _steer_down_line(run, hl, msd):
    """One frame's stick pointing DOWN the exact herd line (`hl.bearing_bam`) at deflection ``msd``,
    placed at the run's live csangle (state-relative, not a byte constant). In the untarget EBS this
    input REVERSES Link (a controlled brake up-herd, `decel_probe`), and its push stays ON the line --
    the `place_on_thread` steering, reused for the decel brake."""
    sx, sy = stick_for_bearing(hl.bearing_bam(), int(run.csangle), msd=msd)
    return dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                substickX=T.CSTICK_NEUTRAL, substickY=0)


def _reverse_brake(run, hl, *, msd=0.06, max_frames=16, rest_tol=0.5):
    """Kill the hot post-chain EBS by steering DOWN the herd line at a low deflection: in the untarget
    backslide this reverses Link (an on-line brake), so he coasts to near-rest UP-herd while the plow
    stays on the line -- Tetra freezes with ~0 lateral drift (measured: tlat -1.3 u vs a neutral
    brake's -6 u, session 50). This is the "kill the EBS" half the s49 handoff called for -- separate
    the momentum off FAR from the coord (Tetra frozen once centre_feet passes the bar), NOT at deep
    contact where a hot pass drags her laterally. Returns ``(run, inputs)`` (run stepped in place)."""
    inputs = []
    for _ in range(int(max_frames)):
        d = _steer_down_line(run, hl, msd)
        run.step(d)
        inputs.append(d)
        if run._follow_warned or abs(run.link.speedF) < rest_tol:
            break
    return run, inputs


_DECEL_BACKS = tuple(float(x) for x in range(40, 82, 2))   # on-line target sweep (Link feet behind coord)


def decel_place(placed, hl, placements=None, coord_idx=None, *, brake_msd=0.06,
                gains=_WALK_GAINS, backs=_DECEL_BACKS, min_crawl=0.043, max_walk=200,
                coast_max=40, brake_frames=16):
    """**Route (a), piece 1: the DECELERATING on-line placement approach** (session 50) -- the terminal
    that BEATS the s49 grazing barrier by inverting its failure mode.

    Session 49 proved the hot -23 EBS glide places Tetra on a coord only at DEEP contact, then drags
    her ~10 u LATERALLY off the thin thread as it separates to freeze_ok (the miss is lateral). This
    maneuver instead arrives NEAR-REST and ON-LINE, so the miss becomes a clean 1-D ALONG-line tune
    with ZERO lateral drift (measured: lat_drift +0.000, pd < 0.13 u, arrival_ok across d_short
    30/40/55). Two phases, both reusing existing machinery:

      1. **Kill the EBS** (`_reverse_brake`): steer down the herd line at a low deflection, which
         reverses the hot backslide -- Link coasts to near-rest UP-herd while the plow stays on the
         line, so Tetra freezes with ~0 lateral drift (the separation happens far from the coord, not
         at deep contact). This is the s49 "decelerate, do not sustain the EBS" step.
      2. **On-line forward glide** (`_glide_to_entry`, the `walk_to_entry` reach_precise machinery):
         from the braked rest, proportional-speed-glide FORWARD to an on-line point ``back`` u behind
         the coord, coasting to a crawl. Because the approach is on-line and metered, the plow herds
         Tetra straight DOWN the thread (lat_drift ~0) onto the coord; ``back`` and the controller
         gain are SWEPT (not tuned) and the best `arrival_ok`/min-pd release kept. `place_on_thread`
         finishes (a no-op when the glide already froze her on-coord).

    This herds Tetra straight down the line and so needs her ALREADY on the thread laterally; when the
    chain leaves her off-thread (the s44 lateral OFFSET), use `homing_place` (session 51), which aims
    Link at a moving standoff behind Tetra RELATIVE to the coord so the plow corrects along + lateral
    together. Returns
    ``dict(run, log, frames, pd, centre_feet, lat_drift, approach, arrival_ok, back, gain,
    brake_frames, coord_idx)``; `log`/`frames` carry the FULL placed -> brake -> glide -> place
    sequence, so `confirm_plan` replays it 0-ULP once the placement is chain-reachable (a synthetic
    arrival does not replay, like `walk_to_entry`/`place_on_thread`)."""
    if placements is None:
        placements, _ = seeds.load_placements()
    # 1) kill the EBS
    br = placed['run'].clone()
    br, br_inputs = _reverse_brake(br, hl, msd=brake_msd, max_frames=brake_frames)
    # target coord: the given one, else the nearest to Tetra now
    if coord_idx is None:
        coord_idx = min(range(len(placements)),
                        key=lambda i: math.hypot(placements[i]['x'] - br.tx,
                                                 placements[i]['z'] - br.tz))
    cp = placements[coord_idx]
    t0 = (br.tx, br.tz)
    best = None
    for back in backs:
        ax = cp['x'] - back * hl.dx
        az = cp['z'] - back * hl.dz
        for k in gains:
            b, _td = _glide_to_entry(br.clone(), ax, az, t0, k, min_crawl, max_walk, coast_max)
            if b is None:
                continue
            glide_log = b['inputs'][:b['n_walk']] + [_neutral_input()] * b['coast']
            res = place_on_thread(dict(run=b['run'].clone(), log=[], frames=0), hl, placements)
            cand = dict(run=res['run'], glide_log=glide_log, place_log=res['log'],
                        pd=res['pd'], centre_feet=res['centre_feet'], lat_drift=res['lat_drift'],
                        approach=res['approach'], arrival_ok=res['arrival_ok'],
                        back=back, gain=k)
            # prefer arrival_ok, then min pd (the along-line residual)
            key = (not cand['arrival_ok'], cand['pd'])
            if best is None or key < (not best['arrival_ok'], best['pd']):
                best = cand
    if best is None:                                        # brake never produced a glide (degenerate)
        pd = _placement_dist(br, placements)
        return dict(run=br, log=list(placed.get('log', [])) + br_inputs,
                    frames=placed.get('frames', 0) + len(br_inputs), pd=pd,
                    centre_feet=_centre_feet(br), lat_drift=0.0, approach=_approach_rate(br),
                    arrival_ok=False, back=None, gain=None, brake_frames=len(br_inputs),
                    coord_idx=coord_idx)
    log = (list(placed.get('log', [])) + br_inputs + best['glide_log'] + best['place_log'])
    frames = placed.get('frames', 0) + len(br_inputs) + len(best['glide_log']) + len(best['place_log'])
    return dict(run=best['run'], log=log, frames=frames, pd=best['pd'],
                centre_feet=best['centre_feet'], lat_drift=best['lat_drift'],
                approach=best['approach'], arrival_ok=best['arrival_ok'], back=best['back'],
                gain=best['gain'], brake_frames=len(br_inputs), coord_idx=coord_idx)


_HOMING_STANDOFFS = tuple(float(x) for x in range(38, 74, 4))   # Link's standoff behind Tetra (rel. coord)
_HOMING_GAINS = (0.5, 0.35, 0.25, 0.15)                         # the proportional-crawl gain sweep


def _homing_glide(run0, cp, hl, placements, standoff, k, *, min_crawl, max_walk, coast_max):
    """One proportional-speed HOMING glide toward a moving standoff point ``standoff`` u behind Tetra
    on the far side from the target coord ``cp`` -- so the plow ejects Tetra TOWARD the coord (along +
    lateral together). Each frame re-aims at ``Tetra + standoff * unit(Tetra - coord)`` and, like
    `_glide_to_entry`, clones + neutral-coasts to REST to read the clean frozen placement at that
    release (bit-exact mid-walk clone makes the O(n) release sweep equal to per-release re-simulation).
    Returns the best ``dict(pd, centre_feet, run, inputs, n_walk, coast)`` (prefer frozen, then min-pd)
    or None. The coast is what freezes Tetra (`centre_feet >= CO_RADII_BAR` once Link separates)."""
    def pdist(run):
        return min(math.hypot(p['x'] - run.tx, p['z'] - run.tz) for p in placements)

    walk = run0.clone()
    walk_inputs = []
    best = None
    for n in range(1, int(max_walk) + 1):
        vx, vz = walk.tx - cp['x'], walk.tz - cp['z']       # coord -> Tetra
        vn = math.hypot(vx, vz)
        ux, uz = (hl.dx, hl.dz) if vn < 1e-6 else (vx / vn, vz / vn)
        ax, az = walk.tx + standoff * ux, walk.tz + standoff * uz
        rem = math.hypot(ax - walk.link.pos_x, az - walk.link.pos_z)
        target_speed = min(max(k * rem, min_crawl), _WALK_MAX_NSPEED)
        msd = min(max(math.sqrt(target_speed / _WALK_MAX_NSPEED), 0.051), 1.0)
        th = world_angle_s16(ax - walk.link.pos_x, az - walk.link.pos_z)
        sx, sy = stick_for_bearing(th, walk.csangle, msd)
        d = dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                 substickX=T.CSTICK_NEUTRAL, substickY=0)
        walk.step(d)
        walk_inputs.append(d)
        if walk._follow_warned:                             # left the plow regime
            break
        coast = walk.clone()
        cn, broke = 0, False
        for _ in range(int(coast_max)):
            coast.step(_neutral_input())
            cn += 1
            if coast._follow_warned:
                broke = True
                break
            if _at_rest(coast):
                break
        if broke:
            continue
        cf = _centre_feet(coast)
        cand = (0 if cf >= CO_RADII_BAR else 1, pdist(coast))
        if best is None or cand < best['key']:
            best = dict(key=cand, pd=cand[1], centre_feet=cf, run=coast,
                        inputs=list(walk_inputs), n_walk=n, coast=cn)
    return best


def homing_place(placed, hl, placements=None, coord_idx=None, *, brake_msd=0.06,
                 gains=_HOMING_GAINS, standoffs=_HOMING_STANDOFFS, min_crawl=0.043,
                 max_walk=240, coast_max=40, brake_frames=16):
    """**Route (a), piece 1: the HOMING placement terminal** (session 51) -- the terminal that closes
    2b for an OFF-THREAD arrival, correcting the s44 lateral OFFSET the decelerating on-line
    `decel_place` (s50) cannot.

    `decel_place` proved the DECELERATE-then-glide recipe lands Tetra on a coord with ZERO lateral
    DRAG (inverting the s49 hot-glide drag), but it herds her straight DOWN the line, so it needs her
    already on the thread laterally. Run on the real 3-cycle chain endpoint (s50) it stalled at pd ~41
    because the chain leaves Tetra ~28 u OFF the thread laterally and the on-line herd cannot pull her
    onto it from behind. This terminal fixes exactly that: after the same reverse-brake, its glide
    AIMS Link each frame at a moving standoff point BEHIND Tetra RELATIVE TO THE TARGET COORD
    (`Tetra + standoff * unit(Tetra - coord)`), so the plow -- which ejects Tetra away from Link's
    exec centre -- pushes her TOWARD the coord in BOTH along and lateral, converging as she nears it.

    Two phases: (1) `_reverse_brake` kills the hot EBS on-line (as in `decel_place`); (2) the homing
    glide (`_homing_glide`) chases the moving standoff to a metered crawl, coast-probing to REST each
    frame for the clean frozen placement, sweeping ``standoff`` + gain and keeping the best frozen
    min-pd release. Measured on `synthetic_hot_arrival(lat_off=+-28..40)`: Tetra pd < 0.1 u ON a
    genuine coord, `centre_feet >= 80` (freeze_ok), lateral offset nulled (|lat| < 3) -- so it closes
    the arrival for the off-thread chain endpoint, the deliverable `walk_to_entry` then consumes.

    Returns ``dict(run, log, frames, pd, centre_feet, lat_drift, approach, arrival_ok, standoff, gain,
    brake_frames, coord_idx)``; `log`/`frames` carry the FULL placed -> brake -> homing sequence, so
    `confirm_plan` replays it 0-ULP once the placement is chain-reachable (a synthetic arrival does not
    replay, like `decel_place`/`walk_to_entry`). ``lat_drift`` is Tetra's net lateral move over the
    homing (intentionally large here -- the correction -- unlike `decel_place`'s ~0)."""
    if placements is None:
        placements, _ = seeds.load_placements()
    br = placed['run'].clone()
    br, br_inputs = _reverse_brake(br, hl, msd=brake_msd, max_frames=brake_frames)
    if coord_idx is None:
        coord_idx = min(range(len(placements)),
                        key=lambda i: math.hypot(placements[i]['x'] - br.tx,
                                                 placements[i]['z'] - br.tz))
    cp = placements[coord_idx]
    lat0 = hl.lateral(br.tx, br.tz)
    best = None
    for standoff in standoffs:
        for k in gains:
            b = _homing_glide(br.clone(), cp, hl, placements, standoff, k,
                              min_crawl=min_crawl, max_walk=max_walk, coast_max=coast_max)
            if b is None:
                continue
            if best is None or b['key'] < best['key'] or (b['key'] == best['key']
                                                          and b['n_walk'] < best['n_walk']):
                best = dict(b, standoff=standoff, gain=k)
    if best is None:                                        # brake never produced a homing glide
        pd = _placement_dist(br, placements)
        return dict(run=br, log=list(placed.get('log', [])) + br_inputs,
                    frames=placed.get('frames', 0) + len(br_inputs), pd=pd,
                    centre_feet=_centre_feet(br), lat_drift=0.0, approach=_approach_rate(br),
                    arrival_ok=False, standoff=None, gain=None, brake_frames=len(br_inputs),
                    coord_idx=coord_idx)
    run = best['run']
    glide_log = best['inputs'][:best['n_walk']] + [_neutral_input()] * best['coast']
    log = list(placed.get('log', [])) + br_inputs + glide_log
    frames = placed.get('frames', 0) + len(br_inputs) + len(glide_log)
    cf = best['centre_feet']
    approach = _approach_rate(run)
    return dict(run=run, log=log, frames=frames, pd=best['pd'], centre_feet=cf,
                lat_drift=hl.lateral(run.tx, run.tz) - lat0, approach=approach,
                arrival_ok=(cf >= CO_RADII_BAR and best['pd'] <= 2.0 and approach <= 3.0),
                standoff=best['standoff'], gain=best['gain'], brake_frames=len(br_inputs),
                coord_idx=coord_idx)


def synthetic_hot_arrival(env, hl, coord_idx=241, *, d_short=40.0, feet=64.0, lat_off=0.0,
                          snap_camera=False):
    """**A SYNTHETIC below-the-bar HOT pre-placement, the state the grazing chain terminal produces**
    (session 50): Link in the hot post-untarget EBS, ``feet`` u BEHIND Tetra along the herd line, with
    Tetra ``d_short`` u UP-herd (short) of genuine coord ``coord_idx`` -- the deep-contact, closing
    arrival whose hot glide s49 showed drags Tetra laterally. It is the testbed `decel_place` must
    beat, the hot counterpart of `synthetic_frozen_arrival` (which mints the ABOVE-the-bar frozen
    arrival for the walk).

    ``lat_off`` (session 51) shifts BOTH actors ``lat_off`` u off the thread laterally (Tetra
    off-thread, Link still on-line-behind HER) -- the s44 lateral OFFSET the REAL 3-cycle chain
    endpoint carries (~28 u; endpoint pd 74.7 = hypot(69 along, 28 lat)). With ``lat_off=0`` this is
    the s50 on-line testbed; with ``lat_off != 0`` it is the real-chain testbed the lateral-bias
    `decel_place` must correct (approach from the HIGH-lateral side so the plow pulls Tetra onto the
    thread). Relocation only (position does not feed anim/momentum), so it is self-consistent but NOT
    reachable by a state-2 input log -- it gates the decel recipe's physics/regime, not a bit-confirm.

    ``snap_camera`` (session 73) fabricates the one thing this bed was silently missing: the CAMERA a
    real arrival brings. The escape atom's turnaround needs the csangle inside its snap window and the
    last roll's ``target_cs`` is what delivers it (`camera_probe_key`); a relocated bed has no roll, so
    its inherited csangle sits ~25 deg outside the window and NOTHING fires there -- measured, 0 of 2048
    swept variants. With it True the bed carries the paid camera (`away_walk.snap_csangle`) and the atom
    runs at bill 0, which is what an escape test wants. Default False so every existing walk/place bed
    is byte-unchanged (those recipes never run the atom).
    Returns a ``placed`` node (``dict(run, log=[], frames=0))``."""
    from harness.tetrapush.reposition import seed_to_untarget
    placements, _ = seeds.load_placements()
    p = placements[coord_idx]
    tx = float(p['x']) - d_short * hl.dx + lat_off * hl.px
    tz = float(p['z']) - d_short * hl.dz + lat_off * hl.pz
    run, _aim = seed_to_untarget(env)                       # the hot post-untarget EBS
    run.place_link(tx - feet * hl.dx, tz - feet * hl.dz, tetra=(tx, tz))
    run._follow_warned = False
    if snap_camera:
        # the camera a real arrival's last roll would have delivered -- see the docstring
        from harness.tetrapush import away_walk as AW
        cs = AW.snap_csangle(run)
        if cs is not None:
            run.camera = None
            run.csangle = int(cs)
    return dict(run=run, log=[], frames=0, plan=[])


def synthetic_frozen_arrival(env, hl, coord_idx=241, *, target_cf=88.0, lat_off=0.0,
                             momentum='rest'):
    """**A SYNTHETIC above-the-bar frozen placement, for developing/gating the 2b walk BEFORE the
    grazing chain (route a, piece 1) can mint a real one** (session 47). Seeds a real Courtyard Link
    state (`reposition.seed_to_untarget`); for ``momentum='rest'`` it parks Tetra out of range and
    coasts Link to a genuine WAIT rest (the clean route-(a) arrival), for ``momentum='ebs'`` it keeps
    the hot post-untarget EBS backslide (the hostile arrival); then it relocates Tetra onto genuine
    coord `coord_idx` and Link `target_cf`-worth of centre_feet UP-HERD (behind) her (``lat_off`` u
    lateral), recomputing the pending push from the moved pose exactly as `step` does. Position does
    not feed anim/momentum, so the state stays self-consistent, and `centre_feet >= CO_RADII_BAR`
    freezes Tetra.

    NOT reachable from state 2 by an input log (fabricated by relocation), so its plan does NOT
    bit-confirm -- it exercises the walk's REGIME/FREEZE properties, not the state-2 replay. The
    `momentum` knob is the session-47 finding's lever: 'rest' -> the walk keeps Tetra frozen; 'ebs'
    -> the walk re-plows her (freeze_ok is positional, momentum is the other half). Returns a
    ``placed`` node (``dict(run, log=[], frames=0, plan=[])``)."""
    from harness.tetrapush.reposition import seed_to_untarget
    import tww_sim.core.fp as fp
    placements, _ = seeds.load_placements()
    p = placements[coord_idx]
    tx, tz = float(p['x']), float(p['z'])
    run, _aim = seed_to_untarget(env)
    if momentum == 'rest':
        run.tx, run.tz = fp.f32(9000.0), fp.f32(9000.0)     # park out of range -> no plow
        for _ in range(48):
            run.step(_neutral_input())
            if _at_rest(run):
                break
    elif momentum != 'ebs':
        raise ValueError("momentum must be 'rest' or 'ebs'")

    def place(feet):
        run.place_link(tx - feet * hl.dx + lat_off * hl.px,
                       tz - feet * hl.dz + lat_off * hl.pz, tetra=(tx, tz))

    lo, hi = 60.0, 150.0                                 # centre_feet is monotone in feet
    for _ in range(44):
        mid = 0.5 * (lo + hi)
        place(mid)
        if _centre_feet(run) < target_cf:
            lo = mid
        else:
            hi = mid
    place(0.5 * (lo + hi))
    run._follow_warned = False
    return dict(run=run, log=[], frames=0, plan=[])


def _placement_dist(run, placements):
    """Tetra's distance to the nearest genuine coord, from a live run."""
    tx, tz = run.tx, run.tz
    return min(math.hypot(p['x'] - tx, p['z'] - tz) for p in placements)


def _terminal_alphabet(run, hl, *, n_dirs=24, mags=(0.08, 0.2, 0.35, 0.5, 0.7, 1.0)):
    """**The terminal glide's push-direction alphabet** -- a full-circle fan of Link push bearings at
    SEVERAL magnitudes. Unlike the junction alphabet (low-mag ESS to preserve the -25.7 backslide,
    plus a full-mag aim fan), the terminal needs FINE control of the plow push at MID magnitudes:
    the deepest coord approach comes from moderate down-herd sticks that neither the ESS fan
    (msd <= 0.10) nor the aim fan (msd 1.0) contains. Measured (`_terminal_alphabet` vs the junction
    alphabet on the 3-cycle endpoint): the mid-mags take the terminal from 10.4 u to **2.0 u** of a
    genuine coord -- Tetra INTO the band (along 956, lat 4). Each bearing is placed at the run's live
    csangle via `stick_for_bearing`, so the fan is state-relative, not a byte constant."""
    cs = int(run.csangle)
    hb = hl.bearing_bam()
    step = 0x10000 // int(n_dirs)
    out = {stick_for_bearing((hb + (i - int(n_dirs) // 2) * step) & 0xFFFF, cs, msd=m)
           for i in range(int(n_dirs)) for m in mags}
    out.add(ESS_DOWN)
    return list(out)


def _terminal_ready(run):
    """Rule 3's CHEAP half off a live run (`objective.terminal_moving`): is Link still MOVING at
    this frame? The EXACT rule 3 is the escape atom (`objective.escape_ready` -- a rollout, run on
    winners and on `terminal_targeting`'s placement candidates, never per beam frame)."""
    return O.terminal_moving(run.link.speedF)


def lateral_authority(run, hl, *, frames=6, n_dirs=24):
    """**MEASURE what a unit of lateral costs** -- the number behind `objective.LATERAL_RATE`, and
    the reason the last cycle gets a rank of its own (session 62).

    `objective.plan_bound` divides the straight distance to a coord by `PUSH_CEILING`, which prices a
    unit of lateral exactly like a unit of along. Whether that is wrong, and by how much, is a
    measurement: hold each stick of the terminal glide's own alphabet for ``frames`` frames and read
    the SPREAD of Tetra laterals it reaches. That spread over the frames is the plan's lateral
    authority -- how far apart two plans' lateral outcomes can be per frame of glide -- against
    `PUSH_CEILING` for the along axis.

    Held sticks, not a beam, deliberately. A per-frame beam is the stronger policy but its first
    generation is degenerate (the input pipeline delays a frame, so every candidate's first step is
    identical), which makes its early ranking arbitrary; holding is the simplest policy that isolates
    the axis, and it UNDER-states the authority, which is the safe direction for a rank.

    The mechanism behind the number: the plow ejects Tetra along the line from Link's exec Co-centre
    to her feet, so the lateral component is the push magnitude times the sine of Link's off-line
    angle -- and swinging far off-line is what costs the contact that produced the push.

    Returns ``dict(hi, lo, spread, per_frame, along_max, frames, n)``, laterals relative to the start.
    ``hi``/``lo`` also say whether the reachable set is ONE-SIDED, which at the cycle-3 endpoints it
    is: every stick loses lateral, so what a rank chooses there is how FAST, not which way."""
    walls = O.courtyard_walls()
    lat0, al0 = hl.lateral(run.tx, run.tz), hl.along(run.tx, run.tz)
    lats, alongs = [], []
    for (sx, sy) in _terminal_alphabet(run, hl, n_dirs=n_dirs):
        for l in (0, 1):
            r, ok = run.clone(), True
            for _ in range(int(frames)):
                r.step(dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                            triggerL=255 if l else 0,
                            substickX=T.CSTICK_NEUTRAL, substickY=0))
                if not frame_in_model(r, walls):
                    ok = False
                    break
            if ok:
                lats.append(hl.lateral(r.tx, r.tz) - lat0)
                alongs.append(hl.along(r.tx, r.tz) - al0)
    if not lats:
        return None
    hi, lo = max(lats), min(lats)
    return dict(hi=hi, lo=lo, spread=hi - lo, per_frame=(hi - lo) / float(frames),
                along_max=max(alongs), frames=int(frames), n=len(lats))


def junction_authority(node, hl, placements=None, *, frames=5, box=None, ess_step=1, aim_step=16,
                       arm_frames=12):
    """**MEASURE what the JUNCTION can do to Tetra's corridor offset, and what it costs to use it**
    -- `lateral_authority`'s method one stage earlier, and the measurement that retired session 63's
    next step ("correct the lateral in the junction, not in the roll").

    That next step rested on a premise worth checking before building a keep on it: that the junction
    can move Tetra onto `objective.push_corridor` because Link repositions there in single frames.
    The premise is TRUE and the conclusion does not follow, which only a measurement separates.

    Hold each `junction_alphabet` member (with and without L) for ``frames`` frames and read the
    corridor offsets reached; then walk every held family frame by frame to ``arm_frames`` and count
    how many produce a gate-passing (`two_roll.junction_gates`) endpoint. Measured from the s62/s63
    cycle-1 beam, entry offset 3.51:

      * AUTHORITY IS REAL -- over the branches that SURVIVE every prune, 5 held frames span corridor
        offset **0.79..14.10** on one cycle-1 node and **0.01..9.16** on another (Tetra lateral
        spread 13.1 / 11.0 u, 2.6 / 2.2 u per frame, the same order as `LATERAL_RATE`; 14.6 u
        unpruned). The corridor-good branches are not pruned and not exotic: they clear the box, the
        walls and the regime with Link INSIDE the human's envelope (offset 0.01 at Link lat -7.56,
        lead -46.6), against a beam that lands its own endpoints at 8.12 and 13.73.
      * AND IT IS UNUSABLE, because those branches are CONSTANT-STICK families and a constant stick
        never ARMS: **0** gate-passing endpoints over every held family, with the pursuit box on OR
        off. Arming needs a varying sequence (clear the cone, then L + a toward-Tetra stick on the
        delay-1 timing), so within the junction, steering Tetra and arming Link are mutually
        exclusive. Running the shipped `junction_beam` from a corridor-good steered state confirms
        it from the other side: 0 armed endpoints in 6 further frames.

    So the junction's authority cannot be spent, and three frontier variants built on the premise are
    inert or worse -- a corridor order MIXED into `_frontier_score`'s cut is byte-identical (every
    candidate in a generation shares one corridor offset, and `sorted` is stable, so the corridor
    order IS the base order), a uniform stride over the ties gives 74 endpoints and 0 rollable, and a
    corridor order computed on a 2-frame lookahead gives 424 endpoints and 1.

    Returns ``dict(entry_off, lo, hi, spread, per_frame, best, n_alive, n_held, armed, frames)``;
    ``best`` is the corridor-best surviving hold. ``box`` prunes on `in_pursuit_box` when given."""
    rows = placements if placements is not None else seeds.load_placements()[0]
    cor = O.push_corridor(hl, rows)
    walls = O.courtyard_walls()
    run0 = node['run']
    entry_off = cor['offset'](hl.along(run0.tx, run0.tz), hl.lateral(run0.tx, run0.tz))

    def _alive(r):
        return (not r._follow_warned
                and O.frame_is_wall_free(r.link.pos_x, r.link.pos_z, r.tx, r.tz, walls)
                and (box is None or in_pursuit_box(r, hl, box)))

    reached, armed, n_held = [], 0, 0
    for (sx, sy) in junction_alphabet(run0, hl, ess_step=ess_step, aim_step=aim_step):
        for l in (0, 1):
            n_held += 1
            r = run0.clone()
            for jf in range(1, max(int(frames), int(arm_frames)) + 1):
                r.step(dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                            triggerL=255 if l else 0,
                            substickX=T.CSTICK_NEUTRAL, substickY=0))
                if not _alive(r):
                    break
                if jf <= int(arm_frames) \
                        and T.junction_gates(r, hl, node['frames'] + jf) is None:
                    armed += 1
                if jf == int(frames):
                    reached.append(dict(off=cor['offset'](hl.along(r.tx, r.tz),
                                                          hl.lateral(r.tx, r.tz)),
                                        t_lat=hl.lateral(r.tx, r.tz),
                                        l_lat=hl.lateral(r.link.pos_x, r.link.pos_z),
                                        lead=hl.lead(r.link.pos_x, r.link.pos_z, r.tx, r.tz),
                                        stick=(sx, sy), l=l))
    if not reached:
        return None
    lo = min(r['off'] for r in reached)
    hi = max(r['off'] for r in reached)
    lats = [r['t_lat'] for r in reached]
    return dict(entry_off=entry_off, lo=lo, hi=hi, spread=max(lats) - min(lats),
                per_frame=(max(lats) - min(lats)) / float(frames),
                best=min(reached, key=lambda r: r['off']), n_alive=len(reached),
                n_held=n_held, armed=armed, frames=int(frames))


def glide_probe(run, frames, hl, placements, thread, *, max_frames=5, beam=4, n_dirs=12):
    """**The LAST cycle's endpoint keep: GLIDE-ABILITY, not the frame bound** (session 62) -- the
    terminal's counterpart of `roll_probe`, and the same lesson one stage later.

    `roll_probe` exists because the endpoints that LOOK best (flattest) are measurably not the ones a
    roll can fire from, and ranking on the proxy stalled the chain four times. The last cycle has the
    same shape of bug against the terminal: `objective.thread_cost` scores a post-roll endpoint on
    where TETRA is, and says nothing about how much push LINK has left -- yet that is what decides the
    handoff. Measured on the s62 cycle-3 beam, the two disagree and the proxy is wrong: the endpoint
    the thread cost likes best (node 6, lat +15.3, cost 74.47) glides to h 4.71, while the one it
    ranks worst (node 3, cost 74.51) glides to **h 2.54** -- because node 6's Link has 11.7 u of
    along left in him and node 3's has 40.3.

    So: run the real terminal glide, short and narrow, and rank the endpoint by the best
    ``frames + objective.thread_frames`` it reaches -- what this cycle actually hands the terminal.
    ~1 s per endpoint, which is why it re-ranks the final survivors rather than the aim fan.

    Returns ``dict(bound, h, frames, along, lat)`` for the best state the probe glide reached."""
    walls = O.courtyard_walls()
    a0, l0 = hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz)
    best = dict(bound=frames + O.thread_frames(a0, l0, thread),
                h=O.thread_frames(a0, l0, thread), frames=frames, along=a0, lat=l0)
    live = [(run, frames)]
    for _ in range(int(max_frames)):
        nxt, seen = [], set()
        for (r0, fr) in live:
            for (sx, sy) in _terminal_alphabet(r0, hl, n_dirs=n_dirs):
                for l in (0, 1):
                    r = r0.clone()
                    r.step(dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                                triggerL=255 if l else 0,
                                substickX=T.CSTICK_NEUTRAL, substickY=0))
                    if not frame_in_model(r, walls):
                        continue
                    tag = (round(r.link.pos_x, 1), round(r.link.pos_z, 1),
                           round(r.tx, 1), round(r.tz, 1))
                    if tag in seen:
                        continue
                    seen.add(tag)
                    a, la = hl.along(r.tx, r.tz), hl.lateral(r.tx, r.tz)
                    h = O.thread_frames(a, la, thread)
                    cand = dict(bound=fr + 1 + h, h=h, frames=fr + 1, along=a, lat=la)
                    if cand['bound'] < best['bound']:
                        best = cand
                    nxt.append((r, fr + 1, cand['bound']))
        if not nxt:
            break
        nxt.sort(key=lambda t: t[2])
        live = [(r, f) for (r, f, _b) in nxt[:int(beam)]]
    return best


def escape_probe(run, frames, hl, placements, thread, atom_landing=True, atom_flip=None,
                 atom_rots=None, atom_rank=None):
    """**The LAST cycle's endpoint keep, one stage further out than `glide_probe`: what its ESCAPE
    lands, not what its glide reaches** (session 67).

    `glide_probe` exists because ranking a post-roll endpoint on where the ROLL left Tetra says
    nothing about what the terminal can do from it. Session 67 measured that the terminal can do
    NOTHING from it: sweep the whole `_terminal_alphabet` off a real cycle-3 endpoint and Tetra's
    position is bit-identical across every branch for four frames (the input pipeline acts 2 frames
    late, and by then the actors have separated -- see `aim`), which is why six terminal rank
    configurations returned byte-identical results across s61-s63. The only inputs with authority
    left are the escape's own conversion frames, and they are placement frames.

    So probe THEM: run the escape atom (`away_walk.probe`, the exact rule-3 acceptance) and rank the
    endpoint by where it leaves Tetra -- `aim.landing_miss` against the target thread, and the frames
    that landing costs. ~2-5 s per endpoint (16 atom variants), so it re-ranks the final survivor
    list, never an aim fan.

    ``atom_landing`` (session 71, default ON) makes the atom sweep pick its variant by where it leaves
    HER rather than by entry progress (`away_walk.probe`'s ``thread``) -- the same argument one level in:
    if the atom's frames are the last with authority over Tetra, the atom's own knobs are part of the
    placement, and ranking them by how far Link got toward the entry roll spends that authority on the
    separate search. Measured over 8 real arrivals it improves 6, median 2.70 u and max 10.08 u of
    landing, taking this stage's best from 16.34 u off the thread to 6.25 at 77 frames.

    ``atom_flip`` / ``atom_rots`` / ``atom_rank`` (session 72) hand `away_walk.probe` the two knobs it
    was leaving at their defaults -- ``flip_bearing``, the direction the conversion frames PUSH her,
    and ``rotate_off`` -- plus the frames-currency rank that sweeping them requires. That probe's
    docstring holds the measurement; what it is worth HERE, on four real 71-frame arrivals of the
    s71 full-resolution jf-7 band: the landing goes **4.90 -> 0.33**, **4.99 -> 0.01** and
    **8.23 -> 0.00 u**, ``spec`` reads True for the first time, and under ``atom_rank='frames'`` the
    bound goes **77.50 -> 75.13**. It costs one atom per (flip, rotate) pair, so it is opt-in: at
    ``atom_flip=0x400`` with all four rotates that is ~544 atoms (~30 s) per endpoint against the
    shipped 8 (~0.06 s), which is a last-cycle terminal budget, not an aim-fan one.

    Returns ``dict(fires, miss, pd, frames, bound, resid, freeze_f, spec)``; a non-firing endpoint
    reads ``fires=False`` with an infinite bound so it sorts last (it cannot end a plan: rule 3)."""
    from harness.tetrapush import away_walk as AW
    from harness.tetrapush import aim as A
    res = AW.probe(run, hl, thread=(thread if atom_landing else None), flip_step=atom_flip,
                   rotate_offs=atom_rots, rank=(atom_rank or 'miss'))
    if res is None or not AW.fires(res):
        return dict(fires=False, miss=None, pd=None, frames=frames, bound=float('inf'),
                    resid=None, freeze_f=None if res is None else res['freeze_f'], spec=None)
    resid = (res['resid_along'], res['resid_lat'])
    lm = A.landing_miss(run, hl, thread, resid)
    fr = frames + res['freeze_f']
    return dict(fires=True, miss=lm['miss'], pd=_placement_dist(res['run'], placements), frames=fr,
                bound=fr + O.thread_frames(lm['along'], lm['lat'], thread), resid=resid,
                freeze_f=res['freeze_f'],
                spec=A.handoff_spec(run, hl, thread, frames, resid=resid))


def _terminal_score(run, hl, placements, objective, w_deficit, w_approach, frames=0, thread=None,
                    resid=None):
    """The terminal beam's rank key.

    ``resid`` (session 66, the atom wiring) shifts the ``'thread'`` rank by the escape atom's
    probed residual ``(resid_along, resid_lat)``: the atom's conversion frames keep pushing Tetra
    ~35-45 u down-corridor AFTER the glide hands off, so the glide must aim at coord-minus-residual
    -- ranking the POST-atom landing point, not the pre-atom one. Probed per terminal state
    (`_atom_place` updates the estimate as it measures), never a constant.

    ``'thread'`` (session 62, THE objective's rank) = `objective.thread_cost`: the plan length this
    trajectory implies with along and lateral counted at the rates the plow achieves on EACH, and
    rule 3 (`_terminal_ready`) floored into it. It is `'frame_minimal'` with the two blind spots
    closed -- the ones that made s61's terminal drift Tetra from lat +8.90 (on the thread's near end)
    to -2.44 (off it) while its score improved, and finish `ready=False`.

    ``'frame_minimal'`` (session 60) = `objective.plan_bound(frames, pd)`. Within one generation every
    live node has the same ``frames``, so it orders exactly as ``'placement'`` does -- the difference
    is in the GLOBAL best, which prefers an earlier adequate placement over a later perfect one.

    ``'placement'`` (the s44 default) = pure Tetra->coord distance, the deepest-contact lander.
    ``'grazing'`` (route a, session 48) additionally penalises the coupled-entry `deficit`
    (`CO_RADII_BAR - centre_feet`) and a closing `approach_rate` -- the near-rest arrival the s44-s51
    endgame needed, which rule 3 RETIRES (kept because its physics is still true and measurable).
    Returns ``(score, placement)``; in placement mode ``score == placement`` so that rank is
    byte-for-byte unchanged."""
    pd = _placement_dist(run, placements)
    if objective == 'placement':
        return pd, pd
    if objective == 'frame_minimal':
        return O.plan_bound(frames, pd), pd
    if objective == 'thread':
        a, la = hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz)
        if resid is not None:
            a, la = a + resid[0], la + resid[1]
        return O.thread_cost(frames, a, la, thread, ready=_terminal_ready(run)['ready']), pd
    deficit = max(0.0, CO_RADII_BAR - _centre_feet(run))
    return pd + w_deficit * deficit + w_approach * max(0.0, _approach_rate(run)), pd


def _atom_place(cand, hl, placements, band):
    """**Run the escape atom from one terminal candidate and read the placement where the plan
    actually ENDS: at the slam (separation) frame, AFTER the conversion frames' push** (session 66,
    wiring the s65 atom's residual into the terminal).

    The atom's conversion frames keep pushing Tetra (they are placement frames -- `away_walk`), so
    a candidate whose PRE-atom distance reads 0 is really ~35-45 u PAST the coord once the escape
    runs. This is the exact form of that accounting: probe the atom (`away_walk.probe`, the small
    knob sweep), require it to FIRE (rule 3 exact, `away_walk.fires`), and measure Tetra's distance
    to the nearest genuine coord at the atom's endpoint -- she is frozen from the slam on, so the
    endpoint distance IS the slam-frame distance. The residual is read off the probe per state,
    never a constant.

    Returns None when no variant fires; else a node-shaped dict: ``frames`` counts to the SLAM
    (where the herd ends -- rule 2's currency), ``log`` carries the WHOLE atom (through the
    receding-at-cap handoff, where the entry leg takes over, `handoff_frames`), ``dist`` is the
    post-atom placement distance, ``placed_ok`` = inside ``band``, ``atom`` the probe result
    (knobs, per-frame rows, and the ``csangle`` it ran at with its ``cs_bill`` -- 0 since session 73,
    when the atom stopped commanding the camera and the last roll's ``target_cs`` started paying for
    it, `camera_probe_key`)."""
    from harness.tetrapush import away_walk as AW
    res = AW.probe(cand['run'], hl)
    if not AW.fires(res):
        return None
    r = res['run']
    pd = _placement_dist(r, placements)
    fr = cand['frames'] + res['freeze_f']
    return dict(run=r, log=cand['log'] + res['log'], frames=fr, dist=pd,
                score=O.plan_bound(fr, pd), atom=res, placed_ok=pd <= band,
                handoff_frames=cand['frames'] + len(res['log']),
                # the pre-atom candidate: the log the acceptance test replays (score_plan's exact
                # rule 3 then re-fires the atom from ITS endpoint) and the state confirm_plan pins
                pre_run=cand['run'], pre_log=cand['log'], pre_frames=cand['frames'])


def terminal_targeting(nodes, hl, placements=None, *, max_frames=18, beam=64,
                       n_dirs=24, objective='placement', w_deficit=1.0, w_approach=2.0,
                       band=None, atom=None, atom_probes=2, verbose=False):
    """**The TERMINAL cycle, ranked by PLACEMENT distance instead of u/frame** -- the endgame stage
    the chain hands off to once one more full roll would OVERSHOOT the cluster.

    ``objective`` selects the rank (`_terminal_score`). ``'thread'`` (session 62) is the current one:
    the frame-minimal bound with along and lateral priced apart and rule 3 folded in, which is what
    the glide needs, because the thing it spends is exactly the thing `'frame_minimal'` could not
    see. Measured on the s61 winner: the terminal took Tetra from lat +8.90 -- essentially ON the
    thread's near end -- to -2.44 over four frames, improving its score the whole way, and stopped
    31.4 u short with `ready=False`. Both misses are the rank, not the alphabet.

    ``'frame_minimal'`` is the session-60 one. Either of these two also STOPS at the first generation
    that satisfies the objective -- Tetra inside ``band`` of a genuine coord (rule 1) with Link still
    MOVING (rule 3, `_terminal_ready`) -- and returns it as ``placed``, because nothing found later
    can be shorter. That is what "the placement RIDES the last push" means operationally: the terminal
    stops when the coord is landed, instead of spending further frames polishing a distance that is
    already inside the band.
    ``'placement'`` is the s44 rank (nearest coord, the deep-contact lander) and ``'grazing'``
    (route a, session 48) the near-rest one -- kept, measurable, but retired by rule 3.

    The geometry forces this (`endgame_geom`): each full cycle herds ~280 u but only ~99 u along
    (and a ~28 u lateral correction) separate the 3-cycle endpoint from the nearest coord, so a full
    +26 roll lands Tetra PAST every coord -- worse than not rolling. What is controllable at this
    range is the plow GLIDE: Link stays in contact (dist < 80) through the junction, so a metered
    glide keeps herding Tetra down-line at ~13 u/frame AND steers her lateral (push ejects her away
    from Link's centre, so approaching from the high-lateral side pulls her back toward the line).

    So this is a per-frame BEAM (the atom is one frame's (stick, L), as in `junction_beam`) ranked by
    the CURRENT Tetra-to-nearest-coord distance, tracking the global closest state reached at ANY
    frame (a glide sweeps THROUGH the coord band, so the best endpoint is mid-glide, not at the
    horizon). Returns ``dict(best, dist, per_node, placed, closest, closest_ready, band)``: ``best`` by
    the chosen rank (carrying its full input log, so `confirm_plan` replays it end-to-end),
    ``placed`` = the frame-minimal objective actually hit, ``closest`` = the smallest distance reached at
    ANY frame. **In ``frame_minimal`` mode read ``closest``, not ``best``**: there a frame costs 1.0
    of score and can win back at most `PUSH_CEILING`/`PUSH_CEILING` = 1.0 of it, so ``best`` sits at
    the start of the glide by construction and says nothing about how close the glide came.

    **The atom wiring (session 66, default in ``'thread'`` mode; ``atom=`` overrides):** the s65
    escape atom's conversion frames keep pushing Tetra ~35-45 u down-corridor after the glide hands
    off, so "on the coord" is a POST-atom fact. In atom mode the thread rank aims the glide at
    coord-minus-residual (`_terminal_score(resid=)`, the residual probed off the node and refined
    by every fire), the old pre-atom ``dist <= band`` placement is disabled, and each generation's
    most-landable candidates (``atom_probes`` of them, by |pre-atom dist - residual|) run
    `_atom_place`: the full probe, rule 3 EXACT (`away_walk.fires`), placement read at the slam
    frame. ``placed``/``done`` nodes then carry the atom (its log through the handoff, knobs, the
    commanded csangle) and their ``frames`` count to the SLAM -- where the herd actually ends.
    ``closest_atom`` is the best post-atom placement probed anywhere (the atom-mode analogue of
    ``closest``).

    ``closest_ready`` (session 63) is ``closest`` restricted to states satisfying rule 3, and it exists
    because ``closest`` is blind to that rule while the two measurably disagree: the same chain under
    two different cycle-3 keeps ends either **31.406 u** out with ``ready=False`` or **33.482 u** out at
    74 frames with ``ready=True``, and it is the second that is one frame of herding from a PASS. A
    solve reporting only the smaller number hides the better plan, so `_cmd_solve` prints both.

    **Why the prune is the MODEL BOUNDARY, not the pursuit box** (measured, `probe_glide`): the
    deepest approach happens AFTER Link overtakes Tetra and leaves the box -- e.g. a plain (111,111)
    glide off the 3-cycle endpoint carries her from 74.7 u to **6.4 u**, but the minimum lands at f8
    when Link is already lead +18 (out of the box). The pursuit box exists to keep a posture for the
    NEXT roll; the terminal has none, so the only hard constraints are the ones the MODEL imposes --
    the stt-3 plow regime and the unmodelled walls (`frame_in_model`) -- plus talk-safety, which
    holds trivially in a glide (no A-press)."""
    if placements is None:
        placements, _ = seeds.load_placements()
    band = O.PLACEMENT_BAND if band is None else float(band)
    walls = O.courtyard_walls()
    thread = O.placement_thread(hl, placements)
    stop_when_placed = objective in ('frame_minimal', 'thread')
    # Atom mode (s66) defaults ON for the objective's own rank; the other ranks keep the
    # pre-atom semantics their gates pin. See the docstring.
    atom = (objective == 'thread') if atom is None else bool(atom)
    best = None
    placed = None                     # the EARLIEST frame that satisfies rules 1 + 3
    closest = None                    # the smallest placement distance at ANY frame (diagnostic)
    # ...and the same among rule-3-MET states, which `closest` is blind to -- see the docstring
    closest_ready = None
    closest_atom = None               # atom mode: the best POST-atom placement probed anywhere
    per_node = []
    for node in nodes:
        est = None                    # the probed atom residual (along, lat) -- the rank shift
        if atom:
            ap0 = _atom_place(dict(run=node['run'], log=node['log'], frames=node['frames']),
                              hl, placements, band)
            if ap0 is not None:
                est = (ap0['atom']['resid_along'], ap0['atom']['resid_lat'])
                closest_atom = ap0 if closest_atom is None or (
                    (ap0['dist'], ap0['frames'])
                    < (closest_atom['dist'], closest_atom['frames'])) else closest_atom
                if ap0['placed_ok'] and (placed is None or (ap0['frames'], ap0['dist'])
                                         < (placed['frames'], placed['dist'])):
                    placed = dict(ap0, plan=node.get('plan', []))
        s0, d0 = _terminal_score(node['run'], hl, placements, objective, w_deficit, w_approach,
                                 node['frames'], thread, resid=est)
        node_best = dict(run=node['run'], log=node['log'], frames=node['frames'], dist=d0,
                         score=s0, plan=node.get('plan', []))
        if best is None or s0 < best['score']:
            best = node_best
        if closest is None or (d0, node['frames']) < (closest['dist'], closest['frames']):
            closest = node_best
        live = [dict(run=node['run'], log=node['log'], frames=node['frames'])]
        for _f in range(int(max_frames)):
            nxt, seen, done = [], set(), []
            for nd in live:
                for (sx, sy) in _terminal_alphabet(nd['run'], hl, n_dirs=n_dirs):
                    for l in (0, 1):
                        r = nd['run'].clone()
                        d = dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                                 triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL, substickY=0)
                        r.step(d)
                        if not frame_in_model(r, walls):   # regime + walls -- see the docstring
                            continue
                        tag = (round(r.link.pos_x, 1), round(r.link.pos_z, 1),
                               r.link.facing >> 5, round(r.link.speedF, 2),
                               round(r.tx, 1), round(r.tz, 1))
                        if tag in seen:
                            continue
                        seen.add(tag)
                        fr = nd['frames'] + 1
                        score, dist = _terminal_score(r, hl, placements, objective,
                                                      w_deficit, w_approach, fr, thread,
                                                      resid=est)
                        cand = dict(run=r, log=nd['log'] + [d], frames=fr,
                                    dist=dist, score=score)
                        nxt.append(cand)
                        # Pre-atom placement (non-atom ranks only): in atom mode the escape would
                        # push her ~35-45 u past the coord, so `_atom_place` below decides.
                        if not atom and dist <= band and _terminal_ready(r)['ready']:
                            done.append(cand)
                        if score < best['score']:
                            best = dict(cand, plan=node.get('plan', []))
                        if score < node_best['score']:
                            node_best = dict(cand, plan=node.get('plan', []))
                        if (dist, fr) < (closest['dist'], closest['frames']):
                            closest = dict(cand, plan=node.get('plan', []))
                        if _terminal_ready(r)['ready'] and (
                                closest_ready is None
                                or (dist, fr) < (closest_ready['dist'], closest_ready['frames'])):
                            closest_ready = dict(cand, plan=node.get('plan', []))
            if atom and nxt:
                # Probe the most-landable candidates: nearest |pre-atom dist - probed residual|
                # (nearest coord until one is measured); each fire refines the rank's estimate.
                key = ((lambda c: abs(c['dist'] - math.hypot(est[0], est[1])))
                       if est is not None else (lambda c: c['dist']))
                for cand in sorted(nxt, key=key)[:int(atom_probes)]:
                    ap = _atom_place(cand, hl, placements, band)
                    if ap is None:
                        continue
                    est = (ap['atom']['resid_along'], ap['atom']['resid_lat'])
                    if closest_atom is None or (ap['dist'], ap['frames']) < (
                            closest_atom['dist'], closest_atom['frames']):
                        closest_atom = dict(ap, plan=node.get('plan', []))
                    if ap['placed_ok']:
                        done.append(ap)              # rules 1 + 3-EXACT met, at the slam frame
            if done:
                done.sort(key=lambda c: c['dist'])
                cand = dict(done[0], plan=node.get('plan', []))
                if placed is None or (cand['frames'], cand['dist']) < (placed['frames'],
                                                                      placed['dist']):
                    placed = cand
                if stop_when_placed:
                    break        # frame-minimal: no later generation can be shorter than this one
            nxt.sort(key=lambda c: c['score'])
            live = nxt[:int(beam)]
            if not live:
                break
        per_node.append(node_best)
        if verbose:
            print("    start dist %.1f -> best %.1f (%d frames)%s"
                  % (d0, node_best['dist'], node_best['frames'],
                     '' if placed is None else '   [PLACED at %d f, %.3f u]'
                     % (placed['frames'], placed['dist'])))
    return dict(best=best, dist=best['dist'] if best else None, per_node=per_node,
                placed=placed, closest=closest, closest_ready=closest_ready,
                closest_atom=closest_atom, band=band)


def cluster_distance(env, hl):
    """The herd budget: how far down-herd the genuine-coord centroid sits from Tetra's start."""
    placements, _ = seeds.load_placements()
    cx = sum(p['x'] for p in placements) / len(placements)
    cz = sum(p['z'] for p in placements) / len(placements)
    return hl.along(cx, cz)


# --------------------------------------------------------------------------- CLI

def _cmd_sep(env):
    r = target_cs_is_exit_only(env)
    print("TARGET_CS SEPARABILITY -- does the camera target change the roll's PUSH?\n")
    print("  roll frames: %d   roll speedF %.4f facing %d (identical across target_cs: %s)"
          % (r['roll_frames'], r['roll_speedF'], r['roll_facing'], r['tetra_identical']))
    print("  first frame ANY state diverges: %d (roll ends at %d)"
          % (r['first_diverge'], r['roll_frames']))
    print("\n  => target_cs is %s\n"
          % ('EXIT-ONLY (the roll stage factors: aim sweep, then tcs sweep)' if r['ok']
             else 'NOT exit-only -- the roll stage cannot be factored'))


def _cmd_box(env, hl):
    box = pursuit_box(env, hl)
    h = human_in_box(env, hl, box)
    print("THE PURSUIT BOX -- the plow regime, measured off the recorded window\n")
    print("  lead    %.1f .. %.1f u behind Tetra along the push axis" % (box['lead_lo'],
                                                                        box['lead_hi']))
    print("  |lat|   <= %.1f u off the herd line" % box['max_lat'])
    print("  |delta| <= %d BAM (%.1f deg) between the bearing-to-Tetra and the herd direction"
          % (box['max_delta'], box['max_delta'] / 65536.0 * 360))
    print("\n  containment: the human is inside it on %s\n"
          % ('EVERY frame' if h['ok'] else 'all but frames %s' % h['outside']))


def _cmd_plan(env, hl, kw):
    import time
    goal = cluster_distance(env, hl)
    print("FULL HERD: the genuine-coord cluster is %.1f u down-herd from Tetra's start" % goal)
    t0 = time.perf_counter()
    res = chain_herd(env, hl, ncycles=int(kw.get('cycles', 3)),
                     c1_beam=int(kw.get('c1', 8)), beam=int(kw.get('beam', 8)),
                     jn_keep=int(kw.get('jkeep', 6)), ess_step=int(kw.get('ess', 1)),
                     jn_beam=int(kw.get('jbeam', 24)),
                     aim_keep=int(kw.get('aimkeep', 3)), c1_step=int(kw.get('step', 4)),
                     verbose=True)
    print("\n(%.1f s)  per-cycle best:" % (time.perf_counter() - t0))
    print("  cyc  nodes  frames   herd     u/f     lead    lat   remaining")
    for i, b in enumerate(res['beams'], 1):
        if not b:
            print("  %2d      0   -- beam empty (chain stalled)" % i)
            continue
        n = b[0]
        m = n['m']
        print("  %2d   %4d    %3d  %+7.1f  %6.3f  %+6.1f %+6.1f   %7.1f"
              % (i, len(b), n['frames'], m['herd'], m['per_frame'], m['lead'], m['lat'],
                 goal - m['herd']))
    best = res['best']
    if best is None:
        print("\n  no surviving chain")
        return
    c = confirm_plan(env, hl, best)
    p = placement_report(best)
    print("\n  best: %.3f u/f over %d frames (%s the human's 2-roll %.3f), %d rolls"
          % (c['per_frame'], c['frames'],
             'CLEARS' if c['per_frame'] > res['bar'] else 'below', res['bar'], c['rolls']))
    print("  confirm (fresh replay of its own log): bit_exact=%s talk_safe=%s -> %s"
          % (c['bit_exact'], c['talk_safe'], 'CONFIRMED' if c['ok'] else 'NOT CONFIRMED'))
    print("  Tetra at (%.3f, %.3f); nearest genuine coord idx %d at (%.3f, %.3f), %.1f u away"
          % (p['tetra'][0], p['tetra'][1], p['nearest']['idx'], p['nearest']['x'],
             p['nearest']['z'], p['dist']))


def _cmd_endgame(env, hl, kw):
    import time
    placements, _ = seeds.load_placements()
    ncyc = int(kw.get('cycles', 3))
    print("ENDGAME: chain %d cycles, then PLACEMENT-target the terminal cycle\n" % ncyc)
    t0 = time.perf_counter()
    res = chain_herd(env, hl, ncycles=ncyc, beam=int(kw.get('beam', 8)),
                     jn_keep=int(kw.get('jkeep', 6)), verbose=True)
    if not res['best']:
        print("\n  chain stalled; no terminal beam")
        return
    lastbeam = res['beams'][-1]
    print("\n  cycle %d beam: %d nodes, best %.1f u from a coord"
          % (ncyc, len(lastbeam), min(placement_report(n, placements)['dist'] for n in lastbeam)))
    tt = terminal_targeting(lastbeam, hl, placements,
                            max_frames=int(kw.get('tframes', 18)),
                            beam=int(kw.get('tbeam', 48)), verbose=True)
    print("\n(%.1f s)" % (time.perf_counter() - t0))
    best = tt['best']
    c = confirm_plan(env, hl, best)
    eg = endgame_report(best, hl, placements)
    print("\n  TERMINAL: Tetra %.1f u from genuine coord idx %d, in %d frames"
          % (eg['placement']['dist'], eg['placement']['nearest']['idx'], best['frames']))
    print("  confirm (fresh replay of its own log): bit_exact=%s talk_safe=%s -> %s"
          % (c['bit_exact'], c['talk_safe'], 'CONFIRMED' if c['ok'] else 'NOT CONFIRMED'))
    print("  Tetra at (%.3f, %.3f); coord idx %d at (%.3f, %.3f)"
          % (best['run'].tx, best['run'].tz, eg['placement']['nearest']['idx'],
             eg['placement']['nearest']['x'], eg['placement']['nearest']['z']))
    print("  Link at (%.3f, %.3f) facing %d; final-clip ENTRY gap: %.1f u, %d BAM off facing"
          % (eg['link'][0], eg['link'][1], eg['link'][2], eg['entry_dist'], eg['entry_dfacing']))

    # milestone 2b: the coupled reposition (Link -> entry, Tetra holds) + the measured barrier
    sc = separation_scan(best, hl, placements)
    aq = arrival_quality(best, hl, placements)
    print("\n  ARRIVAL GATE (route a, both coupled halves -- the cheap pre-chain check):")
    print("    POSITION: Tetra %.2f u from a coord, centre_feet %.1f (freeze_ok=%s)"
          % (aq['placement_dist'], aq['centre_feet'], aq['freeze_ok']))
    print("    MOMENTUM: approach_rate %+.2f u/f toward Tetra (receding=%s) -> arrival_ok=%s"
          % (aq['approach_rate'], aq['receding'], aq['arrival_ok']))
    print("\n  SEPARATION BARRIER (why Link cannot yet leave for the entry):")
    print("    placement centre_feet %.1f u vs the %.0f u Co-radii bar -> %.1f u TOO DEEP "
          "(freeze_ok=%s)" % (sc['centre_feet'], sc['co_radii_bar'], sc['deficit'], sc['freeze_ok']))
    print("    (feet dist %.1f u; best one-step keeps Tetra %.2f u from a coord; strict one-step "
          "clean_separation=%s)"
          % (sc['start_dist'], sc['best_step_placement'], sc['clean_separation']))
    if sc['freeze_ok']:
        w = walk_to_entry(best, hl, placements)
        print("  ABOVE THE BAR -> Link-only WALK: entry %.1f u (Tetra moved %.3f u, clean=%s), %d frames"
              % (w['dist'], w['max_tetra_disp'], w['clean'], w['frames']))
    else:
        print("  (deep contact: the WALK planner is inert until the chain arrives grazing -- "
              "route a, piece 1. See `full_herd walk` for the above-the-bar maneuver on a "
              "synthetic frozen arrival.)")
        et = entry_targeting(best, hl, placements, max_frames=int(kw.get('rframes', 30)),
                             beam=int(kw.get('rbeam', 48)))
        print("  in-band GUARD (push fan, stalls above the bar): Link -> entry %.1f u "
              "(Tetra %.2f u from coord), %d frames"
              % (et['dist'], et['placement'], et['best']['frames']))


def _cmd_walk(env, hl, kw):
    """**Milestone-2b piece 2 demo**: the Link-only WALK to the final-clip entry, above the
    clean-separation bar. Runs on a SYNTHETIC frozen arrival (`synthetic_frozen_arrival`) because the
    current chain lands DEEP (route a, the grazing chain, is piece 1). Shows the session-47 momentum
    finding: at the SAME freeze_ok position a REST arrival walks clean (Tetra frozen) while a hot EBS
    arrival re-plows her -- freeze_ok is positional, the arrival momentum is the other half."""
    idx = int(kw.get('coord', 241))
    cf = float(kw.get('cf', 88.0))
    placements, _ = seeds.load_placements()
    print("WALK TO ENTRY (milestone 2b, above the bar): coord idx %d, target centre_feet %.0f\n" % (idx, cf))
    for mom in ('rest', 'ebs'):
        placed = synthetic_frozen_arrival(env, hl, idx, target_cf=cf, momentum=mom)
        sc = separation_scan(placed, hl, placements)
        w = walk_to_entry(placed, hl, placements)
        r0 = placed['run']
        print("  %-4s arrival: proc %d speedF %+6.2f  centre_feet %.1f (freeze_ok %s)"
              % (mom, r0.link.state, r0.link.speedF, sc['centre_feet'], sc['freeze_ok']))
        print("       walk -> entry %.2f u in %d frames  (Tetra moved %.3f u, clean=%s, %d BAM off facing)\n"
              % (w['dist'], w['frames'], w['max_tetra_disp'], w['clean'], w['entry_dfacing']))
    print("  => freeze_ok is POSITIONAL and necessary but not sufficient; a clean walk also needs the\n"
          "     grazing chain (route a) to arrive NEAR-REST / receding up-herd, not a hot EBS at Tetra.")


def _cmd_arrivals(env, hl, kw):
    """**The CHEAP arrival gate demo** (route a, piece 1): `arrival_quality` scores the SAME
    freeze_ok position two ways -- from rest (clean) and from a hot EBS (re-plows) -- and the
    `arrival_ok` verdict separates them WITHOUT running the walk. This is the monotone predictor a
    grazing-chain candidate is gated by before paying `walk_to_entry`/the 800 s chain."""
    idx = int(kw.get('coord', 241))
    cf = float(kw.get('cf', 88.0))
    placements, _ = seeds.load_placements()
    print("ARRIVAL GATE (cheap, both coupled halves): coord idx %d, target centre_feet %.0f\n"
          % (idx, cf))
    print("  arrival  freeze_ok  approach(u/f)  receding  arrival_ok   walk max_disp  clean")
    for mom in ('rest', 'ebs'):
        placed = synthetic_frozen_arrival(env, hl, idx, target_cf=cf, momentum=mom)
        aq = arrival_quality(placed, hl, placements)
        w = walk_to_entry(placed, hl, placements)
        print("  %-4s        %-5s     %+7.2f       %-5s     %-5s        %8.3f     %s"
              % (mom, aq['freeze_ok'], aq['approach_rate'], aq['receding'],
                 aq['arrival_ok'], w['max_tetra_disp'], w['clean']))
    print("\n  => the cheap `arrival_ok` (freeze_ok AND approach_rate <= a few u/f) agrees with the\n"
          "     expensive walk: it PASSES the clean rest arrival and REJECTS the hot EBS one, so a\n"
          "     grazing-chain rank can gate on it before the walk / the chain re-run.")


def _cmd_place(env, hl, kw):
    """**The clean grazing-arrival recipe demo** (milestone 2b, session 49): from a near-REST arrival
    behind a coord, `place_on_thread`'s single gentle down-line push freezes Tetra ON the thread (pd
    < 1, ~0 lateral drift) -- the arrival the hot EBS terminal glide CANNOT reach (session 49 measured
    it drag her from pd 1.98 to 10.85 LATERALLY as it separates to freeze_ok). Sweeps the arrival
    depth (centre_feet just below the bar) to show the freeze is robust; the lever is the ARRIVAL
    MOMENTUM (near-rest), not the lateral position -- even an off-center rest arrival places clean,
    because a gentle push barely drags, while the -23 glide overshoots and drags ~10 u."""
    idx = int(kw.get('coord', 241))
    placements, _ = seeds.load_placements()
    print("PLACE ON THREAD (milestone 2b, the clean grazing arrival): coord idx %d\n" % idx)
    print("  arrival_cf  freeze pd   lat_drift  centre_feet  freeze_ok  arrival_ok")
    for cf in (74.0, 76.0, 78.0):
        arr = synthetic_frozen_arrival(env, hl, idx, target_cf=cf, lat_off=0.0, momentum='rest')
        p = place_on_thread(arr, hl, placements)
        print("    %5.1f      %6.2f      %+6.3f     %6.1f       %-5s      %s"
              % (cf, p['pd'], p['lat_drift'], p['centre_feet'], p['freeze_ok'], p['arrival_ok']))
    print("\n  => from a near-REST arrival the placing push ejects Tetra ALONG the line, so she freezes\n"
          "     ON-thread (pd < 1, ~0 lateral drift), arrival_ok. Contrast the current terminal's hot\n"
          "     -23 EBS glide, which overshoots and drags her 10.85 u off-thread (session 49). So route\n"
          "     (a)'s chain must decelerate Link to near-rest behind Tetra before the placing push, NOT\n"
          "     sustain the EBS glide -- the concrete next target.")


def _cmd_decel(env, hl, kw):
    """**Route (a), piece 1 demo** (session 50): the DECELERATING on-line placement approach that
    BEATS the s49 grazing barrier. On a SYNTHETIC hot pre-placement (`synthetic_hot_arrival` -- the
    deep-contact, hot, closing arrival the chain terminal produces), it contrasts:
      * the s49 hot glide (`place_on_thread` fed the raw hot arrival) -- drags Tetra LATERALLY;
      * `decel_place` -- kills the EBS (reverse-brake) then glides on-line to near-rest, landing Tetra
        ON the coord with ~0 lateral drift (arrival_ok).
    Sweeps d_short (chain-endpoint variability) to show the recipe is not a single-case tune."""
    idx = int(kw.get('coord', 241))
    placements, _ = seeds.load_placements()
    print("DECEL PLACE (milestone 2b, route a piece 1): coord idx %d\n" % idx)
    print("  d_short |  hot glide (s49): pd    lat_drift | decel_place: pd     lat_drift  cf    aok   frames")
    for d in (30.0, 40.0, 55.0):
        hot = synthetic_hot_arrival(env, hl, idx, d_short=d, feet=64.0)
        raw = place_on_thread(dict(run=hot['run'].clone(), log=[], frames=0), hl, placements)
        r = decel_place(hot, hl, placements, coord_idx=idx)
        print("   %5.0f   |             %6.2f  %+7.3f  |          %6.3f  %+8.4f  %5.1f  %-5s  %d"
              % (d, raw['pd'], raw['lat_drift'], r['pd'], r['lat_drift'],
                 r['centre_feet'], r['arrival_ok'], r['frames']))
    print("\n  => decel_place inverts the s49 failure: the hot glide's miss is LATERAL (it drags Tetra\n"
          "     off the thin thread as it separates), while the decel approach arrives near-rest ON-LINE\n"
          "     so the miss is a clean sub-unit ALONG-line residual (lat_drift ~0), arrival_ok True. It\n"
          "     is the arrival `walk_to_entry` needs; the open piece is feeding it a REAL chain endpoint.")


def _cmd_homing(env, hl, kw):
    """**Route (a), piece 1 demo** (session 51): the HOMING placement terminal that corrects the s44
    lateral OFFSET the on-line `decel_place` cannot. On an OFF-THREAD synthetic hot pre-placement
    (`synthetic_hot_arrival(lat_off=...)` -- Tetra seeded ~28 u off the thread, the state the real
    3-cycle chain endpoint leaves), it contrasts:
      * `decel_place` (s50, on-line herd) -- stalls at the lateral offset (pd ~ the offset);
      * `homing_place` -- aims Link at a moving standoff behind Tetra rel. the coord so the plow pulls
        her ONTO the thread, landing her ON a coord (arrival_ok), the lateral offset nulled.
    Sweeps lat_off (both signs) to show the correction is not a single-case tune."""
    idx = int(kw.get('coord', 241))
    placements, _ = seeds.load_placements()
    print("HOMING PLACE (milestone 2b, route a piece 1): coord idx %d\n" % idx)
    print("  lat_off |  decel_place (s50): pd   lat_drift aok | homing_place (s51): pd   lat_drift aok  frames")
    for lo in (0.0, 28.0, -28.0):
        d = synthetic_hot_arrival(env, hl, idx, d_short=40.0, feet=64.0, lat_off=lo)
        h = synthetic_hot_arrival(env, hl, idx, d_short=40.0, feet=64.0, lat_off=lo)
        rd = decel_place(d, hl, placements, coord_idx=idx)
        rh = homing_place(h, hl, placements, coord_idx=idx)
        print("   %+5.0f  |            %6.2f  %+8.3f %-5s |           %6.3f  %+8.3f %-5s  %d"
              % (lo, rd['pd'], rd['lat_drift'], rd['arrival_ok'],
                 rh['pd'], rh['lat_drift'], rh['arrival_ok'], rh['frames']))
    print("\n  => homing_place corrects the lateral offset the on-line decel cannot: the plow ejects\n"
          "     Tetra AWAY from Link's exec centre, so aiming Link at a standoff behind her RELATIVE to\n"
          "     the coord pushes her toward it in along AND lateral -> she lands ON a coord (arrival_ok)\n"
          "     with the offset nulled (lat_drift cancels the seed). This is the terminal the off-thread\n"
          "     chain endpoint needs; feeding it a REAL ranked chain endpoint closes 2b.")


def _cmd_lat(env, hl, kw):
    """`objective.LATERAL_RATE`'s measurement, reproducible in ~20 s: how much LATERAL a plan can buy
    per frame of terminal glide, against `PUSH_CEILING` for the along axis.

    Sweeps ``feet`` (the contact depth) and not `synthetic_hot_arrival`'s `d_short`/`lat_off`: those
    two translate BOTH actors rigidly, so no relative measurement moves with them at all."""
    placements, _ = seeds.load_placements()
    th = O.placement_thread(hl, placements)
    print("THE LATERAL AUTHORITY (`lateral_authority`) -- what a unit of lateral costs\n")
    print("  along ceiling  %.2f u/frame (`PUSH_CEILING`, the CC split law)" % O.PUSH_CEILING)
    print("  LATERAL_RATE   %.2f u/frame (the worst measured bed below)\n" % O.LATERAL_RATE)
    for feet in (56.0, 64.0, 72.0):
        nd = synthetic_hot_arrival(env, hl, int(kw.get('coord', 287)), d_short=40.0, feet=feet)
        a = lateral_authority(nd['run'], hl)
        print("  hot arrival, Link %2.0f u behind: lateral spread %6.2f u / %d f = %4.2f u/f "
              "[%+7.2f .. %+7.2f], along_max %5.2f u/f  (%d sticks survived)"
              % (feet, a['spread'], a['frames'], a['per_frame'], a['lo'], a['hi'],
                 a['along_max'] / a['frames'], a['n']))
    print("\n  => lateral is ~%.0fx dearer than along, which `plan_bound` (distance / the along"
          % (O.PUSH_CEILING / O.LATERAL_RATE))
    print("     ceiling) prices at 1x. `objective.thread_frames` is the version that counts them")
    print("     apart; the target thread runs along %.1f..%.1f, lateral %+.2f..%+.2f."
          % (th['along_lo'], th['along_hi'], th['lat_lo'], th['lat_hi']))


def _cmd_solve(env, hl, kw):
    """**THE SOLVE, end to end, under the session-60 objective** -- chain, frame-minimal terminal,
    then the acceptance test on the winner's own input log (`objective.replay_and_score` from state 2,
    not the search node, so no beam prune is taken on trust).

    This is the command a session runs and quotes. It prints the frame accounting against the bar and
    where the endpoint sits on the target thread, because those are the two things that decide whether
    a plan is a plan: frames versus the budget, and whether Tetra's LATERAL is inside the window any
    along could place her at (`objective.placement_thread`)."""
    import time
    placements, _ = seeds.load_placements()
    bar = O.frame_floor(env, placements)
    th = O.placement_thread(hl, placements)
    ncyc = int(kw.get('cycles', 3))
    rank = kw.get('rank', 'bound')
    print("SOLVE: %d cycles (rank %s) -> frame-minimal terminal -> the objective\n" % (ncyc, rank))
    print("  bar: floor %d frames, accepted %d, preferred %d (nearest coord idx %d, %.1f u)"
          % (bar['frames_int'], bar['budget'], bar['preferred'], bar['coord']['idx'], bar['dist']))
    print("  target thread: along %.1f..%.1f, lateral %+.2f..%+.2f, %.1f deg off the herd axis\n"
          % (th['along_lo'], th['along_hi'], th['lat_lo'], th['lat_hi'], th['deg_off_axis']))
    t0 = time.perf_counter()
    res = chain_herd(env, hl, ncycles=ncyc, beam=int(kw.get('beam', 8)),
                     jn_keep=int(kw.get('jkeep', 6)), rank=rank,
                     last_rank=kw.get('last_rank', 'thread'), placements=placements,
                     budget=(float(kw['budget']) if 'budget' in kw else None), verbose=True)
    last = res['beams'][-1]
    if not last:
        print("\n  CHAIN STALLED at cycle %d -- read the per-cycle dead counts above (they are split "
              "by reason)" % len(res['beams']))
        return
    tt = terminal_targeting(last, hl, placements, max_frames=int(kw.get('tframes', 12)),
                            beam=int(kw.get('tbeam', 48)),
                            objective=kw.get('terminal', 'thread'), verbose=True)
    win = tt['placed'] or tt.get('closest_atom') or tt['closest']
    print("\n(%.0f s)  terminal: %s" % (time.perf_counter() - t0,
                                        "PLACED at frame %d (the SLAM), %.3f u from coord"
                                        % (win['frames'], win['dist']) if tt['placed'] else
                                        "NOT placed -- closest %.3f u at frame %d"
                                        % (win['dist'], win['frames'])))
    if tt['placed'] and win.get('atom') is not None:
        a = win['atom']
        print("            atom: knobs %s csangle %s resid %.1f u dips %d rec17 f%s "
              "(handoff at plan frame %d)"
              % (a.get('knobs'), a.get('csangle'), a['resid'], len(a['dips']), a['rec17_f'],
                 win.get('handoff_frames', win['frames'])))
    if not tt['placed'] and tt.get('closest_atom') is not None:
        ca = tt['closest_atom']
        print("            closest POST-ATOM placement (rule 3 exact): %.3f u at slam frame %d"
              % (ca['dist'], ca['frames']))
    if not tt['placed'] and tt['closest_ready'] is not None:
        # `closest` is rule-3-blind, and the two disagree (session 63) -- print both frontiers
        cr = tt['closest_ready']
        print("            closest with rule 3-cheap MET (moving): %.3f u at frame %d%s"
              % (cr['dist'], cr['frames'],
                 '  (same state)' if cr['frames'] == win['frames']
                 and abs(cr['dist'] - win['dist']) < 1e-9 else ''))
    # An atom win confirms/scores on its PRE-atom log (the atom ran camera-detached); the
    # acceptance replay's exact rule 3 re-fires the atom from that endpoint.
    if win.get('pre_log') is not None:
        c = confirm_plan(env, hl, dict(win, run=win['pre_run'], log=win['pre_log']))
        sc = O.replay_and_score(env, win['pre_log'], hl=hl, placements=placements)
    else:
        c = confirm_plan(env, hl, win)
        sc = O.replay_and_score(env, win['log'], hl=hl, placements=placements)
    print("  confirm (fresh replay of its own log): bit_exact=%s talk_safe=%s wall_ok=%s -> %s"
          % (c['bit_exact'], c['talk_safe'], c['wall_ok'], 'CONFIRMED' if c['ok'] else 'NOT'))
    print("\n  ACCEPTANCE TEST (`objective.score_plan`):")
    print("    frames %d vs floor %d -> timeloss %+d (budget %+d)"
          % (sc['frames'], sc['floor'], sc['timeloss'], O.TIMELOSS_BUDGET))
    print("    placement %.3f u from coord idx %d -> complete=%s"
          % (sc['placement_dist'], sc['placement_idx'], sc['complete']))
    print("    Tetra along %.1f lat %+.2f -> %+.2f u off the thread, placeable=%s"
          % (sc['tetra_along'], sc['tetra_lat'], sc['lat_error'], sc['placeable']))
    print("    walls %+.1f u (frame %s) | regime %s | terminal speed %.2f ready=%s"
          % (sc['wall_margin'], sc['wall_margin_at'],
             'ok' if sc['regime_ok'] else 'LEFT at %d' % sc['left_regime_at'],
             sc['terminal']['speed'], sc['terminal_ok']))
    print("    frame bound %.1f (`plan_bound`) / %.1f (`thread_cost`)   VERDICT %s"
          % (sc['bound'], sc['thread_bound'], 'PASS' if O.verdict(sc) else 'fail'))
    if 'dump' in kw:
        # persist the whole run: a 3-cycle solve costs ~16 min, and every node's log rebuilds
        # bit-exact (`beam_io`), so the next session continues instead of re-searching.
        from harness.tetrapush import beam_io
        beam_io.dump_beams(kw['dump'], res['beams'] + [[win]], hl, placements)
        print("\n  dumped %d beams + the winner -> %s (rebuild with beam_io.rebuild_beam)"
              % (len(res['beams']), kw['dump']))


def main(argv):
    import warnings
    warnings.simplefilter('ignore')
    env = seeds.load_env()
    hl = HerdLine.from_env(env)
    cmd = argv[0] if argv else 'sep'
    kw = dict(kv.split('=') for kv in argv[1:] if '=' in kv)
    if cmd == 'sep':
        _cmd_sep(env)
    elif cmd == 'box':
        _cmd_box(env, hl)
    elif cmd == 'plan':
        _cmd_plan(env, hl, kw)
    elif cmd == 'endgame':
        _cmd_endgame(env, hl, kw)
    elif cmd == 'walk':
        _cmd_walk(env, hl, kw)
    elif cmd == 'arrivals':
        _cmd_arrivals(env, hl, kw)
    elif cmd == 'place':
        _cmd_place(env, hl, kw)
    elif cmd == 'decel':
        _cmd_decel(env, hl, kw)
    elif cmd == 'homing':
        _cmd_homing(env, hl, kw)
    elif cmd == 'lat':
        _cmd_lat(env, hl, kw)
    elif cmd == 'solve':
        _cmd_solve(env, hl, kw)
    else:
        print("usage: python -m harness.tetrapush.full_herd "
              "{solve | lat | sep | box | plan | endgame | walk | arrivals | place | decel | homing}")


if __name__ == '__main__':
    main(sys.argv[1:])
