"""IS THE ROLL THE SWEEP SCORES THE ROLL LINK ACTUALLY DOES?  (session 80, the s79 open gate)

`entry_search` scores a RESEEDED roll: `turnaround.extract_schedule_at` builds a cold LandState
already in FRONT_ROLL at nspeed 26 with an explicit (entry, facing, m351C), and forces
``_roll_m3570 = False``. A real turnaround roll arrives out of a walk carrying anim and pose history,
and `_roll_init` decides m3570 for itself. Three ways that could differ, each of which would have
invalidated the whole locus rather than merely shifted it:

  1. **the anim PHASE.** The reseed's step 0 runs `_proc_roll` with ``_roll_entered`` False, so it
     advances `roll_frame` immediately; a real roll's ENTRY frame does not advance it. The reseed's
     step 0 is therefore the roll's SECOND frame -- which is why ``link_x0`` has to be the position
     at the END of the entry frame, and why handing it the pre-entry position mismatches `chx/chz`.
  2. **the POSE/LEAN history**, which the reseed only carries as an m351C on an otherwise cold state.
  3. **the ROLL BONK.** A roll started in the open ARMS the mid-roll crash; the reseed disarms it and
     `ShoveCtx` has no crash branch at all. The clip's roll runs ~350 u into the corner and does hit
     the wall, so this is a live question, not a formality.

Measured, in the walled coupled engine (`CcCoupledStepper` + `turnaround.WALLS`, the same engine the
reseed builds into): all nine baked tables are bit-identical, and the bonk never fires before the B
edge on any (entry x facing) over the usable locus. Gated in `tests/test_entry_search.py`.

`walk_then_roll` is also how the aim alphabet is checked: never treat a commanded facing as achieved
([[search-space-contains-human]] s41) -- fire the roll and read the facing back.
"""
import os
import sys

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.core import mathlib as ML
from tww_sim.core.fp import f32, fmuls
from tww_sim.core.anim import body_cyl
from tww_sim.core.npc_zl1 import Zl1FollowState, STT_IDLE
from tww_sim.land.land import LandState, WAIT, FRONT_ROLL, CUT_F, CUT_A
from harness.rollstab import fast_shove as FS
from harness.rollstab import turnaround as TA
from harness.rollstab.cc_stepper import CcCoupledStepper
from harness.tetrapush import two_roll as TR

#: The nine fields a `ShoveCtx` is built from -- the whole of what the reseed has to get right.
TABLE_KEYS = ('dx', 'dz', 'cutx', 'cutz', 'is_pose', 'chx', 'chz', 'nroot', 'cut_step')
_ROLL_POSE = (FRONT_ROLL, CUT_F, CUT_A)


def stick_for_facing(facing, csangle, msd_min=1.0):
    """The realizable byte pair whose world facing is nearest `facing` at this camera. The default
    floor is the saturated one because a WALK stick has to reach the speedF 17 cap; an AIM does not,
    so pass ``msd_min=0`` for those (see `entry_search.aim_alphabet`)."""
    best = None
    for ang, byts in TR.reachable_stick_fan(msd_min=msd_min):
        f = (ang + 0x8000 + int(csangle)) & 0xFFFF
        d = abs(((f - int(facing) + 0x8000) & 0xFFFF) - 0x8000)
        if best is None or d < best[0]:
            best = (d, f, byts)
    return best[1], best[2]


