"""THE FAN ON THE NATIVE FLEET, and what running it honestly measured (session 81).

The entry search's fan was the whole budget: 43596 candidates cost 1444 s of Python `FreeRun` at
~3.5k steps/s against 11 s of eval. `harness/tetrapush/entry_fan.py` moves it onto
`CourtyardFleet.run_par` -- 17 s for the same pass, key-for-key identical -- and that throughput paid
for measurements the Python fan could not afford. Three of them change what the search is:

  1. **the graft** is what makes a native fan possible at all. The stripped native config does NOT
     reproduce the WIRED replay of the console log (it diverges at log frame 19 on `facing`, the
     proc-9 re-aim falling back to Tetra's feet), so the base state comes from the wired Python run
     and is transplanted into a `LandCore`. `LandCore.setup` resets the mid-walk physics scalars, and
     restoring them is the whole graft -- gated bit-for-bit here.
  2. **the acceptance band is per (facing, thrust, m351C)**, not per (facing, thrust). s80 measured
     bands at lean 0 and `search` scored every candidate against them; ~83% of those draws sit at a
     lean where NOTHING is genuine at any entry, which is most of what "near-zero, 0 genuine" was
     counting. Honestly recounted, the widest one-segment pass is E[hits] 0.02, not 0.23.
  3. **the productive facing window is 32 BAM wide and the frozen camera reaches 4 aims in it.** The
     "3 distinct productive facings" of s80 was the spread of the aim SAMPLES, not the window.

Plus two structural facts the descent probe walked into: an appended aim is BUFFERED (`INPUT_DELAY`),
so a one-frame aim change cannot move the endpoint, and when it does act it drops Link off the
speedF 17 cap -- and that cap is a `fast_schedule` assumption (ROLL_NSPEED 26), not a physical one.

Offline: the native fleet + `ShoveCtx`, no Dolphin. The full-resolution equality gate needs the
gitignored s80 fan cache and is skipped without it.
"""
import math
import os
import struct

import pytest

from tww_sim.core.anim import _anmc as N
from tww_sim.land.plan_land._primitives import main_stick_decode
from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_search as ES
from harness.tetrapush import two_roll as TR

SEED = ES.console_seed()
HOLD = dict(SEED['log'][-1], buttons=0)
TRG = int(HOLD.get('triggerL', 0))

#: The two configurations this file pins the band structure at (facing 40820 is reachable at the
#: frozen csangle; thrust 15 is the one with a real interval rather than a single f32 value).
FACING, THRUST = 40820, 15


def _bits(v):
    return struct.pack('<d', float(v)).hex()


def _walk(base, rows):
    """One core through a list of (sx, sy) frames -> (x, z, m351C, speedF)."""
    c = base.clone(base.pe.clone_state())
    fl = N.CourtyardFleet([c], 1)
    for r in rows:
        fl.set_schedule([[(r[0], r[1], 0, TRG, ES.CSANGLE)]])
        fl.run_par(1, 0)
    return c.pos_x, c.pos_z, int(c.m351C) & 0xFFFF, c.speedF


# ------------------------------------------------------------------------ the graft is bit-exact

