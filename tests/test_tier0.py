"""Gates for the session-22 planner scaffolding: the seed factory (`harness/tetrapush/seeds`),
the Phase-1 primitive characterization (`primitives`), and the tier-0 geometric shove planner
(`tier0`), all against the locked courtyard fixtures.

Also pins the session-22 DRIFT-STRUCTURE finding: the self-contained replay's closed-loop
position drift vs the live capture is DIFFERENTIAL (e_link ~ -e_tetra, a pair mode the plow
feedback amplifies ~1.35x/contact frame), NOT common-mode as the session-16 README box read --
so the planner's exact tier is blocked on the exec-centre FK residual (<=3e-4 u/frame, ~1-2
f32 ULP at courtyard coordinates) until the FK is made bit-exact. The drift gate self-skips
once that residual is killed (drift < 0.01 u at f30), so the FK fix will not break it.

Skips cleanly when the dev-supplied fixtures/_generated data are absent (like test_zl1_look).
"""
import math
import os

import pytest

_rb = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_NEEDED = [
    os.path.join(_rb, 'fixtures', f) for f in (
        'courtyard_push_cyl.json', 'courtyard_push_dtm.json', 'courtyard_push_seed.json',
        'courtyard_cam_oracle.json', 'courtyard_zl1look.json', 'courtyard_m3564.json')
] + [os.path.join(_rb, '_generated', 'anim', 'zl1_anims.json'),
     os.path.join(_rb, '_generated', 'tetra_placements.tsv')]


@pytest.fixture(scope='module')
def env():
    for p in _NEEDED:
        if not os.path.exists(p):
            pytest.skip("planner fixture not present: %s" % os.path.basename(p))
    from harness.tetrapush import seeds
    return seeds.load_env()


def test_seed_factory_matches_gate_config(env):
    """`seeds.make_freerun` builds EXACTLY the session-21 gate configuration: driving it with
    the DTM bytes reproduces the wrapped `replay(centers='computed', camera, zl1, neck)`
    byte-for-byte on every dynamics field f1..43. Pins the factory so the planner path can
    never silently fork from the gated one."""
    from harness.tetrapush import seeds
    from harness.tetrapush.from_f0 import replay
    from tww_sim.core.camera.land_cam import LandCamera, seed_from_block
    from tww_sim.core.npc_zl1_look import Zl1Look
    from tww_sim.land.neck_look import NeckLook
    cam = seed_from_block(LandCamera(), bytes.fromhex(env['cam']['seed_cam_raw']))
    zl1 = Zl1Look.seed_from_row(env['look'][0])
    m0 = env['m3564'][0]['m3564']
    neck = NeckLook(x=m0[0], y=m0[1], z=m0[2])
    inp = seeds.dtm_input_at(env)
    ref = replay(env['cyl'], inp, 0, upto=44, seed_nspeed=env['seed']['link']['nspeed'],
                 centers='computed', seed_old_pose=env['seed'].get('old_pose'),
                 camera=cam, zl1=zl1, neck=neck)
    run = seeds.make_freerun(env)
    run.pre_seed_input(inp(0))
    for w in ref:
        row = run.step(inp(w['f']))
        for key in ('sim_proc', 'speedF', 'sim_facing', 'sim_shape_z', 'sim_link',
                    'sim_tetra', 'sim_cyl', 'sim_csangle'):
            assert row[key] == w[key], "f%d: factory %s %r != gate %r" % (
                w['f'], key, row[key], w[key])


def test_tier0_tracks_freerun_on_recorded_aims(env):
    """The tier-0 geometric stepper (rigid cycle templates + the exact fp plow laws) tracks the
    full FreeRun over the recorded window: cycle 1 exact by construction (the recorded state-2
    entry), and through the canonical second cycle both actors stay within 0.5 u at the last
    gated frame (measured 0.13 u -- the honest tier-0 ranking error budget over one novel-cycle
    horizon)."""
    from harness.tetrapush import tier0
    v = tier0.validate(env)
    assert v['tetra_err_cyc1'] < 1e-9 and v['link_err_cyc1'] < 1e-9, (
        "cycle 1 must be exact by construction: %r" % v)
    assert v['tetra_err_last'] < 0.5 and v['link_err_last'] < 0.5, (
        "tier-0 error budget blew past 0.5 u: %r" % v)


def test_shove_map_sweet_band(env):
    """The session-22 steering law: from the recorded cycle-1 end state, the canonical cycle
    sustains the chase-and-plow only in a narrow aim band ~+1000 BAM off the Link->Tetra
    bearing (>= 15 contact frames, end dist inside the follow bound), while aiming dead-on or
    +-2400 BAM breaks contact mid-roll and Link rolls away past the follow bound. The sweep's
    fine grid + guard pruning exist because of this razor."""
    from harness.tetrapush import seeds as S, tier0
    recs = tier0.P.window_records(env)
    tpl0 = tier0.build_first_template(env, records=recs)
    tpl = tier0.build_template(env, records=recs)
    st0 = tier0.seed_state(env)
    tier0.step_cycle(st0, 35316, tpl0)          # the recorded cycle-1 aim
    bearing = tier0._dir_bam((st0.tx - st0.lx, st0.tz - st0.lz))

    sweet = st0.clone()
    tier0.step_cycle(sweet, (bearing + 1000) & 0xFFFF, tpl)
    assert sweet.contact - st0.contact >= 15, "the sweet band must sustain the plow"
    assert sweet.max_dist <= 230, "the sweet band must hold the follow guard"

    for off in (0, -2400, 2400):
        broke = st0.clone()
        tier0.step_cycle(broke, (bearing + off) & 0xFFFF, tpl)
        assert broke.max_dist > 230, (
            "aim offset %+d should break the plow regime (got max dist %.1f)" % (
                off, broke.max_dist))


def test_drift_is_differential_not_common_mode(env):
    """The session-22 drift-structure finding (overturns the session-16 'common-mode' README
    reading): at f30 the self-contained replay's Link and Tetra errors vs the live capture are
    near-equal in magnitude and OPPOSITE in direction (|e_link - e_tetra| ~ 2|e_link|), i.e. a
    differential pair mode. Self-skips once the FK residual is killed (drift < 0.01 u) -- the
    fix makes this gate moot, not red."""
    from harness.tetrapush import primitives as P
    rep = {d['f']: d for d in P.drift_report(env, upto=44)}
    d30 = rep[30]
    if d30['link_err'] < 0.01:
        pytest.skip("FK residual fixed -- the drift is gone; retire this gate with the README box")
    assert d30['link_err'] == pytest.approx(d30['tetra_err'], rel=0.05)
    assert d30['diff'] > 1.5 * d30['link_err'], (
        "drift no longer differential: |diff| %.4f vs link_err %.4f" % (
            d30['diff'], d30['link_err']))


def test_placements_loader(env):
    from harness.tetrapush import seeds
    rows, header = seeds.load_placements()
    assert len(rows) == 288
    assert all('x' in r and 'z' in r for r in rows)
    assert any('SETUP' in h for h in header)
