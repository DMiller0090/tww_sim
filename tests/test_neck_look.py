"""Gates for Link's head-look m3564 model (`land.neck_look`) -- setNeckAngle (session 21),
against the LOCKED live probe fixture `fixtures/courtyard_m3564.json`
(`_notes/tetrapush-m3564_probe.py`: slot 2, single-stepped f0..f44, m3564 + m34DE/m34C3/m34E2 +
Link mHeadTopPos per frame).

The unit gates pin the chase law (knobs 3/0x1000/0x100 + the gate-fail decay) and the attention
lock-on-list timing with no fixture dependency. The wiring gates run the from-f0 replay with the
wired camera + Zl1Look + NeckLook in BOTH modes:

  * **diag mode** (`centers='diag'`: computed pose for the FK, live-injected Co centres, so
    positions stay capture-tight) -- the 0-TOLERANCE model gate: every m3564 f1..43 == the live
    probe exactly, every facing == live exactly (the <=16-BAM eye-aim echo of the README planner
    box is GONE -- m3564 was its whole cause), head-top Y inside 1e-3 u once the (unmodeled,
    downstream-inert) m35B8 seed residue dies (f1-f2).
  * **self-contained mode** (`centers='computed'`, no injections at all) -- the planner-mode
    envelope gate: physics stays 0-ULP/live-exact, m3564 stays exact outside the untarget window
    and inside a +-16-BAM envelope on the target-chase frames f19..32, where the amplified
    common-mode seed noise (README session-16 box) bends the measured bearings by single BAMs
    (every chase INCREMENT still matches live; the offsets are quantization of drift-shifted
    geometry, not model error -- diag mode proves the law exact).

Skips (like test_zl1_look) when the dev-supplied fixtures/_generated data are absent.
"""
import json
import os
import struct

import pytest

_rb = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIX = os.path.join(_rb, 'fixtures', 'courtyard_m3564.json')
_LOOK = os.path.join(_rb, 'fixtures', 'courtyard_zl1look.json')
_CYL = os.path.join(_rb, 'fixtures', 'courtyard_push_cyl.json')
_DTM = os.path.join(_rb, 'fixtures', 'courtyard_push_dtm.json')
_SEED = os.path.join(_rb, 'fixtures', 'courtyard_push_seed.json')
_CAM = os.path.join(_rb, 'fixtures', 'courtyard_cam_oracle.json')
_GEN = os.path.join(_rb, '_generated', 'anim', 'zl1_anims.json')


def _bits(x):
    return struct.unpack('>I', struct.pack('>f', x))[0]


def test_chase_law_gate_fail_decay():
    """The (3, 0x1000, 0x100) chase toward 0 while the gate fails (roll frames / empty list):
    the live f0..f5 pitch decay 1262 -> 842 -> 562 -> 306 -> 50 -> 0 -> 0, bit-for-bit. Pure
    integer law -- the head matrix is measured but unconsumed when no look pos is selected, so a
    unit base pose suffices."""
    from tww_sim.land.neck_look import NeckLook
    ident = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 100.0], [0.0, 0.0, 1.0, 0.0]]
    nl = NeckLook(x=1262)
    seen = []
    for _ in range(6):
        nl.update(ident, 0, 30, None)          # FRONT_ROLL: mode flags off -> chase 0
        seen.append(nl.x)
    assert seen == [842, 562, 306, 50, 0, 0]
    assert nl.y == 0 and nl.z == 0


def test_list_present_timing():
    """The attention lock-on-list timing the look-target selection needs (d_attention.cpp):
    stocked on every NONE-state Run with a chaseable target, kept through LOCK/RELEASE, and
    EMPTY exactly on the transition-to-NONE Run (freeAttention runs, stockAttention doesn't --
    the probe's f21 chase-to-0 hole between the lock drop and the restock)."""
    from tww_sim.land.attention import AttentionLock, NONE, LOCK, RELEASE
    atn = AttentionLock(fade_frames=2)
    assert atn.update(False, True).list_present          # NONE + target: stocked
    assert not atn.update(False, False).list_present     # NONE + no target: nothing to stock
    atn.update(True, True)                               # rising L -> LOCK
    assert atn.state == LOCK and atn.list_present
    atn.update(False, True)                              # L released -> RELEASE (fade 2)
    assert atn.state == RELEASE and atn.list_present
    atn.update(False, True)                              # fade 1
    assert atn.state == RELEASE and atn.list_present
    atn.update(False, True)                              # fade out -> NONE: freed THIS Run
    assert atn.state == NONE and not atn.list_present
    assert atn.update(False, True).list_present          # next NONE Run restocks


@pytest.fixture(scope='module')
def neck_fix():
    if not os.path.exists(_FIX):
        pytest.skip("m3564 fixture not present (session-21 probe)")
    return json.load(open(_FIX))


@pytest.fixture(scope='module')
def replay_env(neck_fix):
    for p in (_LOOK, _CYL, _DTM, _SEED, _CAM):
        if not os.path.exists(p):
            pytest.skip("courtyard replay fixtures not present")
    if not os.path.exists(_GEN):
        pytest.skip("Zl1 anim extraction not present (run harness/anim/extract_zl1.py)")
    look = json.load(open(_LOOK))['frames']
    cyl = json.load(open(_CYL))['frames']
    dtm = json.load(open(_DTM))['frames']
    seed = json.load(open(_SEED))
    cam_o = json.load(open(_CAM))
    return look, cyl, dtm, seed, cam_o


