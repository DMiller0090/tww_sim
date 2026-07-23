"""The Tetra-push SEARCH foundation (`harness/tetrapush/search`) -- the exact aim-per-cycle search
primitives built on the 0-ULP `FreeRun` forward model.

TEST-RIGOR POLICY (`[[zero-ulp-tests-only]]`): the two sim-vs-console claims here are asserted at
0 ULP (`_bits == _bits`), never a tolerance:
  * the rollout HARNESS, fed the recorded delivered inputs, reproduces the recorded window bit-for-bit;
  * the macro RE-AIM, at a cycle's own recorded aim with the recorded C-stick + frame-aligned csangle,
    reproduces the recorded cycle bit-for-bit (so re-aiming a cycle is a faithful control primitive);
  * `FreeRun.clone` produces a state that steps BIT-IDENTICALLY to its parent (the beam-search node
    branch must not perturb the model).
The rest are STRUCTURAL / capability gates (not fidelity): the pinned-C-stick cycle is clean and stays
in the plow regime, the per-cycle reach RESONANCE at the recorded aim exists, and the beam search
reaches its first cycle. Cycle CHAINING under a pinned C-stick is the documented open blocker (module
docstring / the `chain` CLI); it is deliberately NOT gated as an invariant.

Needs the locked courtyard fixtures (`seeds.load_env`); skipped when absent.
"""
import struct

import pytest

from harness.tetrapush import primitives as P
from harness.tetrapush import search as S
from harness.tetrapush import seeds
from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST

_FRONT_ROLL = 30

# The beam/reach sweeps deliberately try out-of-regime candidates (the FOLLOW guard prunes them);
# the guard's UserWarning is expected here, not a failure.
pytestmark = pytest.mark.filterwarnings("ignore:FreeRun:UserWarning")


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope='module')
def env():
    try:
        return seeds.load_env()
    except FileNotFoundError as e:
        pytest.skip("planner fixtures not present: %s" % e)


@pytest.fixture(scope='module')
def recs(env):
    return P.window_records(env)


def test_rollout_recorded_reproduces_the_window_0ulp(env, recs):
    """0-ULP: the rollout harness, fed the RECORDED delivered inputs (raw DTM bytes incl. the
    recorded C-stick), reproduces the recorded window bit-for-bit -- Link AND Tetra, every frame
    f1..43. This locks the FreeRun-stepping harness `search.rollout` is built on."""
    by_f = {r['f']: r for r in recs}
    res = S.rollout_recorded(env, upto=44, recs=recs)
    for row in res['rows']:
        r = by_f[row['f']]
        assert _bits(row['link'][0]) == _bits(r['feet'][0]) and \
            _bits(row['link'][1]) == _bits(r['feet'][1]), "f%d: Link pos not bit-exact" % row['f']
        assert _bits(row['tetra'][0]) == _bits(r['tetra'][0]) and \
            _bits(row['tetra'][1]) == _bits(r['tetra'][1]), "f%d: Tetra pos not bit-exact" % row['f']


def test_macro_reaim_reproduces_cycle1_0ulp(env, recs):
    """0-ULP: the canonical cycle macro, re-aimed to its OWN recorded aim, driven with the recorded
    C-stick + frame-aligned csangle, reproduces the recorded cycle 1 bit-for-bit (Link + Tetra,
    f1..25). This is the faithfulness of the re-aim CONTROL primitive -- `_frame_input` /
    `stick_for_bearing` reconstruct a stick whose physics outcome is the recorded one exactly.
    (Under a pinned C-stick the csangle evolves differently by design, so the search reads the
    ACHIEVED aim back from FreeRun -- see `test_pinned_cycle_is_clean_and_in_regime`.)"""
    by_f = {r['f']: r for r in recs}
    macro, aim1 = S.canonical_cycle(env, recs)
    dtm = seeds.dtm_input_at(env)
    cs_stream = lambda g: (dtm(g).get('substickX', 128), dtm(g).get('substickY', 128))
    cs_live = lambda g: (by_f[g]['csangle'] if g in by_f else env['cyl'][g]['csangle'])
    res = S.rollout(env, [aim1], recs=recs, macro=macro, cstick_stream=cs_stream,
                    csangle_at=cs_live, stop_on_follow=False)
    assert res['rows'], "no rows produced"
    for row in res['rows']:
        r = by_f[row['f']]
        assert _bits(row['link'][0]) == _bits(r['feet'][0]) and \
            _bits(row['link'][1]) == _bits(r['feet'][1]), "f%d: Link pos not bit-exact" % row['f']
        assert _bits(row['tetra'][0]) == _bits(r['tetra'][0]) and \
            _bits(row['tetra'][1]) == _bits(r['tetra'][1]), "f%d: Tetra pos not bit-exact" % row['f']


