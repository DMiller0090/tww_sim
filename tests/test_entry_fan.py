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
  3. **`BandTable` reports 32 BAM of productive facings and the frozen camera reaches 4 aims in it.**
     The "3 distinct productive facings" of s80 was the spread of the aim SAMPLES, not even that.
     Session 92: that 32 BAM is a `configuration_band`-at-one-`ref` reading and NOT the window, which is
     22 live cells in two lobes (`knowledge/strategy/clip-exit-angle.md`). It is still the right thing to
     RANK a candidate's neighbourhood by, and it is still never a veto on a genuine hit.

Plus two structural facts the descent probe walked into: an appended aim is BUFFERED (`INPUT_DELAY`),
so a one-frame aim change cannot move the endpoint, and when it does act it drops Link off the
speedF 17 cap -- and that cap is a `fast_schedule` assumption (ROLL_NSPEED 26), not a physical one.

Offline: the native fleet + `ShoveCtx`, no Dolphin. The full-resolution equality gate needs the
gitignored s80 fan cache and is skipped without it.
"""
import json
import math
import os
import struct

import pytest

from tww_sim.core.anim import _anmc as N
from tww_sim.land.constants import ROLL_FROM
from tww_sim.land.land import LandState
from tww_sim.land.plan_land._primitives import main_stick_decode
from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_search as ES
from harness.tetrapush import two_roll as TR

SEED = ES.console_seed()

#: PINNED because measuring it costs 624 s (`entry_search.curve_scan`); spot-checked by
#: `test_the_pinned_qualification_still_measures_the_same_way` so it cannot rot.
_QUALS = []


def productive_quals():
    """The productive set, off the fixture. Never "speed this up" with ``escalate=False`` or
    ``curve=False`` -- those are the two readings that hid half the seam's facing window."""
    if not _QUALS:
        _QUALS.append(json.load(open(_fx('courtyard_qualified_s92.json')))['quals'])
    return _QUALS[0]


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
    carry the full 3.2e-5 interval, +266 a narrower one, and a far enough negative lean is DEAD. s80
    scored every candidate against the lean-0 band, so a candidate at a dead lean was ranked as a
    near-miss it could never convert.

    Session 87 re-measured this against the fixed Co centre (`body_cyl.co_leans` -- the baked chain
    was missing the `body_chn` twist, which is a function of the lean, so the lean axis is exactly
    where the old engine was most wrong). The structure is unchanged and the productive widths are
    the same to the bit; which negative leans die, and how, moved -- s81's three examples are in
    `knowledge/history/`."""
    bands = EF.BandTable(SEED, path=None)
    live = bands.get(FACING, THRUST, 0)
    assert live['productive'] and live['width'] > 3e-5
    assert bands.get(FACING, THRUST, 6)['width'] == pytest.approx(live['width'], abs=0.0)
    narrow = bands.get(FACING, THRUST, 266)
    assert narrow['productive'] and 0.0 < narrow['width'] < live['width']
    # -1234: the roll leaves Tetra out of Co range on the cut frame, so no entry moves the razor.
    b = bands.get(FACING, THRUST, 64302)
    assert not b['productive'] and b['n_genuine'] == 0
    assert b['reason'] == 'no leverage' and b['grad'] == 0.0


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
    quals = productive_quals()
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
    ~12 BAM. Swept directly, `BandTable` reports 32 BAM of CONSECUTIVE productive facings at thrust 15 --
    and the frozen csangle reaches exactly four aims inside it. That gap is the camera lever: the
    C-stick shifts the whole alphabet, and each facing bakes its own locus.

    **This is a `BandTable` fact, not the window** (session 92). `BandTable` is `configuration_band` at
    ONE `ref` entry, which is what the search ranks a candidate's neighbourhood by -- and it is exactly
    the reading that hid the second lobe (cells 2560-2575), so 40860 being "outside it" below means
    "no band at this seed", NOT "cannot clip". The window is
    `knowledge/strategy/clip-exit-angle.md` + `fixtures/courtyard_facing_window_s92.json`."""
    bands = EF.BandTable(SEED, path=None)
    for facing in (40816, 40824, 40832, 40840, 40847):
        b = bands.get(facing, THRUST, 0)
        assert b['productive'], facing
    for facing in (40800, 40860):                  # outside it, nothing is productive
        assert not bands.get(facing, THRUST, 0)['productive'], facing
    # Session 88 halved this: two of the four aims were representatives too shallow to dispatch a roll
    # (`test_attack_threshold.py`), and facing 40834 has no deep member at all.
    reach = [f for f, _b in ES.aim_alphabet() if 40816 <= f <= 40847]
    assert reach == [40820, 40841]
    assert [f for f, _b in ES.aim_alphabet(msd_min=0.0)
            if 40816 <= f <= 40847] == [40820, 40826, 40834, 40841]
    assert len({ES.aim_cell(f) for f in reach}) == 2, "both productive cells are still reachable"


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


def test_the_uncapped_fleet_fan_is_the_python_fan():
    """The equality contract holds with the speed prune dropped too -- key AND value, and the key is
    now a 4-tuple carrying the endpoint's own speedF."""
    kw = dict(base_frames=(0, 1), stride=32, jmax=4, cap=None)
    ref = ES.walk_fan(**kw)
    nat = EF.fleet_fan(**kw)
    r = EF.fan_equality(ref, nat)
    assert ref and all(len(k) == 4 for k in ref)
    assert r['equal'], (r['n_only_reference'], r['n_only_native'], r['value_diffs'][:3])


# --------------------------------------------- the momentum axis: generalized, then measured DEAD
# Session 82. "Each sub-cap momentum is its own locus" is true; "with genuine dust on it" is not.

def test_the_momentum_below_the_cap_is_a_dead_axis():
    """THE FINDING. Scanned ALONG the whole locus (not a one-point band -- `entry_search.locus_scan`,
    which re-projects onto resid 0 at every station), the cap lights up most of its curve and every
    sub-cap momentum is barren end to end. So a sub-cap roll is not a worse draw at the same target;
    it is a draw at a target that does not exist."""
    ref = EF.ref_entry(SEED)
    live = ES.locus_scan(SEED['tetra'], 40826, THRUST, 0, ref, span=60.0, step=4.0)
    assert live['stations'] > 20 and live['live'] > 0.5 * live['stations']   # the control
    assert live['walkable'] == live['live']
    dead = []
    for nsp in (22.673213958740234, 14.608858108520508, 8.3131036758422852):
        r = ES.locus_scan(SEED['tetra'], 40826, THRUST, 0, ref, nspeed=nsp, span=60.0, step=4.0)
        assert r['live'] == 0, (nsp, r)
        dead.append(r)
    # both death modes present: a locus carrying no dust, and no leverage at all (at 14.6 the roll
    # leaves Tetra out of Co range on the cut frame, so the push is zero and no entry moves the razor)
    assert any(d['stations'] > 20 for d in dead)
    assert any(d['reason'] == 'no leverage at the seed' for d in dead)


