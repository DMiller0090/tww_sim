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
"""The PER-CYCLE BRANCHING SEARCH for the frame-minimal Courtyard Tetra push (session 40).

This is the search the session-39 handoff called for, built on the realizable primitives
`steered_reposition.py` validated. It replaces the two beams that failed:

  * s38's native-fleet BFS and s39's full-Python beam were both PER-FRAME GREEDY on down-herd
    progress. Both find ZERO rolls -- the continuous glide-push scores better frame-by-frame, so
    the beam is absorbed into a lateral-drift local optimum and every roll prunes as an overshoot.
  * Both also treated csangle as a free per-frame lever. It is NOT: the camera yaw only moves via
    the C-stick at a bounded rate (`steered_reposition.camera_authority`), so an injected-csangle
    plan is unrealizable on console.

THE STRUCTURE (Dereck's s39 design, made concrete)
--------------------------------------------------
The unit of search is a CYCLE, not a frame -- so a roll is committed whole and scored on the herd
it delivers, never out-competed mid-flight by a glide. One cycle, from an armed EBS root:

  A "glide"   -- ``nglide`` frames of the EBS backslide at a SMALL stick magnitude (``glide_msd``),
                 aimed up-herd + ``glide_off``. Small msd is the human's glide: the speed decays
                 only ~0.01/frame (a full stick costs ~3.5/frame, which is what made the s40 first
                 draft's roll fire at +18.5 instead of +26). Since the backslide's facing tracks the
                 stick and the MOTION is opposite it, aiming up-herd both faces Link AWAY from Tetra
                 (-> TALK-SAFE for free, no dedicated turn frames) and steers his position. Substick
                 free -> steer toward ``target_cs``.
  B "flip"    -- ``nflip`` frames of L-held + stick toward Tetra. Facing is away so Tetra is out of
                 the +-0x4000 cone: L RE-TARGETS (proc 7) instead of hard-locking (proc 9), and the
                 DIR_BACKWARD negation flips the -25.7 backslide to a POSITIVE pre-roll speed.
  C "trigger" -- A + stick toward ``roll_aim``. Gated on `search.a_press_is_talk` (facing away ->
                 safe). Pre-roll speed >= ~17 makes `_roll_init` clamp to the full +26, not the +5
                 floor (the s32 weak-roll defect).
  D "roll"    -- ~16 frames, facing LOCKED: ZERO branching. Hold the stick on the aim, hold L until
                 ``release_at`` then drop it (the 1-frame untarget tier -> the -25.727 retention),
                 and spend the free substick pre-rotating the camera to ``target_cs_next`` -- the
                 csangle the NEXT cycle's glide phase needs. Exits at the next armed EBS root.

THE HERD-RATE CEILING (s40; `push_ceiling` / the ``ceiling`` CLI) -- READ THIS BEFORE OPTIMIZING
------------------------------------------------------------------------------------------------
Both actors eject the FULL Co overlap depth each contact frame (the gated 50/50 half-from-exec law),
so a contact frame is a pure SPLIT of Link's step: he advances ``|speedF| - e`` down-herd and Tetra
advances ``e``. A sustained push is the steady state ``|speedF| - e == e``, i.e.

    herd rate  <=  |speedF| / 2  =  13.0 u/frame   (speedF is capped at 26 by `_roll_init`)

Measured on the recorded human window: mean Link down-herd move 12.627 u/f, mean Tetra 12.761 u/f,
sum 25.388 == mean |speedF|. **The human runs at 12.76 u/f = 98.2% of the ceiling**, in contact 95%
of frames with a push alignment of ~1.000 (essentially perfectly down-herd) on every one.

That single fact explains every prior negative result and re-points this search:
  * A ROLL IS NOT PRIVILEGED. The -25.7 backslide pushes as hard as the +26 roll (25.7/2 vs 26/2),
    which is why the s38/s39 greedy beams "found no rolls" and were not wrong to -- the glide-push
    local optimum they fell into is worth 98% of a roll. The rolls matter for talk-safety and for
    holding 26 over 25.4, not for the push itself.
  * NO REPOSITION CAN PAY FOR ITSELF. Any frame out of contact, or at reduced |speedF|, is a direct
    unrecoverable loss; there is no compensating mechanism, because the rate depends on NOTHING but
    |speedF| and contact.
  * FRAME-MINIMAL therefore reduces to: maximize the sum of |speedF| over frames subject to staying
    in contact and on-line. The human's residual is ~1.8% -- his two lost-contact frames (f9, f35,
    where d crosses 85 > the 80 u contact radius) and the frames spent at -25.4 rather than +26.
    That is the whole remaining prize on the push proper: ~1.3 frames over a ~75-frame push.

BRANCHING is at the JUNCTIONS only (phases A-C), over the knobs in `Knobs`; phase D is
deterministic. Pruning is the s33/s32 physics: past-Tetra / off-line (`reposition.HerdLine`),
talk-unsafe (`search.a_press_is_talk`), out-of-regime (`FreeRun._follow_warned`), and rolless.
Ranking is FRAME-MINIMAL (`[[tetrapush-frame-minimal]]`): down-herd gained per frame spent.

REALIZABILITY IS ENFORCED, NOT ASSUMED. Every run here is a full `from_f0.FreeRun` with the
camera and zl1 look wired (`seeds.make_freerun`), so csangle is DRIVEN by the delivered substick
and the proc-7/9 re-aim uses Tetra's eyePos (the s38 -102-BAM stripped-sim defect cannot occur).
`bit_confirm` replays a plan's raw bytes on a FRESH run and checks the trajectory 0-ULP.

DELAY-1 (the trap that burned s39's scratch probes, `[[run-dtm-1frame-jitter]]`): a delivered stick
acts on the NEXT frame while an injected csangle acts on THIS one -- so a single-step observation of
a turnaround is meaningless, and the `reposition.turnaround` snap cannot be reproduced by choosing
stick bytes at the live csangle (probed s40). Phases here therefore HOLD a command for their whole
duration and read back the achieved state, never a one-frame delta.

Pure stdlib, no Dolphin. CLI:
``python -m harness.tetrapush.steered_search {probe | cycle | search | confirm}``.
"""
import math
import struct

