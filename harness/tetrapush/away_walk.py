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
     L targets her, you were facing toward her during the EBS"). **The snap csangle is a bill the
     PREVIOUS ROLL pays** (`snap_bill`, session 73): the atom's own C-stick is neutral, so the
     camera holds whatever the arrival brings, and slewing 15-38 deg here would cost 6-15 frames
     against a 2-frame budget. The channel that pays is the last roll's ``target_cs``, idle for its
     whole duration and worth -46.6..+40.7 deg (`full_herd.ESCAPE_TCS_SPAN`).
     **The snap is the cleanest way for this frame to do its job, not the only one** (session 75):
     what the frame must achieve is that the L does not act with Tetra in the cone, and on the banked
     ``deep`` arrival the ESS turns only 0x1425 = 28.3 deg -- under `_SNAP_MIN_TURN`, with Tetra still
     in the cone right after it -- yet the escape fires, the cone being cleared a frame later by the
     frame the L acts on. So `probe` sweeps the turnaround unconditionally and lets `fires` judge it.
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

_BAM_DEG = 360.0 / 65536.0

#: The conversion's DIR_BACKWARD cone, 90 deg wide about 180 (`reference/constants.md`'s 0x6000 row).
#: NOT a bound on the flip bearing -- see `flip_arc`.
DIR_BACKWARD_CONE = 0x8000 - 0x6000

#: The flip sweep's default half-width about the herd down-bearing -- a BUDGET, see `flip_arc`.
FLIP_SPAN = 0x2800

