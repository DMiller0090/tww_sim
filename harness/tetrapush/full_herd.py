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

Pure stdlib, no Dolphin. CLI: ``python -m harness.tetrapush.full_herd {sep | box | plan}``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import search as S
from harness.tetrapush import two_roll as T
from harness.tetrapush.reposition import HerdLine, ESS_DOWN
from harness.tetrapush.steered_reposition import _bearing, _s16
from tww_sim.land.land import FRONT_ROLL
from tww_sim.land.plan_land._primitives import stick_for_bearing

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
    else:
        print("usage: python -m harness.tetrapush.full_herd {sep | box | plan}")


if __name__ == '__main__':
    main(sys.argv[1:])