from harness.tetrapush import seeds
from harness.tetrapush import search as S
from harness.tetrapush.reposition import HerdLine, on_line_ok
from harness.tetrapush.steered_reposition import _s16, _bearing
from tww_sim.land.land import FRONT_ROLL
from tww_sim.land.plan_land._primitives import stick_for_bearing


# The substick deadband: |target - live| below this is close enough to hold neutral (which FREEZES
# csangle -- `steered_reposition.camera_authority`). Above it, peg the stick (~+-460..530 BAM/frame).
CS_DEADBAND = 300
CSTICK_NEUTRAL = 128
# Phase-D exit: a roll longer than this never returns to an EBS root (the plan is malformed).
MAX_ROLL_FRAMES = 30
# Phase-A cap: the facing chase needs a handful of frames to swing ~180 out of the cone.
MAX_TURN_FRAMES = 8


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _sub_toward(live_cs, target_cs):
    """The substickX byte that steers the camera yaw toward ``target_cs`` (neutral = FREEZE)."""
    if target_cs is None:
        return CSTICK_NEUTRAL
    gap = _s16(int(target_cs) - int(live_cs))
    if gap > CS_DEADBAND:
        return 255
    if gap < -CS_DEADBAND:
        return 0
    return CSTICK_NEUTRAL


def _inp(bearing, csangle, msd, *, buttons=0, triggerL=0, subx=CSTICK_NEUTRAL):
    """One delivered raw-input dict: main stick aimed at world ``bearing`` under the live
    ``csangle`` (the clamp-aware `stick_for_bearing` inverse), C-stick held DOWN (substickY = 0
    keeps `manualCamera` mode 12) with ``subx`` the camera yaw command."""
    sx, sy = stick_for_bearing(int(bearing) & 0xFFFF, int(csangle), msd=min(msd, 1.0))
    return dict(stickX=sx, stickY=sy, buttons=buttons, triggerL=triggerL,
                substickX=subx, substickY=0)


class Knobs(dict):
    """The per-cycle junction knobs (phase D takes none -- rolls do not branch).

    ``nglide``      -- phase-A length in frames (the "main-stick position" control: the free
                       reposition, at ~0.01/frame speed cost).
    ``glide_off``   -- phase-A aim, as a BAM offset from "directly up-herd". Facing follows this
                       (talk-safety); Link's MOTION is the opposite of it (position).
    ``glide_msd``   -- phase-A stick magnitude. Small == the human's EBS glide (speed retained).
    ``nflip``       -- phase-B length: how many L-held proc-7 frames build the positive pre-roll speed.
    ``roll_off``    -- phase-C aim, as a BAM offset from the herd-line down-bearing (the roll travels
                       STRAIGHT, so this is the whole pursuit geometry).
    ``release_at``  -- phase-D roll-frame at which the mid-roll lock-L is dropped (the -25.727 lever).
    ``target_cs``   -- the csangle phase D pre-rotates the camera to, for the NEXT cycle's phase A.
    """
    __getattr__ = dict.__getitem__


