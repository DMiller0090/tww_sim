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
from harness.tetrapush import search as S
from harness.tetrapush import two_roll as T
from harness.tetrapush.reposition import HerdLine, ESS_DOWN
from harness.tetrapush.steered_reposition import _bearing, _s16
from harness.tetrapush.from_f0 import _computed_center, cc_push_pair
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


def in_pursuit_box(run, hl, box):
    """Is this coupled state inside the measured pursuit regime (`pursuit_box`)?"""
    lx, lz, tx, tz = run.link.pos_x, run.link.pos_z, run.tx, run.tz
    lead = hl.lead(lx, lz, tx, tz)
    if not (box['lead_lo'] <= lead <= box['lead_hi']):
        return False
    if abs(hl.lateral(lx, lz) - hl.lateral(tx, tz)) > box['max_lat']:
        return False
    return abs(_s16(_bearing((lx, lz), (tx, tz)) - hl.bearing_bam())) <= box['max_delta']


def human_in_box(env, hl, box=None):
    """Containment for the regime gate (`[[search-space-contains-human]]`): the recorded human must
    sit inside the pursuit box on EVERY frame of his window -- the box is read off him, so this
    asserts the margin logic never inverts. Returns ``dict(ok, outside)``."""
    box = pursuit_box(env, hl) if box is None else box
    hb = hl.bearing_bam()
    outside = []
    for r in S.rollout_recorded(env, upto=45)['rows']:
        lx, lz, tx, tz = r['link'][0], r['link'][-1], r['tetra'][0], r['tetra'][-1]
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


def roll_probe(endpoint, hl, *, step=24, l_window=(4, 7), min_roll=20.0, half_window=0x2800):
    """**Is this junction endpoint ROLLABLE at all?** -- a coarse aim sweep returning the best
    surviving roll's down-herd rate, or None.

    This is the endpoint keep's real criterion, because FLATNESS DOES NOT PREDICT IT. Measured over
    three cycle-1 nodes (400 endpoints probed each): 32 / 43 / 71 were rollable, and on the first
    node NONE of them were among the flattest (they sat at |lat| ~17) while on the other two the
    rollable ones were the flattest (|lat| 0.2-0.4). So a flatness keep silently empties the stage on
    some entry states and works on others -- which is exactly how the cycle-2 stage kept reporting
    hundreds of valid-looking endpoints and zero surviving rolls. Probe; do not rank by proxy."""
    best = None
    for (_want, aim) in T.roll_facing_fan(endpoint['run'], hl.bearing_bam(), half_window, step):
        rr = endpoint['run'].clone()
        seg = T.roll_segment(rr, aim, target_cs=None, l_window=l_window)
        if seg['talk_unsafe'] or not seg['ok'] or seg['roll_speedF'] is None \
                or seg['roll_speedF'] < min_roll:
            continue
        m = T.metrics(rr, hl, endpoint['frames'] + seg['frames'])
        if T.alive(m) and (best is None or m['per_frame'] > best):
            best = m['per_frame']
    return best


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


def _frontier_score(hl):
    """The junction frontier's ranking: get Link's facing OUT of the +-90 deg talk/target cone
    first (that is the gate that blocks arming), then hug the herd line.

    Ranking on |lat| ALONE is myopic in exactly the wrong direction -- the flattest states are the
    ones still facing Tetra, which can never arm, so they crowd out the productive branch. Measured:
    a beam of 16 then found ZERO endpoints where a beam of 12 found 162 (a wider beam finding
    strictly less is the tell)."""
    def score(n):
        r = n['run']
        tb = _bearing((r.link.pos_x, r.link.pos_z), (r.tx, r.tz))
        deficit = max(0, 0x4000 - abs(_s16(r.link.facing - tb)))
        lat = abs(hl.lateral(r.link.pos_x, r.link.pos_z) - hl.lateral(r.tx, r.tz))
        return (deficit, lat)
    return score