def test_the_graft_reproduces_the_wired_python_walk_bit_exactly():
    """THE LICENCE FOR THE WHOLE NATIVE FAN. A `LandCore` grafted from the wired Python `FreeRun` at a
    mid-walk base node must track it 0-ULP on both actors -- position, facing, travel, speedF, proc,
    lean. `LandCore.setup` resets `m34dc`/`target`/`msd`/`direction`/`roll_frame`/`_l_prev` (right for
    the f0 seed, wrong here) and `entry_fan.CARRY` restores them; the private fields it cannot reach
    are inert at this base, which is what this test actually proves."""
    run, _rows = ES.continue_walk([HOLD] * 4)
    core = EF.graft(run)
    pyr = run.clone()
    inp = dict(HOLD, stickX=200, stickY=90)
    for _j in range(13):
        pyr.step(inp)
        core.step_courtyard(int(inp['stickX']), int(inp['stickY']), 0, TRG,
                            int(ES.CSANGLE) & 0xFFFF, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0, 1)
        assert _bits(pyr.link.pos_x) == _bits(core.pos_x)
        assert _bits(pyr.link.pos_z) == _bits(core.pos_z)
        assert _bits(pyr.link.speedF) == _bits(core.speedF)
        assert int(pyr.link.facing) & 0xFFFF == int(core.facing) & 0xFFFF
        assert int(pyr.link.travel) & 0xFFFF == int(core.travel) & 0xFFFF
        assert int(pyr.link.state) & 0xFF == int(core.state) & 0xFF
        assert int(pyr.link.m351C) & 0xFFFF == int(core.m351C) & 0xFFFF
        assert _bits(pyr.tx) == _bits(core._tetra_x) and _bits(pyr.tz) == _bits(core._tetra_z)


def test_the_graft_needs_the_carried_scalars():
    """The graft is not just `_build_core`: drop the carried scalars and the walk diverges. Keeps the
    CARRY list honest -- if a future `setup` stops resetting them this test says so."""
    run, _rows = ES.continue_walk([HOLD] * 4)
    bare = run._build_core()                       # no CARRY restore, no delay-1 buffer
    good = EF.graft(run)
    inp = dict(HOLD, stickX=200, stickY=90)
    for _j in range(3):
        for c in (bare, good):
            c.step_courtyard(int(inp['stickX']), int(inp['stickY']), 0, TRG,
                             int(ES.CSANGLE) & 0xFFFF, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0, 1)
    assert _bits(bare.pos_x) != _bits(good.pos_x) or _bits(bare.pos_z) != _bits(good.pos_z)


# --------------------------------------------------------------- the fan equality gate

def test_the_fleet_fan_is_the_python_fan():
    """`fleet_fan` == `walk_fan`, key AND value, bit-for-bit. The write order is part of the contract:
    the reference collapses many writes onto one key and the LAST writer wins, so the fleet applies
    each core's hits stick-major / j-inner exactly as the reference loop does."""
    kw = dict(base_frames=(0, 1), stride=32, jmax=4)
    ref = ES.walk_fan(**kw)
    nat = EF.fleet_fan(**kw)
    r = EF.fan_equality(ref, nat)
    assert ref, "the reference fan is empty -- the comparison would be vacuous"
    assert r['equal'], (r['n_only_reference'], r['n_only_native'], r['value_diffs'][:3])


@pytest.mark.slow
def test_the_fleet_fan_reproduces_the_cached_full_resolution_pass():
    """The same equality at the resolution the search actually runs (stride 1, jmax 12, 7 bases,
    43596 candidates) against the CACHED s80 Python pass -- 17 s against the 1444 s that produced the
    cache. Skipped when the gitignored cache is absent."""
    if not os.path.exists(EF.FAN_CACHE):
        pytest.skip("no cached s80 fan at %s" % EF.FAN_CACHE)
    ref = EF.load_cached_fan()
    nat = EF.fleet_fan(base_frames=tuple(range(7)), stride=1, jmax=12)
    r = EF.fan_equality(ref, nat)
    assert len(ref) == 43596
    assert r['equal'], (r['n_only_reference'], r['n_only_native'], r['n_value_diffs'])


# ------------------------------------------------------- the band is per lean, not per configuration

def test_the_acceptance_band_is_per_lean_not_just_per_configuration():
    """THE s81 CORRECTION. At one (facing, thrust) the band is a function of m351C: lean 0 and +6
    carry the full 3.2e-5 interval, +136 a narrower one, and the negative leans measured here have
    NOTHING genuine at any entry along the locus. s80 scored every candidate against the lean-0 band,
    so a candidate at a dead lean was ranked as a near-miss it could never convert."""
    bands = EF.BandTable(SEED, path=None)
    live = bands.get(FACING, THRUST, 0)
    assert live['productive'] and live['width'] > 3e-5
    assert bands.get(FACING, THRUST, 6)['width'] == pytest.approx(live['width'], abs=0.0)
    for dead in (64302, 65342, 64891):             # signed -1234, -194, -645
        b = bands.get(FACING, THRUST, dead)
        assert not b['productive'] and b['n_genuine'] == 0
        assert b['reason'] == 'no genuine on the residual zero'