DEFAULT_KNOBS = Knobs(nglide=3, glide_off=0, glide_msd=0.08, nflip=2, roll_off=0,
                      release_at=15.0, target_cs=None)


# --------------------------------------------------------------------------- the herd-rate ceiling

CONTACT_RADIUS = 80.0          # R_link (30) + R_tetra (50) -- `tetra_plow.plow_depth`
ROLL_SPEED_CAP = 26.0          # `_roll_init`: clamp(pre_speedF * 1.5 + 0.5, 5, 26)


def push_ceiling(env, hl=None, rows=None):
    """Measure the SPLIT LAW that bounds every plan (see the module docstring). On each contact
    frame both actors eject the full overlap depth, so Link's step is split between them: he
    advances ``|speedF| - e`` down-herd and Tetra advances ``e``. Sustained pushing is the steady
    state ``e == |speedF| / 2``.

    Returns the recorded window's realised numbers: ``link_rate`` / ``tetra_rate`` (mean down-herd
    u/frame), ``sum_rate`` (== mean |speedF| if the split law holds), ``contact_frac``, ``align``
    (mean cosine of Tetra's push vs the herd axis), ``ceiling`` (``ROLL_SPEED_CAP / 2``) and
    ``efficiency`` (tetra_rate / ceiling)."""
    hl = HerdLine.from_env(env) if hl is None else hl
    rows = S.rollout_recorded(env, upto=45)['rows'] if rows is None else rows
    pl = pt = None
    sL = sT = sSpd = sAl = 0.0
    n = nal = ncon = 0
    for r in rows:
        lx, lz = r['link']
        tx, tz = r['tetra']
        if pl is not None:
            sL += (lx - pl[0]) * hl.dx + (lz - pl[1]) * hl.dz
            vx, vz = tx - pt[0], tz - pt[1]
            dT = math.hypot(vx, vz)
            sT += vx * hl.dx + vz * hl.dz
            if dT > 1e-9:
                sAl += (vx * hl.dx + vz * hl.dz) / dT
                nal += 1
            sSpd += abs(r['speedF'])
            n += 1
            if math.hypot(lx - tx, lz - tz) < CONTACT_RADIUS:
                ncon += 1
        pl, pt = (lx, lz), (tx, tz)
    ceiling = ROLL_SPEED_CAP / 2.0
    return dict(link_rate=sL / n, tetra_rate=sT / n, sum_rate=(sL + sT) / n,
                mean_speed=sSpd / n, contact_frac=ncon / n, align=sAl / nal if nal else 0.0,
                ceiling=ceiling, efficiency=(sT / n) / ceiling, frames=n)


# --------------------------------------------------------------------------- one cycle

