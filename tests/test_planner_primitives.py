"""The Tetra-push planner PRIMITIVES -- structural gates that keep the reusable extraction layer
from rotting (the anti-drift mandate: the land layer bloated for months because sound conventions
were UNGATED).

`harness/tetrapush/primitives` decomposes the bit-exact `FreeRun` window into the reusable pieces a
search consumes: `window_records` (the instrumented rollout), `find_cycles` (the cycle spans),
`cycle_template` (one cycle in the aim frame), and `input_macro`/`macro_inputs` (the cycle's raw-input
pattern, re-aimable to any world angle). `seeds` builds the fully self-contained FreeRun + loads the
genuine target coords.

TEST-RIGOR POLICY (`[[zero-ulp-tests-only]]`): the sim-vs-console fidelity of this layer is already
gated by `tests/test_from_f0.py` (`window_records` IS the 0-ULP `replay` path). The gates HERE are
NOT sim-vs-console fidelity claims -- they are STRUCTURAL invariants of the extraction (cycle count /
roll placement), a model-internal RIGIDITY check (the roll shove is cycle-independent, so it is
re-aimable), and the DISCRETE input channel (macro_inputs reproduces the exact button/trigger pattern
and emits valid bytes). The analog stick re-aim is a documented tier-0 approximation (near-neutral
roll-body frames quantize ~4 deg, but the roll LOCKS facing at the aim and ignores the stick angle
there), NOT gated tightly -- the exact achieved aim is read back from tier-1 FreeRun.

Needs the locked courtyard fixtures (`seeds.load_env`); skipped when they are absent.
"""
import math

import pytest

from harness.tetrapush import primitives as P
from harness.tetrapush import seeds
from tww_sim.core.mathlib import main_stick_decode

_FRONT_ROLL = 30


def _s16(v):
    v = int(v) & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


@pytest.fixture(scope='module')
def env():
    try:
        return seeds.load_env()
    except FileNotFoundError as e:
        pytest.skip("planner fixtures not present: %s" % e)


@pytest.fixture(scope='module')
def recs(env):
    return P.window_records(env)


def test_window_records_covers_the_gated_window(env, recs):
    """`window_records` runs the self-contained FreeRun over f1..43 and every row carries the fields
    the template/search read. Pins that the primitive extraction still runs on the current (0-ULP,
    session-27) model -- if the FreeRun API drifts, this trips before anything downstream."""
    assert [r['f'] for r in recs] == list(range(1, 44)), "expected one row per game-frame f1..43"
    for r in recs:
        for key in ('proc', 'speedF', 'facing', 'travel', 'feet', 'tetra', 'cyl_exec', 'cyl',
                    'o_local', 'recoil', 'plow', 'foot_world', 'depth'):
            assert key in r, "frame %d: window record missing %r" % (r['f'], key)


def test_find_cycles_recovers_the_two_recorded_cycles(recs):
    """The recorded window is exactly TWO push cycles, rolling at f3 and f29 (proc-30 entries). A
    STRUCTURAL invariant of `find_cycles` -- the search enumerates plans as one aim per cycle, so it
    must segment the window into the right cycles."""
    spans = P.find_cycles(recs)
    assert len(spans) == 2, "expected 2 recorded cycles, got %d: %r" % (len(spans), spans)
    roll_entries = [r for (_s, r, _e) in spans]
    assert roll_entries == [3, 29], "roll entries should be f3, f29; got %r" % roll_entries
    by_f = {r['f']: r for r in recs}
    for rf in roll_entries:
        assert by_f[rf]['proc'] == _FRONT_ROLL, "f%d should be a FRONT_ROLL entry" % rf


def test_roll_body_locomotion_is_rigid_across_cycles(recs):
    """STRUCTURAL RIGIDITY (NOT a sim-vs-console fidelity gate): aligned at the roll entry, the two
    recorded rolls' per-frame FOOT term (the actual body displacement, in each cycle's own aim frame)
    is cycle-independent to < 0.02 u. This is WHY a cycle is a re-aimable primitive -- the roll shove
    depends only on the aim, not on which cycle it is (facing is locked at the aim, speedF is the
    plow-independent 26.0). The exec-centre offset (`o_local`, pose data) varies more at the entry
    morf and is re-simulated exactly at tier-1, so it is not asserted here."""
    spans = P.find_cycles(recs)
    by_f = {r['f']: r for r in recs}

    def _roll_frames(span):
        _s, _r, e = span
        return [f for f in range(_r, e + 1) if by_f[f]['proc'] == _FRONT_ROLL]

    rf1, rf2 = _roll_frames(spans[0]), _roll_frames(spans[1])
    n = min(len(rf1), len(rf2))
    assert n >= 12, "expected >=12 common roll-body frames, got %d" % n
    aim1 = by_f[spans[0][1]]['facing']
    aim2 = by_f[spans[1][1]]['facing']
    worst = 0.0
    for i in range(n):
        f1 = P.to_local(by_f[rf1[i]]['foot_world'][0], by_f[rf1[i]]['foot_world'][1], aim1)
        f2 = P.to_local(by_f[rf2[i]]['foot_world'][0], by_f[rf2[i]]['foot_world'][1], aim2)
        worst = max(worst, math.hypot(f1[0] - f2[0], f1[1] - f2[1]))
    assert worst < 0.02, "roll-body foot term not cycle-rigid: max |d foot| %.4f u" % worst