#: The rotate offsets on the 0x1000 grid that keep the slam's want-angle step under the genuine-flip
#: gate (0x6000, `_check_next_mode`'s procSlip branch); 0x4000 is the recipe's own.
ROTATE_OFFS = (0x3000, 0x4000, 0x5000, 0x6000)


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
    commands the value the sticks are decoded at. The atom's own inputs carry a NEUTRAL C-stick,
    which FREEZES csangle (`steered_reposition.camera_authority`). Commanding a DIFFERENT value is a
    claim on the camera that only the last roll's C-stick can pay (`snap_bill`); the atom itself has
    no frames to spare for it.

    **The freeze is real; the arrival's LIVE value is not what it freezes AT** (session 78,
    console-measured). The yaw TARGET stops moving with the C-stick, but the view-cache chases it at
    a 0.66/frame cushion (`knowledge/mechanics/land-camera.md`), so a plan whose last roll SLEWED the
    C-stick hands the atom a globe still in flight: on the shipped plan the stick sits at 255 through
    the last roll and csangle finishes its chase on the atom's FIRST frame, 34181 -> 34330 -> 34325,
    constant thereafter. The console plays the wired value (`tests/test_plan_console.py`), so
    `escape_atom`'s ``csangle='live'`` default -- and its ``cs_bill`` of 0 -- describe a camera 144
    BAM off the delivered one.

    Kept anyway, because the cost is MEASURED and it is zero where the objective looks: over the
    shipped plan's atom, Tetra is bit-identical on every frame and so are ``freeze_f``, ``l_ok``,
    ``rec17_f``, the dips and every ``tstep``; what moves is Link's own escape path (0.12 -> 0.65 u),
    which belongs to the separate entry search. Detaching also keeps s65-s77's banked rows
    comparable. Before pricing a camera bill on an arrival whose last roll slewed, read the settled
    value off a WIRED clone rather than ``run0.csangle``."""
    r = run0.clone()
    if getattr(r, 'camera', None) is not None:
        r.camera = None
    return r


def snaps_at(run0, csangle):
    """Does the ESS turnaround frame snap this terminal's facing at ``csangle``? One frame, no atom
    -- the cheap half of `snap_bill` and the predicate `snap_csangle` scans with."""
    from harness.tetrapush.reposition import turnaround
    c = _clone_for_atom(run0)
    return bool(turnaround(c, int(csangle)) > _SNAP_MIN_TURN and c.link.state == 6
                and c.link.speedF <= _SNAP_KEEP_SPEED)


def snap_csangle(run0, *, step=512, near=True):
    """The turnaround's csangle window off THIS terminal state: a csangle whose ESS frame snaps the
    facing (`reposition.turnaround`) while preserving the EBS. A terminal with no window cannot run
    the snap (report, don't guess).

    ``near`` (session 73, the default, and the correction of a real bill) returns the window member
    NEAREST the live csangle instead of the first in absolute scan order. The window is WIDE --
    measured over 112 real arrivals it holds 28-30 members on the 512 grid, i.e. **78.8-81.6 deg** --
    so which member a scan returns is not cosmetic. Scanning ``range(0, 0x10000)`` returned its FAR
    edge on every arrival, **91.3-113.8 deg** off the live csangle, and that value is the csangle
    every atom result from session 65 to 72 was computed at: a camera state no single roll's ~47 deg
    of C-stick slew can deliver, so the whole frontier was conditional on a leg nothing paid for. The
    NEAREST member is **15.3-37.8 deg** (median 21.0) -- inside one roll's slew, which is what makes
    the bill payable at all (`full_herd.ESCAPE_TCS_SPAN`). Pass ``near=False`` for the legacy order."""
    live = int(run0.csangle)
    grid = list(range(0, 0x10000, int(step)))
    if near:
        grid.sort(key=lambda cs: abs(_s16(cs - live)))
    for cs in grid:
        if snaps_at(run0, cs):
            return cs
    return None


def snap_bill(run0, *, step=512):
    """**What the CAMERA owes for this terminal's turnaround, and who pays it** (session 73).

    The snap needs a csangle in the window; the atom cannot slew there itself (its C-stick is neutral
    -- see `_clone_for_atom` -- and at ~460-530 BAM/frame the 15-38 deg bill would cost 6-15 frames
    against `objective.TIMELOSS_BUDGET` 2). The only channel that CAN pay is the last roll's C-stick,
    which is idle for its whole duration and slews -46.6..+40.7 deg (measured over 112 arrivals). So
    this reports the bill in the currency that stage spends: ``free`` when the arrival's own live
    csangle already snaps -- nothing to pay -- else ``bam``/``deg`` off it.

    NOTE the bill is not separable from the arrival: the post-roll EBS travel chases csangle, so
    steering the camera to satisfy it MOVES the arrival (s42). It is a term in the roll's ``target_cs``
    cut (`full_herd.roll_candidates`), never a credit an atom result may assume.

    **AND ON A REAL ARRIVAL IT IS LARGELY UNCOLLECTABLE, not merely coupled** (session 77, and the
    reason a whole band has no frame answer): the snap is a relation between the ESS stick's world
    want-angle and the state's TRAVEL, not between the stick and the camera
    (`reposition.turnaround`) -- and travel chases csangle, so slewing the camera rotates BOTH and
    the relation is nearly preserved. `snap_reach` measures it: over a roll's whole reachable camera
    set the quantity that decides the snap has an 87 deg HOLE which is exactly where the snapping
    band sits, so 0-1 of 110 reachable states snap where a COMMANDED sweep of the same csangles (on a
    travel-FROZEN state) snaps 5 of 21. A bill this reports as 29 deg can therefore be unpayable at
    any price -- ask `snap_reach`, not this, before spending a session on the camera."""
    live = int(run0.csangle)
    if snaps_at(run0, live):
        return dict(csangle=live, bam=0, deg=0.0, free=True)
    cs = snap_csangle(run0, step=step)
    if cs is None:
        return dict(csangle=None, bam=None, deg=None, free=False)
    return dict(csangle=cs, bam=_s16(cs - live), deg=abs(_s16(cs - live)) * _BAM_DEG, free=False)


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
    stick); ``exit_bearing`` to the live entry bearing.

    ``csangle`` defaults to the terminal's own LIVE csangle -- the REPLAY-FAITHFUL convention
    (session 73, and a change of default). It used to default to `snap_csangle`, which COMMANDED the
    camera into the turnaround's window for every variant, including the ``turnaround_first=False``
    ones that never snap. On real arrivals that value sat 91-114 deg off live, so from session 65 to
    72 every atom number described a camera state nothing in the plan paid for. The atom cannot pay
    it -- its C-stick is neutral and slewing would cost 6-15 frames against a 2-frame budget
    (`snap_bill`) -- so the value it may assume is the one the arrival arrives WITH. A caller that
    wants the window buys it upstream, in the last roll's ``target_cs``, and the arrival then carries
    it live. The result records ``cs_bill`` (BAM off live; 0 = faithful).

    Returns the measurement dict:
      ``rows``          per-frame (f, proc, speedF, disp, head, cf, d_t, d_e, tres, tstep, rec)
                        -- ``tstep`` is Tetra's own displacement THAT frame, the escape's push in the
                        objective's currency (`push_profile`); ``tres`` is her distance from the start,
                        which is NOT its running sum once the plow direction turns
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
        csangle = int(run0.csangle)          # replay-faithful: the camera holds what it arrived at
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
    tprev = t0
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
        tstep = math.hypot(r.tx - tprev[0], r.tz - tprev[1])
        tprev = (r.tx, r.tz)
        rows.append(dict(f=f + 1, proc=r.link.state, speedF=r.link.speedF, disp=disp,
                         head=head, cf=cf, d_t=dd,
                         d_e=math.hypot(r.link.pos_x - ex, r.link.pos_z - ez),
                         tres=math.hypot(r.tx - t0[0], r.tz - t0[1]), tstep=tstep, rec=rec))
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
                cs_bill=_s16(cs - int(run0.csangle)),
                d_e_end=rows[-1]['d_e'] if rows else None)


def push_profile(res, *, upto=None):
    """**WHAT THE ESCAPE'S FRAMES ARE WORTH, in the objective's own push currency** (session 74) --
    and the answer to where the frontier's 2-frame timeloss actually goes.

    The frontier has read 75 frames (floor 73) since session 71, and s72/s73/s74 each widened a
    different search axis without moving it. This says why, by pricing the atom's frames against
    `objective.PUSH_CEILING` -- the sustained plow rate the frame floor itself assumes. Measured on
    the shipped 75-frame plan (`fixtures/courtyard_plan_s73.json`):

      * the LAST ROLL pushes Tetra **12.911 u/frame over all 19 of its frames -- 99.3% of the
        ceiling**. The herd is not where the frames are lost.
      * the ESCAPE's 4 frames to separation push **9.177 u/frame, 70.6%**, because its frame 2 -- the
        proc-7 negation frame, where the flip has Link receding and the conversion has not yet fired
        -- plows **0.000 u**, and its frame 4 (the slam) plows 7.7 u on a HALVED mNormalSpeed.
      * so the escape costs **1.18 frames** of the 2-frame timeloss on its own, and that is the
        recipe's shape (module docstring), not a knob: no camera target, aim, flip or rotate can buy
        a dead plow frame back.

    The consequence for a search is the useful part. What the escape RECOVERS of the placement is
    capped by what it pushes -- measured over 85192 firing variants, at most 22.94 u at ``freeze_f``
    3, 34.54 at 4 and **-0.24 at 1** -- so the frame rung a plan can reach is fixed by its ARRIVAL:
    ``total = arrival_frames + freeze_f`` needs ``pd_pre <= recovery(freeze_f) + PLACEMENT_BAND``.
    74 frames therefore has exactly three routes, and all three are arrival quality, not escape
    tuning (`README.md`'s session-74 box has the ledger).

    ``upto`` defaults to ``freeze_f`` (the separation frame -- the plan's own end), so the rate is the
    one the frame count is charged for; pass an int to price a different window.

    Returns ``dict(plow, frames, total, rate, ceiling, saturation, dead, frames_lost)``."""
    from harness.tetrapush import objective as O
    rows = res['rows']
    n = int(res['freeze_f'] or len(rows)) if upto is None else int(upto)
    n = max(0, min(n, len(rows)))
    plow = [rr['tstep'] for rr in rows[:n]]
    total = sum(plow)
    rate = (total / n) if n else 0.0
    return dict(plow=plow, frames=n, total=total, rate=rate, ceiling=O.PUSH_CEILING,
                saturation=(rate / O.PUSH_CEILING) if O.PUSH_CEILING else 0.0,
                dead=[rows[i]['f'] for i in range(n) if plow[i] <= 1e-9],
                frames_lost=(n * (O.PUSH_CEILING - rate) / O.PUSH_CEILING
                             if O.PUSH_CEILING else 0.0))


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


#: `fires`' five clauses (True = PASSES), so a refusal can be ATTRIBUTED (`fires_census`) not counted.
#: The acceptance itself stays in `fires`; this is only its decomposition, gated equivalent to it.
FIRES_CLAUSES = dict(
    l_ok=lambda r: bool(r['l_ok']),
    no_follow=lambda r: not r['followed'],
    separates=lambda r: r['freeze_f'] is not None,
    dips=lambda r: len(r['dips']) <= DIP_BUDGET,
    recedes_at_cap=lambda r: r['rec17_f'] is not None,
)


def fires_census(run0, hl, *, flip_step=0x400, rotate_offs=ROTATE_OFFS, csangle='live',
                 max_frames=18):
    """**WHICH `fires` clause refuses an arrival** -- because a count is not a diagnosis (session 77).

    Session 76 reported "0 of 672 variants FIRE" on the jf-7 band and stopped there, which is the same
    shape of dead end as "the pool is empty" (this work's most-repeated failure mode). `fires` is a
    CONJUNCTION of five clauses and they belong to different stages: ``l_ok`` is a facing question the
    previous roll's camera has authority over, ``dips`` and ``recedes_at_cap`` are the recipe's own
    shape and no upstream knob buys them back, ``separates`` is the arrival's depth. Which one refuses
    decides whether there is anything left to spend a session on.

    Measured on the jf-7 band's closest arrivals: ``l_ok`` fails on **all 672** variants and is the SOLE
    blocker on 239-295 of them -- so nothing about the escape's own shape needed fixing, and the whole
    question was the facing at the frame the L acts. `snap_reach` is then what says whether the camera
    can move it.

    ``sole`` is the useful column: a variant whose ONLY failing clause is X fires the moment X is fixed.

    Returns ``dict(n_var, n_fire, fail, sole)``, ``fail``/``sole`` counted per clause name."""
    ex, ez = seeds.ENTRY_ROLL_POS
    b_entry = world_angle_s16(ex - run0.link.pos_x, ez - run0.link.pos_z)
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    cs = int(run0.csangle) if csangle == 'live' else (snap_csangle(run0) if csangle == 'snap'
                                                     else int(csangle))
    cs = int(run0.csangle) if cs is None else cs
    fail, sole, n_var, n_fire = {}, {}, 0, 0
    for flip in flip_arc(hl, step=int(flip_step)):
        for ro in tuple(rotate_offs):
            for ta in (False, True):
                for side in (1, -1):
                    for exb in (b_entry, up_herd):
                        r = escape_atom(run0, hl, turnaround_first=ta, rotate_side=side,
                                        rotate_off=ro, flip_bearing=flip, exit_bearing=exb,
                                        csangle=cs, max_frames=max_frames)
                        if r is None:
                            continue
                        n_var += 1
                        bad = [k for k, ok in FIRES_CLAUSES.items() if not ok(r)]
                        if not bad:
                            n_fire += 1
                            continue
                        for k in bad:
                            fail[k] = fail.get(k, 0) + 1
                        if len(bad) == 1:
                            sole[bad[0]] = sole.get(bad[0], 0) + 1
    return dict(n_var=n_var, n_fire=n_fire, fail=fail, sole=sole)


def _ess_want(csangle):
    """The ESS turnaround stick's WORLD want-angle at ``csangle`` -- the game's own ``m34E8``, i.e.
    what the facing chase steps toward on the snap frame (`reposition.turnaround`)."""
    from harness.tetrapush import two_roll as T
    from harness.tetrapush.reposition import ESS_DOWN
    from tww_sim.land.plan_land._primitives import main_stick_decode
    return T.world_facing(main_stick_decode(ESS_DOWN[0], ESS_DOWN[1])[0], int(csangle))


def snap_reach(node, aim, hl, *, span=None, step=64, l_window=(4, 7), gap_min=2000):
    """**WHICH CAMERA STATES A ROLL CAN ACTUALLY DELIVER, and why the snap is not among them**
    (session 77) -- the measurement that closes the escape's camera bill instead of re-pricing it.

    `snap_bill` reports the bill against the arrival's live csangle and `full_herd.derived_target_css`
    supplies the grid the last roll can pay it from, so a bill of 29 deg inside a 56 deg span reads
    payable. It is not, and the reason is mechanical: `reposition.turnaround`'s snap fires when the ESS
    stick's world want-angle steps the facing chase ACROSS TRAVEL, so the quantity that decides it is
    ``want - travel`` -- and the post-roll EBS travel CHASES csangle (s42). Slewing the camera moves the
    stick and the travel together, so ``want - travel`` stays pinned near 0 while the camera sweeps 87
    deg, and the snapping band (measured 16-38 deg BEHIND travel) sits in a HOLE of the reachable set.

    Measured on the jf-7 band's three closest arrivals, a +-0x4000 grid at step 64 (513 targets, 110
    distinct reachable ``(exit_cs, travel)`` states each): ``want - travel`` reaches -21906..+6195 BAM
    with a **15866 BAM (87 deg) gap**, 0/0/1 states snap, and the same csangles COMMANDED onto a
    travel-frozen state snap 5 of 21 and clear the talk cone. So a commanded-camera probe sees a cliff
    no payable state can cross, which is what made a whole band look merely expensive.

    ``node`` is a PRE-roll endpoint (`full_herd.junction_beam`'s shape -- ``run``/``frames``), ``aim``
    its roll aim: the sweep has to re-fire the roll per target, because the camera's effect on the
    arrival is the whole point.

    Returns ``dict(n_states, n_snap, n_clear, wt_lo, wt_hi, gap, best_cone, states)``; ``gap`` is the
    widest hole (> ``gap_min`` BAM) in the reachable ``want - travel`` set, ``None`` if there is none."""
    from harness.tetrapush import two_roll as T
    from harness.tetrapush.reposition import ESS_DOWN
    from harness.tetrapush import search as S
    span = FH.ESCAPE_TCS_SPAN if span is None else int(span)
    cs0 = int(node['run'].csangle)
    seen, states = set(), []
    for off in range(-int(span), int(span) + 1, int(step)):
        rr = node['run'].clone()
        seg = T.roll_segment(rr, tuple(aim), target_cs=(cs0 + off) & 0xFFFF, l_window=l_window)
        if not seg['ok']:
            continue
        cs, travel = int(rr.csangle), int(rr.link.travel)
        if (cs, travel) in seen:
            continue
        seen.add((cs, travel))
        c = _clone_for_atom(rr)
        f0 = int(c.link.facing)
        c.step(_mk(*ESS_DOWN))
        turned = abs(_s16(int(c.link.facing) - f0))
        c.step(_mk(*stick_for_bearing(hl.bearing_bam(), int(c.csangle), msd=1.0), l=1))
        states.append(dict(cs=cs, travel=travel, want_minus_travel=_s16(_ess_want(cs) - travel),
                           turned=turned, snaps=turned > _SNAP_MIN_TURN,
                           l_active=bool(S.talk_active(c)), cone=_cone_margin(c)))
    wts = sorted(s['want_minus_travel'] for s in states)
    gap = None
    for a, b in zip(wts, wts[1:]):
        if b - a > int(gap_min) and (gap is None or b - a > gap[1] - gap[0]):
            gap = (a, b)
    return dict(n_states=len(states), n_snap=sum(1 for s in states if s['snaps']),
                n_clear=sum(1 for s in states if not s['l_active']),
                wt_lo=(wts[0] if wts else None), wt_hi=(wts[-1] if wts else None), gap=gap,
                best_cone=(max(s['cone'] for s in states) if states else None), states=states)


def _cone_margin(run):
    """How far OUTSIDE the +-90 deg talk cone Tetra sits, in degrees (negative = inside it, i.e. an L
    acting now targets her). The `search.talk_active` predicate as a signed margin, so a refusal can be
    read as a distance rather than a boolean."""
    b = world_angle_s16(run.tx - run.link.pos_x, run.tz - run.link.pos_z)
    return abs(_s16(b - int(run.link.facing))) * _BAM_DEG - 90.0


def recovery_row(run0, hl, placements, *, flip_step=0x400, rotate_offs=ROTATE_OFFS, csangle='live',
                 max_frames=18):
    """**What the escape RECOVERS of one arrival's placement, per separation frame** -- the measuring
    function `objective.along_floor`'s ``recovery`` argument needs, and did not have (session 77).

    The ledger the frame rungs are decided by is ``pd_pre <= recovery(freeze_f) + PLACEMENT_BAND``, and
    session 76 established the hard half of it: that row is a property of the ARRIVAL, never portable
    between bands (``freeze_f`` is set by the arrival's own `full_herd._centre_feet`, and the plow the
    escape can spend scales with the frames that buys -- at ``freeze_f`` 3 the bound reads 20.31 u on one
    real arrival and 48.57 on another). A rule that says "measure it here" needs something that measures
    it, and until this the only producers were scratch scripts, so the numbers banked in
    `fixtures/courtyard_arrivals_s75.json` were not re-derivable by anything tracked.

    Every variant of the same knob grid `probe` sweeps, bucketed by ``freeze_f`` -- because that bucket
    IS the frame count a plan reaches (``total = arrival_frames + freeze_f``), so a row is only usable
    against the rung it belongs to. Both populations, for the same reason `push_profile` keeps both: the
    FIRING ones are what a plan may use, and ALL of them give the physical plow bound the allowance is
    made of.

    **This is a bucket, not a new rank** (the correction of session 76's step 1). At a FIXED arrival
    ``pd_pre`` is constant, so maximising ``recovery = pd_pre - pd_post`` is the same ORDER as
    minimising the landing -- which `probe`'s ``rank='miss'`` already is. What the recovery question adds
    over that rank is the ``freeze_f`` split: `probe` returns ONE variant, and a rung needs the best
    landing reachable AT ITS OWN separation frame, not the best landing anywhere in the grid.

    Returns ``dict(pd_pre, centre_feet, csangle, n_var, n_fire, rows)``, ``rows`` keyed by ``freeze_f``
    with ``n_all``/``n_fire``/``recovery``/``recovery_all``/``plow``/``plow_all``/``pd_post``/``knobs``
    (``recovery``/``plow``/``pd_post``/``knobs`` are the FIRING population; ``None`` where none fires)."""
    ex, ez = seeds.ENTRY_ROLL_POS
    b_entry = world_angle_s16(ex - run0.link.pos_x, ez - run0.link.pos_z)
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    cs = int(run0.csangle) if csangle == 'live' else (snap_csangle(run0) if csangle == 'snap'
                                                     else int(csangle))
    if cs is None:
        cs = int(run0.csangle)
    pd0 = FH._placement_dist(run0, placements)
    rows, n_var, n_fire = {}, 0, 0
    for flip in flip_arc(hl, step=int(flip_step)):
        for ro in tuple(rotate_offs):
            for ta in (False, True):
                for side in (1, -1):
                    for exb in (b_entry, up_herd):
                        r = escape_atom(run0, hl, turnaround_first=ta, rotate_side=side,
                                        rotate_off=ro, flip_bearing=flip, exit_bearing=exb,
                                        csangle=cs, max_frames=max_frames)
                        n_var += 1
                        if r is None or r['freeze_f'] is None:
                            continue
                        d = rows.setdefault(r['freeze_f'],
                                            dict(n_all=0, n_fire=0, recovery=None,
                                                 recovery_all=-1e9, plow=None, plow_all=0.0,
                                                 pd_post=None, knobs=None))
                        rec = pd0 - FH._placement_dist(r['run'], placements)
                        plow = push_profile(r)['total']
                        d['n_all'] += 1
                        d['recovery_all'] = max(d['recovery_all'], rec)
                        d['plow_all'] = max(d['plow_all'], plow)
                        if not fires(r):
                            continue
                        n_fire += 1
                        d['n_fire'] += 1
                        d['plow'] = plow if d['plow'] is None else max(d['plow'], plow)
                        if d['recovery'] is None or rec > d['recovery']:
                            d['recovery'], d['pd_post'] = rec, pd0 - rec
                            d['knobs'] = dict(turnaround_first=ta, rotate_side=side,
                                              rotate_off=ro, flip_bearing=flip, exit_bearing=exb)
    return dict(pd_pre=pd0, centre_feet=FH._centre_feet(run0), csangle=cs, n_var=n_var,
                n_fire=n_fire, rows=rows)


def flip_arc(hl, *, step=0x400, half=FLIP_SPAN, center=None):
    """The flip bearings a swept probe tries: ``center +- half`` thinned by ``step``, with the herd's
    own down-bearing (the shipped default, `escape_atom`'s ``flip_bearing=None``) always included so
    a swept probe can never rank worse than the unswept one. Sorted by distance from that default, so
    a truncated sweep degrades toward it rather than to an arbitrary member.

    ``half`` is a BUDGET, not a bound, and session 72 measured the cost of mistaking it for one. The
    branch that gates the conversion is `getDirectionFromAngle`'s DIR_BACKWARD cone -- 90 deg wide
    about 180, `DIR_BACKWARD_CONE`, the constant `knowledge/reference/constants.md` already names --
    which looks like a derived arc about ``travel + 0x8000``. It is not: the cone is about ``travel``
    AT THE CONVERSION FRAME, which the optional ESS snap and the L frame's own travel chase move. On a
    real 71-frame arrival the variant that lands **1.644 u** at the accepted 75-frame budget sits
    **61 deg** off the ARRIVAL's back-bearing -- outside the cone -- where the best variant inside it
    lands 4.112. So `FLIP_SPAN` is simply wide enough for every firing variant s72 measured (winners
    out to +-56 deg), a caller that cares can widen to the full circle (``half=0x8000``), and `fires`
    stays the filter."""
    down = hl.bearing_bam()
    cen = down if center is None else (int(center) & 0xFFFF)
    out = {down}
    for d in range(-int(half), int(half) + 1, int(step)):
        out.add((cen + d) & 0xFFFF)
    return sorted(out, key=lambda b: abs(_s16(b - down)))


def probe(run0, hl, *, max_frames=18, thread=None, flip_step=None, rotate_offs=None, rank='miss',
          csangle='live'):
    """Sweep the atom's knobs from a terminal state and return the best variant.

    Rank: L-cone compliance first (Dereck's rule -- a locking variant is wrong tech however fast),
    then fewest post-separation dips (the s65 bar), then earliest receding->=17, then entry
    progress. Small by design (~16 variants); the atom is 4-5 inputs + a held exit stick, not a
    search space. ``turnaround_first`` is swept rather than inferred: a terminal already faced
    away wastes a frame (and ~10 u of extra push) on the snap, one still facing her NEEDS it --
    `l_ok` ranks the wrong choice out.

    ``thread`` (session 71) ranks the COMPLIANT variants by where they leave TETRA
    (`aim.landing_miss`) instead of by entry progress, and it is authority the search was throwing
    away. Session 67 established that the atom's conversion frames are the LAST inputs with any
    authority over her -- and then this rank spent that authority on ``d_e_end``, how far Link got
    toward the entry roll position, which belongs to the SEPARATE entry search (s60). The variants
    differ by much more than the tie-break suggested: ``rotate_side`` decides which way Link steps
    before the slam, hence where he stands relative to her, hence the eject direction -- measured, the
    residual's lateral tracks his offset from her at **-0.53 u per u** and its along collapses from
    41.6 u aligned to 6-15 u at 30-47 u off. Swept over 8 real arrivals, ranking by the landing
    improves **6 of 8** (median 2.70 u, max 10.08) and takes the best from 16.34 u off the thread to
    **6.25** at 77 frames, with ``rotate_side=+1`` winning 6 of 8.

    The acceptance is unchanged and comes FIRST: ``l_ok``, the follow shell, separation, Dereck's
    ``DIP_BUDGET`` and receding-at-the-cap are all hard terms ahead of the landing, so this only
    reorders variants that `fires` already accepts. Below the bar the order is the stock one, and
    without ``thread`` the key is bit-identical to the session-65 rank.

    ``flip_step``/``rotate_offs`` (session 72) sweep the two knobs this probe was leaving at their
    defaults, and they are the two that STEER the placement rather than merely time it. The
    conversion frames are the last inputs with authority over Tetra (s67) and ``flip_bearing`` IS the
    direction that push points -- yet it sat at the herd's own down-bearing while ``rotate_off`` sat
    at 0x4000, so the 8 variants swept everything about the atom EXCEPT where it pushes her. Measured
    on four real 71-frame arrivals of the s71 full-resolution jf-7 band, off the shipped default:
    landing **4.90 -> 0.33**, **4.99 -> 0.01**, **8.23 -> 0.00** and 7.01 -> 4.09 u, the first
    `aim.handoff_spec` True this work has produced (it needs the landing inside
    `objective.PLACEMENT_BAND` 1.0), and separately a 2-frame gain on the escape's own bound
    (77.50 -> 75.13). ``flip_step`` thins `flip_arc`, the DIR_BACKWARD arc derived per state; the
    landing is PIECEWISE CONSTANT in the flip bearing (plateaus 10-25 deg wide), so 0x400 resolves
    every plateau -- a 0x40 pass over the same span found nothing between them. Default None keeps
    the shipped single default, so an unswept call is bit-identical.

    ``rank='frames'`` is what the flip sweep MAKES necessary, and it is not a preference: the sweep
    buys landing WITH frames (the same arrival reaches 0.33 u at ``freeze_f`` 12 and 1.64 u at 4), so
    a landing-only rank spends 8 frames on 1.3 u against an objective that allows 2 over the floor
    (`objective.frame_floor`). The frames key is the landing in the objective's OWN currency --
    ``freeze_f + objective.thread_frames(landing)``, i.e. `full_herd.escape_probe`'s ``bound`` minus
    the arrival frames, which are constant across variants -- with the miss kept as the tie-break.
    Measured on the same four arrivals it is worth 2.4 frames of bound (77.50 -> 75.13) where the
    miss rank reads 83.06. Default ``'miss'`` so the s71 key is bit-identical.

    ``csangle`` (session 73) is the camera convention every variant is run at, and its default is now
    the honest one:
      * ``'live'`` (default) -- the arrival's own csangle. The atom's C-stick is neutral so the camera
        holds it, and the prediction is what a plain replay delivers. This is a CHANGE: s65-s72 ran
        every variant at `snap_csangle`, 91-114 deg off live on real arrivals, a camera state nothing
        in the plan paid for (`snap_bill`). What buys the window is the last roll's ``target_cs``
        (`full_herd.ESCAPE_TCS_SPAN`), and measured over 112 arrivals 63 of them reach a snapping
        camera state inside their own roll's slew -- at which point the window IS live and this mode
        sees it.
      * ``'snap'`` -- command `snap_csangle` (the nearest window member). The old behaviour, kept for
        research and for a caller that has separately shown the roll can deliver it. Every result
        carries ``cs_bill``, so a billed variant can never be mistaken for a faithful one.
      * an int -- that csangle exactly.

    ``turnaround_first`` is swept UNCONDITIONALLY, and until session 75 it was not: a variant was
    skipped whenever `snaps_at` reported no window at the csangle, on the reading "no window -> the
    snap cannot fire". That is a SUFFICIENT condition used as a NECESSARY one -- the same shape of
    error session 73 found in the snap scan order -- and it discards real escapes. What the ESS frame
    has to earn is ``l_ok``, i.e. the L must not act with Tetra in the front cone, and the snap is only
    one way to earn it: on the banked ``deep`` arrival (`fixtures/courtyard_arrivals_s75.json`, a real
    74-frame jf-10 arrival) the ESS turns **0x1425 = 28.3 deg**, well under `_SNAP_MIN_TURN`, and Tetra is
    STILL in the cone immediately after it -- yet the variant fires, because the cone is cleared a
    frame later, by the frame the L acts on. Over the 10 closest arrivals of the session-74 jf-9/jf-10
    probe the guard turned a FIRING escape (``freeze_f`` 4, pd **7.739**, ``cs_bill`` 0) into a
    non-firing one (pd 8.147) on **7** of them and changed nothing on the other 3.

    `fires` is the acceptance and always was; the guard only decided which variants got to be judged by
    it. Removing it buys no FRAMES on the population that motivated it (78 against the shipped 75) and
    is inert on the synthetic bed (56 turnaround variants run at its live csangle, 0 fire); what it buys
    is that a keep no longer prunes on a condition the physics does not require. It costs at most 2x the
    variant count, and only where the camera has no window (where the window exists nothing changes).
    Gate:
    `tests/test_away_walk.py::test_a_non_snapping_camera_does_not_veto_the_turnaround`, which pins the
    result as INDEPENDENT of `snaps_at` -- re-introducing any form of the guard fails it."""
    ex, ez = seeds.ENTRY_ROLL_POS
    b_entry = world_angle_s16(ex - run0.link.pos_x, ez - run0.link.pos_z)
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    # The camera convention is a property of the START state, so resolve it once for all variants.
    if csangle == 'live':
        cs = int(run0.csangle)
    elif csangle == 'snap':
        cs = snap_csangle(run0)
    else:
        cs = int(csangle)
    flips = [None] if flip_step is None else flip_arc(hl, step=int(flip_step))
    rots = ROTATE_OFFS[1:2] if rotate_offs is None else tuple(rotate_offs)
    best = None
    for flip in flips:
        for ro in rots:
            for ta in (False, True):
                for side in (1, -1):
                    for exit_b in (b_entry, up_herd):
                        r = escape_atom(run0, hl, turnaround_first=ta, rotate_side=side,
                                        rotate_off=ro, flip_bearing=flip, exit_bearing=exit_b,
                                        csangle=cs if cs is not None else int(run0.csangle),
                                        max_frames=max_frames)
                        if r is None:
                            continue
                        key = (not r['l_ok'], r['followed'], r['freeze_f'] is None, len(r['dips']),
                               r['rec17_f'] if r['rec17_f'] is not None else 99,
                               r['d_e_end'] if r['d_e_end'] is not None else 1e9)
                        if thread is not None:
                            from harness.tetrapush import aim as A
                            from harness.tetrapush import objective as O
                            # the acceptance stays ahead of the landing; only ACCEPTED variants move
                            lm = A.landing_miss(run0, hl, thread,
                                                (r['resid_along'], r['resid_lat']))
                            if rank == 'frames':
                                # the landing priced in the objective's own currency, plus what the
                                # separation itself costs -- the trade the flip sweep creates
                                cost = ((r['freeze_f'] or 0)
                                        + O.thread_frames(lm['along'], lm['lat'], thread))
                                key = (not fires(r), cost, lm['miss']) + key
                            else:
                                key = (not fires(r),) + (lm['miss'],) + key
                        r['knobs'] = dict(turnaround_first=ta, rotate_side=side,
                                          exit_bearing=exit_b, rotate_off=ro, flip_bearing=flip)
                        if best is None or key < best[0]:
                            best = (key, r)
    return best[1] if best else None


# --------------------------------------------------------------------------- CLI

def _print_atom(res):
    k = res.get('knobs', {})
    print("knobs %s" % k)
    print("csangle %d (bill %+d BAM = %.1f deg off live -- 0 is replay-faithful)"
          % (res['csangle'], res['cs_bill'], abs(res['cs_bill']) * _BAM_DEG))
    print("l_ok %s  followed %s  freeze f%s  reversed f%s  receding>=17 f%s  dips %s"
          % (res['l_ok'], res['followed'], res['freeze_f'], res['reversed_f'],
             res['rec17_f'], res['dips']))
    print("tetra residual %.3f u (along %+.3f lat %+.3f); entry gap at end %.1f u"
          % (res['resid'], res['resid_along'], res['resid_lat'], res['d_e_end']))
    print("  f proc  speedF    disp   head     cf    d_t    d_e   tres  tstep    rec")
    for rr in res['rows']:
        print("  %2d %3d %8.3f %7.3f %6s %6.1f %6.1f %6.1f %6.2f %6.2f %+7.2f"
              % (rr['f'], rr['proc'], rr['speedF'], rr['disp'],
                 rr['head'] if rr['head'] is not None else '-', rr['cf'], rr['d_t'],
                 rr['d_e'], rr['tres'], rr['tstep'], rr['rec']))
    p = push_profile(res)
    print("push over the %d frames to separation: %.3f u/frame = %.1f%% of the %.1f ceiling "
          "(dead frames %s) -> %.2f frames of timeloss from the escape alone"
          % (p['frames'], p['rate'], 100.0 * p['saturation'], p['ceiling'], p['dead'],
             p['frames_lost']))


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
        bill = snap_bill(run)
        print("=== the escape atom off the synthetic hot terminal (coord 287) ===")
        print("camera bill: %s\n" % bill)
        for mode in ('live', 'snap'):
            res = probe(run, hl, csangle=mode)
            print("--- csangle=%r -> %s" % (mode, "FIRES" if fires(res) else "does NOT fire"))
            if res is not None:
                _print_atom(res)
            print("")
        print("The bed's own live csangle is %.1f deg outside the snap window, so nothing fires\n"
              "there: a synthetic terminal has no roll to have paid the bill (session 73). On a real\n"
              "arrival the last roll's target_cs buys the window -- 63 of 112 measured arrivals can."
              % (bill['deg'] or 0.0))
    elif cmd == 'trace':
        res = escape_atom(run, hl, csangle=snap_csangle(run))
        _print_atom(res)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
