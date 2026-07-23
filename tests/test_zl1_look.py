"""Gates for the Tetra look-at head model (`core.npc_zl1_look`) -- the eyePos + tattn streams
(session 20), against the LOCKED live probe fixture `fixtures/courtyard_zl1look.json`
(`_notes/tetrapush-zl1look_probe.py`: slot 2, single-stepped f0..f44, the dNpc_JntCtrl_c block +
McaMorf ctrl + look fields + eyePos/tattn + Link mHeadTopPos per frame).

The model gate (`test_look_replay_bit_exact_vs_live`) drives `Zl1Look` with the LIVE per-frame
inputs (her plowed position, Link's pos + mHeadTopPos) and requires every output bit-exact -- the
look-at chase (all four JntCtrl angles + the clamped targets), the half-angle twists, the head FK
eye position, and the attention position, f1..f44, 0 ULP, no tolerances.

The wiring gates then run the fully SELF-CONTAINED from-f0 replay (computed centres + wired
camera + wired Zl1Look -- ZERO per-frame injections, only the static f0 seed + the raw DTM
bytes) and require the physics byte-identical to the injected-streams reference and the
committed csangles still live-exact. eye/tattn there track the SIM's Tetra (the known amplified
common-mode capture-noise drift, ~1.35x/frame -- README session-16 box), so they are bounded,
not 0-ULP, vs live; the f1-f4 head-top Y residue is the KNOWN unmodeled m35B8 seed decay (same
class as the camera attn-Y transient, README session-19 box) and is downstream-inert (eye Y is
never consumed: the re-aim uses XZ only, the camera consumes tattn).

Skips (like test_from_f0) when the dev-supplied fixtures/_generated data are absent.
"""
import json
import os
import struct

import pytest

_rb = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIX = os.path.join(_rb, 'fixtures', 'courtyard_zl1look.json')
_CYL = os.path.join(_rb, 'fixtures', 'courtyard_push_cyl.json')
_DTM = os.path.join(_rb, 'fixtures', 'courtyard_push_dtm.json')
_SEED = os.path.join(_rb, 'fixtures', 'courtyard_push_seed.json')
_CAM = os.path.join(_rb, 'fixtures', 'courtyard_cam_oracle.json')
_EYES = os.path.join(_rb, 'fixtures', 'courtyard_push_eyepos.json')
_GEN = os.path.join(_rb, '_generated', 'anim', 'zl1_anims.json')


def _bits(x):
    return struct.unpack('>I', struct.pack('>f', x))[0]


def _ulp(a, b):
    return _bits(a) - _bits(b)


@pytest.fixture(scope='module')
def look_fix():
    if not os.path.exists(_FIX):
        pytest.skip("Zl1 look fixture not present (session-20 probe)")
    if not os.path.exists(_GEN):
        pytest.skip("Zl1 anim extraction not present (run harness/anim/extract_zl1.py)")
    return json.load(open(_FIX))['frames']


def _seeded_look(fr0):
    from tww_sim.core.npc_zl1_look import Zl1Look
    return Zl1Look.seed_from_row(fr0)