def test_macro_inputs_reproduces_the_discrete_channel(env, recs):
    """`macro_inputs`, re-aimed at a cycle's OWN recorded aim, reproduces that cycle's exact
    per-frame BUTTON + trigger pattern (the roll-trigger A and the soft-lock L land on the right
    relative frames -- 0 mismatch) and emits only valid controller bytes with the C-stick pinned
    DOWN (the manualCamera hold, substick (128, 0)). The discrete channel is what sequences the
    cycle; the analog re-aim is tier-0 (see the module docstring)."""
    spans = P.find_cycles(recs)
    by_f = {r['f']: r for r in recs}
    inp = seeds.dtm_input_at(env)
    for sp in spans:
        aim = by_f[sp[1]]['facing']
        macro = P.input_macro(env, sp, recs)
        cs0 = by_f[sp[0] - 1]['csangle'] if (sp[0] - 1) in by_f \
            and by_f[sp[0] - 1]['csangle'] is not None else env['cyl'][sp[0] - 1]['csangle']
        built = P.macro_inputs(macro, aim, cs0)
        assert len(built) == len(macro)
        for m, b, in zip(macro, built):
            raw = inp((sp[0] + m['j']) - 1)          # delay-1: frame f acts inp[f-1]
            assert b['buttons'] == raw['buttons'], (
                "j%d: macro buttons %d != recorded %d" % (m['j'], b['buttons'], raw['buttons']))
            assert b['triggerL'] == raw['triggerL'], (
                "j%d: macro triggerL %d != recorded %d" % (m['j'], b['triggerL'], raw['triggerL']))
            assert b['substickX'] == 128 and b['substickY'] == 0, (
                "j%d: C-stick not pinned DOWN (manualCamera hold)" % m['j'])
            for ch in ('stickX', 'stickY'):
                assert 0 <= b[ch] <= 255, "j%d: %s byte %d out of range" % (m['j'], ch, b[ch])


def test_macro_reaim_faithful_where_the_stick_bites(env, recs):
    """The analog re-aim IS faithful on the frames where the stick angle matters -- at meaningful
    magnitude (msd > 0.3), re-aiming at the recorded aim reproduces the recorded want-bearing to
    within one stick LSB (~1.5 deg = ~270 BAM). The large residuals are ALL at msd ~ 0.05 (the
    roll body, near-neutral, facing locked -- angle irrelevant), which this gate deliberately
    excludes. Proves `stick_for_bearing` is the correct clamp-aware inverse where it is used to
    SET an aim, not just where the roll ignores it."""
    spans = P.find_cycles(recs)
    by_f = {r['f']: r for r in recs}
    checked = 0
    for sp in spans:
        aim = by_f[sp[1]]['facing']
        macro = P.input_macro(env, sp, recs)
        cs0 = by_f[sp[0] - 1]['csangle'] if (sp[0] - 1) in by_f \
            and by_f[sp[0] - 1]['csangle'] is not None else env['cyl'][sp[0] - 1]['csangle']
        built = P.macro_inputs(macro, aim, cs0)
        for m, b in zip(macro, built):
            if m['stick'] is None or m['stick'][1] <= 0.3:
                continue
            rel_in, _msd = m['stick']
            ang, _ = main_stick_decode(b['stickX'], b['stickY'])
            assert ang is not None, "j%d: aim-setting stick rebuilt to neutral" % m['j']
            rel_out = _s16(((ang + 0x8000 + cs0) & 0xFFFF) - aim)
            d = abs(_s16(rel_out - rel_in))
            assert d <= 270, "j%d (msd %.2f): re-aim off %d BAM (> 1 LSB)" % (m['j'], m['stick'][1], d)
            checked += 1
    assert checked >= 2, "expected some aim-setting (msd>0.3) frames to check, got %d" % checked