def run_cycle(run, hl, knobs, *, log=None):
    """Advance ``run`` (a camera-wired `FreeRun` at an armed EBS root) through ONE full cycle under
    ``knobs``. Appends every delivered raw input to ``log`` if given, so a plan is reproducible from
    its bytes alone (`bit_confirm`).

    Returns a metrics dict: ``frames``, ``herd`` (down-herd gained this cycle), ``per_frame``,
    ``rolled``, ``roll_speedF``, ``preroll_speedF``, ``talk_unsafe``, ``worst_lead``,
    ``worst_lat``, ``on_line``, ``followed``, ``ended_ebs``, ``exit_speedF``, ``contact``
    (fraction of the cycle's frames inside the 80 u contact radius -- the ceiling metric)."""
    k = dict(DEFAULT_KNOBS, **knobs)
    frames = 0
    ncontact = 0
    talk_unsafe = False
    worst_lead = -1e9
    worst_lat = 0.0
    on_line = True
    herd0 = hl.along(run.tx, run.tz)

    def _observe():
        nonlocal worst_lead, worst_lat, on_line, ncontact
        lx, lz = run.link.pos_x, run.link.pos_z
        worst_lead = max(worst_lead, hl.lead(lx, lz, run.tx, run.tz))
        worst_lat = max(worst_lat, abs(hl.lateral(lx, lz) - hl.lateral(run.tx, run.tz)))
        if math.hypot(lx - run.tx, lz - run.tz) < CONTACT_RADIUS:
            ncontact += 1
        if not on_line_ok(lx, lz, run.tx, run.tz, hl):
            on_line = False

    def _step(d):
        nonlocal frames
        if log is not None:
            log.append(dict(d))
        run.step(d)
        frames += 1
        _observe()

    # --- A: the EBS glide. Aiming up-herd faces Link AWAY (talk-safe) while the DIR_BACKWARD
    #     backslide carries him down-herd; a small msd keeps the -25.7 (~0.01/frame decay).
    up_herd = (hl.bearing_bam() + 0x8000 + int(k['glide_off'])) & 0xFFFF
    for _ in range(int(k['nglide'])):
        _step(_inp(up_herd, run.csangle, k['glide_msd'],
                   subx=_sub_toward(run.csangle, k['target_cs'])))

    # --- B: the L-held proc-7 flip. Hard conflict (s40): the negation needs the stick ~opposite
    #     travel (at Tetra), but that faces Link at her -- losing contact AND making the A talk.
    for _ in range(int(k['nflip'])):
        fa = (_bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz))
              if k['flip_at_tetra'] else up_herd)
        _step(_inp(fa, run.csangle, k['flip_msd'], buttons=S.PAD_L, triggerL=255,
                   subx=_sub_toward(run.csangle, k['target_cs'])))
    preroll = run.link.speedF

    # --- C: the A-roll trigger (must be talk-safe at the press) -------------------------------
    #     The roll snaps facing to the stick target; the talk gate reads the PRE-press facing.
    roll_aim = (_bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz))
                + int(k['roll_off'])) & 0xFFFF
    d = _inp(roll_aim, run.csangle, 1.0, buttons=S.PAD_A,
             subx=_sub_toward(run.csangle, k['target_cs']))
    if S.a_press_is_talk(run, d):
        talk_unsafe = True
    _step(d)
    roll_speedF = run.link.speedF if run.link.state == FRONT_ROLL else None

    # --- D: the roll -- ZERO branching. Hold the aim, release L at `release_at`, steer the -----
    #     camera to `target_cs` for the NEXT cycle's phase A.
    seen_roll = run.link.state == FRONT_ROLL
    ended_ebs = False
    for _ in range(MAX_ROLL_FRAMES):
        in_roll = run.link.state == FRONT_ROLL
        hold_L = in_roll and getattr(run.link, 'roll_frame', 0.0) < float(k['release_at'])
        _step(_inp(roll_aim, run.csangle, 1.0,
                   buttons=S.PAD_L if hold_L else 0, triggerL=255 if hold_L else 0,
                   subx=_sub_toward(run.csangle, k['target_cs'])))
        if run.link.state == FRONT_ROLL:
            seen_roll = True
            if roll_speedF is None:
                roll_speedF = run.link.speedF
        elif seen_roll and run.link.state == 6:
            ended_ebs = True
            break

    herd = hl.along(run.tx, run.tz) - herd0
    return dict(frames=frames, herd=herd, per_frame=herd / frames if frames else 0.0,
                rolled=seen_roll, roll_speedF=roll_speedF, preroll_speedF=preroll,
                talk_unsafe=talk_unsafe, worst_lead=worst_lead, worst_lat=worst_lat,
                on_line=on_line, followed=run._follow_warned, ended_ebs=ended_ebs,
                exit_speedF=run.link.speedF,
                contact=ncontact / frames if frames else 0.0)


def cycle_ok(m):
    """The hard prune: a cycle is usable only if it actually rolled, stayed talk-safe, never
    overtook Tetra, stayed in the stt-3 plow regime, and came back to an EBS root to chain from."""
    return (m['rolled'] and not m['talk_unsafe'] and not m['followed'] and m['ended_ebs']
            and m['on_line'] and m['worst_lead'] < 0.0)


# --------------------------------------------------------------------------- bootstrap

BOOTSTRAP_PREFIXES = (20, 21, 22, 23, 24, 25)