def test_look_replay_bit_exact_vs_live(look_fix):
    """THE model gate: seeded at f0 and fed the LIVE per-frame inputs (pos_pre = her f(k-1) pos,
    pos_post = her f(k) pos, Link's f(k) pos + mHeadTopPos.y), the model reproduces EVERY live
    output f1..f44 bit-exact: eyePos (all 3), attention position (all 3), all four JntCtrl chased
    angles, the per-frame clamped targets, and the head half-angle twists. 0 ULP, no tolerances."""
    fr = look_fix
    lk = _seeded_look(fr[0])
    for k in range(1, len(fr)):
        rk, rp = fr[k], fr[k - 1]
        eye, tattn = lk.step(pos_pre=tuple(rp['pos']), pos_post=tuple(rk['pos']),
                             link_pos=tuple(rk['link']['pos']),
                             link_head_top_y=rk['link']['head_top'][1],
                             angle_y=rk['travel'])
        for i in range(3):
            assert _ulp(eye[i], rk['eye'][i]) == 0, (
                "f%d eye[%d] %r != live %r" % (k, i, eye[i], rk['eye'][i]))
            assert _ulp(tattn[i], rk['tattn'][i]) == 0, (
                "f%d tattn[%d] %r != live %r" % (k, i, tattn[i], rk['tattn'][i]))
        assert lk.jnt.angles == rk['jnt']['angles'], (
            "f%d JntCtrl angles %r != live %r" % (k, lk.jnt.angles, rk['jnt']['angles']))
        assert (lk.jnt.f2c, lk.jnt.f2e, lk.jnt.f30, lk.jnt.f32) == (
            rk['jnt']['f2c'], rk['jnt']['f2e'], rk['jnt']['f30'], rk['jnt']['f32']), (
            "f%d JntCtrl targets diverged" % k)
        assert (lk.f83c, lk.f83e) == (rk['f83c'], rk['f83e']), (
            "f%d head half-angles (%d, %d) != live (%d, %d)" % (
                k, lk.f83c, lk.f83e, rk['f83c'], rk['f83e']))
        assert lk.f7b8 == rk['f7b8'] and lk.f84d == rk['f84d'] and lk.cur_anm == rk['f849'], (
            "f%d look timer/anim state diverged" % k)
        assert abs(lk.morf.frame - rk['morf']['frame']) == 0.0, (
            "f%d anim frame %r != live %r" % (k, lk.morf.frame, rk['morf']['frame']))
        assert not lk.rng_horizon


def test_look_timer_switches_to_look_anim(look_fix):
    """The optn_1 look-around machine: when field_0x7B8 runs out the model switches to look.bck
    (morf 8, LOOP, frame 0) with field_0x84D = 0 (target released -> the chase decays toward 0),
    and steps without error through the whole look cycle (the RNG horizon flag only rises at the
    wait03 RETURN, where the game reseeds from the global RNG stream)."""
    fr = look_fix
    lk = _seeded_look(fr[0])
    lk.f7b8 = 3
    from tww_sim.core.npc_zl1_look import ANM_LOOK
    p = tuple(fr[0]['pos'])
    lp = tuple(fr[0]['link']['pos'])
    hty = fr[0]['link']['head_top'][1]
    for k in range(3):
        lk.step(pos_pre=p, pos_post=p, link_pos=lp, link_head_top_y=hty)
    assert lk.cur_anm == ANM_LOOK and lk.f84d == 0 and lk.f7ba in (1, 2)
    assert lk.morf.cur_morf < 1.0, "the anim switch must engage the 8-frame morf"
    assert not lk.rng_horizon
    for k in range(200):
        lk.step(pos_pre=p, pos_post=p, link_pos=lp, link_head_top_y=hty)
    assert lk.rng_horizon, "a full look cycle must flag the RNG-reseed horizon"


@pytest.fixture(scope='module')
def replay_env(look_fix):
    for p in (_CYL, _DTM, _SEED, _CAM):
        if not os.path.exists(p):
            pytest.skip("courtyard replay fixtures not present")
    cyl = json.load(open(_CYL))['frames']
    dtm = json.load(open(_DTM))['frames']
    seed = json.load(open(_SEED))
    cam_o = json.load(open(_CAM))
    return cyl, dtm, seed, cam_o


def _self_contained_rows(look_fix, replay_env):
    from harness.tetrapush.from_f0 import replay
    from tww_sim.core.camera.land_cam import LandCamera, seed_from_block
    cyl, dtm, seed, cam_o = replay_env
    cam = seed_from_block(LandCamera(), bytes.fromhex(cam_o['seed_cam_raw']))
    zl1 = _seeded_look(look_fix[0])
    return replay(cyl, lambda k: dtm[k]['inp'], 0, upto=44,
                  seed_nspeed=seed['link']['nspeed'], centers='computed',
                  seed_old_pose=seed.get('old_pose'), camera=cam, zl1=zl1)