def test_the_bands_locus_moves_with_the_lean():
    """Why the lean is a configuration axis and not noise: the zero-residual entry itself moves with
    m351C (~0.05 u per 130 BAM), so each productive lean is its own locus."""
    bands = EF.BandTable(SEED, path=None)
    e0 = bands.get(FACING, THRUST, 0)['entry']
    e1 = bands.get(FACING, THRUST, 266)['entry']
    d = math.hypot(e1[0] - e0[0], e1[1] - e0[1])
    assert 0.01 < d < 1.0, d


def test_most_of_the_draws_sit_at_a_dead_lean():
    """The honest recount, on a small fan: the majority of (candidate x configuration) draws are at a
    lean with no usable band. This is the number that turned s80's 72 near-misses into 6."""
    bands = EF.BandTable(SEED, path=None)
    fan = EF.fleet_fan(base_frames=(0,), stride=32, jmax=5)
    quals = EF.qualified(SEED, path=None)
    live = dead = 0
    for k in fan:
        lean = ES.lean_at_roll(k[2])
        for q in quals:
            if bands.usable(q['facing'], q['thrust'], lean):
                live += 1
            else:
                dead += 1
    assert live + dead == len(fan) * len(quals)
    assert dead > live, (live, dead)


# ----------------------------------------------------- the productive facing window vs the alphabet

def test_the_productive_facing_window_is_wider_than_the_aims_that_reach_it():
    """s80 read "3 distinct productive facings" off the aim alphabet, which samples facing space every
    ~12 BAM. Swept directly, the window is 32 BAM of CONSECUTIVE productive facings at thrust 15 --
    and the frozen csangle reaches exactly four aims inside it. That gap is the camera lever: the
    C-stick shifts the whole alphabet, and each facing bakes its own locus."""
    bands = EF.BandTable(SEED, path=None)
    for facing in (40816, 40824, 40832, 40840, 40847):
        b = bands.get(facing, THRUST, 0)
        assert b['productive'], facing
    for facing in (40800, 40860):                  # outside it, nothing is productive
        assert not bands.get(facing, THRUST, 0)['productive'], facing
    reach = [f for f, _b in ES.aim_alphabet() if 40816 <= f <= 40847]
    assert reach == [40820, 40826, 40834, 40841]


# -------------------------------------------------------- the two structural facts the descent hit

def test_an_appended_aim_is_buffered_not_acted_on():
    """`INPUT_DELAY`: the last delivered frame only lands in the controller buffer, so re-aiming the
    final frame of a plan cannot move the endpoint -- 12 held frames and 11 held plus a different aim
    land on the SAME point. A local descent that perturbs the last frame therefore has no gradient at
    all, which is exactly what the s81 descent probe measured before this was understood."""
    base, _run = EF.base_core(5, seed=SEED, hold=HOLD)
    sx, sy = 88, 191
    a0, _msd = main_stick_decode(sx, sy)
    alt = next(b for ang, b in TR.reachable_stick_fan(0.0) if abs(ang - a0 - 12) < 7)
    held = _walk(base, [(sx, sy)] * 12)
    swapped = _walk(base, [(sx, sy)] * 11 + [alt])
    assert _bits(held[0]) == _bits(swapped[0]) and _bits(held[1]) == _bits(swapped[1])
    # and once it DOES act, the turn costs the cap the roll's full nspeed depends on
    acted = _walk(base, [(sx, sy)] * 11 + [alt, alt])
    assert held[3] == 17.0 and acted[3] < 17.0


