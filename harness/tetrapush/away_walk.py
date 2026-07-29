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
"""THE AWAY-WALK: the escape that ends the herd (session 65, Dereck's steer).

Once the last push lands Tetra on her coord, Link has to REVERSE TRAVEL DIRECTION and head
roughly toward the roll-from region (`seeds.ENTRY_ROLL_POS`, ~170 u up-herd of the coords);
herding is COMPLETE when the actors separate (`centre_feet >= CO_RADII_BAR`, Tetra frozen).
The placement planner accounts for this movement -- its first frames are the plan's last push
frames -- and past separation the Link-only leg to the exact roll position is a SEPARATE search
that borrows the existing 2D planners (`walk_to_entry` / `plan_land.reach_precise`).

THE ATOM (decomp-grounded, no A press -- Dereck's rule):

  1. **The slam-turn** (1 frame): a full stick within +-0x800 of the anti-travel-field fires
     `procMoveTurn(1)` (`checkNextMode` 4483: moving + >0x7800 + not a slammed genuine flip ->
     MoveTurn): travel := the stick target, mNormalSpeed halves KEEPING SIGN (6623) -- so from the
     terminal EBS (travel field up-herd, speed ~-25.7) the GROUND MOTION reverses UP-HERD at ~12.9
     u/f in ONE frame, and the contact push stops the same frame (Tetra freezes at ~1 pipeline
     push of residual, ~13.5 u -- not the 27-80 u a brake-through leaves).
  2. **The L conversion** (2 frames): L + a stick >0x6000 from the new travel enters ATN_MOVE
     (frame 1 = the proc init, no body work) and fires the `setSpeedAndAngleAtn` DIR_BACKWARD
     negation (frame 2, d_a_player_main.cpp 2863): travel += 0x8000 (back up-herd), mNormalSpeed
     positive -- the backslide is now a normal FORWARD run away from her.
     **The L must never target Tetra** (Dereck, s65): it must act while she is OUTSIDE the +-90 deg
     front cone, i.e. facing already away -- if the L locks her the facing was wrong, the proc-9
     re-aim chases HER and the run stays ATN-capped at 12. The MoveTurn facing sweep rotates
     toward the (down-line) slam stick, so the window is the 1-2 frames right after the slam.
  3. **Release L, accelerate**: full stick toward the exit bearing; MOVE cap 17.

THE MEASURED BAR (Dereck, s65): true per-frame ground displacement < `WALK_FLOOR` (17 u, the walk
cap) for more than `DIP_BUDGET` (1) frame after separation = unoptimal; expected 0. **The model
cannot reach 0 from a hot terminal**: every reversal primitive crosses the slow zone (MoveTurn
halves; the negation mirrors ~0.68-0.9 of an already-halved speed; procSlip skids to ZERO before
flipping (6658); walk accel is ~2.5 u/f^2; and a beam search over the full stick alphabet x L,
depth 14, found NO receding >= 17 state within 4 post-separation dips). The measured floor is
~5 sub-17 frames. If a live tech recipe beats this, the MODEL is missing a mechanic -- re-open.

Pure stdlib, no Dolphin. CLI: ``python -m harness.tetrapush.away_walk [probe|trace]``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import search as S
from harness.tetrapush import full_herd as FH
from tww_sim.land.plan_land._primitives import stick_for_bearing, world_angle_s16

#: Dereck's displacement bar (s65): below the walk cap for more than DIP_BUDGET frames after
#: separation = unoptimal. Spec, not a measurement; the measured model floor is ~5 (docstring).
WALK_FLOOR = 17.0
DIP_BUDGET = 1

#: The slam stick must sit >0x7800 from the travel FIELD (the near-reversal gate, move.py:63);
#: the window is +-0x800 around the exact anti-travel.
SLAM_WINDOW = 0x800


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def _mk(sx, sy, l=0):
    return dict(stickX=int(sx), stickY=int(sy), buttons=S.PAD_L if l else 0,
                triggerL=255 if l else 0, substickX=128, substickY=0)


def _locked(run):
    atn = getattr(run.link, '_atn', None)
    return (atn is not None and atn.locked) or run.link.state == 9


def escape_atom(run0, hl, *, slam_off=0, flip_bearing=None, l_frames=2, exit_bearing=None,
                csangle=None, max_frames=20):
    """Run ONE escape-atom variant from a terminal state (cloned; ``run0`` untouched).

    ``slam_off`` offsets the slam stick from the exact anti-travel-field (must stay inside
    `SLAM_WINDOW` to fire the near-reversal). ``flip_bearing`` is the L-conversion stick (default:
    up-herd); ``exit_bearing`` the post-flip acceleration stick (default: the live entry bearing).
    ``csangle`` overrides the run's C-stick camera angle for the whole atom (constant).

    Returns the measurement dict:
      ``rows``          per-frame (f, proc, speedF, disp, head, cf, d_t, d_e, tres)
      ``freeze_f``      first frame with `centre_feet` >= the bar that persists to the end
      ``reversed_f``    first frame with ground motion receding from Tetra
      ``rec17_f``       first frame receding at >= `WALK_FLOOR` (None if never)
      ``dips``          post-freeze frames below `WALK_FLOOR` before ``rec17_f`` (Dereck's bar)
      ``resid``/``resid_along``/``resid_lat``  Tetra's displacement over the atom (herd coords)
      ``l_ok``          True iff no L acted while Tetra was in the front cone AND no lock acquired
      ``followed``      the follow shell tripped (dist > 230)
      ``run``, ``log``  the endpoint state + the exact inputs (extend a plan with them)
    """
    r = run0.clone()
    if csangle is not None:
        r.csangle = int(csangle)
    cs = int(r.csangle)
    anti = (int(r.link.travel) + 0x8000 + int(slam_off)) & 0xFFFF
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    flip = up_herd if flip_bearing is None else (int(flip_bearing) & 0xFFFF)
    if exit_bearing is None:
        ex, ez = seeds.ENTRY_ROLL_POS
        exit_bearing = world_angle_s16(ex - r.link.pos_x, ez - r.link.pos_z)
    exit_bearing = int(exit_bearing) & 0xFFFF

    slam = _mk(*stick_for_bearing(anti, cs, msd=1.0))
    flip_in = _mk(*stick_for_bearing(flip, cs, msd=1.0), l=1)
    exit_in = _mk(*stick_for_bearing(exit_bearing, cs, msd=1.0))
    inputs = [slam] + [flip_in] * int(l_frames)

    ex, ez = seeds.ENTRY_ROLL_POS
    t0 = (r.tx, r.tz)
    prev = (r.link.pos_x, r.link.pos_z)
    rows, log = [], []
    l_ok = True
    freeze_run = None                        # first index of the suffix that stays >= the bar
    reversed_f = rec17_f = None
    pend_l = False                           # was last-delivered input an L (acts this frame)?
    for f in range(int(max_frames)):
        d = inputs[f] if f < len(inputs) else exit_in
        if pend_l and S.talk_active(r):      # the L ACTS this frame with her in the cone
            l_ok = False
        r.step(d)
        log.append(d)
        pend_l = bool(d['buttons'] & S.PAD_L)
        if _locked(r):                       # the lock acquired: the L targeted her
            l_ok = False
        disp = math.hypot(r.link.pos_x - prev[0], r.link.pos_z - prev[1])
        head = (world_angle_s16(r.link.pos_x - prev[0], r.link.pos_z - prev[1])
                if disp > 1e-9 else None)
        prev = (r.link.pos_x, r.link.pos_z)
        cf = FH._centre_feet(r)
        vx, vz = FH._link_velocity(r)
        dx, dz = r.link.pos_x - r.tx, r.link.pos_z - r.tz
        dd = math.hypot(dx, dz)
        rec = 0.0 if dd < 1e-9 else (vx * dx + vz * dz) / dd
        rows.append(dict(f=f + 1, proc=r.link.state, speedF=r.link.speedF, disp=disp,
                         head=head, cf=cf, d_t=dd,
                         d_e=math.hypot(r.link.pos_x - ex, r.link.pos_z - ez),
                         tres=math.hypot(r.tx - t0[0], r.tz - t0[1]), rec=rec))
        if cf >= FH.CO_RADII_BAR:
            if freeze_run is None:
                freeze_run = f + 1
        else:
            freeze_run = None                # dipped back under the bar: not a freeze yet
        if reversed_f is None and rec > 0.0:
            reversed_f = f + 1
        if rec17_f is None and rec >= WALK_FLOOR:
            rec17_f = f + 1
        if r._follow_warned:
            break
    dips = [rr['f'] for rr in rows
            if rr['disp'] < WALK_FLOOR and freeze_run is not None and rr['f'] >= freeze_run
            and (rec17_f is None or rr['f'] < rec17_f)]
    ta = hl.along(r.tx, r.tz) - hl.along(t0[0], t0[1])
    tl = hl.lateral(r.tx, r.tz) - hl.lateral(t0[0], t0[1])
    return dict(rows=rows, run=r, log=log, freeze_f=freeze_run, reversed_f=reversed_f,
                rec17_f=rec17_f, dips=dips, resid=math.hypot(ta, tl), resid_along=ta,
                resid_lat=tl, l_ok=l_ok, followed=r._follow_warned,
                d_e_end=rows[-1]['d_e'] if rows else None)


def probe(run0, hl, *, csangles=None, max_frames=20):
    """Sweep the atom's knobs from a terminal state and return the best variant.

    Rank: L-cone compliance first (Dereck's rule -- a locking variant is wrong tech however fast),
    then fewest post-freeze dips (the s65 bar), then earliest receding->=17, then entry progress.
    Small by design (~40 variants); the atom is 3 inputs + a held exit stick, not a search space.
    """
    ex, ez = seeds.ENTRY_ROLL_POS
    b_entry = world_angle_s16(ex - run0.link.pos_x, ez - run0.link.pos_z)
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    if csangles is None:
        csangles = (int(run0.csangle),)
    best = None
    for cs in csangles:
        for slam_off in (-0x400, 0, 0x400):
            for flip in (up_herd, b_entry):
                for lf in (1, 2):
                    r = escape_atom(run0, hl, slam_off=slam_off, flip_bearing=flip,
                                    l_frames=lf, csangle=cs, max_frames=max_frames)
                    key = (not r['l_ok'], r['followed'], len(r['dips']),
                           r['rec17_f'] if r['rec17_f'] is not None else 99,
                           r['d_e_end'] if r['d_e_end'] is not None else 1e9)
                    r['knobs'] = dict(csangle=cs, slam_off=slam_off, flip_bearing=flip,
                                      l_frames=lf)
                    if best is None or key < best[0]:
                        best = (key, r)
    return best[1] if best else None


# --------------------------------------------------------------------------- CLI

def _print_atom(res):
    k = res.get('knobs', {})
    print("knobs %s" % k)
    print("l_ok %s  followed %s  freeze f%s  reversed f%s  receding>=17 f%s  dips %s"
          % (res['l_ok'], res['followed'], res['freeze_f'], res['reversed_f'],
             res['rec17_f'], res['dips']))
    print("tetra residual %.3f u (along %+.3f lat %+.3f); entry gap at end %.1f u"
          % (res['resid'], res['resid_along'], res['resid_lat'], res['d_e_end']))
    print("  f proc  speedF    disp   head     cf    d_t    d_e   tres    rec")
    for rr in res['rows']:
        print("  %2d %3d %8.3f %7.3f %6s %6.1f %6.1f %6.1f %6.2f %+7.2f"
              % (rr['f'], rr['proc'], rr['speedF'], rr['disp'],
                 rr['head'] if rr['head'] is not None else '-', rr['cf'], rr['d_t'],
                 rr['d_e'], rr['tres'], rr['rec']))


def main(argv):
    import warnings
    warnings.simplefilter('ignore')
    from harness.tetrapush.reposition import HerdLine
    cmd = argv[0] if argv else 'probe'
    env = seeds.load_env()
    hl = HerdLine.from_env(env)
    node = FH.synthetic_hot_arrival(env, hl, coord_idx=287, d_short=0.0, feet=64.0)
    run = node['run']
    if cmd == 'probe':
        res = probe(run, hl, csangles=(16384, 24576, 32768))
        print("=== the best escape atom off the synthetic hot terminal (coord 287) ===")
        _print_atom(res)
    elif cmd == 'trace':
        res = escape_atom(run, hl, csangle=24576)
        _print_atom(res)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
