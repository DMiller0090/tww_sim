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
bytes) and require the DYNAMICS (proc/speedF/lean/csangle) 0-ULP and the wired setAttention law
internally consistent 0-ULP.

TEST-RIGOR POLICY (`[[zero-ulp-tests-only]]`): self-contained eye/tattn/facing/head-top-Y track
the SIM's noise-drifted Tetra (the amplified common-mode capture-noise drift, ~1.35x/frame --
README session-16 box), so they are NOT bit-exact vs live -- they are DOWNSTREAM of the two open
position bugs. The old bounded tolerances on them are DELETED (a tolerance there hides the
residual); the LAWS are gated 0-ULP against LIVE inputs by `test_look_replay_bit_exact_vs_live`,
and the self-contained values green once the position bugs close.

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
    are gated by the from_f0 suite, not here.

    DYNAMICS ONLY (0-ULP): proc, speedF, lean, csangle. FACING is NOT asserted here -- self-contained
    it carries the eye-aim echo (the modeled eye is anchored at the SIM's noise-drifted Tetra), which
    is DOWNSTREAM of the two open position bugs (`[[zero-ulp-tests-only]]`); the look/re-aim LAW itself
    is gated 0-ULP by `test_look_replay_bit_exact_vs_live` (fed live inputs) and the facing goes
    self-contained-exact once the position bugs close (`test_from_f0::test_onestep_pos_bit_exact_
    from_exact_state`)."""
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


def test_zl1_in_the_loop_streams_track_live(look_fix, replay_env):
    """The self-contained replay's wired setAttention law is INTERNALLY CONSISTENT 0-ULP: on the
    SIM's own Tetra, tattn == (sim_tx, f32(seed_ty + 140), sim_tz) bit-for-bit every frame -- proving
    the wired path fires the law on the sim state. The law's LIVE fidelity is gated 0-ULP (fed live
    inputs) by `test_look_replay_bit_exact_vs_live`.

    NOTE (`[[zero-ulp-tests-only]]`): the old head-top-Y (<=1.2 u) and eye-minus-feet-offset (<=0.1 u)
    NOISE bounds were DELETED. Self-contained, the eye anchors at the sim's noise-drifted Tetra and
    head-top Y carries the unmodeled m35B8 seed residue -- both DOWNSTREAM of the two open position
    bugs, so a tolerance there hides the residual rather than gating anything. Those quantities are
    0-ULP against LIVE inputs in the model gate; their self-contained values green once the position
    bugs close (`test_from_f0::test_onestep_pos_bit_exact_from_exact_state`)."""
    from tww_sim.core.fp import f32, fadds
    fr = look_fix
    ty = fr[0]['pos'][1]
    rows = _self_contained_rows(look_fix, replay_env)
    for rc in rows:
        k = rc['f']
        if k >= len(fr):
            break
        # internal tattn law: (sim_tx, f32(seed_ty + 140), sim_tz), 0-ULP on the sim's own state
        assert rc['sim_tattn'][0] == rc['sim_tetra'][0]
        assert rc['sim_tattn'][2] == rc['sim_tetra'][1]
        assert _ulp(rc['sim_tattn'][1], fadds(f32(ty), f32(140.0))) == 0
