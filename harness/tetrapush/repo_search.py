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
"""The FRAME-MINIMAL ON-LINE reposition SEARCH for the Courtyard Tetra push (session 34+).

Session 34 re-diagnosis (`_notes/tetrapush-session34-rediagnosis.md`, `[[courtyard-tetra-push]]`):
the session-33 turnaround-roll primitive is a DEAD END for on-line placement (validity sweep:
worst_lead >= +235 for EVERY (nflip, aim, csangle) -- the roll shoves Tetra sideways and overshoots),
and neither the from-scratch fixed-stick curve nor a replay of the human's recorded reposition chains
a valid on-line cycle. The reposition is a STATE-ADAPTIVE, razor-margin control problem: from each
cycle's actual post-roll untarget state, the backslide must rotate facing ~110-120 deg off the bearing
to Tetra (so she leaves the +-90 deg cone -> the L-retarget gives the proc-7 +18 DIR_BACKWARD flip and
the A-roll is talk-safe, NOT the actor-locked +12 slide) WHILE holding Link on the herd line behind her
(lat ~ 0, lead < 0) and PRESERVING the -25.4 EBS speed -- then a +26 roll aimed along the herd line is
a self-stabilising pursuit (dist 40-85, never overtakes).

Dereck's session-34 steers, encoded here as the search design:
  * **Closed-loop, per-frame adaptive.** The ESS angle (and csangle) are chosen EACH FRAME from the
    actual state -- not a fixed macro. This is a per-frame beam over the reposition inputs.
  * **FINE granularity.** The on-line window is narrow (the human's chain hinges on a ~650-BAM csangle
    difference); coarse sampling misses it. The beam sweeps aim in small BAM steps + a csangle vernier.
  * **csangle is an active lever** (inject a schedule; map to a C-stick via the wired LandCamera later).
  * **PRUNE speed drops.** A steering input that brakes the -25.4 backslide (speedF toward 0) is
    physically dead (a stalled backslide cannot herd) -- pruned hard, collapsing the search to the
    speed-preserving manifold.

Built on the 0-ULP `from_f0.FreeRun` (fidelity is `test_from_f0`'s) + `reposition.HerdLine` + the
`search` talk gate. Pure stdlib, no Dolphin.
CLI: ``python -m harness.tetrapush.repo_search {curve|cycle|chain}``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import search as S
from harness.tetrapush.reposition import HerdLine
from tww_sim.land.plan_land._primitives import stick_for_bearing
from tww_sim.land.land import FRONT_ROLL

# Speed-preservation prune: the -25.4 EBS backslide. A curve input that drops |speedF| below this is
# braking (Dereck steer s34) -> pruned. The human's preserved backslide holds ~-25.3 (decays ~0.01/f).
PRESERVE_MIN = 24.0                 # |speedF| must stay >= this during the curve
CONE_HALF = 0x4000                  # Tetra's +-90 deg attention/talk cone (front-of-player)
CSTICK_NEUTRAL = (128, 128)


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def _bearing_bam(ax, az, bx, bz):
    return int(math.atan2(bx - ax, bz - az) / (2.0 * math.pi) * 65536.0) & 0xFFFF


def cone_off(run):
    """|facing - bearing(Link->Tetra)| in BAM. > CONE_HALF == Tetra is OUT of Link's front cone
    (the L-retarget then gives proc-7 not the actor lock, and the A-roll press is talk-safe)."""
    bear = _bearing_bam(run.link.pos_x, run.link.pos_z, run.tx, run.tz)
    return abs(_s16(run.link.facing - bear))


def metrics(run, hl):
    lx, lz = run.link.pos_x, run.link.pos_z
    return dict(lead=hl.lead(lx, lz, run.tx, run.tz),
                lat=hl.lateral(lx, lz) - hl.lateral(run.tx, run.tz),
                dist=math.hypot(lx - run.tx, lz - run.tz),
                coff=cone_off(run), spF=run.link.speedF, facing=run.link.facing,
                proc=run.link.state)


# --------------------------------------------------------------------------- per-frame curve beam

def _curve_candidates(run, *, aim_span, aim_step, msd_levels, cs_offsets, lockL=True):
    """FINE per-frame candidate inputs for the curve: aim (the stick world-target m34E8) swept in
    small BAM steps around the current travel (the preserve zone -- m34E8 near travel keeps
    cos(m34E8-travel) ~ 1), at several msd magnitudes, with a csangle vernier. Realized via the
    gated `stick_for_bearing` inverse. C-stick neutral (csangle injected). Yields (csangle, input).

    When ``lockL`` also yields L-held (soft-lock) variants: holding L freezes facing to m34E6
    (`checkAttentionLock` = ... || AttnFlag_20000000, the soft-lock; the facing chase gates on
    !checkAttentionLock) WITHOUT actor-locking while Tetra is out of cone -- so facing can stop
    rotating (freeze out-of-cone) while the backslide continues and the bearing to Tetra shifts,
    growing cone_off with NO further lat drift. This is the human's mechanic (session-34 lever)."""
    base_cs = run.csangle
    tv = run.link.travel
    for cs_off in cs_offsets:
        cs = (base_cs + cs_off) & 0xFFFF
        d = -aim_span
        while d <= aim_span:
            aim = (tv + d) & 0xFFFF
            for msd in msd_levels:
                sx, sy = stick_for_bearing(aim, cs, msd=msd)
                yield cs, dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                               substickX=CSTICK_NEUTRAL[0], substickY=CSTICK_NEUTRAL[1])
                if lockL:
                    yield cs, dict(stickX=sx, stickY=sy, buttons=0x40, triggerL=255,
                                   substickX=CSTICK_NEUTRAL[0], substickY=CSTICK_NEUTRAL[1])
            d += aim_step