def test_dropping_the_cap_multiplies_the_draws_and_buys_no_near_misses():
    """The same thing end to end, which is the only version that settles it: at one resolution, the
    uncapped pass reaches 3x the candidates and finds the SAME near-miss population, gap for gap.
    Every extra candidate rolls at a momentum where nothing is genuine at any entry -- the s80 error
    (counting draws that could never convert) one axis over.

    Stride 4, not s82's 16: on the fixed Co centre (session 87) this ONE-SEGMENT coarse fan reaches
    no near-miss at all, and a comparison of two empty populations settles nothing. Note the scope --
    the full TWO-segment pass's yield barely moved (see
    `test_the_current_candidate_list_still_scores_and_confirms`); it is the coarse one-segment
    population that thinned."""
    kw = dict(base_frames=tuple(range(7)), stride=4, jmax=12)
    bands, quals = EF.BandTable(SEED, path=None), productive_quals()
    capped = EF.stream_search(EF.iter_fan(cap=ES.WALK_CAP, **kw), quals=quals, bands=bands)
    uncapped = EF.stream_search(EF.iter_fan(cap=None, **kw), quals=quals, bands=bands)
    assert uncapped['n_candidates'] > 2.5 * capped['n_candidates']
    assert capped['n_near'] > 0, "vacuous: this resolution found no near-miss either way"
    assert uncapped['near'] == capped['near']
    assert uncapped['expected_hits'] == capped['expected_hits']
    assert len(uncapped['hits']) == len(capped['hits']) == 0


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
    nsp = set(ES.roll_nspeed(s) for s in speeds)
    assert len(nsp) > 50, len(nsp)               # that many distinct schedules, one locus each
    assert ES.ROLL_NSPEED == 26.0 and max(nsp) == 26.0
    # ...and exactly ONE of them is the cap, which is the only one worth a draw (the two tests above)
    assert sum(1 for v in nsp if v >= 25.89) == 1


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
    quals = productive_quals()
    a = EF.stream_search(EF.iter_fan(**kw), quals=quals, bands=bands, batch=10 ** 9)
    b = EF.stream_search(EF.iter_fan(**kw), quals=quals, bands=bands, batch=97)
    assert a['n_candidates'] == b['n_candidates'] > 0
    assert a['n_evaluations'] == b['n_evaluations']
    assert a['n_dead_lean'] == b['n_dead_lean']
    assert a['n_near'] == b['n_near'] and a['near'] == b['near']
    assert [h['entry'] for h in a['hits']] == [h['entry'] for h in b['hits']]


# ---------------------------------------------- the pass is priced in families (session 84)

def test_the_family_price_is_counted_and_does_not_change_the_answer():
    """A two-segment pass pays in PREFIX FAMILIES, so `stream_search` counts them -- and counting
    them must be pure bookkeeping.

    `family_of_plan` is the unit: the same run scored with and without it has to return the same
    candidates, the same near-misses and the same hits, and the counted families have to be exactly
    the ``(n0, sx1, sy1, j1)`` prefixes the fan was asked for -- not the candidates, which is the
    number that made every wide one-segment pass look like it was still buying draws."""
    kw = dict(base_frames=(0,), s1_stride=64, j1=(2, 4), s2_stride=32, j2max=3)
    bands = EF.BandTable(SEED, path=None)
    quals = productive_quals()
    plain = EF.stream_search(EF.iter_fan2(**kw), quals=quals, bands=bands, batch=997)
    priced = EF.stream_search(EF.iter_fan2(**kw), quals=quals, bands=bands, batch=997,
                              family_of=EF.family_of_plan)
    assert priced['n_candidates'] == plain['n_candidates'] > 0
    assert priced['n_near'] == plain['n_near'] and priced['near'] == plain['near']
    assert [h['entry'] for h in priced['hits']] == [h['entry'] for h in plain['hits']]

    wanted = {(0, sx, sy, j) for (sx, sy) in EF.stick_grid(64) for j in (2, 4)}
    seen = {EF.family_of_plan(p) for _k, p in EF.iter_fan2(**kw)}
    assert seen <= wanted and seen                      # dead junctions are dropped, none invented
    assert priced['n_families'] == len(seen)
    assert priced['near_per_family'] == priced['n_near'] / priced['n_families']
    assert plain['n_families'] == 0 and plain['near_per_family'] is None


def test_the_marginal_rate_is_the_saturation_reading_not_the_cumulative_one():
    """The stop signal has to be able to FALL while the cumulative rate is still rising.

    That is the whole point of watching the margin: a pass whose families stop paying keeps a
    healthy-looking cumulative near/family for a long time, because the early families are in the
    average forever. Fed a trace that goes dead after the first batch, `_marginal` reads 0 while the
    cumulative rate is still 5-per-100."""
    dead = [dict(families=100, near=5), dict(families=200, near=5), dict(families=300, near=5)]
    assert EF._marginal(dead) == 0.0
    assert dead[-1]['near'] / dead[-1]['families'] > 0.0
    live = [dict(families=100, near=5), dict(families=200, near=15)]
    assert EF._marginal(live) == 0.1
    assert EF._marginal([dict(families=100, near=5)]) is None
    assert EF._marginal([dict(families=0, near=0), dict(families=0, near=0)]) is None


def test_a_near_miss_population_is_counted_in_draws_not_in_scorings():
    """`distinct_near` is the s83 lesson encoded: report what the count IS, not how often it was
    scored.

    One walk endpoint scored against three configurations is three near-misses and ONE draw -- the
    same confusion, one level up, as the 48 near-misses that were 3 candidates counted sixteen times
    once the aim alphabet collapsed onto its sine-table cells. Two candidates that merely share a
    lean, or a walk x, are still two draws."""
    def n(x, z, lean, facing):
        return (1e-4, dict(walk=[x, z], m351C=lean, facing=facing))

    one_walk_three_aims = [n(1.0, 2.0, 900, 40816), n(1.0, 2.0, 900, 40820), n(1.0, 2.0, 900, 40834)]
    assert len(one_walk_three_aims) == 3 and EF.distinct_near(one_walk_three_aims) == 1
    assert EF.distinct_near(one_walk_three_aims + [n(1.0, 2.0, 901, 40820)]) == 2   # lean differs
    assert EF.distinct_near(one_walk_three_aims + [n(1.0, 3.0, 900, 40820)]) == 2   # endpoint does
    assert EF.distinct_near([]) == 0