def test_freerun_clone_steps_bit_identically(env, recs):
    """0-ULP: a cloned `FreeRun` stepped with the same inputs as its parent stays bit-identical over
    multiple cycles (Link, Tetra, facing, proc) -- the beam-search node branch must not perturb the
    model. `FreeRun.clone` shares the immutable anim tables (so it is ~0.025 ms, not the ~60 ms a
    whole-object deepcopy costs) yet is a true deep copy of the mutable state."""
    macro, aim1 = S.canonical_cycle(env, recs)
    run = seeds.make_freerun(env)
    S.rollout(env, [aim1], recs=recs, macro=macro, run=run, stop_on_follow=False)  # advance a cycle
    clone = run.clone()

    def _one(rr, aim, base):
        return S.step_one_cycle(rr, macro, aim & 0xFFFF, base_gidx=base, start_j=0)['rows']

    for k, aim in enumerate([(aim1 + 300) & 0xFFFF, (aim1 - 700) & 0xFFFF], start=1):
        a = _one(run, aim, k * S.CYCLE_PERIOD)
        b = _one(clone, aim, k * S.CYCLE_PERIOD)
        assert len(a) == len(b)
        for x, y in zip(a, b):
            assert x['proc'] == y['proc'], "clone proc diverged at f%d" % x['f']
            assert _bits(x['link'][0]) == _bits(y['link'][0]) and \
                _bits(x['link'][1]) == _bits(y['link'][1]), "clone Link diverged at f%d" % x['f']
            assert _bits(x['tetra'][0]) == _bits(y['tetra'][0]) and \
                _bits(x['tetra'][1]) == _bits(y['tetra'][1]), "clone Tetra diverged at f%d" % x['f']
            assert x['facing'] == y['facing'], "clone facing diverged at f%d" % x['f']


def test_pinned_cycle_is_clean_and_in_regime(env, recs):
    """STRUCTURAL: a pinned-C-stick single cycle at the recorded aim is a clean push cycle
    (re-target proc 7 -> FRONT_ROLL 30 -> ATN_ACTOR untarget 9 -> MOVE backslide 6), stays in the
    stt-3 plow regime (never past FOLLOW_ENGAGE_DIST), and its ACHIEVED roll aim is within a few
    tens of BAM of the commanded aim (the byte-quantization + 1-frame csangle-staleness the search
    reads back, not a guarantee)."""
    macro, aim1 = S.canonical_cycle(env, recs)
    res = S.rollout(env, [aim1], recs=recs, macro=macro, stop_on_follow=False)
    procs = [row['proc'] for row in res['rows']]
    assert _FRONT_ROLL in procs, "no FRONT_ROLL in the pinned cycle"
    assert 7 in procs and 9 in procs and 6 in procs, "missing the re-target/untarget/backslide procs"
    assert not res['followed'] and res['max_dist'] < FOLLOW_ENGAGE_DIST, \
        "pinned cycle left the plow regime (max %.1f u)" % res['max_dist']
    achieved = res['cycles'][0]['roll_facing']
    assert achieved is not None
    d = ((achieved - aim1 + 0x8000) & 0xFFFF) - 0x8000
    assert abs(d) < 200, "achieved aim %d too far from commanded %d (%d BAM)" % (achieved, aim1, d)


def test_per_cycle_reach_resonance(env, recs):
    """STRUCTURAL: the per-cycle reach has a sharp RESONANCE at the recorded aim -- one cycle there
    herds Tetra > 300 u while staying in regime, whereas aims +-600 BAM off herd < 220 u (the roll
    grazes rather than driving through her). This is the hand-performed TAS's chosen aim, and the
    reason the search must sample the productive cone finely."""
    macro, aim1 = S.canonical_cycle(env, recs)
    t0 = env['cyl'][0]['tetra']['pos']
    import math
    got = S.reach_one_cycle(env, [(aim1 - 600) & 0xFFFF, aim1, (aim1 + 600) & 0xFFFF],
                            recs=recs, macro=macro)
    herd = [math.hypot(r['tetra'][0] - t0[0], r['tetra'][1] - t0[2]) for r in got]
    assert not got[1]['followed'], "resonance cycle left the plow regime"
    assert herd[1] > 300.0, "resonance herd only %.1f u (expected > 300)" % herd[1]
    assert herd[0] < 220.0 and herd[2] < 220.0, \
        "off-resonance neighbours herd too far: %.1f / %.1f u" % (herd[0], herd[2])


def test_beam_search_reaches_first_cycle(env):
    """CAPABILITY: the beam search runs and its first cycle lands on the resonance -- a real FreeRun
    rollout (no approximation), Tetra herded > 300 u toward the genuine band while in regime. (The
    coarse multi-cycle herd is blocked on cycle chaining -- module docstring; not gated here.)"""
    import math
    best, _ = S.beam_search(env, n_cycles=1, beam=4, cone_half=1500, step=80)
    assert best is not None, "beam search found no in-regime cycle-1 candidate"
    assert len(best['aims']) == 1
    assert best['max_dist'] < FOLLOW_ENGAGE_DIST, "cycle-1 best left the plow regime"
    env2 = seeds.load_env()
    t0 = env2['cyl'][0]['tetra']['pos']
    herd = math.hypot(best['run'].tx - t0[0], best['run'].tz - t0[2])
    assert herd > 300.0, "beam cycle-1 best herd only %.1f u" % herd


def test_lockless_macro_strips_L(env, recs):
    """STRUCTURAL: `lockless_macro` removes the L button (0x40) and analog triggerL from every frame
    (the lockless roll-herd probe for the chaining work) and leaves the rest untouched."""
    macro, _ = S.canonical_cycle(env, recs)
    ll = S.lockless_macro(macro)
    assert len(ll) == len(macro)
    for m, l in zip(macro, ll):
        assert l['buttons'] == (m['buttons'] & ~0x40) and l['triggerL'] == 0
        assert l['stick'] == m['stick']
