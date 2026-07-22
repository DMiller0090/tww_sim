"""The Courtyard from-f0 (and roll-entry) COUPLED replay -- the full-depth CC coupling wired together.

This is the last piece before the planner: seed a closed-loop `LandState` (Link) + a tracked Tetra
point at state 2 (or a roll entry), drive Link with the REAL DTM controller bytes, and apply BOTH
gated plow laws each frame:

  * `link_plow.recoil`  -- Link recoils the FULL Co-overlap depth AWAY from Tetra (his own slowdown),
  * `tetra_plow.plow_step` -- Tetra is shoved the FULL depth AWAY from Link (the herd),

each computed from Link's ANIMATED mCyl Co centre. Both eject the full `cross_len` (the mirror pair,
2*depth total separation per frame -- the live 41-85 u chase-and-plow). Tetra is stt-3 the WHOLE
Courtyard window (pure plow, speedF 0 -- see the cyl-fixture timeline), so she is a bare XZ point
moved by `tetra_plow`; there is no follow leg to model here.

This is the COURTYARD-SPECIFIC full-depth coupling. It does NOT touch the general FOLLOWING-Tetra
sandbox (`harness/rollstab/cc_stepper` + `core/cc_push.co_move_pair`, a gated 50/50) -- that stays the
default for the sandbox.

Two modelling shortcuts, both deliberate (see README "## Plan / status" from-f0 box):
  * Link's mCyl Co centre is INJECTED per frame from the live capture (`courtyard_push_cyl.json`
    `link.cyl`) rather than modelled offline -- the MOVE-phase `daPy_lk_c::setCollision` centre is not
    yet ported (`body_cyl.roll_co_center` only covers rolls). A future `move_co_center` replaces the
    injection; the coupling code here is unchanged by that swap.
  * `csangle` is INJECTED per frame (`_cam.yaw` forced, C-stick neutral) rather than integrated from
    the substick -- the "inject the camera, don't model it" convention (the frozen-cam shortcut the
    tier test uses, generalised to the captured per-frame value).

VALIDATED (`tests/test_from_f0.py`), seeded at the FIRST roll entry: the replay now CHAINS bit-exact
through cycle 2's roll -- f4..f44 is 0-ULP (every speedF, every proc, Link pos <1.4e-4 u), covering
cycle 1 (roll + the 2-frame ATN_ACTOR untarget tier -25.727/-25.452 + backslide), the whole
backslide->roll-setup re-target (proc-7 entry f26, the +18 flip f28, cyc2 roll f29), and cycle 2's
roll. Tetra is 0-ULP over the whole window. The gated range stops at f44, before the cyl fixture's
single-step-jittered cyc2 untarget (f45+, session-8 known corruption).

Runs at `input_delay=1` (see `_seed_link`): the DTM stream IS the polled `g_mDoCPd` pad, already one
pipeline stage into the raw-controller latency `LandState` models from (shipped default 2, for the live
walk goldens) -- so a DTM replay is delay-1 (live-probed s11: `m34E8`/roll-A/soft-L all land 1 frame
after the DTM). This is what makes the +18 re-target flip land on the right frame. The remaining gap is
the TRUE f0 seed (state 2): all procs match from f0 but f1-f2 speedF is off ~0.4/0.2 -- the seed must
carry the prior cycle's `mDirection` + attention-RELEASE residual (Link is mid-backslide at f0).

Pure-sim / no calibration: the replay takes only the seed + the DTM bytes + the injected centre/csangle
(all from the locked capture); the diff against the capture is the out-of-band gate, never in a loop.
Pure stdlib, no Dolphin."""
import struct

from tww_sim.land.land import LandState, FRONT_ROLL, MOVE
from harness.tetrapush.link_plow import recoil
from harness.tetrapush.tetra_plow import plow_step


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _yaw_from_csangle(csangle):
    """The `dCamera_c` yaw for a captured `csangle` (== `(yaw + 0x8000) & 0xFFFF`), so forcing
    `_cam.yaw` with a neutral C-stick holds `csangle` frozen at the injected value that frame."""
    return (int(csangle) - 0x8000) & 0xFFFF


def full_depth_push(link_center, tetra_xz):
    """The Courtyard full-depth CC push for one frame, as the two gated laws: returns
    ``((link_dx, link_dz), (tetra_dx, tetra_dz))`` -- Link's recoil (`link_plow.recoil`, full depth
    away from Tetra) and Tetra's move (`tetra_plow.plow_step` delta, full depth away from Link),
    computed from Link's Co centre ``link_center`` (x, z or x, y, z) and Tetra's feet ``tetra_xz``.
    The two are exact opposites of the same magnitude (both eject the full `cross_len`)."""
    tx, tz = float(tetra_xz[0]), float(tetra_xz[-1])
    rlx, rlz = recoil(link_center, (tx, tz))
    ntx, ntz = plow_step(link_center, (tx, tz))
    return (float(rlx), float(rlz)), (float(ntx) - tx, float(ntz) - tz)