def test_the_near_misses_are_reported_with_their_identity():
    """The gaps and their identities are the same population in the same order -- so a suspicious
    multiplier can be audited from the pass's own output instead of a re-run."""
    kw = dict(base_frames=(0,), s1_stride=64, j1=(2, 4), s2_stride=32, j2max=3)
    r = EF.stream_search(EF.iter_fan2(**kw), quals=productive_quals(),
                         bands=EF.BandTable(SEED, path=None), family_of=EF.family_of_plan)
    assert [d['gap'] for d in r['near_detail']] == r['near']
    assert r['n_near_candidates'] <= r['n_near']
    for d in r['near_detail']:
        assert EF.family_of_plan(d['plan'])[0] == 0 and len(d['plan']) == 7


def test_the_lottery_is_priced_at_each_draws_own_band_not_the_lean_zero_one():
    """`lottery` sums each near-miss's OWN band; the pre-s84 estimate multiplied the count by a
    mean width measured at lean 0.

    They agree only when every draw happens to sit at that width. Give the population a real spread
    -- which is what a fan carrying ~2000 distinct entry leans has -- and the two disagree, so the
    old one was pricing draws at a band none of them stands in."""
    gap = 5e-3
    wide, narrow = 1e-4, 1e-6
    pop = [(1e-4, dict(width=wide)), (2e-4, dict(width=narrow)), (3e-4, dict(width=narrow))]
    assert EF.lottery(pop, gap) == (wide + 2 * narrow) / (2 * gap)
    assert EF.lottery([], gap) == 0.0

    lean0 = EF._expected_hits([g for g, _ in pop], [wide], gap)
    assert lean0 == 3 * wide / (2 * gap)                     # count x the lean-0 width
    assert lean0 > EF.lottery(pop, gap) * 2                  # and here it overprices 2.9x
    same = [(1e-4, dict(width=wide)), (2e-4, dict(width=wide))]
    assert EF.lottery(same, gap) == EF._expected_hits([g for g, _ in same], [wide], gap)


# ------------------------------------- the alphabet is the decoded stick, not the bytes (s84)

def test_byte_pairs_that_decode_alike_walk_alike_bit_for_bit():
    """The licence for `stick_alphabet`. A held stick reaches the walk only through
    `main_stick_decode`, so two byte pairs with the same ``(angle, msd)`` must bake an identical
    walk -- endpoint, lean, speedF and facing, to the bit, for as long as it is held.

    Checked on the widest classes the octagon and the dead zone produce, which is where a byte-grid
    fan spends most of its frames."""
    base, _run = EF.base_core(3, seed=SEED, hold=HOLD)
    classes = {}
    for p in EF.stick_grid(1):
        classes.setdefault(EF._decoded(*p), []).append(p)
    big = sorted((v for v in classes.values() if len(v) > 1), key=len, reverse=True)[:6]
    assert len(big[0]) > 100                          # the dead zone really is one draw, not 1944
    for members in big:
        out = {_walk(base, [members[0]] * 8), _walk(base, [members[-1]] * 8)}
        assert len(out) == 1


def test_the_decoded_alphabet_keeps_every_draw_and_survives_delivery():
    """Collapsing the grid must lose no physics and no delivery: one member per decoded class, the
    classes themselves unchanged, and the representative clear of the 0/255 bytes `dtm_make`
    rewrites to 1/254 (`[[octagon-clamp-decode-bug]]`) wherever the class offers an interior one."""
    for stride in (32, 8, 1):
        grid, alpha = EF.stick_grid(stride), EF.stick_alphabet(stride)
        assert {EF._decoded(*p) for p in alpha} == {EF._decoded(*p) for p in grid}
        assert len(alpha) == len({EF._decoded(*p) for p in alpha}) < len(grid)
    full = EF.stick_alphabet(1)
    assert len(full) == 11405 and len(EF.stick_grid(1)) / len(full) > 5.0
    interior = {EF._decoded(*p) for p in EF.stick_grid(1) if 0 < p[0] < 255 and 0 < p[1] < 255}
    for p in full:
        if EF._decoded(*p) in interior:
            assert 0 < p[0] < 255 and 0 < p[1] < 255


def test_the_two_segment_fan_on_the_decoded_alphabet_is_the_byte_grid_fan():
    """The 5.75x is pure waste, so it must not move the answer.

    What the search consumes is the CANDIDATE SET -- the ``(endpoint, lean)`` keys -- and that has to
    be identical, reached with strictly fewer frames. The plan a key carries may differ: two
    genuinely different sticks can land on one endpoint, and which is the last writer depends on the
    order the alphabet is enumerated in. Every plan must still be a member of the alphabet."""
    kw = dict(base_frames=(0,), s1_stride=64, j1=(2,), j2max=2)
    deduped = list(EF.iter_fan2(s2_stride=32, **kw))
    byte_grid = _iter_fan2_bytes(s2_stride=32, **kw)
    assert dict(deduped).keys() == dict(byte_grid).keys() and len(dict(deduped)) > 100
    assert len(deduped) < len(byte_grid)                          # and cost strictly less
    alpha = set(EF.stick_alphabet(32))
    for _k, plan in deduped:
        assert tuple(plan[1:3]) in EF.stick_alphabet(64) and tuple(plan[4:6]) in alpha


def _iter_fan2_bytes(**kw):
    """`iter_fan2` on the raw byte grid -- the pre-s84 alphabet, for the equality gate above."""
    real = EF.stick_alphabet
    EF.stick_alphabet = EF.stick_grid
    try:
        return list(EF.iter_fan2(**kw))
    finally:
        EF.stick_alphabet = real