def junction_beam(node, hl, box, *, max_frames=12, beam=24, ess_step=1, aim_step=16,
                  keep=12, collect=None, dead=None):
    """**The junction as a per-frame BEAM, not an enumerated family.** The atom is one frame's
    (stick, L): each generation extends every live node by the whole alphabet
    (`junction_alphabet`), prunes anything that leaves the pursuit box, dedups by state, and keeps
    ``beam``. Any node that also passes `two_roll.junction_gates` is collected as a usable endpoint.

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
    dead = {} if dead is None else dead
    for _f in range(int(max_frames)):
        nxt, seen = [], set()
        for nd in live:
            # the alphabet is state-dependent (the arming stick aims at Tetra from HERE)
            for (sx, sy) in junction_alphabet(nd['run'], hl, ess_step=ess_step,
                                              aim_step=aim_step):
                for l in (0, 1):
                    r = nd['run'].clone()
                    d = dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                             triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL, substickY=0)
                    r.step(d)
                    if r._follow_warned or not in_pursuit_box(r, hl, box):
                        dead['outbox'] = dead.get('outbox', 0) + 1
                        continue
                    jf = nd['jf'] + 1
                    tag = (round(r.link.pos_x, 1), round(r.link.pos_z, 1), r.link.facing >> 5,
                           round(r.link.speedF, 2), r.link.state, sx, sy, l)
                    if tag in seen:
                        continue
                    seen.add(tag)
                    cand = dict(run=r, log=nd['log'] + [d], jf=jf)
                    nxt.append(cand)
                    why = T.junction_gates(r, hl, node['frames'] + jf)
                    dead[why or 'ENDPOINT'] = dead.get(why or 'ENDPOINT', 0) + 1
                    if why is None:
                        e = dict(cand)
                        e['m'] = T.metrics(r, hl, node['frames'] + jf)
                        e['frames'] = node['frames'] + jf
                        e['jv'] = dict(kind='beam', phases=T._fit_phases(e['log'][-jf:]))
                        ends.append(e)
                        if collect is not None:
                            collect.append(e)
        # cone deficit first, then flatness (see `_frontier_score`)
        nxt.sort(key=_frontier_score(hl))
        live = nxt[:int(beam)]
        if not live:
            break
    # MIXED keep (the s42 lesson): half by flatness, half by shortness -- neither ranking alone
    # keeps the survivors. `extend_cycle` re-keeps by ROLLABILITY, which is stronger than both.
    ends.sort(key=lambda e: (abs(e['m']['lat']), e['jf']))
    flat = ends[:int(keep) - int(keep) // 2]
    rest = [e for e in ends if e not in flat]
    rest.sort(key=lambda e: (e['jf'], abs(e['m']['lat'])))
    return flat + rest[:int(keep) // 2]


def junction_quality(run, hl, box, *, frames=6, sticks=None):
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
    best = None
    for st in sticks:
        r = run.clone()
        inbox = 0
        for _ in range(int(frames)):
            r.step(dict(stickX=st[0], stickY=st[1], buttons=0, triggerL=0,
                        substickX=T.CSTICK_NEUTRAL, substickY=0))
            if r._follow_warned or not in_pursuit_box(r, hl, box):
                break
            inbox += 1
        if inbox < 2:
            continue
        lat = abs(hl.lateral(r.link.pos_x, r.link.pos_z) - hl.lateral(r.tx, r.tz))
        score = (-inbox, lat)
        if best is None or score < best:
            best = score
    return best


def roll_candidates(node, hl, box, *, half_window=0x2800, step=8, l_windows=((4, 7), (5, 8)),
                    aim_keep=3, min_roll=20.0, tcs_keep=3, target_css=None,
                    fan_center=None, require_quality=True):
    """The cycle's ROLL stage from a junction endpoint, factored by the separability above.

    R1: sweep the reachable aim fan (camera frozen) x the L windows, prune talk-unsafe / weak /
    off-line, keep the ``aim_keep`` best by chained down-herd rate.
    R2: re-run each kept aim over the DERIVED `target_cs` grid and keep the ``tcs_keep`` camera
    targets whose endpoint the NEXT junction can actually continue from, ranked by
    `junction_quality` -- a tcs that strands the plan is worthless however fast the roll was.

    Returns the surviving post-roll nodes (each ``dict(run, log, frames, m, knobs, quality)``)."""
    out = []
    r1 = []
    center = hl.bearing_bam() if fan_center is None else int(fan_center)
    for (want, aim) in T.roll_facing_fan(node['run'], center, half_window, step):
        for lw in l_windows:
            rr = node['run'].clone()
            seg = T.roll_segment(rr, aim, target_cs=None, l_window=lw)
            if seg['talk_unsafe'] or not seg['ok'] or seg['roll_speedF'] is None \
                    or seg['roll_speedF'] < min_roll:
                continue
            fr = node['frames'] + seg['frames']
            m = T.metrics(rr, hl, fr)
            if not T.alive(m):
                continue
            r1.append((m['per_frame'], want, aim, lw, seg))
    r1.sort(key=lambda t: -t[0])
    for (_pf, want, aim, lw, _seg) in r1[:int(aim_keep)]:
        css = derived_target_css(node['run']) if target_css is None else target_css
        graded = []
        for tcs in css:
            rr = node['run'].clone()
            log = list(node['log'])
            seg = T.roll_segment(rr, aim, target_cs=tcs, l_window=lw, log=log)
            if seg['talk_unsafe'] or not seg['ok'] or seg['roll_speedF'] is None \
                    or seg['roll_speedF'] < min_roll:
                continue
            fr = node['frames'] + seg['frames']
            m = T.metrics(rr, hl, fr)
            if not T.alive(m):
                continue
            q = junction_quality(rr, hl, box)
            if q is None and require_quality:     # this camera target strands the plan next cycle
                continue                          # (a TERMINAL roll has no next cycle to strand)
            graded.append((q, dict(run=rr, log=log, frames=fr, m=m, quality=q,
                                   knobs=dict(roll_bam=want, aim=aim, l_window=lw, target_cs=tcs,
                                              roll_speedF=seg['roll_speedF'], jframes=node['jf'],
                                              junction=node['jv']['kind'],
                                              phases=node['jv']['phases']))))
        # unscored (quality None) only occurs on a terminal roll -- rank those by herd rate
        graded.sort(key=lambda t: t[0] if t[0] is not None
                    else (0, -t[1]['m']['per_frame']))
        out.extend(n for _q, n in graded[:int(tcs_keep)])
    return out


# --------------------------------------------------------------------------- the N-cycle chain

def _state_tag(run):
    """Beam dedup key: the coupled state at a cycle boundary, coarse enough to collapse duplicates
    and fine enough to keep genuinely different plans (the same granularity the junction stage
    uses)."""
    return (round(run.link.pos_x, 1), round(run.link.pos_z, 1), run.link.facing >> 5,
            round(run.link.speedF, 2), round(run.tx, 1), round(run.tz, 1), int(run.csangle) >> 5)


def extend_cycle(nodes, hl, box, *, jn_keep=6, jn_beam=24, ess_step=1, aim_step=16,
                 max_frames=12, beam=8, aim_keep=3, half_window=0x2800, step=8,
                 probe_cap=250, verbose=False):
    """One chained cycle applied to a whole beam: the junction stage (`junction_beam`), whose
    endpoints are kept by ROLLABILITY (`roll_probe` -- not flatness, which measurably selects
    unrollable states), followed by the roll stage (`roll_candidates`), deduped by state and cut to
    ``beam`` by down-herd rate.

    Every node carries its FULL delivered input log, so any survivor is replayable end-to-end on a
    fresh `FreeRun` (`confirm_plan`)."""
    out = []
    jdead = {}
    for node in nodes:
        ends = junction_beam(node, hl, box, max_frames=max_frames, beam=jn_beam,
                             ess_step=ess_step, aim_step=aim_step, keep=10 ** 6, dead=jdead)
        uniq = _dedup_endpoints(ends)
        if len(uniq) > int(probe_cap):
            # never a silent truncation: say what was dropped
            if verbose:
                print("    (probing %d of %d unique endpoints -- capped)"
                      % (probe_cap, len(uniq)))
            uniq = uniq[:int(probe_cap)]
        scored = [(p, e) for p, e in ((roll_probe(e, hl), e) for e in uniq) if p is not None]
        scored.sort(key=lambda t: -t[0])
        kept = [e for _p, e in scored[:int(jn_keep)]]
        jdead['unrollable'] = jdead.get('unrollable', 0) + (len(uniq) - len(scored))
        for j in kept:
            for cand in roll_candidates(j, hl, box, aim_keep=aim_keep, half_window=half_window,
                                        step=step):
                cand['plan'] = list(node.get('plan', [])) + [cand['knobs']]
                out.append(cand)
    # rate first, then continuability -- a faster cycle that strands the plan is worth less than a
    # marginally slower one the next junction can pick up (the s42 entry-state lesson).
    out.sort(key=lambda n: (-n['m']['per_frame'], n.get('quality')))
    seen, beamed = set(), []
    for n in out:
        t = _state_tag(n['run'])
        if t in seen:
            continue
        seen.add(t)
        beamed.append(n)
        if len(beamed) >= int(beam):
            break
    if verbose:
        print("    -> %d roll survivors, %d after dedup/beam (junction dead: %s)"
              % (len(out), len(beamed), ' '.join('%s=%d' % kv for kv in sorted(jdead.items()))))
    return beamed


def cycle1_nodes(env, hl, box, *, nflips=(1, 2, 3), flip_msd=1.0, half_window=0x2000, step=4,
                 l_windows=((5, 8), (4, 7), (6, 9)), aim_keep=4, beam=8,
                 tcs_keep=3, verbose=False):
    """Cycle 1 from state 2, FACTORED like every later cycle (`roll_candidates`) rather than as the
    s42 full aim x tcs cross product -- same search space, ~20x fewer rollouts (159 s -> 10 s for
    the identical 13.147 u/f best), and the `target_cs` values are ranked by `junction_quality`
    instead of by a roll rate they provably cannot affect.

    At state 2 Tetra is ~122 deg BEHIND Link (out of the +-90 cone), so the L-held flip prologue
    re-targets straight into the proc-7 flip -- no turnaround is needed to start."""
    dtm = seeds.dtm_input_at(env)
    out = []
    for nflip in nflips:
        base = seeds.make_freerun(env)
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
                                tcs_keep=tcs_keep)
        for c in cands:
            c['knobs']['nflip'] = nflip
            c['plan'] = [c['knobs']]
        if verbose:
            print("  nflip=%d: preroll %+.2f -> %d cycle-1 survivors"
                  % (nflip, base.link.speedF, len(cands)))
        out.extend(cands)
    # rate first, then continuability -- a faster cycle that strands the plan is worth less than a
    # marginally slower one the next junction can pick up (the s42 entry-state lesson).
    out.sort(key=lambda n: (-n['m']['per_frame'], n.get('quality')))
    seen, beamed = set(), []
    for n in out:
        t = _state_tag(n['run'])
        if t in seen:
            continue
        seen.add(t)
        beamed.append(n)
        if len(beamed) >= int(beam):
            break
    return beamed


def chain_herd(env, hl, *, ncycles=3, c1_beam=8, beam=8, jn_keep=6, aim_keep=3,
               c1_step=4, jn_beam=24, ess_step=1, nodes=None, box=None, verbose=False):
    """**The full-herd chain**: cycle 1 from state 2 (`cycle1_nodes`), then ``ncycles - 1``
    applications of `extend_cycle`, every cycle sweeping its OWN derived `target_cs` grid.

    Returns ``dict(beams, best, bar, box)`` -- the per-cycle beams (so a stalled cycle is
    diagnosable), the best final node, the human's 2-roll rate, and the pursuit box in force."""
    import time
    t0 = time.perf_counter()
    box = pursuit_box(env, hl) if box is None else box
    if nodes is None:
        nodes = cycle1_nodes(env, hl, box, step=c1_step, beam=c1_beam,
                             aim_keep=aim_keep + 1, verbose=verbose)
    beams = [nodes]
    if verbose:
        print("  cycle 1: %d nodes, best %.3f u/f (%.1f s)"
              % (len(nodes), nodes[0]['m']['per_frame'] if nodes else 0.0,
                 time.perf_counter() - t0))
    for c in range(2, int(ncycles) + 1):
        t1 = time.perf_counter()
        nodes = extend_cycle(nodes, hl, box, jn_keep=jn_keep, jn_beam=jn_beam,
                             ess_step=ess_step, beam=beam, aim_keep=aim_keep, verbose=verbose)
        beams.append(nodes)
        if verbose:
            print("  cycle %d: %d nodes, best %.3f u/f, herd %.1f u in %d f (%.1f s)"
                  % (c, len(nodes), nodes[0]['m']['per_frame'] if nodes else 0.0,
                     nodes[0]['m']['herd'] if nodes else 0.0,
                     nodes[0]['frames'] if nodes else 0, time.perf_counter() - t1))
        if not nodes:
            break
    return dict(beams=beams, best=(nodes[0] if nodes else None), box=box,
                bar=T.human_baseline(env, hl)['per_frame'])


