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
"""THE AWAY-WALK: the escape that ends the herd (session 65, Dereck's steer + input recipe).

Once the last push lands Tetra on her coord, Link has to REVERSE TRAVEL DIRECTION and head
roughly toward the roll-from region (`seeds.ENTRY_ROLL_POS`, ~170 u up-herd of the coords);
herding is COMPLETE when the actors separate (`centre_feet >= CO_RADII_BAR`, Tetra frozen).
The placement planner accounts for this movement -- its frames up to the slam are the plan's
LAST PUSH frames -- and past separation the Link-only leg to the exact roll position is a
SEPARATE search that borrows the existing 2D planners (`walk_to_entry` / `plan_land.reach_precise`).

THE ATOM IS THE HERD JUNCTION WITH THE ROLL REPLACED BY A BACKWARDS SLAM (Dereck's recipe,
measured s65: "do the same inputs you do during the herd phase to convert to positive and then
roll, but instead of rolling, slam backwards -- maybe one frame left or right beforehand"):

  1. **The turnaround** (1 frame, no A -- ONLY when the terminal EBS still faces Tetra): ESS at
     the snap csangle (`reposition.turnaround`) -- facing snaps across travel, speed PRESERVED
     (-25.727), Tetra leaves the front cone. An EBS already faced away skips it (Dereck: "if the
     L targets her, you were facing toward her during the EBS").
  2. **The L conversion** (ONE L frame -- Dereck): L + full stick toward Tetra for one frame,
     then the same stick WITHOUT L. The L frame routes into ATN_MOVE; the `setSpeedAndAngleAtn`
     DIR_BACKWARD negation (d_a_player_main.cpp 2863) fires on the NEXT dispatch frame off the
     still-held stick, with the L already released: **-25.7 -> +17.614 POSITIVE** (travel
     down-herd, motion unchanged -- these frames keep pushing her: they are placement frames).
     The L acts with her out of the cone (facing away after the snap) so it never targets her --
     Dereck's rule; an L that locks means the facing was wrong.
  3. **The rotate** (1 frame, the "one frame left or right"): full stick ~90 deg off, so the next
     frame's want-angle step is < 0x6000 -- WITHOUT it the backwards stick re-fires the negation
     ("fast + genuine stick flip") and the run flips back NEGATIVE and decays through zero
     (measured: 8-9 dips).
  4. **The backwards slam** (1 frame): full stick up-herd -> `procMoveTurn(1)` (4483: moving +
     >0x7800 + NOT a genuine flip): travel := the stick, mNormalSpeed halves KEEPING SIGN -- and
     the sign is now POSITIVE, so **+17.0 -> +8.5 along the REVERSED travel: motion reverses
     up-herd with NO zero crossing**. Contact ends here (separation, Tetra frozen).
  5. **Accelerate**: hold the exit stick; +10.2 -> +14.1 -> 17.0 (the walk cap) two frames later.

Measured on the synthetic hot terminal (already faced away, no snap frame): conversion +17.614
at f3, slam +8.5 REVERSED at f5, walk cap at f8 -- **3 post-separation frames under 17** (the
halving dip + two accel frames; Dereck confirmed the dip is inherent, 0 is not feasible),
receding every frame from the slam, Tetra's residual over the conversion frames **34.8 u**
down-corridor -- the terminal targeting undershoots by exactly that (deterministic per
terminal; 44.7 u with the snap frame included). Two measured traps, do not re-pay: slamming
FIRST from the negative EBS also reverses in one frame but decays through zero (~12 sub-17
frames -- a negative run has no positive target to rebuild from; converting FIRST removes the
crossing), and moving the stick to left/right on the NEGATION frame reads DIR_SIDE and never
converts (the toward stick must be the acting want that frame -- hold it across the L release).

Pure stdlib, no Dolphin. CLI: ``python -m harness.tetrapush.away_walk [probe|trace]``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import search as S
from harness.tetrapush import full_herd as FH
from tww_sim.land.plan_land._primitives import stick_for_bearing, world_angle_s16

#: Dereck's s65 bar: sub-17 frames after separation. The dip is inherent (Dereck: 0 infeasible);
#: the recipe's measured best is 3 (the halving + two accel frames), pinned so worse ranks out.
WALK_FLOOR = 17.0
DIP_BUDGET = 3

#: reposition.turnaround's snap-window criterion (the herd junction's own): the ESS frame must
#: snap the facing >0x4000 with the EBS speed preserved and the proc still MOVE.
_SNAP_MIN_TURN = 0x4000
_SNAP_KEEP_SPEED = -24.5


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def _mk(sx, sy, l=0):
    return dict(stickX=int(sx), stickY=int(sy), buttons=S.PAD_L if l else 0,
                triggerL=255 if l else 0, substickX=128, substickY=0)


def _locked(run):
    atn = getattr(run.link, '_atn', None)
    return (atn is not None and atn.locked) or run.link.state == 9


def _clone_for_atom(run0):
    """Clone for the atom, in the planner's commanded-csangle convention: a WIRED camera is
    detached (`seed_to_untarget` does the same for the reposition search) so `r.csangle = ...`
    commands the value the sticks are decoded at. When the commanded csangle equals the live one,
    the wired camera would have HELD it anyway (the (128, 0) manualCamera hold the atom's inputs
    carry), so the prediction is replay-faithful; a snap that needs a DIFFERENT csangle records it
    on the result (``csangle``) -- realizing it with a C-stick slew is the camera leg, the same
    shape as the roll stage's ``target_cs``."""
    r = run0.clone()
    if getattr(r, 'camera', None) is not None:
        r.camera = None
    return r