def _setup_cost(m, hl, *, target_coff, lat_w, lead_lo, lead_hi):
    """Cost of a curve state toward the SETUP: facing out-of-cone (coff >= target_coff), lat ~ 0,
    lead in [lead_lo, lead_hi] (behind Tetra, not too far). Lower = closer to a launchable roll."""
    coff_deficit = max(0, target_coff - m['coff'])
    lead_pen = 0.0
    if m['lead'] > lead_hi:
        lead_pen = (m['lead'] - lead_hi)
    elif m['lead'] < lead_lo:
        lead_pen = (lead_lo - m['lead'])
    return coff_deficit / 256.0 + lat_w * abs(m['lat']) + lead_pen


def curve_beam(entry_run, hl, *, max_frames=10, beam_w=48, aim_span=0x1800, aim_step=0x180,
               msd_levels=(0.056, 0.10, 0.18, 0.30), cs_offsets=(-256, 0, 256),
               target_coff=0x4200, lat_w=1.0, lead_lo=-90.0, lead_hi=-30.0, verbose=False):
    """Per-frame beam over speed-preserving backslide inputs to reach the SETUP state (facing
    out-of-cone, lat ~ 0, lead behind). Returns setup nodes sorted by cost, each
    ``dict(run, cost, nf, hist)``. PRUNES (hard): speed drop below PRESERVE_MIN, overtake (lead >= 0),
    leaving the plow regime. This is the closed-loop adaptive curve (Dereck s34)."""
    beam = [dict(run=entry_run.clone(), cost=1e9, nf=0, hist=[])]
    setups = []
    for frame in range(max_frames):
        nxt = []
        for node in beam:
            for cs, inp in _curve_candidates(node['run'], aim_span=aim_span, aim_step=aim_step,
                                             msd_levels=msd_levels, cs_offsets=cs_offsets):
                c = node['run'].clone()
                c.step(inp, csangle=cs)
                if abs(c.link.speedF) < PRESERVE_MIN:      # PRUNE: braked the backslide
                    continue
                m = metrics(c, hl)
                if m['lead'] >= 0.0:                        # PRUNE: overtook Tetra
                    continue
                if c._follow_warned:                        # PRUNE: left the plow regime
                    continue
                cost = _setup_cost(m, hl, target_coff=target_coff, lat_w=lat_w,
                                   lead_lo=lead_lo, lead_hi=lead_hi)
                nd = dict(run=c, cost=cost, nf=node['nf'] + 1, hist=node['hist'] + [(cs, inp)])
                nxt.append(nd)
                if m['coff'] >= target_coff and abs(m['lat']) <= 6.0 and lead_lo <= m['lead'] <= lead_hi:
                    setups.append(nd)
        if not nxt:
            break
        # dedup-ish by (rounded facing, rounded lat) to keep the beam diverse, then keep best
        nxt.sort(key=lambda n: n['cost'])
        seen = set()
        beam = []
        for n in nxt:
            m = metrics(n['run'], hl)
            key = (m['facing'] >> 8, round(m['lat']), round(m['lead'] / 5))
            if key in seen:
                continue
            seen.add(key)
            beam.append(n)
            if len(beam) >= beam_w:
                break
        if verbose:
            b = beam[0]
            mb = metrics(b['run'], hl)
            print("  curve f%d: %d cand, best cost %.2f (coff %d lat %+.1f lead %+.1f spF %.2f)"
                  % (frame + 1, len(nxt), b['cost'], mb['coff'], mb['lat'], mb['lead'], mb['spF']))
    setups.sort(key=lambda n: (n['nf'], n['cost']))       # fewest frames, then closest to ideal
    return setups, beam