def test_scoping_the_key_set_per_family_reports_the_same_pass():
    """`dedup_scope='family'` is a memory budget, not a different search: it re-evaluates the few
    endpoints two prefixes share, and because the near-misses carry identity and are deduped on the
    draw, the reported population is identical to a globally deduped pass."""
    kw = dict(base_frames=(0,), s1_stride=64, j1=(2, 4), s2_stride=16, j2max=4)
    bands = EF.BandTable(SEED, path=None)
    quals = productive_quals()
    g = EF.stream_search(EF.iter_fan2(**kw), quals=quals, bands=bands, family_of=EF.family_of_plan)
    f = EF.stream_search(EF.iter_fan2(**kw), quals=quals, bands=bands, family_of=EF.family_of_plan,
                         dedup_scope='family')
    assert f['n_families'] == g['n_families'] > 1
    assert f['n_near'] == g['n_near'] and f['near'] == g['near']
    assert f['expected_hits'] == g['expected_hits']
    assert [h['entry'] for h in f['hits']] == [h['entry'] for h in g['hits']]
    assert f['n_candidates'] >= g['n_candidates']     # the shared endpoints, counted once per family


def test_confirm_hits_puts_the_confirmed_frame_minimal_plan_first(monkeypatch):
    """The A-press replay is what turns a swept hit into a result, so its report must rank by that
    first and by the objective second.

    Frame-minimality is the objective (`[[tetrapush-frame-minimal]]`), but a shorter plan that does
    not actually roll is not a shorter plan -- an unconfirmed hit never outranks a confirmed one."""
    def plan(n0, *seg):
        return dict(plan=[n0] + list(seg))
    hits = [plan(0, 1, 1, 9), plan(5, 1, 1, 2), plan(0, 1, 1, 3), plan(0, 1, 1, 4)]
    ok = {9: False, 2: False, 3: True, 4: True}      # keyed by the plan's hold length
    monkeypatch.setattr(ES, 'confirm_entry',
                        lambda h, **kw: dict(all_ok=ok[h['plan'][3]], ok={}, measured={}))
    rows = EF.confirm_hits(hits)
    assert [r['hit']['plan'] for r in rows] == [[0, 1, 1, 3], [0, 1, 1, 4],
                                                [5, 1, 1, 2], [0, 1, 1, 9]]
    assert [r['confirm']['all_ok'] for r in rows] == [True, True, False, False]
    assert EF.confirm_hits([]) == []


def test_a_finer_alphabet_contains_the_coarser_one():
    """A wider pass must CONTAIN the narrower pass it is meant to beat -- the standing steer
    (`[[search-space-contains-human]]`), applied to the collapsed alphabet.

    Byte-grid containment is trivial (stride 4 divides 32); what has to hold after collapsing is
    containment of the DRAWS, because the representative for a class can shift when a finer stride
    offers an earlier or more interior member of it. The drawn physics is what must be a superset,
    not the bytes."""
    for coarse, fine in ((32, 8), (8, 4), (4, 1)):
        c = {EF._decoded(*p) for p in EF.stick_alphabet(coarse)}
        f = {EF._decoded(*p) for p in EF.stick_alphabet(fine)}
        assert c < f, (coarse, fine, len(c), len(f))


def _replay_the_a_press(key, plan, aim):
    """`confirm_entry` on a bare fan candidate: only the roll trigger is under test here, so the
    scoring fields it also checks (entry, facing, lean) are left unset."""
    return ES.confirm_entry(dict(plan=list(plan), aim=list(aim), walk=[key[0], key[1]],
                                 entry=None, facing=None, m351C=None), seed=SEED)