def _seed_link(row, csangle):
    """Seed a Python-path `LandState` from a captured frame ``row`` (``{proc, pos, facing, travel,
    speedF}`` under ``row['link']``). A roll entry is seeded FRONT_ROLL with speedF pinned at 26.0
    (constant-momentum roll -- the `couple_replay` convention, no foot-warming); any other proc is
    seeded at its live speedF with the foot stream warm (the backslide entered its proc mid-run, so
    `getOldFrameFlg` is already true)."""
    ll = row['link']
    proc = row['proc']
    # input_delay=1: the DTM stream IS the polled `g_mDoCPd` pad, one pipeline stage into the sim's
    # raw-controller latency, so physics + attention both act on the delay-1 pad (see README roll-setup).
    if proc == FRONT_ROLL:
        link = LandState(pos_x=ll['pos'][0], pos_z=ll['pos'][2], pos_y=ll['pos'][1],
                         facing=ll['facing'], travel=ll['travel'], csangle=csangle,
                         state=FRONT_ROLL, nspeed=26.0, speedF=26.0,
                         use_anim=True, native=False, sword_drawn=False, input_delay=1)
        link._roll_m3570 = False           # seeded mid-roll: live grinds (no bonk) -> m3570 False
    else:
        link = LandState(pos_x=ll['pos'][0], pos_z=ll['pos'][2], pos_y=ll['pos'][1],
                         facing=ll['facing'], travel=ll['travel'], csangle=csangle,
                         state=proc, nspeed=ll['speedF'], speedF=ll['speedF'],
                         use_anim=True, native=False, foot_native=False, sword_drawn=False,
                         input_delay=1)
        link._foot.started = True
    return link


def replay(frames, input_at, entry, upto=None, pre_inputs=None):
    """Run the coupled from-f0 replay and diff BOTH actors vs the live capture, frame by frame.

    ``frames``   -- the live-capture rows (the cyl fixture), each ``{proc, csangle, link:{pos, facing,
                    travel, speedF, cyl}, tetra:{pos, stt, speedF}}``; ``frames[i]`` is game-frame i.
    ``input_at`` -- ``input_at(k)`` -> the raw controller tuple ``(sx, sy, buttons, triggerL)`` (or a
                    6-tuple; extra entries ignored) delivered at game-frame ``k`` (from the DTM).
    ``entry``    -- the seed frame (0 = true state-2 from-f0; a roll-entry index = the validated mode).
    ``upto``     -- exclusive end frame (default ``len(frames)``).
    ``pre_inputs`` -- optional pre-seed for the delay-1 controller buffer; a single input (or a
                    1-tuple/list). If omitted, uses ``input_at(entry)`` (the convention: after seeding
                    state[entry], ``step(input_at(entry+1))`` acts on ``input_at(entry)`` at
                    input_delay=1 -- physics reads the delay-1 DTM pad). See the README from-f0 box.

    Link's Co centre and csangle are injected from ``frames`` each frame; Tetra is a tracked XZ point
    moved by the full-depth plow. Returns a list of per-frame dicts: ``f``, live/sim ``proc``,
    ``sim_link``/``live_link`` and ``sim_tetra``/``live_tetra`` (x, z), the sim-minus-live position
    ULP diffs ``dlx/dlz/dtx/dtz`` (0 == bit-exact), and ``speedF``/``live_speedF``."""
    if upto is None:
        upto = len(frames)

    e = frames[entry]
    link = _seed_link(e, e['csangle'])
    if pre_inputs is not None:
        pi = pre_inputs[-1] if isinstance(pre_inputs, (list, tuple)) and pre_inputs and \
            isinstance(pre_inputs[0], (list, tuple, dict)) else pre_inputs
        link._inbuf = [_step_args(pi)]
    else:
        link._inbuf = [_step_args(input_at(entry))]     # delay-1: state[entry+1] acts inp[entry]

    tx, tz = e['tetra']['pos'][0], e['tetra']['pos'][2]
    pend_link, pend_tetra = full_depth_push(e['link']['cyl'], (tx, tz))

    out = []
    for k in range(entry + 1, upto):
        # inject the start-of-frame csangle (the previous frame's integrated value; C-stick neutral so
        # the forced yaw holds), then consume the pending full-depth pushes from frame k-1's snapshot.
        link._cam.yaw = _yaw_from_csangle(frames[k - 1]['csangle'])
        link.set_cc_move((pend_link[0], 0.0, pend_link[1]))
        link._atn_actor_pos = (tx, tz)             # Link Z-targets Tetra (drives the ATN_ACTOR tier)
        link.step(*_step_args(input_at(k)))
        tx += pend_tetra[0]
        tz += pend_tetra[1]

        lv = frames[k]
        out.append(dict(
            f=k, sim_proc=link.state, live_proc=lv['proc'],
            sim_link=(link.pos_x, link.pos_z), live_link=(lv['link']['pos'][0], lv['link']['pos'][2]),
            sim_tetra=(tx, tz), live_tetra=(lv['tetra']['pos'][0], lv['tetra']['pos'][2]),
            speedF=link.speedF, live_speedF=lv['link']['speedF'],
            dlx=_bits(link.pos_x) - _bits(lv['link']['pos'][0]),
            dlz=_bits(link.pos_z) - _bits(lv['link']['pos'][2]),
            dtx=_bits(tx) - _bits(lv['tetra']['pos'][0]),
            dtz=_bits(tz) - _bits(lv['tetra']['pos'][2])))
        # end-of-frame k check: the push consumed producing state[k+1] uses frame-k's SETTLED centre
        # + Tetra pos (the decomp draw-phase Ccsp()->Move() order).
        pend_link, pend_tetra = full_depth_push(frames[k]['link']['cyl'], (tx, tz))
    return out


def _step_args(inp):
    """Normalise a raw controller tuple/dict to the 6-arg `LandState.step` call (C-stick neutral --
    csangle is injected via `_cam.yaw`, not steered)."""
    if isinstance(inp, dict):
        return (int(inp['stickX']), int(inp['stickY']), int(inp.get('buttons', 0)),
                int(inp.get('triggerL', 0)), 128, 128)
    t = tuple(inp)
    return (int(t[0]), int(t[1]), int(t[2]) if len(t) > 2 else 0,
            int(t[3]) if len(t) > 3 else 0, 128, 128)