# --------------------------------------------------------------------------- confirm / placement

def confirm_plan(env, hl, node, want_rolls=None):
    """**The winner-confirmation gate, generalized to N rolls** (`two_roll.confirm_chain` is the
    2-roll case): re-run the node's own delivered input log on a FRESH self-contained `FreeRun` and
    require the endpoint to be BIT-IDENTICAL to the search's node -- both actors' positions, Link's
    facing, csangle -- with every grounded A-press talk-safe and the whole log in the plow regime."""
    run = seeds.make_freerun(env)
    dtm = seeds.dtm_input_at(env)
    run.pre_seed_input(dtm(0))
    rolls, in_roll, talk_safe = 0, False, True
    for d in node['log']:
        if S.a_press_is_talk(run, d):
            talk_safe = False
        run.step(d)
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
    ok = bit_exact and talk_safe and not run._follow_warned
    if want_rolls is not None:
        ok = ok and rolls == int(want_rolls)
    return dict(ok=ok, per_frame=herd / frames if frames else 0.0, frames=frames, rolls=rolls,
                herd=herd, talk_safe=talk_safe, bit_exact=bit_exact)


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
    cx = _computed_center(run.link, init_frame=False)
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

    The result is exactly the arrival `arrival_quality` gates for and `walk_to_entry` needs: Tetra ON
    a coord, `freeze_ok`, Link near-rest on-line-behind. Returns
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