def test_zl1_in_the_loop_replay_dynamics_bit_exact(look_fix, replay_env):
    """THE session-20 wiring gate: the from-f0 replay with the wired camera AND the wired Zl1
    look model -- NO injected streams at all; the whole run consumes only the static f0 seeds +
    the raw DTM bytes -- keeps the closed-loop DYNAMICS live-exact through both cycles:

      * every proc f1..43 matches live, every speedF is 0-ULP, every lean (shape_z) exact;
      * every committed csangle == live (position-independent, so noise can't touch it);
      * facing carries at most a +16-BAM eye-aim echo, confined to the untarget window
        (f20-28) -- the modeled eye is anchored at the SIM's noise-drifted Tetra, so the re-aim
        bearing quantizes a few BAM off the live capture there (the same echo class the
        closed-loop computed gate documents at +6 BAM with the INJECTED live eye; README s16).
        Facing returns to live-exact in cyc2's facing-locked roll.

    Positions carry the known amplified common-mode capture noise (README session-16 box) and
    are gated by the from_f0 suite, not here."""
    rows = _self_contained_rows(look_fix, replay_env)
    cyl = replay_env[0]
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
        assert rc['sim_csangle'] == lv['csangle'], (
            "f%d: csangle %d != live %d with the zl1 model wired" % (
                k, rc['sim_csangle'], lv['csangle']))
        echo = ((rc['sim_facing'] - lv['link']['facing'] + 0x8000) & 0xFFFF) - 0x8000
        assert abs(echo) <= 16, "f%d facing echo %+d BAM beyond the documented envelope" % (
            k, echo)


def test_zl1_in_the_loop_streams_track_live(look_fix, replay_env):
    """The self-contained replay's modeled streams: tattn obeys the setAttention law on the
    SIM's own Tetra 0-ULP every frame (internal consistency -- the law itself is live-gated by
    the model gate), head-top Y tracks live to the noise envelope once the (unmodeled,
    downstream-inert) m35B8 seed residue dies (f1-f4), and the eye-minus-feet OFFSET -- the
    common-mode-cancelled comparison -- tracks live through the first full cycle (<=0.1 u,
    f5..f25; beyond that the pair's amplified drift bends the look bearings themselves and the
    offset is sim-consistent, not live-comparable). NOISE bounds, not law tolerances -- the LAW
    is gated 0-ULP by `test_look_replay_bit_exact_vs_live`."""
    from tww_sim.core.fp import f32, fadds
    fr = look_fix
    ty = fr[0]['pos'][1]
    rows = _self_contained_rows(look_fix, replay_env)
    for rc in rows:
        k = rc['f']
        if k >= len(fr):
            break
        zk = fr[k]
        # internal tattn law: (sim_tx, f32(seed_ty + 140), sim_tz), 0-ULP on the sim's state
        assert rc['sim_tattn'][0] == rc['sim_tetra'][0]
        assert rc['sim_tattn'][2] == rc['sim_tetra'][1]
        assert _ulp(rc['sim_tattn'][1], fadds(f32(ty), f32(140.0))) == 0
        if k >= 5:
            # f19-27 = the unmodeled m3564 window (Link's own head-look; README planner box):
            # <=0.96 u of head-top Y there. Elsewhere the law holds to the noise floor.
            lim = 1.2 if 19 <= k <= 27 else 1e-3   # absolute u (ULPs blow up near the y~0 tuck)
            dht = rc['sim_head_top'][1] - zk['link']['head_top'][1]
            assert abs(dht) <= lim, (
                "f%d: head-top Y %r vs live %r beyond the envelope (%.1e > %.1e)" % (
                    k, rc['sim_head_top'][1], zk['link']['head_top'][1], abs(dht), lim))
        if 5 <= k <= 25:
            for i, j in ((0, 0), (2, 2)):
                off_m = rc['sim_eye'][i] - (rc['sim_tetra'][0] if i == 0 else rc['sim_tetra'][1])
                off_l = zk['eye'][i] - zk['pos'][j]
                assert abs(off_m - off_l) <= 0.1, (
                    "f%d: eye offset[%d] %.5f vs live %.5f beyond the envelope" % (
                        k, i, off_m, off_l))
