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
"""Realizable camera-steered reposition -- the VALIDATED primitives for the frame-minimal push
(session 39; Dereck's live design).

The session-38 handoff wanted the zl1 eye-aim ported into the native step so the fleet search's
rolls would pursue. Investigating that in the FULL Python sim (`from_f0.FreeRun` with the 0-ULP
`land_cam` + `zl1` wired) reframed the whole blocker -- and Dereck steered to a REALIZABLE design
that makes the search both correct AND tractable. This module holds the pieces that design is built
from, each validated against the already-0-ULP forward model (fidelity is `test_from_f0`'s; the gates
here are structural / behavioural, like `test_reposition`).

THE DESIGN (why csangle is NOT a free lever, and how the cycle works)
---------------------------------------------------------------------
csangle cannot be injected per frame -- the camera yaw only moves at a BOUNDED rate via the C-stick
(`land_cam`: neutral substickX FREEZES csangle; full stick drives it ~+-460..530 BAM/frame after a
1-frame delay, so ~+-8000 BAM is reachable within a 16-frame roll). The realizable move (Dereck):

  * A ROLL locks Link's facing for ~16 frames, so during it the SUBSTICK is FREE -- spend it
    pre-rotating the camera to the csangle the NEXT turnaround needs. Deterministic given a target
    -> ZERO branching inside a roll.
  * At roll-exit the pre-positioned csangle makes the untarget land Link FACING AWAY from Tetra
    (talk-safe) and armed (the proc-7 +18 flip). No separate ESS frame is even required -- the
    steered untarget IS the turnaround.
  * From that armed, talk-safe state an A-roll toward Tetra fires a +26 pursuit roll.
  * BRANCH at the junctions (post-turnaround): the roll FACING is a free variable (any halfword,
    since facing = decode(stick, csangle) and csangle is C-stick-controllable), so PREDICT the
    plow-into-Tetra facing and fan out around it; branch the main-stick position (ESS dir/mag) and
    the release timing too.

THREE COUPLED PER-CYCLE CONTROLS (pinned this session)
------------------------------------------------------
  * CAMERA (substickX)   -> the roll FACING + talk-safety (steer during the previous roll). The
                            camera does NOT change Link's POSITION: across the whole reachable
                            `target_cs` range the armed-state lateral offset is INVARIANT (the
                            `armed` CLI -- csangle_exit varies, lat/lead do not). Facing only.
  * MAIN STICK (ESS)     -> Link's POSITION (slide on-line directly behind Tetra). This is the
                            control the camera cannot supply -- the search's positioning branch.
  * RELEASE timing       -> the speed/position tradeoff: releasing the mid-roll lock-L 1 frame early
                            retains -25.727 (vs the human's -25.454) but shifts the post-roll exit
                            geometry; the human's full tier lands the second-roll entry ON-line
                            (lat -7.8) at -25.454. Which is frame-minimal is a search question.

THE TALK-SAFE / ON-LINE TENSION (why a roll needs BOTH)
-------------------------------------------------------
The clean post-cyc1 EBS root is near on-line (lat ~+10) but FACES Tetra (talk=True) -- an A-roll
there TALKS. Turning to face away (the camera-steered turnaround) makes it talk-safe. A roll fired
talk-safe still OVERSHOOTS unless Link also rolls INTO Tetra from directly behind (on-line), so the
overlap-push carries her down-line instead of Link glancing past. So talk-safety (camera) and
on-line position (main stick) are BOTH necessary, independently.

SELF-STABILIZATION (Dereck; confirmed by the ground-truth recording)
--------------------------------------------------------------------
An on-line plow-roll KEEPS Link on-line (the recorded 2-roll human window stays behind Tetra the
whole time: worst_lead -40.3, on_line=True, |lat| < 12). So the off-line landing is a ONE-TIME
BOOTSTRAP artifact of transitioning from the human's first roll into our cycle -- once on-line, the
instant-turnaround-roll cycle self-sustains without sliding. The search therefore optimizes per-cycle
knobs WITHIN the on-line self-stabilizing regime (off-line nodes prune as non-self-sustaining),
which bounds the branching.

CLI: ``python -m harness.tetrapush.steered_reposition {authority | armed | selfstab}``.
Pure stdlib, no Dolphin (drives the self-contained `from_f0.FreeRun`).
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import search as S
from harness.tetrapush import primitives as P
from harness.tetrapush.reposition import HerdLine, l_release_early
from tww_sim.land.plan_land._primitives import stick_for_bearing
from tww_sim.land.land import FRONT_ROLL


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def _bearing(fromxz, toxz):
    """World BAM bearing from one XZ point to another (0 == +z, 0x4000 == +x)."""
    return int(math.atan2(toxz[0] - fromxz[0], toxz[-1] - fromxz[-1])
              / (2.0 * math.pi) * 65536.0) & 0xFFFF


# --------------------------------------------------------------------------- camera authority

def camera_authority(env, frames=12):
    """Measure the camera yaw steering rate: hold the post-cyc1 EBS glide with substickX pegged
    (neutral / full-left / full-right) and return the per-frame csangle drift for each. Neutral
    (128) FREEZES csangle (manual-hold, `land_cam` mode 12); full stick drives it at the steady rate.
    Returns ``{subx: [per-frame BAM deltas]}``."""
    hl = HerdLine.from_env(env)
    down = hl.bearing_bam()
    out = {}
    for subx in (0, 128, 255):
        run = _steered_cyc1(env, target_cs=None)   # neutral-camera cyc1 -> the natural EBS
        trail = [run.csangle]
        for _ in range(frames):
            gx, gy = stick_for_bearing(down, run.csangle, msd=0.35)
            run.step(dict(stickX=gx, stickY=gy, buttons=0, triggerL=0, substickX=subx, substickY=0))
            trail.append(run.csangle)
        out[subx] = [_s16(trail[i + 1] - trail[i]) for i in range(len(trail) - 1)]
    return out


# --------------------------------------------------------------------------- steered cyc1

def _steered_cyc1(env, target_cs=None, *, release_early=1):
    """Replay the first roll (the human's cyc1) from state 2 in the FULL sim (camera + zl1 wired),
    steering substickX toward ``target_cs`` DURING the FRONT_ROLL frames (neutral / camera-frozen
    otherwise), and stop at the first post-untarget MOVE EBS -- the armed state entering the SECOND
    roll. ``target_cs=None`` holds the camera neutral (the natural EBS). ``release_early`` frames of
    the mid-roll lock-L are stripped (the -25.727 retention). Camera stays ON (realizable)."""
    recs = P.window_records(env)
    macro, aim0 = S.canonical_cycle(env, recs)
    macro = l_release_early(env, macro, aim0, n=release_early) if release_early else macro
    run = seeds.make_freerun(env)
    d0 = dict(S._frame_input(macro[0], aim0, run.csangle)); d0['substickX'] = 128; d0['substickY'] = 0
    run.pre_seed_input(d0)
    seen9 = False
    for j in range(1, S.CYCLE_PERIOD):
        b = S._frame_input(macro[j], aim0, run.csangle)
        if target_cs is not None and run.link.state == FRONT_ROLL:
            gap = _s16(int(target_cs) - run.csangle)
            b['substickX'] = 255 if gap > 300 else 0 if gap < -300 else 128
        else:
            b['substickX'] = 128
        b['substickY'] = 0
        row = run.step(b)
        if row['sim_proc'] == 9:
            seen9 = True
        elif seen9 and row['sim_proc'] == 6:
            break
    return run


def armed_geometry(run, hl):
    """The reposition-relevant geometry of an armed EBS ``run``: Link<->Tetra lead (along-herd,
    <0 = behind = good), lateral offset, distance, the bearing to Tetra (the plow-into-her facing),
    talk-safety, speedF, facing."""
    lx, lz = run.link.pos_x, run.link.pos_z
    return dict(lead=hl.lead(lx, lz, run.tx, run.tz),
                lateral=hl.lateral(lx, lz) - hl.lateral(run.tx, run.tz),
                dist=math.hypot(lx - run.tx, lz - run.tz),
                bearing_to_tetra=_bearing((lx, lz), (run.tx, run.tz)),
                talk=S.talk_active(run), speedF=run.link.speedF, facing=run.link.facing,
                proc=run.link.state)


# --------------------------------------------------------------------------- self-stabilization

def recorded_online_metrics(env, upto=44):
    """The ground-truth 2-roll human window (`search.rollout_recorded`) projected on the herd line:
    total herd, worst Link lead (< 0 == always behind Tetra), and whether every frame is on-line.
    This is Dereck's self-stabilization evidence -- an on-line plow-roll KEEPS Link on-line, so the
    off-line landing is a one-time bootstrap artifact, not an intrinsic property of the cycle."""
    from harness.tetrapush.reposition import rollout_metrics
    hl = HerdLine.from_env(env)
    rec = S.rollout_recorded(env, upto=upto)
    return hl, rollout_metrics(env, rec, hl)


# --------------------------------------------------------------------------- CLI

def _cmd_authority(env):
    print("camera yaw authority (per-frame csangle BAM drift; neutral 128 must FREEZE):")
    for subx, deltas in camera_authority(env).items():
        print("  substickX=%3d: %s" % (subx, " ".join("%+d" % d for d in deltas)))


def _cmd_armed(env):
    hl = HerdLine.from_env(env)
    print("armed-state (entering roll 2) geometry vs the camera target_cs -- POSITION is invariant\n"
          "(the camera sets facing, NOT lateral position; ~+42.6 u off-line with release-early):\n")
    print("  target_cs  cs_exit facing proc  speedF    lead    lat   dist  btet  talk")
    for tcs in (None, 26000, 31000, 36000, 41000, 46000):
        run = _steered_cyc1(env, tcs)
        g = armed_geometry(run, hl)
        print("  %-9s  %5d  %5d  %d   %7.2f %+6.1f %+6.1f %5.1f %5d %s"
              % ("neutral" if tcs is None else tcs, run.csangle, g['facing'], g['proc'],
                 g['speedF'], g['lead'], g['lateral'], g['dist'], g['bearing_to_tetra'], g['talk']))


def _cmd_selfstab(env):
    hl, m = recorded_online_metrics(env)
    print("self-stabilization evidence (the ground-truth 2-roll human window on the herd line):")
    print("  herd %.1f u over %d frames = %.2f u/frame" % (m['herd'], m['frames'], m['per_frame']))
    print("  worst Link lead %+.1f u (%s), on_line=%s"
          % (m['worst_lead'], "OVERTOOK" if m['worst_lead'] > 0 else "always behind Tetra",
             m['on_line']))
    print("  => an on-line plow-roll KEEPS Link on-line; the off-line landing is a one-time\n"
          "     bootstrap artifact, not an intrinsic property of the cycle (Dereck s39).")


def main(argv):
    env = seeds.load_env()
    import warnings
    warnings.simplefilter('ignore')
    cmd = argv[0] if argv else 'armed'
    if cmd == 'authority':
        _cmd_authority(env)
    elif cmd == 'armed':
        _cmd_armed(env)
    elif cmd == 'selfstab':
        _cmd_selfstab(env)
    else:
        print("usage: python -m harness.tetrapush.steered_reposition {authority | armed | selfstab}")


if __name__ == '__main__':
    main(sys.argv[1:])