def synthetic_hot_arrival(env, hl, coord_idx=241, *, d_short=40.0, feet=64.0):
    """**A SYNTHETIC below-the-bar HOT pre-placement, the state the grazing chain terminal produces**
    (session 50): Link in the hot post-untarget EBS, ON the herd line ``feet`` u BEHIND Tetra, with
    Tetra ``d_short`` u UP-herd (short) of genuine coord ``coord_idx`` -- the deep-contact, closing
    arrival whose hot glide s49 showed drags Tetra laterally. It is the testbed `decel_place` must
    beat, the hot counterpart of `synthetic_frozen_arrival` (which mints the ABOVE-the-bar frozen
    arrival for the walk). Relocation only (position does not feed anim/momentum), so it is
    self-consistent but NOT reachable by a state-2 input log -- it gates the decel recipe's
    physics/regime, not a bit-confirm. Returns a ``placed`` node (``dict(run, log=[], frames=0))``."""
    from harness.tetrapush.reposition import seed_to_untarget
    import tww_sim.core.fp as fp
    placements, _ = seeds.load_placements()
    p = placements[coord_idx]
    tx = float(p['x']) - d_short * hl.dx
    tz = float(p['z']) - d_short * hl.dz
    run, _aim = seed_to_untarget(env)                       # the hot post-untarget EBS
    run.link.pos_x = fp.f32(tx - feet * hl.dx)
    run.link.pos_z = fp.f32(tz - feet * hl.dz)
    run.tx, run.tz = fp.f32(tx), fp.f32(tz)
    cx = _computed_center(run.link, init_frame=False)
    run.pend_link, run.pend_tetra = cc_push_pair(cx, (run.tx, run.tz))
    run._follow_warned = False
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
        run.link.pos_x = fp.f32(tx - feet * hl.dx + lat_off * hl.px)
        run.link.pos_z = fp.f32(tz - feet * hl.dz + lat_off * hl.pz)
        run.tx, run.tz = fp.f32(tx), fp.f32(tz)

    lo, hi = 60.0, 150.0                                 # centre_feet is monotone in feet
    for _ in range(44):
        mid = 0.5 * (lo + hi)
        place(mid)
        if _centre_feet(run) < target_cf:
            lo = mid
        else:
            hi = mid
    place(0.5 * (lo + hi))
    cx = _computed_center(run.link, init_frame=False)
    run.pend_link, run.pend_tetra = cc_push_pair(cx, (run.tx, run.tz))
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