# --------------------------------------------------------------------------- flip + on-line roll

def flip_roll(setup_run, hl, *, aim, nflip=3, release_at=15.0, max_roll=24):
    """From a curve SETUP state (facing out-of-cone), fire the talk-safe re-roll: hold L + stick
    toward ``aim`` for ``nflip`` frames (the proc-7 DIR_BACKWARD +18 flip -> positive pre-roll speedF
    so the roll clamps to +26, not the +5 graze), then A-roll toward ``aim`` (talk-safe iff facing is
    still out-of-cone at the press), ride the roll (release L ``release_at`` frames in for the next
    untarget). Advances a CLONE. Returns metrics incl. ``worst_lead`` (>0 == overtook), ``talk``,
    ``roll_spF``, per-frame ``rows``, ``herd`` (down-herd landing), ``nf`` (frames)."""
    r = setup_run.clone()
    cs = r.csangle
    rows = []
    talk = False

    def _sf(msd=1.0):
        return stick_for_bearing(aim, cs, msd=msd)

    def _log():
        m = metrics(r, hl)
        rows.append(m)

    for _ in range(nflip):
        sx, sy = _sf()
        r.step(dict(stickX=sx, stickY=sy, buttons=0x40, triggerL=255,
                    substickX=128, substickY=128), csangle=cs)
        _log()
    preroll = r.link.speedF
    sx, sy = _sf()
    d_roll = dict(stickX=sx, stickY=sy, buttons=0x100, triggerL=0, substickX=128, substickY=128)
    if S.a_press_is_talk(r, d_roll):
        talk = True
    r.step(d_roll, csangle=cs)
    _log()
    seen = r.link.state == FRONT_ROLL
    roll_spF = r.link.speedF if seen else None
    ended = False
    for _ in range(max_roll):
        sx, sy = _sf()
        in_roll = r.link.state == FRONT_ROLL
        rf = getattr(r.link, 'roll_frame', 0.0)
        hold = in_roll and rf < release_at
        r.step(dict(stickX=sx, stickY=sy, buttons=0x40 if hold else 0,
                    triggerL=255 if hold else 0, substickX=128, substickY=128), csangle=cs)
        _log()
        if r.link.state == FRONT_ROLL:
            seen = True
            if roll_spF is None:
                roll_spF = r.link.speedF
        elif seen and r.link.state == 6:
            ended = True
            break
    worst_lead = max((m['lead'] for m in rows), default=None)
    return dict(run=r, rows=rows, preroll=preroll, roll_spF=roll_spF, talk=talk,
                worst_lead=worst_lead, ended=ended, nf=len(rows),
                herd=hl.along(r.tx, r.tz), followed=r._follow_warned)