def snap_csangle(run0, *, step=512):
    """The turnaround's csangle window off THIS terminal state: the first csangle whose ESS frame
    snaps the facing (`reposition.turnaround`) while preserving the EBS. The herd junction sweeps
    the same window; a terminal with no window cannot run the atom (report, don't guess)."""
    from harness.tetrapush.reposition import turnaround
    for cs in range(0, 0x10000, int(step)):
        c = _clone_for_atom(run0)
        if (turnaround(c, cs) > _SNAP_MIN_TURN and c.link.state == 6
                and c.link.speedF <= _SNAP_KEEP_SPEED):
            return cs
    return None


def escape_atom(run0, hl, *, turnaround_first=False, rotate_side=1, rotate_off=0x4000,
                flip_bearing=None, exit_bearing=None, csangle=None, max_frames=18):
    """Run ONE escape-atom variant from a terminal state (cloned; ``run0`` untouched).

    The input sequence is Dereck's recipe (module docstring): [optional turnaround] ->
    L-conversion (ONE L frame + the stick held one more, so the toward stick is the acting want
    on the negation frame -- the delay-1 bookkeeping of "L+up") -> rotate (one frame,
    ``rotate_side`` * ``rotate_off`` off the flip bearing -- "left/right") -> backwards slam
    ("slam down") -> hold the exit stick. ``turnaround_first`` prepends the ESS facing snap; a
    terminal whose EBS still faces Tetra needs it or the L locks her (`l_ok` False ranks it
    out). ``flip_bearing`` defaults to the herd's down-bearing (the junction's own toward-Tetra
    stick); ``exit_bearing`` to the live entry bearing; ``csangle`` to the auto-detected snap
    window (`snap_csangle`).

    Returns the measurement dict:
      ``rows``          per-frame (f, proc, speedF, disp, head, cf, d_t, d_e, tres, rec)
      ``freeze_f``      first frame with `centre_feet` >= the bar that persists to the end
      ``reversed_f``    first frame with ground motion receding from Tetra
      ``rec17_f``       first frame receding at >= `WALK_FLOOR` (None if never)
      ``dips``          post-freeze frames below `WALK_FLOOR` before ``rec17_f`` (Dereck's bar)
      ``resid``/``resid_along``/``resid_lat``  Tetra's displacement over the atom (herd coords) --
                        the conversion frames keep pushing her, so this is the terminal's UNDERSHOOT
      ``l_ok``          True iff no L acted while Tetra was in the front cone AND no lock acquired
      ``followed``      the follow shell tripped (dist > 230)
      ``run``, ``log``  the endpoint state + the exact inputs (extend a plan with them)
    """
    r = _clone_for_atom(run0)
    if csangle is None:
        csangle = snap_csangle(run0)
        if csangle is None:
            # The window exists for the ESS turnaround frame only; without one, the no-turnaround
            # variants still run on the live csangle (the camera never needed to move).
            if turnaround_first:
                return None
            csangle = int(run0.csangle)
    r.csangle = int(csangle)
    cs = int(r.csangle)
    down = hl.bearing_bam()
    flip = down if flip_bearing is None else (int(flip_bearing) & 0xFFFF)
    slam_bearing = (flip + 0x8000) & 0xFFFF
    rot = (flip + (int(rotate_off) if int(rotate_side) >= 0 else -int(rotate_off))) & 0xFFFF
    if exit_bearing is None:
        ex, ez = seeds.ENTRY_ROLL_POS
        exit_bearing = world_angle_s16(ex - r.link.pos_x, ez - r.link.pos_z)
    exit_bearing = int(exit_bearing) & 0xFFFF

    from harness.tetrapush.reposition import ESS_DOWN
    fsx, fsy = stick_for_bearing(flip, cs, msd=1.0)
    exit_in = _mk(*stick_for_bearing(exit_bearing, cs, msd=1.0))
    inputs = (([_mk(*ESS_DOWN)] if turnaround_first else [])     # the facing snap, when needed
              + [_mk(fsx, fsy, l=1), _mk(fsx, fsy)]              # ONE L frame; negation next frame
              + [_mk(*stick_for_bearing(rot, cs, msd=1.0))]      # defeat the genuine-flip gate
              + [_mk(*stick_for_bearing(slam_bearing, cs, msd=1.0))])   # MoveTurn(1): +v halved, reversed

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
        if rec17_f is None and rec > 0.0 and math.hypot(vx, vz) >= WALK_FLOOR:
            rec17_f = f + 1
        if r._follow_warned:
            break
        if rec17_f is not None and freeze_run is not None:
            # Handoff = receding at the cap AND separated: a deep terminal can recede at 17 with
            # the centre still inside the 80 u bar, Tetra still taking push (see `fires`).
            break
    dips = [rr['f'] for rr in rows
            if rr['disp'] < WALK_FLOOR and freeze_run is not None and rr['f'] >= freeze_run
            and (rec17_f is None or rr['f'] < rec17_f)]
    ta = hl.along(r.tx, r.tz) - hl.along(t0[0], t0[1])
    tl = hl.lateral(r.tx, r.tz) - hl.lateral(t0[0], t0[1])
    return dict(rows=rows, run=r, log=log, freeze_f=freeze_run, reversed_f=reversed_f,
                rec17_f=rec17_f, dips=dips, resid=math.hypot(ta, tl), resid_along=ta,
                resid_lat=tl, l_ok=l_ok, followed=r._follow_warned, csangle=cs,
                d_e_end=rows[-1]['d_e'] if rows else None)