def walk_then_roll(start, walk_bytes, aim_bytes, n_walk, b_step, csangle, n_tail=34,
                   walls=TA.WALLS, force_m3570=None, tetra=None):
    """A REAL from-rest walk, A-press turnaround roll, and UP+B thrust, in the walled coupled engine.

    Returns ``(rows, entry, tables)``: the per-frame log, the roll-entry state, and the same nine
    tables `extract_schedule_at` bakes -- read with the identical expressions, from the frame AFTER
    the entry frame (the reseed's step 0). ``force_m3570`` overrides the crash latch `_roll_init`
    computes, so the bonk can be isolated as the ONLY difference."""
    link = LandState(pos_x=start[0], pos_z=start[1], pos_y=TA.GROUND_Y, facing=0, travel=0,
                     csangle=int(csangle), state=WAIT, nspeed=0.0, speedF=0.0, use_anim=True,
                     native=False, sword_drawn=True, walls=walls)
    tpos = tetra if tetra is not None else (TA.FAR[0], FS.FAR_TETRA_Z)
    tet = Zl1FollowState(x=tpos[0], y=TA.GROUND_Y, z=tpos[1], angle_y=0, speedF=0.0, stt=STT_IDLE)
    drv = CcCoupledStepper(link, tet, walls_tetra=walls, ground_y=TA.GROUND_Y)

    inputs = [(walk_bytes[0], walk_bytes[1], 0, 0, 128, 128)] * n_walk
    inputs.append((aim_bytes[0], aim_bytes[1], 0x100, 0, 128, 128))          # A + aim
    tail = [(128, 128, 0, 0, 128, 128) for _ in range(n_tail)]
    if 0 <= b_step < n_tail:
        tail[b_step] = (128, 255, 0x200, 0, 128, 128)                        # UP + B out of the roll
    inputs += tail

    rows, entry, entry_k = [], None, None
    dx, dz, cutx, cutz, is_pose, chx, chz = [], [], [], [], [], [], []
    cut_step, nroot = None, None
    for k, inp in enumerate(inputs):
        px0, pz0, lean_in = link.pos_x, link.pos_z, link.m351C & 0xFFFF
        drv.step(*inp)
        st = link.state & 0xFF
        if entry_k is None and st == FRONT_ROLL:
            entry_k = k
            if force_m3570 is not None:
                link._roll_m3570 = force_m3570
            entry = dict(k=k, x=link.pos_x, z=link.pos_z, facing=link.facing & 0xFFFF,
                         m351C=link.m351C & 0xFFFF, nspeed=link.nspeed, m3570=link._roll_m3570,
                         walk_x=px0, walk_z=pz0, m351C_walk=lean_in)
        rows.append(dict(k=k, proc=st, x=link.pos_x, z=link.pos_z, speedF=link.speedF,
                         travel=link.travel & 0xFFFF, facing=link.facing & 0xFFFF,
                         roll_frame=link.roll_frame, m351C=link.m351C & 0xFFFF,
                         draw_lean=getattr(link, '_draw_lean', 0),
                         m3570=getattr(link, '_roll_m3570', None),
                         wall_hit=link.wall_hit, cir=bool(link.wall_cir_hit[0])))
        if entry_k is not None and k > entry_k and cut_step is None:
            dx.append(fmuls(link.speedF, ML.cM_ssin_s16(link.travel)))
            dz.append(fmuls(link.speedF, ML.cM_scos_s16(link.travel)))
            if st in (CUT_F, CUT_A):
                cut_step = k - entry_k - 1
                m37 = link._cut_m3700_at(st, link.cut_frame)
                s_, c_ = ML.cM_ssin_s16(link.facing), ML.cM_scos_s16(link.facing)
                cutx.append(f32(f32(m37[2] * s_) + f32(m37[0] * c_)))
                cutz.append(f32(f32(m37[2] * c_) - f32(m37[0] * s_)))
            else:
                cutx.append(0.0)
                cutz.append(0.0)
            pose = st in _ROLL_POSE and body_cyl.available()
            is_pose.append(1 if pose else 0)
            if pose:
                rc, nc = body_cyl.roll_co_chain_consts(link.facing, link.roll_frame,
                                                       shape_z=getattr(link, '_draw_lean', 0))
                nroot = len(rc)
                chx.append([c[0] for c in rc] + [c[0] for c in nc])
                chz.append([c[1] for c in rc] + [c[1] for c in nc])
            else:
                chx.append(None)
                chz.append(None)
        if st in (CUT_F, CUT_A):
            break
    if cut_step is not None:
        nlvl = max(len(c) for c in chx if c is not None)
        chx = [c if c is not None else [0.0] * nlvl for c in chx]
        chz = [c if c is not None else [0.0] * nlvl for c in chz]
    tables = dict(dx=dx, dz=dz, cutx=cutx, cutz=cutz, is_pose=is_pose, chx=chx, chz=chz,
                  nroot=nroot, cut_step=cut_step)
    return rows, entry, tables


def table_diff(a, b):
    """Which of the nine baked fields differ -- [] means the reseed IS the real roll."""
    return [k for k in TABLE_KEYS if a[k] != b[k]]
