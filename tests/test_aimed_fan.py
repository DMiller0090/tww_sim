"""**THE AIMED FAN'S OWN GATES** (session 161) -- `harness/tetrapush/aimed_fan.py`.

Three things have to be true before a prune may be used at all, and each one has a test here:

  * **the bound is an UPPER bound.** `aimed_fan.MAX_STEP` is what makes `reachable` admissible; if a
    stepped frame can move Link further than it says, the prune drops subtrees that could have hit and
    the search silently loses coverage -- the s160 failure one level down.
  * **it does not drop the one junction known to work.** The console's own plan goes through a specific
    junction, and a prune that removes it is wrong however good its arithmetic looks
    (`[[search-must-rediscover-known-answer]]`).
  * **it is lossless where it is checkable.** On a small enough alphabet the whole thing can be run
    twice -- pruned and blind -- and the leaf sets compared near the target, which is the only form of
    "admissible" that is a measurement rather than an argument.

The expensive halves (the full-alphabet bound sweep, the 40-minute containment run) are BANKED and
asserted against their artefacts, per `[[slow-offline-tests]]`.
"""
import json
import math
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.tetrapush import admit_map as AM
from harness.tetrapush import aimed_fan as AF
from harness.tetrapush import entry_aim as EA
from harness.tetrapush import entry_fan as EF
from harness.tetrapush import objective as O
from harness.tetrapush import overnight as ON
from harness.tetrapush import seeds as SD

CC = json.load(open(ON.CONSOLE_CLIP))['hit']


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', float(v)))[0]


@pytest.fixture(scope='module')
def setup():
    """The console item, its base core, and the junction its own plan goes through."""
    env = SD.load_env()
    cc = ON.console_candidate()
    prep, hold, trail = ON.prepared(cc['unit'], env, O.courtyard_walls(), cc['walk'])
    plan = ON.from_triples(cc['plan'])
    csa = ON.aim_camera(plan, cc['walk'], trail)
    segs = [(int(plan[i]), int(plan[i + 1]), int(plan[i + 2]), int(plan[i + 3]))
            for i in range(1, len(plan), 4)]
    n0 = int(plan[0])
    base, _run = EF.base_core(n0, seed=prep['seed'], env=env, hold=hold)
    (sx1, sy1, l1, j1) = segs[0]
    jc = ON._fan(base, [(sx1, sy1)], [l1] * j1, csa, trail, n0, 0)[0][1]
    return dict(env=env, cc=cc, prep=prep, hold=hold, trail=trail, csa=csa, base=base, jc=jc,
                n0=n0, jp=j1, walk=cc['walk'], segs=segs, want=tuple(CC['walk']))


# ------------------------------------------------------------------------------- the bound is a bound

def test_the_step_bound_holds_over_the_alphabet_it_bounds(setup):
    """`MAX_STEP` is only sound while the enumeration stays under it, so it is MEASURED off the same
    primitive the fan steps -- at the branch that peaks (one delivered frame, where speedF overshoots to
    18.70 before decaying). The full-alphabet sweep is `aimed_fan.bound`; this is its coarse, 1-second
    form, and both are the same call."""
    a = EF.stick_alphabet(4)
    for j in (1, 2):
        b = AF.step_bound(setup['base'], a, [0] * (j + 1), setup['csa'], setup['trail'], setup['n0'])
        assert b['per_frame'] <= AF.MAX_STEP, 'a stepped frame moved %.4f u, bound says %.2f' % (
            b['per_frame'], AF.MAX_STEP)
        assert b['n'] == len(a) and b['frames'] == j + 1