def _neck_rows(neck_fix, replay_env, centers):
    from harness.tetrapush.from_f0 import replay
    from tww_sim.core.camera.land_cam import LandCamera, seed_from_block
    from tww_sim.core.npc_zl1_look import Zl1Look
    from tww_sim.land.neck_look import NeckLook
    look, cyl, dtm, seed, cam_o = replay_env
    cam = seed_from_block(LandCamera(), bytes.fromhex(cam_o['seed_cam_raw']))
    zl1 = Zl1Look.seed_from_row(look[0])
    m0 = neck_fix[0]['m3564']
    neck = NeckLook(x=m0[0], y=m0[1], z=m0[2])
    return replay(cyl, lambda k: dtm[k]['inp'], 0, upto=44,
                  seed_nspeed=seed['link']['nspeed'], centers=centers,
                  seed_old_pose=seed.get('old_pose'), camera=cam, zl1=zl1, neck=neck)


def test_m3564_and_facing_bit_exact_vs_live_diag(neck_fix, replay_env):
    """THE model gate (capture-tight diag mode -- live centres keep positions inside the 1.4e-4
    capture precision, so nothing is drift-bent): on EVERY frame f1..43

      * m3564 == the live probe exactly (x, y, z) -- including the razor absXZ<30 yaw dance
        (f19-21 y = 60 / -3 / 0), the f21 empty-list chase-to-0 hole, and every roll decay;
      * facing == live exactly -- the <=16-BAM eye-aim echo (README planner box) is CLOSED;
      * physics 0-ULP (proc, speedF, lean) and head-top Y inside 1e-3 u from f3 (f1-f2 = the
        known unmodeled-m35B8 seed residue, downstream-inert).

    The chase consumes the sim's own head FK, attention lock/list, m34DE, and Tetra's modeled
    eye -- 0-tolerance here gates the entire chain."""
    cyl = replay_env[1]
    rows = _neck_rows(neck_fix, replay_env, 'diag')
    assert len(rows) >= 40
    for rc in rows:
        k = rc['f']
        lv = cyl[k]
        assert rc['sim_proc'] == lv['proc'], "f%d proc %d != live %d" % (
            k, rc['sim_proc'], lv['proc'])
        assert _bits(rc['speedF']) == _bits(lv['link']['speedF']), (
            "f%d speedF %r != live %r (not 0-ULP)" % (k, rc['speedF'], lv['link']['speedF']))
        if lv['link'].get('shape_z') is not None:
            assert rc['sim_shape_z'] == lv['link']['shape_z'], "f%d lean diverged" % k
        assert rc['sim_facing'] == lv['link']['facing'], (
            "f%d facing %d != live %d (the echo must collapse with m3564 modeled)" % (
                k, rc['sim_facing'], lv['link']['facing']))
        if k < len(neck_fix):
            live = tuple(neck_fix[k]['m3564'])
            assert rc['sim_m3564'] == live, (
                "f%d m3564 %r != live %r" % (k, rc['sim_m3564'], live))
            if k >= 3:
                dht = rc['sim_head_top'][1] - neck_fix[k]['head_top'][1]
                assert abs(dht) <= 1e-3, (
                    "f%d head-top Y %r vs live %r: |%.2e| beyond the noise floor" % (
                        k, rc['sim_head_top'][1], neck_fix[k]['head_top'][1], abs(dht)))


def test_m3564_self_contained_envelope(neck_fix, replay_env):
    """The planner-mode (fully self-contained) envelope: physics stays 0-ULP/live-exact with the
    neck model wired (proc, speedF, lean, every committed csangle), m3564 stays EXACT outside
    the untarget window (the gate-off decay is pure integer state) and inside +-16 BAM on the
    target-chase frames f19..32, where the amplified common-mode seed noise (README session-16
    box) bends the measured bearings by single BAMs. Head-top Y holds 1e-3 u from f3 -- the
    0.96-u unmodeled-m3564 gap is gone in BOTH modes."""
    cyl = replay_env[1]
    rows = _neck_rows(neck_fix, replay_env, 'computed')
    for rc in rows:
        k = rc['f']
        lv = cyl[k]
        assert rc['sim_proc'] == lv['proc'], "f%d proc diverged" % k
        assert _bits(rc['speedF']) == _bits(lv['link']['speedF']), "f%d speedF not 0-ULP" % k
        if lv['link'].get('shape_z') is not None:
            assert rc['sim_shape_z'] == lv['link']['shape_z'], "f%d lean diverged" % k
        assert rc['sim_csangle'] == lv['csangle'], "f%d csangle diverged" % k
        if k < len(neck_fix):
            live = tuple(neck_fix[k]['m3564'])
            if 19 <= k <= 32:
                for i in range(3):
                    assert abs(rc['sim_m3564'][i] - live[i]) <= 16, (
                        "f%d m3564[%d] %d vs live %d beyond the noise envelope" % (
                            k, i, rc['sim_m3564'][i], live[i]))
            else:
                assert rc['sim_m3564'] == live, (
                    "f%d m3564 %r != live %r (exact outside the chase window)" % (
                        k, rc['sim_m3564'], live))
            if k >= 3:
                dht = rc['sim_head_top'][1] - neck_fix[k]['head_top'][1]
                assert abs(dht) <= 1e-3, "f%d head-top Y beyond the noise floor" % k