def _cmd_cycle(env, kw):
    """Curve to the out-of-cone setup, then sweep the flip+roll aim FINELY and report which (if any)
    stays on-line (worst_lead < 0). Tests whether an on-line roll launches from the out-of-cone
    setups the curve can reach."""
    import warnings
    warnings.simplefilter('ignore')
    hl = HerdLine.from_env(env)
    down = hl.bearing_bam()
    run, _ = _entry(env)
    setups, beam = curve_beam(run, hl, max_frames=int(kw.get('frames', 10)),
                              beam_w=int(kw.get('beam', 48)), target_coff=CONE_HALF)
    # relaxed: also take out-of-cone beam nodes (any lat) as launch candidates
    pool = setups or [n for n in beam if metrics(n['run'], hl)['coff'] >= CONE_HALF]
    if not pool:
        pool = beam[:6]
    print("launch pool: %d nodes (coff out-of-cone). Sweeping flip+roll aim per node:\n" % len(pool))
    print("  nf_curve coff lat  lead | aim_off nflip roll_spF talk  worst_lead herd  ended")
    best = None
    for nd in pool[:6]:
        m = metrics(nd['run'], hl)
        for aim_off in range(-2000, 2001, 250):
            for nflip in (3,):
                res = flip_roll(nd['run'], hl, aim=(down + aim_off) & 0xFFFF, nflip=nflip)
                valid = (not res['talk']) and (res['worst_lead'] is not None and res['worst_lead'] < 0) \
                    and res['ended'] and not res['followed']
                tag = "  <== ON-LINE" if valid else ""
                if valid and (best is None or res['herd'] > best[0]):
                    best = (res['herd'], nd['nf'], aim_off, res)
                if aim_off % 1000 == 0 or valid:
                    print("  %6d %5d %+4.0f %+5.0f | %+6d %4d  %7s  %-4s %+8.1f  %5.1f  %s%s" % (
                        nd['nf'], m['coff'], m['lat'], m['lead'], aim_off, nflip,
                        ("%.1f" % res['roll_spF']) if res['roll_spF'] else "-",
                        "TALK" if res['talk'] else "ok", res['worst_lead'] or 0,
                        res['herd'], res['ended'], tag))
    if best:
        print("\nBEST ON-LINE cycle: herd %.1f, curve %d f, aim_off %+d" % (best[0], best[1], best[2]))
    else:
        print("\nNO on-line roll found from these setups (the coff-vs-lat coupling: facing exits the "
              "cone only after lat drifts; needs the maintained-actor-lock lever, session 34 finding).")


# --------------------------------------------------------------------------- CLI

def _entry(env, release_early=False):
    """The reposition entry: cyc1 (recorded macro) to the first post-untarget grounded MOVE, camera
    switched off (csangle injected). Full 2-frame tier by default (the on-line-curving entry;
    release-early's -25.7 is INCOMPATIBLE with on-line -- session 34)."""
    from harness.tetrapush import reposition as R
    from harness.tetrapush import primitives as P
    recs = P.window_records(env)
    macro, _ = S.canonical_cycle(env, recs)
    if release_early:
        macro = R.l_release_early(env, macro, S.canonical_cycle(env, recs)[1], n=1)
    return R.seed_to_untarget(env, macro=macro)


def _cmd_curve(env, kw):
    import warnings
    warnings.simplefilter('ignore')
    hl = HerdLine.from_env(env)
    run, _ = _entry(env)
    m0 = metrics(run, hl)
    print("entry: proc %d spF %.3f facing %d coff %d lead %+.1f lat %+.1f"
          % (m0['proc'], m0['spF'], m0['facing'], m0['coff'], m0['lead'], m0['lat']))
    setups, beam = curve_beam(
        run, hl, max_frames=int(kw.get('frames', 10)), beam_w=int(kw.get('beam', 48)),
        aim_step=int(kw.get('aim_step', 0x180)), verbose=True)
    print("\n%d setup node(s) reached (facing out-of-cone + lat~0 + behind):" % len(setups))
    for nd in setups[:8]:
        m = metrics(nd['run'], hl)
        print("  nf=%d cost %.2f: coff %d lat %+.1f lead %+.1f spF %.2f facing %d"
              % (nd['nf'], nd['cost'], m['coff'], m['lat'], m['lead'], m['spF'], m['facing']))
    if not setups:
        print("  (none -- best beam node:)")
        b = beam[0]
        m = metrics(b['run'], hl)
        print("  cost %.2f: coff %d lat %+.1f lead %+.1f spF %.2f" % (b['cost'], m['coff'], m['lat'], m['lead'], m['spF']))


def main(argv):
    env = seeds.load_env()
    cmd = argv[0] if argv else 'curve'
    kw = dict(kv.split('=') for kv in argv[1:] if '=' in kv)
    if cmd == 'curve':
        _cmd_curve(env, kw)
    elif cmd == 'cycle':
        _cmd_cycle(env, kw)
    else:
        print("usage: python -m harness.tetrapush.repo_search {curve|cycle} [frames=N beam=N aim_step=BAM]")


if __name__ == '__main__':
    main(sys.argv[1:])