def bootstrap_roots(env, *, prefixes=BOOTSTRAP_PREFIXES):
    """The cycle-1 bootstrap: replay the RECORDED inputs (the actual TAS bytes, so realizable by
    construction) for ``prefix`` frames and hand the resulting armed EBS root to the search.

    Why the recorded prefix and not a re-aimed `_steered_cyc1`: measured s40, the re-aimed cyc1
    lands ~+10 u OFF-line (its pinned C-stick perturbs the razor cone margin -- the s31 byte-
    quantization sensitivity), and an off-line push is SELF-DESTABILISING (each off-centre contact
    shoves Tetra further sideways, ~+8 u/frame, until contact is lost). The recorded prefix lands
    on-line (lat +6.4 at f21) where the push self-stabilises, and from THAT root our own glide phase
    reproduces the human's lateral behaviour frame for frame. Bootstrapping on-line is step 1 of the
    s39 plan; the prefix length is the knob.

    Returns ``[(tag, run, frames)]``."""
    dtm = seeds.dtm_input_at(env)
    out = []
    for pre in prefixes:
        run = seeds.make_freerun(env)
        run.pre_seed_input(dtm(0))
        for k in range(1, pre + 1):
            run.step(dtm(k))
        out.append(("rec(%d)" % pre, run, pre))
    return out


# --------------------------------------------------------------------------- the branching search

def knob_grid(*, nglides=(2, 3, 4, 5, 6), glide_offs=(-0x0800, 0, 0x0800), glide_msds=(0.08,),
              nflips=(1, 2, 3), roll_offs=(-0x0C00, -0x0600, 0, 0x0600, 0x0C00),
              release_ats=(14.0, 15.0), target_cs_offs=(None,)):
    """The junction knob grid (phases A-C + the phase-D camera target). ``target_cs_offs`` are BAM
    offsets from the herd-line down-bearing -- the camera is aimed relative to the push axis, so a
    grid entry means the same thing at every cycle; ``None`` holds the camera frozen (neutral
    substick), which is the realizable default since phase A no longer needs a camera-set facing."""
    for ng in nglides:
        for go in glide_offs:
            for gm in glide_msds:
                for nf in nflips:
                    for ro in roll_offs:
                        for ra in release_ats:
                            for co in target_cs_offs:
                                yield Knobs(nglide=ng, glide_off=go, glide_msd=gm, nflip=nf,
                                            roll_off=ro, release_at=ra, target_cs=co)


def branching_search(env, *, n_cycles=4, beam=8, grid=None, verbose=False, hl=None,
                     bootstrap=None):
    """Beam search over CYCLES. Each node is a real camera-wired `FreeRun` at an armed EBS root plus
    the raw-input log that produced it; each child is one `run_cycle` under one knob set. Nodes are
    ranked FRAME-MINIMAL -- total down-herd per total frame -- and pruned by `cycle_ok`.

    Returns ``(best, nodes)``; a node is ``dict(run, log, frames, herd, per_frame, knobs, tag,
    cycles)``."""
    hl = HerdLine.from_env(env) if hl is None else hl
    down = hl.bearing_bam()
    grid = list(knob_grid()) if grid is None else list(grid)
    herd0 = None
    nodes = []
    for tag, run, frames in (bootstrap if bootstrap is not None else bootstrap_roots(env)):
        if herd0 is None:
            herd0 = 0.0
        h = hl.along(run.tx, run.tz)
        nodes.append(dict(run=run, log=None, frames=frames, herd=h, per_frame=h / frames,
                          knobs=[], tag=tag, cycles=0))
    nodes.sort(key=lambda n: -n['per_frame'])
    nodes = nodes[:beam]
    best = nodes[0] if nodes else None
    if verbose:
        print("bootstrap: %d roots, best %.1f u / %d f = %.2f u/f (%s)"
              % (len(nodes), best['herd'], best['frames'], best['per_frame'], best['tag']))

    for level in range(n_cycles):
        nxt = []
        for node in nodes:
            for k in grid:
                kk = Knobs(dict(k, target_cs=(down + int(k['target_cs'])) & 0xFFFF
                                if k['target_cs'] is not None else None))
                c = node['run'].clone()
                log = list(node['log']) if node['log'] else []
                m = run_cycle(c, hl, kk, log=log)
                if not cycle_ok(m):
                    continue
                fr = node['frames'] + m['frames']
                h = hl.along(c.tx, c.tz)
                nxt.append(dict(run=c, log=log, frames=fr, herd=h, per_frame=h / fr,
                                knobs=node['knobs'] + [kk], tag=node['tag'],
                                cycles=node['cycles'] + 1, last=m))
        if not nxt:
            if verbose:
                print("cycle %d: NO viable child (every knob set pruned)" % (level + 2))
            break
        nxt.sort(key=lambda n: -n['per_frame'])
        nodes = nxt[:beam]
        if best is None or nodes[0]['per_frame'] > best['per_frame']:
            best = nodes[0]
        if verbose:
            b = nodes[0]
            print("cycle %d: %d viable children -> beam %d; best %.1f u / %d f = %.2f u/f "
                  "(roll %.1f, lead %+.1f, lat %.1f)"
                  % (level + 2, len(nxt), len(nodes), b['herd'], b['frames'], b['per_frame'],
                     b['last']['roll_speedF'] or 0, b['last']['worst_lead'], b['last']['worst_lat']))
    return best, nodes