def test_the_first_stepped_frame_cannot_be_used_to_measure_anything(setup):
    """**THE DEGENERATE PROBE, pinned** (`_notes/s161_step.py`'s first draft was one). At
    ``input_delay = 1`` the stick delivered on a frame acts on the NEXT one, so ONE stepped frame moves
    every draw in the alphabet the same distance -- a spread of exactly zero. Any measurement of "how
    much does the stick change the endpoint" taken over a single stepped frame reads 0 and means
    nothing."""
    a = EF.stick_alphabet(16)
    cores = ON._fan(setup['base'], a, [0], setup['csa'], setup['trail'], setup['n0'], 0,
                    alive_only=False)
    d = {(_bits(c.pos_x), _bits(c.pos_z)) for _i, c in cores}
    assert len(d) == 1, 'the first stepped frame is stick-independent; got %d distinct endpoints' % len(d)


# ---------------------------------------------------------------------- the prune keeps what it must

def test_the_prune_keeps_the_junction_that_contains_the_console_plan(setup):
    """**THE PRUNE'S OWN REDISCOVERY GATE.** The console's plan runs through the junction after 2 frames
    of ``(208, 110)``, and its walk endpoint is 49.66 u away with 3 stepped frames left. A prune that
    drops this junction cannot find the one plan known to work, whatever else it does."""
    r = setup['walk'] - setup['n0'] - setup['jp'] + 1
    d = math.hypot(setup['jc'].pos_x - setup['want'][0], setup['jc'].pos_z - setup['want'][1])
    assert r == 3 and 49.0 < d < 50.0, 'setup moved: r %d, |J-W| %.3f u' % (r, d)
    assert AF.reachable(setup['jc'], setup['want'], r) is True


def test_the_prune_frames_are_stepped_not_delivered(setup):
    """The bug this cost, pinned as an assertion: passing the DELIVERED count instead of the stepped one
    bounds the console's own junction at 38.0 u when it needs 57.0, and the prune removes 20130 of 20130
    junctions -- every branch, including the one that contains the answer."""
    delivered = setup['walk'] - setup['n0'] - setup['jp']
    assert AF.reachable(setup['jc'], setup['want'], delivered) is False
    assert AF.reachable(setup['jc'], setup['want'], delivered + 1) is True


def test_reachable_takes_the_nearest_of_a_curve(setup):
    """The razor's target is a strip, so the prune tests against the NEAREST sample -- a junction kept by
    any one target must be kept by the set containing it."""
    far = (setup['want'][0] + 500.0, setup['want'][1] + 500.0)
    assert AF.reachable(setup['jc'], far, 3) is False
    assert AF.reachable(setup['jc'], [far, setup['want']], 3) is True
    assert AF.reachable(setup['jc'], [far, far], 3) is False


def test_the_prune_is_lossless_against_a_blind_run(setup):
    """**ADMISSIBILITY AS A MEASUREMENT, not an argument.** Run the same coarse enumeration twice --
    once pruned, once blind -- and every blind leaf within the reach of its own junction must still be
    produced. Small alphabets, because the point is the SET comparison and not the coverage."""
    pre, alpha = EF.stick_alphabet(32), EF.stick_alphabet(16)
    want, r = setup['want'], setup['walk'] - setup['n0'] - setup['jp'] + 1
    jcs = ON._fan(setup['base'], pre, [0] * setup['jp'], setup['csa'], setup['trail'], setup['n0'], 0)
    dropped_hits = 0
    for _i, jc in jcs:
        keep = AF.reachable(jc, want, r)
        cores = ON._fan(jc, alpha, [0] * r, setup['csa'], setup['trail'],
                        setup['n0'] + setup['jp'], 0, alive_only=False)
        best = min(math.hypot(c.pos_x - want[0], c.pos_z - want[1]) for _k, c in cores)
        if not keep and best <= AF.REACH_TOL:
            dropped_hits += 1
    assert dropped_hits == 0, '%d pruned junctions could actually reach the target' % dropped_hits


# ------------------------------------------------------------- ordering: the half that is lossless