def _terminal_score(run, hl, placements, objective, w_deficit, w_approach):
    """The terminal beam's rank key. ``'placement'`` (the s44 default) = pure Tetra->coord distance,
    the deepest-contact lander. ``'grazing'`` (route a, session 48) additionally penalises the
    coupled-entry `deficit` (`CO_RADII_BAR - centre_feet`, below the bar) and a closing
    `approach_rate`, so the endpoint the beam seeks is on-thread AND freeze_ok AND near-rest --
    the arrival `walk_to_entry` needs, not merely the closest coord. Returns ``(score, placement)``;
    in placement mode ``score == placement`` so the existing rank is byte-for-byte unchanged."""
    pd = _placement_dist(run, placements)
    if objective == 'placement':
        return pd, pd
    deficit = max(0.0, CO_RADII_BAR - _centre_feet(run))
    return pd + w_deficit * deficit + w_approach * max(0.0, _approach_rate(run)), pd


def terminal_targeting(nodes, hl, placements=None, *, max_frames=18, beam=64,
                       n_dirs=24, objective='placement', w_deficit=1.0, w_approach=2.0,
                       verbose=False):
    """**The TERMINAL cycle, ranked by PLACEMENT distance instead of u/frame** -- the endgame stage
    the chain hands off to once one more full roll would OVERSHOOT the cluster.

    ``objective`` selects the rank (`_terminal_score`): the s44 ``'placement'`` (nearest coord, the
    deep-contact lander) or ``'grazing'`` (route a, session 48) -- the same beam, but ranked to seek
    an on-thread endpoint that is ALSO `freeze_ok` and near-rest, the coupled-entry arrival
    `walk_to_entry` needs. Grazing is the rank the re-ranked chain will inherit; run here it MEASURES
    how close the terminal alone can graze from a given endpoint (s46: from the deep 3-cycle endpoint
    it cannot -- the grazing term belongs on the chain).

    The geometry forces this (`endgame_geom`): each full cycle herds ~280 u but only ~99 u along
    (and a ~28 u lateral correction) separate the 3-cycle endpoint from the nearest coord, so a full
    +26 roll lands Tetra PAST every coord -- worse than not rolling. What is controllable at this
    range is the plow GLIDE: Link stays in contact (dist < 80) through the junction, so a metered
    glide keeps herding Tetra down-line at ~13 u/frame AND steers her lateral (push ejects her away
    from Link's centre, so approaching from the high-lateral side pulls her back toward the line).

    So this is a per-frame BEAM (the atom is one frame's (stick, L), as in `junction_beam`) ranked by
    the CURRENT Tetra-to-nearest-coord distance, tracking the global closest state reached at ANY
    frame (a glide sweeps THROUGH the coord band, so the best endpoint is mid-glide, not at the
    horizon). Returns ``dict(best, dist, per_node)`` -- the closest terminal node (with its full
    input log, so `confirm_plan` replays it end-to-end), its coord distance, and the best per start
    node.

    **Why the prune is REGIME-ONLY, not the pursuit box** (measured, `probe_glide`): the deepest
    approach happens AFTER Link overtakes Tetra and leaves the box -- e.g. a plain (111,111) glide off
    the 3-cycle endpoint carries her from 74.7 u to **6.4 u**, but the minimum lands at f8 when Link
    is already lead +18 (out of the box). The pursuit box exists to keep a posture for the NEXT roll;
    the terminal has none, so the only hard constraint is staying in the stt-3 plow regime (Tetra must
    not start FOLLOWING) and talk-safety (there is no A-press in a glide, so it holds trivially)."""
    if placements is None:
        placements, _ = seeds.load_placements()
    best = None
    per_node = []
    for node in nodes:
        s0, d0 = _terminal_score(node['run'], hl, placements, objective, w_deficit, w_approach)
        node_best = dict(run=node['run'], log=node['log'], frames=node['frames'], dist=d0,
                         score=s0, plan=node.get('plan', []))
        if best is None or s0 < best['score']:
            best = node_best
        live = [dict(run=node['run'], log=node['log'], frames=node['frames'])]
        for _f in range(int(max_frames)):
            nxt, seen = [], set()
            for nd in live:
                for (sx, sy) in _terminal_alphabet(nd['run'], hl, n_dirs=n_dirs):
                    for l in (0, 1):
                        r = nd['run'].clone()
                        d = dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                                 triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL, substickY=0)
                        r.step(d)
                        if r._follow_warned:           # regime only -- see the docstring
                            continue
                        tag = (round(r.link.pos_x, 1), round(r.link.pos_z, 1),
                               r.link.facing >> 5, round(r.link.speedF, 2),
                               round(r.tx, 1), round(r.tz, 1))
                        if tag in seen:
                            continue
                        seen.add(tag)
                        score, dist = _terminal_score(r, hl, placements,
                                                      objective, w_deficit, w_approach)
                        cand = dict(run=r, log=nd['log'] + [d], frames=nd['frames'] + 1,
                                    dist=dist, score=score)
                        nxt.append(cand)
                        if score < best['score']:
                            best = dict(cand, plan=node.get('plan', []))
                        if score < node_best['score']:
                            node_best = dict(cand, plan=node.get('plan', []))
            nxt.sort(key=lambda c: c['score'])
            live = nxt[:int(beam)]
            if not live:
                break
        per_node.append(node_best)
        if verbose:
            print("    start dist %.1f -> best %.1f (%d frames)"
                  % (d0, node_best['dist'], node_best['frames']))
    return dict(best=best, dist=best['dist'] if best else None, per_node=per_node)


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
    else:
        print("usage: python -m harness.tetrapush.full_herd "
              "{sep | box | plan | endgame | walk | arrivals | place | decel}")


if __name__ == '__main__':
    main(sys.argv[1:])