# --------------------------------------------------------------------------- bit-confirm

def bit_confirm(env, node):
    """Re-run a node's RAW INPUT LOG on a FRESH camera-wired `FreeRun` (from the bootstrap root's
    own prefix) and compare both actors' positions bit-for-bit. A plan that survives this is defined
    by its bytes alone -- nothing injected, nothing carried over from the search state.

    Returns ``(worst_ulp, n_frames)``. The bootstrap prefix is re-derived from the recorded DTM
    bytes named by the node's tag, so the confirmed plan is raw bytes end to end."""
    tag = node['tag']
    pre = int(tag[tag.index('(') + 1:tag.rindex(')')])      # tag == "rec(<prefix>)"
    dtm = seeds.dtm_input_at(env)
    fresh = seeds.make_freerun(env)
    fresh.pre_seed_input(dtm(0))
    for k in range(1, pre + 1):
        fresh.step(dtm(k))
    worst = 0
    ref = node['run']
    for d in (node['log'] or []):
        fresh.step(dict(d))
    for a, b in ((fresh.link.pos_x, ref.link.pos_x), (fresh.link.pos_z, ref.link.pos_z),
                 (fresh.tx, ref.tx), (fresh.tz, ref.tz)):
        worst = max(worst, abs(_bits(a) - _bits(b)))
    return worst, len(node['log'] or [])


# --------------------------------------------------------------------------- CLI

def _cmd_probe(env, kw):
    """One default cycle from the bootstrap root, phase by phase -- the structural readout."""
    hl = HerdLine.from_env(env)
    pre = int(kw.get('pre', 21))
    run = dict((t, r) for t, r, _ in bootstrap_roots(env, prefixes=(pre,)))["rec(%d)" % pre]
    print("armed root: proc=%d facing=%d travel=%d speedF=%.4f cs=%d talk=%s"
          % (run.link.state, run.link.facing, run.link.travel, run.link.speedF, run.csangle,
             S.talk_active(run)))
    print("herd down-bearing %d; bearing to Tetra %d"
          % (hl.bearing_bam(), _bearing((run.link.pos_x, run.link.pos_z), (run.tx, run.tz))))
    print("\n nglide nflip  preroll   roll   frames    herd    u/f   contact  lead    lat   ok")
    for nglide in (2, 3, 4, 5, 6):
        for nflip in (1, 2, 3):
            c = run.clone()
            m = run_cycle(c, hl, Knobs(DEFAULT_KNOBS, nglide=nglide, nflip=nflip))
            print("   %2d     %d   %+7.2f  %6s   %3d   %+7.2f  %5.2f   %4.0f%%  %+6.1f %5.1f  %s"
                  % (nglide, nflip, m['preroll_speedF'] or 0,
                     ("%+.2f" % m['roll_speedF']) if m['roll_speedF'] else "-",
                     m['frames'], m['herd'], m['per_frame'], 100 * m['contact'],
                     m['worst_lead'], m['worst_lat'], cycle_ok(m)))


def _cmd_cycle(env, kw):
    """Sweep the roll-aim knob at the best nflip -- the per-cycle reach of the steered cycle."""
    hl = HerdLine.from_env(env)
    pre = int(kw.get('pre', 21))
    run = dict((t, r) for t, r, _ in bootstrap_roots(env, prefixes=(pre,)))["rec(%d)" % pre]
    nflip = int(kw.get('nflip', 2))
    print("roll_off  frames  herd    u/f    roll_spF  lead     lat    ok")
    for ro in range(-0x1800, 0x1801, 0x0400):
        c = run.clone()
        m = run_cycle(c, hl, Knobs(DEFAULT_KNOBS, nflip=nflip, roll_off=ro))
        print("  %+6d   %3d  %+7.2f  %5.2f  %8s  %+6.1f  %5.1f  %s"
              % (ro, m['frames'], m['herd'], m['per_frame'],
                 ("%+.2f" % m['roll_speedF']) if m['roll_speedF'] else "-",
                 m['worst_lead'], m['worst_lat'], cycle_ok(m)))