def fires(res):
    """Does one atom result satisfy rule 3 (the s65 bar)? The conditions in one place, so the
    objective and the terminal consume the same acceptance: the L never acted with Tetra in the
    cone and never locked (`l_ok`), the follow shell never tripped, the escape actually SEPARATES
    (`freeze_f` -- herding complete = separation; a deep terminal can recede at the cap with the
    centre still inside the 80 u bar and Tetra still taking push), the post-separation dips are
    within Dereck's `DIP_BUDGET`, and the walk reaches the cap receding (`rec17_f`)."""
    return bool(res is not None and res['l_ok'] and not res['followed']
                and res['freeze_f'] is not None and len(res['dips']) <= DIP_BUDGET
                and res['rec17_f'] is not None)


def probe(run0, hl, *, max_frames=18):
    """Sweep the atom's knobs from a terminal state and return the best variant.

    Rank: L-cone compliance first (Dereck's rule -- a locking variant is wrong tech however fast),
    then fewest post-separation dips (the s65 bar), then earliest receding->=17, then entry
    progress. Small by design (~16 variants); the atom is 4-5 inputs + a held exit stick, not a
    search space. ``turnaround_first`` is swept rather than inferred: a terminal already faced
    away wastes a frame (and ~10 u of extra push) on the snap, one still facing her NEEDS it --
    `l_ok` ranks the wrong choice out."""
    ex, ez = seeds.ENTRY_ROLL_POS
    b_entry = world_angle_s16(ex - run0.link.pos_x, ez - run0.link.pos_z)
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    # The snap window depends only on the start state -- sweep it once for all knob variants.
    cs = snap_csangle(run0)
    best = None
    for ta in (False, True):
        for side in (1, -1):
            for exit_b in (b_entry, up_herd):
                if ta and cs is None:
                    continue
                r = escape_atom(run0, hl, turnaround_first=ta, rotate_side=side,
                                exit_bearing=exit_b,
                                csangle=cs if cs is not None else int(run0.csangle),
                                max_frames=max_frames)
                if r is None:
                    continue
                key = (not r['l_ok'], r['followed'], r['freeze_f'] is None, len(r['dips']),
                       r['rec17_f'] if r['rec17_f'] is not None else 99,
                       r['d_e_end'] if r['d_e_end'] is not None else 1e9)
                r['knobs'] = dict(turnaround_first=ta, rotate_side=side, exit_bearing=exit_b)
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
        res = probe(run, hl)
        print("=== the best escape atom off the synthetic hot terminal (coord 287) ===")
        _print_atom(res)
    elif cmd == 'trace':
        res = escape_atom(run, hl)
        _print_atom(res)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