def test_the_speed_cap_prune_is_a_schedule_assumption_not_a_physical_one():
    """The fan keeps only speedF == 17.0 because `fast_schedule` bakes ROLL_NSPEED 26, the roll's
    momentum off the walk cap. A sub-cap walk still rolls -- at ``clamp(1.5*speedF + 0.5, 5, 26)`` --
    so those endpoints are a locus FAMILY the search has never looked at, not infeasible entries.
    Dropping the prune multiplies the candidates: 3.0x at full resolution (43610 against 14529,
    `_notes/s81_prunes.py`), ~1.9x on the small fan this gate can afford."""
    base, _run = EF.base_core(3, seed=SEED, hold=HOLD)
    tx, tz = SEED['tetra']
    sticks = EF.stick_grid(16)
    cores = [base.clone(base.pe.clone_state()) for _ in sticks]
    fl = N.CourtyardFleet(cores, 1)
    fl.set_schedule([[(s[0], s[1], 0, TRG, ES.CSANGLE)] for s in sticks])
    allk, capk, speeds = set(), set(), set()
    for j in range(9):
        fl.run_par(1, 0)
        for c in cores:
            if math.hypot(c.pos_x - tx, c.pos_z - tz) > ES.FOLLOW_BAR or j < 1:
                continue
            allk.add((c.pos_x, c.pos_z, int(c.m351C) & 0xFFFF))
            speeds.add(c.speedF)
            if c.speedF == 17.0:
                capk.add((c.pos_x, c.pos_z, int(c.m351C) & 0xFFFF))
    assert capk <= allk
    assert len(allk) > 1.5 * len(capk), (len(capk), len(allk))
    nsp = set(min(26.0, max(5.0, 1.5 * s + 0.5)) for s in speeds)
    assert len(nsp) > 50, len(nsp)               # that many distinct schedules, one locus each
    assert ES.ROLL_NSPEED == 26.0 and max(nsp) == 26.0


# ------------------------------------------------------------------- the analytic gradient swap

def test_the_analytic_entry_gradient_is_the_simulated_one():
    """`entry_gradient` now builds the ANALYTIC ctx (cached) instead of simulating one per Newton
    iteration -- a ~70x cheaper qualification (269 s -> 4 s for 243 configurations). It must be the
    same number to the bit, or every band in this file is measured against a different razor."""
    entry = EF.ref_entry(SEED)
    g = ES.entry_gradient(SEED['tetra'], entry, facing=FACING, thrust=THRUST)
    ctx, _sch, resid = ES.build_at(ES.TAB_ENTRY, FACING, 0, THRUST)
    d = 0.01
    q = ctx.sweep_par([(SEED['tetra'][0], SEED['tetra'][1], entry[0], entry[1]),
                       (SEED['tetra'][0], SEED['tetra'][1], entry[0] + d, entry[1]),
                       (SEED['tetra'][0], SEED['tetra'][1], entry[0], entry[1] + d)], 0)
    r0 = resid(q[0])
    assert _bits(g['resid']) == _bits(r0)
    assert _bits(g['gx']) == _bits((resid(q[1]) - r0) / d)
    assert _bits(g['gz']) == _bits((resid(q[2]) - r0) / d)


def test_the_streaming_search_reproduces_a_materialised_one():
    """`stream_search` over a generator must find what scoring the whole dict finds -- the batching
    and the packed-key dedup are memory plumbing, not a change of answer."""
    kw = dict(base_frames=(0,), stride=32, jmax=4)
    bands = EF.BandTable(SEED, path=None)
    quals = EF.qualified(SEED, path=None)
    a = EF.stream_search(EF.iter_fan(**kw), quals=quals, bands=bands, batch=10 ** 9)
    b = EF.stream_search(EF.iter_fan(**kw), quals=quals, bands=bands, batch=97)
    assert a['n_candidates'] == b['n_candidates'] > 0
    assert a['n_evaluations'] == b['n_evaluations']
    assert a['n_dead_lean'] == b['n_dead_lean']
    assert a['n_near'] == b['n_near'] and a['near'] == b['near']
    assert [h['entry'] for h in a['hits']] == [h['entry'] for h in b['hits']]