def test_the_proc_prune_agrees_with_a_real_a_press_both_ways():
    """THE PRUNE SESSION 84'S FAILURES ASKED FOR. Its three unconfirmed draws all read
    ``procs [24, 24, 6, 6, 6]`` -- `MOVE_TURN` at the aim frame, so the A-press turned instead of
    rolling -- and the fan had no reason to notice, because it pruned only on speedF and the follow
    bar.

    The predicate is `state.py`'s own dispatch condition (`land.ROLL_FROM`) read off the same public C
    field, so what needs gating is not the code path but that the field means what it is being asked
    to mean: the endpoint's proc IS the proc the A frame dispatches. So the prune is checked against a
    real A-press in BOTH directions -- everything kept rolls, and nothing dropped would have."""
    kw = dict(base_frames=(1,), s1_stride=64, j1=(2, 6), s2_stride=8, j2max=4)
    loose = dict(EF.iter_fan2(rollable=False, **kw))
    tight = dict(EF.iter_fan2(rollable=True, **kw))
    assert set(tight) < set(loose), "the prune dropped nothing -- the gate would be vacuous"
    assert all(tight[k] == loose[k] for k in tight), "a surviving key changed its plan"
    dropped = [k for k in loose if k not in tight]
    aim = ES.aim_cells()[0][1]
    for keys, want in ((list(tight)[::max(1, len(tight) // 4)], True),
                       (dropped[::max(1, len(dropped) // 4)], False)):
        for k in keys[:4]:
            c = _replay_the_a_press(k, loose[k], aim)
            assert c['ok']['rolled'] is want, (k, loose[k], c['measured']['procs'])
            # and the WIRED Python replay's own proc at that frame agrees with the native core's:
            # procs is the last 5 rows, whose tail is the aim frame plus three neutral ones
            assert ((c['measured']['procs'][-4] in ROLL_FROM) is want), c['measured']['procs']


def test_a_hit_is_checked_against_what_a_dtm_actually_delivers():
    """The last promise in the chain: a plan's BYTES have to reach the console as the physics they
    were scored at. `dtm_make` clamps the extremes (255 -> 254, 0 -> 1), and simming the raw bytes
    instead of the delivered ones is a known 60-tread error (`[[octagon-clamp-decode-bug]]`).

    The check is on the DECODE, not on the presence of a 0 or a 255: the dead zone and the octagon
    clamp mean a clamped extreme usually lands in the same class, and calling those undeliverable
    would shrink the search for nothing. `confirm_hits` reports the flag and ranks an undeliverable
    hit behind a deliverable one of the same length."""
    assert EF.delivered(0, 255) == (1, 254) and EF.delivered(128, 110) == (128, 110)
    assert EF.survives_delivery(128, 110)                     # interior: delivered verbatim
    extremes = [(sx, sy) for sx in (0, 255) for sy in range(0, 256, 8)]
    assert any(EF.survives_delivery(*p) for p in extremes), "the clamp is never survivable?"
    assert not all(EF.survives_delivery(*p) for p in extremes), "the clamp never bites?"
    # every member of the s84-style alphabet is chosen interior, so the whole alphabet survives
    assert all(EF.survives_delivery(*p) for p in EF.stick_alphabet(16))


def test_the_band_cache_survives_a_killed_pass_and_a_concurrent_one(tmp_path):
    """A HARNESS TRAP, fixed in place (`[[harden-harness-traps]]`). `stream_search` saves the band
    cache every batch, and the save used to be a plain dump onto the live path -- so the file was
    truncated for the duration of every write. Killing a long pass mid-save poisoned the cache for
    every later run, and starting a second pass while the first was running read a torn file and died
    in `json.load` (this happened, session 85).

    Two properties: the save leaves no window where the path is unreadable, and a cache that IS
    damaged costs a re-measure rather than the pass. Nothing here is a tolerance -- the reloaded table
    must be the saved one."""
    path = str(tmp_path / 'bands.json')
    t = EF.BandTable(SEED, path=path)
    t.tab[(FACING, THRUST, 0, EF._f32_bits(ES.ROLL_NSPEED))] = dict(productive=True, width=3.2e-5)
    t.save()
    assert not [p for p in tmp_path.iterdir() if p.name.endswith('.tmp')], "temp file left behind"
    assert EF.BandTable(SEED, path=path).tab == t.tab                      # round-trips exactly

    open(path, 'w').write('{"40820,15,0,1"')                               # a torn write
    with pytest.warns(UserWarning, match='unreadable cache'):
        damaged = EF.BandTable(SEED, path=path)
    assert damaged.tab == {}
    damaged.save()                                                         # and it heals on the next
    assert EF.BandTable(SEED, path=path).tab == {}


def test_a_coarser_pass_is_read_out_of_the_finer_one_it_is_contained_in():
    """THE TWO-ALPHABET SATURATION TEST, FROM ONE PASS. `clip-lottery-draws.md` says the honest read
    on whether an axis still pays is two whole-circle alphabets compared on draws per family -- which
    costs a second pass, and the tail marginal (the number that is free) is the one s84 proved is
    misleading, because the stick grid is x-major and a sweep crosses the productive band once.

    A fine alphabet CONTAINS every coarser one, so the coarse pass's rate is just the finer pass's
    families restricted to the coarse sub-grid. Gated on a real pass rather than a fabricated dict:
    the sub-grid must be a subset, must shrink as the stride grows, and the full pass must agree with
    `subgrid_rate` at stride 1."""
    kw = dict(base_frames=(0,), s1_stride=8, j1=(2,), s2_stride=16, j2max=4)
    r = EF.stream_search(EF.iter_fan2(**kw), quals=productive_quals(),
                         bands=EF.BandTable(SEED, path=None), family_of=EF.family_of_plan)
    assert r['n_families'] > 1 and r['near_families'], "no draws -- the readout would be vacuous"
    assert sum(n for _f, n in r['near_families']) == r['n_near']
    # the running pass must report the SAME quantity it is judged on: the trace's counts are draws,
    # not scorings (they differed by 2.3x while the s85 pass ran, which is the number a human watches)
    assert r['trace'][-1]['near'] == r['n_near']
    assert r['trace'][-1]['genuine'] == r['n_hit_draws']
    whole = EF.subgrid_rate(r, 1)
    assert whole['families'] == r['n_families'] and whole['draws'] == r['n_near']
    prev = whole
    for s in (16, 32, 64):
        g = EF.subgrid_rate(r, s)
        assert g['families'] <= prev['families'] and g['draws'] <= prev['draws'], (s, g, prev)
        prev = g


def test_entry_fan_still_re_exports_the_scoring_half():
    """The session-85 split moved the streaming eval to `entry_score`, and the re-export is a
    CONTRACT (the repo's shim convention: import paths must not churn on a refactor). Every public
    name has to be the same object, not a copy -- a shadowing redefinition would pass an equality
    test and silently give callers a second `BandTable` class."""
    from harness.tetrapush import entry_score as EC
    for name in ('stream_search', 'BandTable', 'qualified', 'ref_entry', 'family_of_plan',
                 'draw_key', 'hit_draws', 'dedupe_near', 'lottery', 'distinct_near',
                 'confirm_hits', 'MIN_BAND', 'BAND_PROBE', 'QUAL_CACHE', 'BAND_CACHE',
                 'facing_window', 'parse_cell_spec', 'cell_scope', 'select_quals'):
        assert getattr(EF, name) is getattr(EC, name), name


# ------------------------------------------------------- scoping a pass by cell (session 93)

def test_a_cell_spec_is_the_measured_window_not_a_typed_list():
    """``lobe2`` has to MEAN the measured lobe, so a re-scan moves every selector with it.

    The s92 handoff named the second lobe's aimable cells by hand -- "2561, 2562, 2564, 2567-2570,
    2572, 2573" -- and a hardcoded list is exactly what goes stale when the window's right edge moves
    (the handoff itself flags that the scan stopped at 2575 while the qualification reached 2581). So
    the named forms resolve out of `fixtures/courtyard_facing_window_s92.json`, and ``right`` is
    defined against the DELIVERED cell rather than a number anyone chose."""
    w = EF.facing_window()
    lo, hi = w['lobes'][1]
    assert EF.parse_cell_spec('lobe2') == tuple(range(lo, hi + 1))
    assert EF.parse_cell_spec('lobe1') == tuple(range(*[w['lobes'][0][0], w['lobes'][0][1] + 1]))
    # `right` runs from one cell past the delivered clip's to the AIM ALPHABET's edge, not the scan's:
    # the s92 scan stopped at 2575 while its own qualification reached 2581 (`parse_cell_spec`).
    right = EF.parse_cell_spec('right')
    assert min(right) == w['delivered']['cell'] + 1
    assert max(right) == ES.AIM_WINDOW[1] >> 4 > w['scanned'][1]
    assert w['delivered']['cell'] not in right
    quals = productive_quals()
    assert max(EF.cell_scope(quals, right)['kept']) > w['scanned'][1], \
        "the productive set reaches past the scanned window; `right` must too"
    assert EF.parse_cell_spec('2561,2562') == (2561, 2562)
    assert EF.parse_cell_spec('2564-2566') == (2564, 2565, 2566)
    assert EF.parse_cell_spec('2561, 2564-2566, lobe1') == \
        tuple(sorted(set((2561, 2564, 2565, 2566)) | set(EF.parse_cell_spec('lobe1'))))


def test_the_cell_scope_says_which_cells_it_missed_and_which_kind_of_miss_it_was():
    """A cell absent from the productive set is absent for one of TWO reasons, and they are different
    facts about the search rather than one shortfall.

    **Not aimable at this camera:** `qualified` only ever qualifies `aim_cells(csangle)`, so a cell no
    A-press aim resolves to at the frozen csangle was never offered a qualification. That is the camera
    lever session 92 re-opened -- s83 priced a slew at exactly zero against a 2-cell window, and five
    cells of the real window are in this class. **Barren:** the cell was qualified and nothing genuine
    was found, which is what the measured dead gap is. Conflating them would read a camera limit as a
    geometric negative."""
    quals = productive_quals()
    w = EF.facing_window()
    aimable = {ES.aim_cell(f) for f, _b, _s in ES.aim_cells(ES.CSANGLE)}

    sc = EF.cell_scope(quals, EF.parse_cell_spec('lobe2'))
    assert sc['kept'] and sc['not_aimable'] and not sc['barren']
    for c in sc['not_aimable']:
        assert c not in aimable, c            # a camera miss, not a barren cell
    for c in sc['kept']:
        assert c in aimable

    # the measured DEAD GAP is the other kind: aimable cells that qualified and found nothing
    gap = EF.cell_scope(quals, range(w['dead_gap'][0], w['dead_gap'][1] + 1))
    assert not gap['kept'], "the dead gap must not be in the productive set"
    assert gap['barren'], "and its aimable cells are barren, not unaimable"
    assert set(gap['barren']) <= aimable


def test_narrowing_a_pass_never_silently_returns_an_empty_scope():
    """The scope a pass ran is part of its result, and an empty one is an ERROR.

    This thread has paid for a silently-narrowed scope twice -- session 89 re-ran the old aim alphabet
    from a cache key that did not cover the ATTACK gate, and sessions 81-91 ran a 2-cell facing window
    because a negative had been argued from one seed entry. Both looked like completed passes.
    `[[search-space-contains-human]]`: state the range, then check it."""
    quals = productive_quals()
    assert len(EF.select_quals(quals, cells=(2561, 2562))) == 2
    assert len(EF.select_quals(quals)) == len(quals)          # no scope == every configuration
    with pytest.raises(ValueError):
        EF.select_quals(quals, cells=(9999,))
    with pytest.raises(ValueError):
        EF.select_quals(quals, cells=EF.parse_cell_spec(str(EF.facing_window()['dead_gap'][0])))
    with pytest.raises(ValueError):
        EF.select_quals(quals, thrusts=(99,))


def test_the_frame_cap_drops_exactly_the_plans_the_objective_would_reject():
    """``frames=`` is the objective as a PRUNE, not a ranking.

    `iter_fan2`'s shape arguments bound the fan but not the plan LENGTH, so a bounded pass spends most
    of its evaluation on plans Dereck would refuse outright -- the herd must lose ZERO frames
    (`[[tetrapush-frame-minimal]]`; session 91's own note is "do not bring him a 5-frame plan"). The
    cap must be order-preserving, since a family-major stream is what bounds `stream_search`'s
    memory, and `None` must be the identity so every pass through session 91 still means what it did."""
    kw = dict(base_frames=(0, 1), s1_stride=64, j1=(1, 2), s2_stride=32, j2max=3)
    full = list(EF.iter_fan2(**kw))
    assert {EF.plan_frames(p) for _k, p in full} - {2, 3, 4} , "this fan must span past the floor"
    cap4 = list(EF.capped(EF.iter_fan2(**kw), 4))
    assert cap4 == [kv for kv in full if EF.plan_frames(kv[1]) <= 4]     # order preserved
    assert cap4 and len(cap4) < len(full)
    assert max(EF.plan_frames(p) for _k, p in cap4) <= 4
    assert list(EF.capped(EF.iter_fan2(**kw), None)) == full             # None is the identity
    assert EF.plan_frames([0, 208, 110, 2, 169, 192, 2]) == 4            # the delivered clip's plan
    assert EF.plan_frames([3, 9, 9, 6]) == 9                             # one segment: n0 + j


def test_a_scoped_pass_is_the_unscoped_pass_restricted_to_those_cells():
    """**THE CONTRACT THE WHOLE SCOPING RESTS ON: it may change the COST and never an ANSWER.**

    Session 92's productive set is 40 configurations where every pass before it ran 6, and evaluation
    is per candidate per configuration -- so a pass at the cells the objective wants is the only
    affordable one. That is a budget decision, and it is only legitimate if the hits and near-misses
    it reports at those cells are bit-for-bit the ones the whole-set pass reports there. Same gate
    shape as the fan-equality one: the cheap path has to reproduce the reference exactly."""
    kw = dict(base_frames=(0,), s1_stride=64, j1=(2,), s2_stride=32, j2max=2)
    cells = (2551, 2552)
    quals = productive_quals()
    sub = EF.select_quals(quals, cells=cells)
    assert 0 < len(sub) < len(quals)
    bands = EF.BandTable(SEED, path=None)
    wide = EF.stream_search(EF.iter_fan2(**kw), quals=quals, bands=bands, batch=997)
    narrow = EF.stream_search(EF.iter_fan2(**kw), quals=sub, bands=bands, batch=997)

    assert narrow['n_candidates'] == wide['n_candidates'] > 0     # the same fan, scored less widely
    assert narrow['n_evaluations'] == wide['n_evaluations'] * len(sub) // len(quals)
    pick = lambda r: sorted((h['facing'], h['thrust'], tuple(h['entry']), tuple(h['plan']))
                            for h in r['hits'] if ES.aim_cell(h['facing']) in cells)
    assert pick(narrow) == pick(wide)
    nearby = lambda r: sorted((g, i['facing'], i['thrust'], tuple(i['entry']))
                              for g, i in [(d['gap'], d) for d in r['near_detail']]
                              if ES.aim_cell(i['facing']) in cells)
    assert nearby(narrow) == nearby(wide)


def test_the_one_segment_fan_keeps_its_unpruned_contract():
    """`iter_fan` must NOT take the prune. It is gated key AND value against `entry_search.walk_fan`,
    which has no proc condition, so pruning it would break an equality the whole native fan rests on
    -- the same reason `stick_alphabet` is deliberately not wired into it."""
    kw = dict(base_frames=(0, 1), stride=64, jmax=4)
    assert EF.fan_equality(ES.walk_fan(**kw), EF.fleet_fan(**kw))['equal']


def test_genuine_hits_are_counted_in_draws_like_near_misses_are():
    """A hit is a draw too, and the wide pass proved it matters: 118 genuine SCORINGS were 23 draws,
    one entry reached by 95 different prefixes.

    `hit_draws` keeps one representative per draw, frame-minimal first (frames are the objective,
    `[[tetrapush-frame-minimal]]`), and keeps the rest available -- they are alternative deliveries
    of an entry, and `confirm_entry` rejects some of them."""
    def hit(walk, lean, facing, plan, resid=1e-5):
        return dict(walk=list(walk), m351C=lean, facing=facing, thrust=15,
                    nspeed=ES.ROLL_NSPEED, plan=list(plan), resid=resid)
    one_entry_three_prefixes = [hit((1.0, 2.0), 900, 40820, [0, 9, 9, 6]),
                                hit((1.0, 2.0), 900, 40820, [0, 9, 9, 2, 3, 3, 1]),
                                hit((1.0, 2.0), 900, 40820, [5, 9, 9, 4])]
    got = EF.hit_draws(one_entry_three_prefixes)
    assert len(got) == 1 and got[0]['plan'] == [0, 9, 9, 2, 3, 3, 1]      # 3 frames, the fewest
    other = hit((1.0, 3.0), 900, 40820, [0, 9, 9, 1])
    two = EF.hit_draws(one_entry_three_prefixes + [other])
    assert len(two) == 2 and two[0]['plan'] == [0, 9, 9, 1]               # frame-minimal first
    assert EF.hit_draws([]) == []


# ------------------------------------------------------- the session-85 pass, re-scored (session 87)

_RESCORED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'fixtures', 'courtyard_entry_s87_rescored.json')


def test_the_session_85_pass_rescores_to_its_seven_survivors():
    """**THE 49, ASKED AGAIN.** They were scored by an engine whose baked Co centre dropped the
    `body_chn` twist (`body_cyl.co_leans`) -- a term that scales with the roll's turn lean, i.e. with
    the candidate -- so the correction could not be reasoned about hit by hit and every one had to be
    re-swept. **7 of 49 survive**, and the frame floor moves from the 4 the console falsified to 5.

    Pinned as a fixture because the survivor set is the current candidate list: if the engine moves
    again this names which hits moved with it. It is a MODEL output, not a console capture -- and a
    survivor rate is a lower bound on the axis, since the fixed engine can make genuine a candidate
    the old one threw away. Re-running the pass is what measures that."""
    fx = json.load(open(_RESCORED))
    rows = EF.rescore([dict(r, plan=list(r['plan'])) for r in fx['rows']])
    assert len(rows) == fx['n_hits'] == 49
    for got, want in zip(rows, fx['rows']):
        assert got['genuine'] is want['genuine'], want['plan']
        assert got['resid'] == want['resid'], want['plan']
    kept = [r for r in fx['rows'] if r['genuine']]
    assert len(kept) == fx['n_kept'] == 7
    assert min(r['frames'] for r in kept) == 5
    # the rejected ones are not near-misses that drifted: they land decades outside the window
    tossed = [r for r in fx['rows'] if not r['genuine']]
    assert max(r['resid'] for r in tossed) < -1e-3
    # and every survivor's recorded resid is UNCHANGED -- their leans are the small ones, where the
    # twist is below the sine-table bucket. That is the shape of the term, not a coincidence.
    assert all(r['resid'] == r['resid_s85'] for r in kept)


_FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures')
_S87_HITS = os.path.join(_FIXTURES, 'courtyard_entry_s87_hits.json')


def _fx(name):
    return os.path.join(_FIXTURES, name)


def test_the_session_87_pass_still_scores_but_two_thirds_of_it_cannot_ROLL():
    """**THE PASS, AND THE GATE IT WAS MISSING.** Same scoping as session 85's
    (`search2 2 1,2 1 6 2`, 39.3 M candidates, 4997 s): 55 distinct genuine draws, frame floor 4, and
    the yield barely moved -- 1950 near draws against s85's 2007, E[hits] 4.547 against 4.638.

    Every one of the 55 still SCORES genuine at the residual it recorded: `rescore` is bit-stable, so
    the razor itself has not drifted. What moved is `confirm`. Session 88's first console delivery
    found that an A-press below `LandState.ATTACK_MSD_MIN` does not roll at all
    (`test_attack_threshold.py`), and this pass drew from an aim alphabet that offered two
    representatives, one of them 0.5705 deep. **36 of the 55 cannot roll on console and 19 can**, so
    the frame floor moves 4 -> 5. The list is still pinned in full because that split is the
    measurement: `fixtures/courtyard_entry_s88_hits.json` carries the survivors."""
    fx = json.load(open(_S87_HITS))
    hits = [dict(r, plan=list(r['plan'])) for r in fx['rows']]
    assert len(hits) == fx['n_hits'] == 55
    assert fx['frame_floor'] == min(r['frames'] for r in fx['rows']) == 4
    for got, want in zip(EF.rescore(hits), fx['rows']):
        assert got['genuine'] is True, want['plan']
        assert got['resid'] == want['resid'], want['plan']
    # `confirm_hits` re-ranks (confirmed first), so index its rows by plan rather than by position.
    by_plan = {(tuple(r['hit']['plan']), tuple(r['hit']['aim'])): r for r in EF.confirm_hits(hits)}
    assert len(by_plan) == 55
    deep = [h for h in hits if main_stick_decode(*h['aim'])[1] > float(LandState.ATTACK_MSD_MIN)]
    assert len(deep) == 19
    for h in hits:
        got = by_plan[(tuple(h['plan']), tuple(h['aim']))]
        if h in deep:
            assert got['confirm']['all_ok'] and got['deliverable'], h['plan']
        else:
            assert not got['confirm']['ok']['rolled'], h['plan']
    s88 = json.load(open(_fx('courtyard_entry_s88_hits.json')))
    assert s88['frame_floor'] == 5 and len(s88['dropped']) == 36


def test_the_two_passes_of_one_scoping_overlap_only_where_the_lean_is_small():
    """The engine fix is not a filter on the old output, it is a different search. Of s85's 49 exactly
    7 are in the s87 pass's 55, and they are the small-lean ones -- which is the shape of the
    `body_chn` twist (`body_cyl.co_leans`), a term that is a no-op below ~30 BAM of lean."""
    old = json.load(open(_RESCORED))
    new = json.load(open(_S87_HITS))
    key = lambda r: (tuple(r['plan']), r['facing'], r['thrust'])
    shared = {key(r) for r in old['rows']} & {key(r) for r in new['rows']}
    assert len(shared) == 7
    kept = [r for r in old['rows'] if r['genuine']]
    assert {key(r) for r in kept} == shared, "the survivors ARE the overlap, by construction"


def test_the_session_89_pass_is_the_same_population_reached_by_an_aim_that_ROLLS():
    """**THE RE-RUN, AND WHAT IT ACTUALLY CORRECTED.** Same scoping again
    (`search2 2 1,2 1 6 2`, 39.3 M candidates, 4701 s), and the first attempt came back
    BIT-IDENTICAL to session 87's because `entry_score.qualified`'s cache did not key on the ATTACK
    threshold (`test_attack_threshold.py::test_the_gate_reaches_the_PASS_and_not_only_the_alphabet`).
    With the key fixed the pass is still the same 81 scorings at the same entries and residuals --
    because the physical atom is the sine-table CELL and 40834/40841 are both cell 2552 -- but the
    REPRESENTATIVE moved: cell 2552's aim goes from `[95,168]` msd 0.5705, which sheathes, to
    `[82,186]` msd 0.9817, which rolls.

    So session 88's "36 of the 55 cannot roll" was a property of the PINNED ROW, not of the
    candidates. Re-represented, **0 of 81 scorings carry an unrollable aim** (against 57), all 55
    draws confirm, and the frame floor returns to 4. The 4 that the cross-engine gate still rejected
    here were the Co-centre seam, and session 90's console run settled it -- so this file is the
    pass as the PRE-FIX engine filtered it, and the current list is the one below."""
    s89 = json.load(open(_fx('courtyard_entry_s89_hits.json')))
    assert s89['n_hits'] == 51 and s89['frame_floor'] == 4
    assert len(s89['dropped']) == 0, "every candidate now rolls; nothing dies at the A-press"
    assert len(s89['rejected']) == 4

    rows = s89['rows']
    for r in rows:
        assert main_stick_decode(*r['aim'])[1] > float(LandState.ATTACK_MSD_MIN), r['plan']
        assert r['confirmed'] and r['deliverable'] and r['cross_engine']['deliverable']
    assert min(r['frames'] for r in rows) == 4

    # the cell is the atom: the s87 pass's population survives, only its representative moved
    s87 = json.load(open(_S87_HITS))
    key = lambda r: (tuple(r['plan']), r['thrust'], r['m351C'], tuple(r['entry']))
    assert ({key(r) for r in s87['rows']}
            == {key(r) for r in rows} | {key(r) for r in s89['rejected']})
    assert {ES.aim_cell(r['facing']) for r in rows} == {2551, 2552}
    assert ES.aim_cell(40834) == ES.aim_cell(40841) == 2552


def test_the_session_90_list_is_the_whole_pass_because_the_seam_closed():
    """**THE CURRENT CANDIDATE LIST.** Session 90 delivered one of the four cross-engine rejections
    to console and it clipped, which settled the Co-centre seam -- and the root cause turned out to
    be a ULP of ANIM FRAME (`FrameCtrl` holding `enter_roll`'s Python double `1.1` where
    `J3DFrameCtrl::mRate` is f32), not a wrong centre. See `test_centre_seam.py`.

    So the same pass, re-confirmed on the fixed engine, loses NOBODY: the s89 rows plus the four it
    rejected are exactly the s90 rows. The candidate list a delivery indexes is this one; the s89
    file above stays as the record of what the seam cost while it was open."""
    s89 = json.load(open(_fx('courtyard_entry_s89_hits.json')))
    s90 = json.load(open(_fx('courtyard_entry_s90_hits.json')))
    assert s90['n_hits'] == 55 and s90['frame_floor'] == 4
    assert len(s90['rejected']) == 0 and len(s90['dropped']) == 0

    key = lambda r: (tuple(r['plan']), r['thrust'], r['m351C'], tuple(r['entry']))
    assert ({key(r) for r in s90['rows']}
            == {key(r) for r in s89['rows']} | {key(r) for r in s89['rejected']})
    for r in s90['rows']:
        assert main_stick_decode(*r['aim'])[1] > float(LandState.ATTACK_MSD_MIN), r['plan']
        assert r['confirmed'] and r['deliverable'] and r['cross_engine']['deliverable']
        assert r['cross_engine']['worst_ulp'] == 0 and r['cross_engine']['cut_ok'], r['plan']
    # ranked frame-minimal first, so row 0 is what a delivery script picks up
    assert [r['frames'] for r in s90['rows']] == sorted(r['frames'] for r in s90['rows'])
    assert s90['rows'][0]['frames'] == 4


def test_the_pinned_qualification_still_measures_the_same_way():
    """The productive set is PINNED (624 s to measure), so it has to be spot-checked or it rots.

    Re-measure two configurations for real: one the fixture calls productive at a right-lobe cell -- the
    class that only exists because a negative is argued from the residual-zero curve now (session 92) --
    and one facing in the measured DEAD GAP, which must still read dead. Also pins the fixture's own
    provenance: a set measured with `escalate=False`/`curve=False`, or before the ATTACK gate, is the
    reading that hid half the facing window and must never be what these gates consume."""
    fx = json.load(open(_fx('courtyard_qualified_s92.json')))
    assert fx['escalate'] is True and fx['curve'] is True
    assert fx['msd_min'] == fx['attack_msd_min'] == float(LandState.ATTACK_MSD_MIN)
    assert fx['csangle'] == ES.CSANGLE and tuple(fx['thrusts']) == tuple(ES.THRUSTS)
    quals = fx['quals']
    assert len(quals) > 6, "the pre-session-92 weak form found 6; this must be the wide set"

    right = max((q for q in quals), key=lambda q: q['cell'])
    assert right['cell'] > ES.aim_cell(40841), "the set must reach past the delivered cell"
    live = ES.qualify(SEED['tetra'], EF.ref_entry(SEED), facings=[right['facing']],
                      thrusts=(right['thrust'],), lean=right['lean'])
    assert len(live) == 1 and live[0]['productive'], right['facing']

    dead = ES.qualify(SEED['tetra'], EF.ref_entry(SEED), facings=[40898], thrusts=(15,))
    assert not dead[0]['productive'], "cell 2556 is in the measured dead gap"