def test_the_at_cap_leaves_live_on_a_thin_annulus_not_the_reach_disc(setup):
    """**WHY `rank` RANKS ON ``frames * WALK_CAP``.** The leaves `fan_exact` actually keeps -- at the cap
    and rollable -- do not fill their reach disc: they went nearly straight, because holding the cap is
    what being at the cap means. The envelope must sit just under the straight-line distance and be a
    small fraction of the disc, or the ranking key is aimed at nothing."""
    a = EF.stick_alphabet(4)
    r = setup['walk'] - setup['n0'] - setup['jp'] + 1
    cores = ON._fan(setup['jc'], a, [0] * r, setup['csa'], setup['trail'],
                    setup['n0'] + setup['jp'], 0, alive_only=False)
    env = AF.annulus(setup['jc'], cores, r,
                     keep=lambda c: ON.at_cap(c.speedF) and EF._is_rollable(c))
    assert env['n'] > 0 and env['lo'] is not None
    assert env['hi'] <= env['straight'] + 1e-6, 'an at-cap leaf outran the cap'
    assert (env['hi'] - env['lo']) < 0.15 * env['straight'], 'envelope %.2f..%.2f vs straight %.2f' % (
        env['lo'], env['hi'], env['straight'])
    assert env['hi'] < r * AF.MAX_STEP, 'the disc the prune uses is strictly looser'


def test_the_ranking_drops_nothing(setup):
    """`rank` is a permutation. It is used because the annulus above is an EMPIRICAL envelope and an
    empirical envelope used as a prune is the s160 failure -- so it may reorder and may not filter."""
    a = EF.stick_alphabet(32)
    jcs = ON._fan(setup['base'], a, [0] * setup['jp'], setup['csa'], setup['trail'], setup['n0'], 0)
    out = AF.rank(jcs, setup['want'], 3)
    assert len(out) == len(jcs)
    assert {i for i, _c in out} == {i for i, _c in jcs}


def test_the_ordering_is_only_weakly_selective_and_that_is_the_measurement(setup):
    """**HOW MUCH AIMING ACTUALLY BUYS AT THE JUNCTION, pinned as a number rather than hoped for.**

    A deadline reads the front of this order, so the question is not whether the console's junction is
    enumerated but how early. Ranked against its own delivered walk endpoint it lands at **1366 of
    3355** -- the top 41%, i.e. about 2.4x on time-to-first-hit and nowhere near the 114x that
    containment costs.

    The reason is measured (`_notes/s161_prune.py` and the session log): the hold segment steers the
    at-cap endpoint over a **33 degree arc** covering ~12 x 25 u, so knowing the ENDPOINT constrains the
    junction only to an arc band that most junctions already sit in -- and the band's own bearing window
    is a property of each junction, not a constant (over 12 sampled junctions the union is 41% of the
    circle). Aiming localises the razor beautifully and the FAN barely at all. This test exists so that
    a future session reads the number instead of re-deriving the disappointment."""
    pre = EF.stick_alphabet(ON.CONTAINED_PRE_STRIDE)
    want = (208, 110)
    idx = next(i for i, p in enumerate(pre) if EF._decoded(*p) == EF._decoded(*want))
    jcs = ON._fan(setup['base'], pre, [0] * setup['jp'], setup['csa'], setup['trail'], setup['n0'], 0)
    order = [i for i, _c in AF.rank(jcs, setup['want'], 3)]
    frac = order.index(idx) / float(len(order))
    assert 0.25 < frac < 0.60, 'console junction ranked %d of %d (%.2f)' % (
        order.index(idx), len(order), frac)


# ------------------------------------------------------------------------------ the target is a curve