def _cmd_search(env, kw):
    import time
    hl = HerdLine.from_env(env)
    t0 = time.perf_counter()
    best, nodes = branching_search(env, n_cycles=int(kw.get('cycles', 4)),
                                   beam=int(kw.get('beam', 8)), verbose=True, hl=hl)
    dt = time.perf_counter() - t0
    print("\n(%.1f s)" % dt)
    if best is None or best['cycles'] == 0:
        print("NO viable chained cycle found (see the per-level prune counts above).")
        return
    print("BEST: %d searched cycles, %d frames, herd %.1f u = %.2f u/frame"
          % (best['cycles'], best['frames'], best['herd'], best['per_frame']))
    placements, _ = seeds.load_placements()
    p, d = S.nearest_placement(placements, best['run'].tx, best['run'].tz)
    print("  Tetra (%.4f, %.4f) -- %.2f u from genuine coord #%d" % (
        best['run'].tx, best['run'].tz, d, p['idx']))
    ulp, n = bit_confirm(env, best)
    print("  bit-confirm on a fresh run: worst %d ULP over %d logged frames" % (ulp, n))


def _cmd_confirm(env, kw):
    hl = HerdLine.from_env(env)
    best, _ = branching_search(env, n_cycles=int(kw.get('cycles', 2)),
                               beam=int(kw.get('beam', 4)), hl=hl)
    if best is None or not best['log']:
        print("no plan to confirm")
        return
    ulp, n = bit_confirm(env, best)
    print("bit-confirm: worst %d ULP over %d frames (0 == the plan is its bytes)" % (ulp, n))


def _cmd_ceiling(env):
    """The decisive s40 measurement: the herd rate is a pure SPLIT of Link's speed, so it is capped
    at |speedF|/2 = 13.0 u/frame -- and the recorded human already runs at 98% of that."""
    c = push_ceiling(env)
    print("the CC split law on the recorded window (%d frames):" % c['frames'])
    print("  mean Link  down-herd move   %7.3f u/frame" % c['link_rate'])
    print("  mean Tetra down-herd move   %7.3f u/frame" % c['tetra_rate'])
    print("  sum                         %7.3f u/frame   (mean |speedF| = %.3f)"
          % (c['sum_rate'], c['mean_speed']))
    print("  => each contact frame SPLITS Link's step between the two actors; a sustained push is\n"
          "     the steady state e == |speedF|/2.")
    print("\n  contact frames  %.0f%%   push alignment %.4f (1.0 == perfectly down-herd)"
          % (100 * c['contact_frac'], c['align']))
    print("  CEILING  = roll cap %.1f / 2 = %.2f u/frame" % (ROLL_SPEED_CAP, c['ceiling']))
    print("  HUMAN    = %.2f u/frame = %.1f%% of the ceiling" % (c['tetra_rate'],
                                                                 100 * c['efficiency']))
    print("\n  A roll is NOT privileged (the -25.7 backslide pushes as hard as the +26 roll), and no\n"
          "  reposition can pay for itself: every out-of-contact or reduced-speed frame is a direct\n"
          "  loss. The whole remaining prize on the push proper is ~%.1f%% (~%.1f frames per 75)."
          % (100 * (1 - c['efficiency']), 75 * (1 - c['efficiency'])))


def main(argv):
    import warnings
    warnings.simplefilter('ignore')
    env = seeds.load_env()
    cmd = argv[0] if argv else 'probe'
    kw = dict(kv.split('=') for kv in argv[1:] if '=' in kv)
    if cmd == 'ceiling':
        _cmd_ceiling(env)
    elif cmd == 'probe':
        _cmd_probe(env, kw)
    elif cmd == 'cycle':
        _cmd_cycle(env, kw)
    elif cmd == 'search':
        _cmd_search(env, kw)
    elif cmd == 'confirm':
        _cmd_confirm(env, kw)
    else:
        print("usage: python -m harness.tetrapush.steered_search "
              "{ceiling | probe | cycle [nflip=N] | search [cycles=N beam=N] | confirm}")


if __name__ == '__main__':
    main(sys.argv[1:])