@pytest.fixture(scope='module')
def curve():
    """One sampled strip at the console's own configuration, and the razor context that produced it --
    shared, because `entry_search.build_fast` is the cost here and the three questions below are all
    about the same curve."""
    from harness.tetrapush import entry_search as ES
    cfg = AM.CONSOLE
    ctx, sch, resid = ES.build_fast(cfg['facing'], cfg['lean'] & 0xFFFF, cfg['thrust'])
    band = EA.band_for(cfg['facing'], cfg['lean'], cfg['thrust'], cfg['entry'], cfg['tetra'],
                       ctx=ctx, sch=sch, resid=resid)
    c = AF.aim_curve(cfg['facing'], cfg['lean'], cfg['thrust'], cfg['entry'], cfg['tetra'], n=8,
                     ctx=ctx, sch=sch, resid=resid, band=band)
    return cfg, c, dict(ctx=ctx, sch=sch, resid=resid, band=band)


def test_the_aim_curve_returns_only_entries_the_sim_calls_genuine(curve):
    """`aim_curve` samples along the razor's level curve and RE-AIMS each step, so a sample that drifts
    off the strip is dropped and counted -- never returned as a target. The band prices a row; only the
    sim verdicts one (`entry_aim`'s own discipline)."""
    cfg, c, sh = curve
    assert 0 < len(c['entries']) <= c['tried'] and len(c['entries']) == len(c['walk_ends'])
    for e in c['entries']:
        p = EA.price(cfg['facing'], cfg['lean'], cfg['thrust'], (e[0], e[1]), cfg['tetra'], **sh)
        assert p['genuine'] is True, 'aim_curve returned a non-genuine entry %s' % e


def test_the_curve_spans_more_than_the_fans_own_lattice(curve):
    """A fan whose endpoint lattice is 0.2-0.4 u has to MEET the target, and a point is not meetable at
    that resolution -- the curve is what makes the target reachable at all. If this ever collapses to a
    point the prune is aiming at something a plan cannot land on."""
    _cfg, c, _sh = curve
    assert AF.curve_span(c['walk_ends']) > 0.4


def test_each_curve_sample_inverts_back_onto_its_own_entry(curve):
    """`walk_end_for` is `roll_entry` inverted, and the prune aims at the WALK end -- so a sample whose
    inverse does not round-trip would be a target no plan could satisfy."""
    cfg, c, _sh = curve
    for e, w in zip(c['entries'], c['walk_ends']):
        rt = EA.walk_end_for(e, cfg['facing'])
        assert rt['error'] < 1.0e-3
        assert (_bits(rt['walk_end'][0]), _bits(rt['walk_end'][1])) == (_bits(w[0]), _bits(w[1]))


# ------------------------------------------------------------- the banked leaf-set containment result

@pytest.mark.skipif(not os.path.exists(AF.CONTAIN_BANK), reason='containment run not banked yet')
def test_the_contained_fans_leaf_set_holds_the_console_endpoint():
    """**THE HONEST CONTAINMENT GATE** (`[[search-must-rediscover-known-answer]]`), asserted against the
    banked run because producing it is ~40 minutes (`[[slow-offline-tests]]`).

    s160 proved the fan's PRIMITIVE reaches the endpoint when handed the console's own letters. This is
    the ENUMERATION reaching it: `overnight.fan_exact` at the contained knobs, every ``n0``, both
    families, the full stride-2 pre alphabet and the pinned stride-1 hold, returning the endpoint as a
    KEY -- bit-exactly, at the cap, with the fixture's own lean."""
    r = json.load(open(AF.CONTAIN_BANK))
    assert r['ok'] is True, 'the contained fan does not contain the console endpoint: %s' % r['nearest']
    assert (_bits(r['hit']['xz'][0]), _bits(r['hit']['xz'][1])) == (_bits(CC['walk'][0]),
                                                                   _bits(CC['walk'][1]))
    assert r['hit']['at_cap'] is True
    assert r['stats']['contained'] is True and r['stats']['alpha_pinned'] is True
    assert r['stats']['alpha_stride'] == ON.CONTAINED_ALPHA_STRIDE
    assert r['stats']['pre_stride'] == ON.CONTAINED_PRE_STRIDE
