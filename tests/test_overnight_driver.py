"""**THE OVERNIGHT DRIVER'S OWN GATES** -- the arithmetic, the plan encoding, and the checkpoint layer.

Three things are worth gating about a search that runs for hours unattended, and none of them is its
answers:

  * **the frame arithmetic**, because it is what orders the work and what "beats the console" means. It
    is checked against the LOCKED delivery fixture rather than restated: the driver's own
    ``total_frames`` of the console plan must be the fixture's own cut frame.
  * **the plan encoding**, because a plan is delivered as a DTM and a plan that cannot be rebuilt into
    the exact rows it was scored at is not a plan. `overnight.composite_log` of the console's own plan
    must be the console's own log, row for row -- which also makes this a containment gate with no
    simulation in it (`[[search-space-contains-human]]`; the simulating half is
    `overnight.verify_console`).
  * **the checkpoint layer**, because the run has to survive being killed. Claiming, resuming and the
    cross-process incumbent are exercised for real in a tmpdir.

Fast by construction: nothing here steps the sim (`tests/conftest.py` enforces a 1.5 s per-test budget
and a 120 s whole-selection one). The simulating end-to-end check is the driver's own
``verify-console`` command, which is a research run and not a gate.
"""
import json
import os

import pytest

from harness.tetrapush import entry_fan as EF
from harness.tetrapush import objective as O
from harness.tetrapush import overnight as ON
from harness.tetrapush import overnight_io as IO

with open(ON.CONSOLE_CLIP) as _fh:
    FIX = json.load(_fh)
CC = FIX['hit']
N_CONSOLE = FIX['plan']['n_console']
CUT_I = FIX['plan']['cut_i']


# --------------------------------------------------------------------------- the frame arithmetic

def test_the_console_plans_total_is_the_locked_cut_frame():
    """The driver's frame arithmetic, checked against the delivery instead of restated.

    ``herd + walk + thrust + 4`` must land exactly on the frame the console cut on. If this drifts,
    every floor, every branch-and-bound cut and the whole meaning of "beats 101" drifts with it."""
    assert ON.total_frames(N_CONSOLE, CC['frames'], CC['thrust']) == CUT_I


def test_roll_frames_is_entry_fans_own_plan_cost():
    """One arithmetic, two names: `entry_fan.plan_cost` charges ``plan_frames + thrust + 4``."""
    for thrust in (13, 14, 15):
        plan = (0, 208, 110, 2)
        assert (EF.plan_frames(plan) + ON.roll_frames(thrust)
                == EF.plan_cost(plan, thrust))


def test_the_incumbent_is_the_console_total():
    """`objective.TOTAL_INCUMBENT` is what the run is ordered and pruned against."""
    assert O.TOTAL_INCUMBENT == CUT_I


def test_every_dropped_unit_is_a_proof_and_no_kept_unit_is_hopeless():
    """A bounded search must be able to say what it did not look at, and why.

    Drops are on the ADMISSIBLE floor (the cheapest thrust and the shortest possible walk), so a dropped
    unit provably cannot produce a plan that beats the incumbent -- and conversely nothing kept is
    already hopeless, which is what makes the ascending-floor order a branch-and-bound."""
    keep, drop = ON.units()
    assert keep and drop, 'expected both live and provably-hopeless units at the console bound'
    for u in keep:
        assert u['floor'] < O.TOTAL_INCUMBENT
        assert u['thrusts'], u
        for t in u['thrusts']:
            assert ON.total_frames(u['herd'], ON.max_walk(u['herd'], t, O.TOTAL_INCUMBENT), t) \
                == O.TOTAL_INCUMBENT - 1
    for x in drop:
        assert x['floor'] >= O.TOTAL_INCUMBENT, x
    assert [u['floor'] for u in keep] == sorted(u['floor'] for u in keep), 'floors must ascend'


def test_the_console_herd_is_a_unit_with_room_to_be_found():
    """At a bound one frame past the console total, the console's own herd must be live and its own walk
    length inside the budget -- the arithmetic half of `overnight.verify_console`."""
    keep, _drop = ON.units(incumbent=CUT_I + 1)
    u = next(x for x in keep if x['unit'] == 'console')
    assert u['herd'] == N_CONSOLE
    assert CC['thrust'] in u['thrusts']
    assert u['walks'][CC['thrust']] >= CC['frames']


# --------------------------------------------------------------------------- the plan encoding

def test_the_plan_encoding_round_trips_the_console_walk():
    """The L-capable encoding must carry a pre-s150 plan unchanged: same frames, same letters."""
    plan = ON.from_triples(CC['plan'])
    assert ON.plan_frames(plan) == CC['frames']
    letters = [tuple(plan[i:i + 2]) for i in range(1, len(plan), 4)]
    assert letters == [tuple(CC['plan'][i:i + 2]) for i in range(1, len(CC['plan']), 3)]
    assert all(int(plan[i + 2]) == 0 for i in range(1, len(plan), 4)), 'L up on a legacy plan'


def test_the_walk_letters_are_in_the_fans_own_alphabet():
    """Containment, on the axis the fan actually enumerates: the human's letters must be MEMBERS.

    As decoded CLASSES, not bytes -- `entry_fan.stick_alphabet` is the byte grid collapsed onto what the
    physics reads, so a class is one draw and any member of it walks identically."""
    alpha = {EF._decoded(*p) for p in EF.stick_alphabet(1)}
    plan = ON.from_triples(CC['plan'])
    for i in range(1, len(plan), 4):
        assert EF._decoded(int(plan[i]), int(plan[i + 1])) in alpha, plan[i:i + 2]


def test_the_composite_log_is_the_console_log_row_for_row():
    """**The driver rebuilds the delivered movie exactly.**

    `overnight.composite_log` off the console's own herd, plan, aim and thrust must reproduce the locked
    log -- every stick byte, every button, every frame, including the A-press index, the UP+B index and
    the cut frame. A plan is delivered as a DTM, so an encoding that cannot round-trip to the exact rows
    it was scored at is not a plan, and this is the cheapest possible statement of that."""
    seed = dict(log=[dict(r) for r in FIX['log'][:N_CONSOLE]],
                tetra=(0.0, 0.0), link=(0.0, 0.0))
    # the fixture's own tail: the delivery ran a few neutral frames past the UP+B so a truncate-and-read
    # halt could sit past the cut (`cross_engine.TAIL`)
    log, ix = ON.composite_log(seed, ON.from_triples(CC['plan']), CC['aim'], CC['thrust'],
                               tail=len(FIX['log']) - (FIX['plan']['b_log'] + 1))
    assert ix['a_i'] == FIX['plan']['a_i']
    assert ix['entry_i'] == FIX['plan']['entry_i']
    assert ix['b_log'] == FIX['plan']['b_log']
    assert len(log) == len(FIX['log'])
    keys = ('stickX', 'stickY', 'buttons', 'triggerL', 'substickX', 'substickY')
    bad = [(i, {k: a.get(k) for k in keys}, {k: b.get(k) for k in keys})
           for i, (a, b) in enumerate(zip(log, FIX['log']))
           if any(int(a.get(k, 0)) != int(b.get(k, 0)) for k in keys)]
    assert not bad, 'the driver does not rebuild the console log at frames %s' % [x[0] for x in bad[:6]]


def test_plan_rows_delivers_the_l_press_it_is_asked_for():
    """The whole reason for the encoding: an L frame has to reach the log as a real L."""
    hold = dict(stickX=128, stickY=110, buttons=0, triggerL=0, substickX=128, substickY=0)
    rows = ON.plan_rows(hold, (1, 20, 30, 1, 2, 20, 30, 0, 1))
    assert len(rows) == 4 == ON.plan_frames((1, 20, 30, 1, 2, 20, 30, 0, 1))
    assert rows[0]['stickX'] == 128 and not rows[0]['buttons']
    assert [r['buttons'] & ON.PAD_L != 0 for r in rows] == [False, True, True, False]
    assert [r['triggerL'] for r in rows] == [0, ON.TRIG_L, ON.TRIG_L, 0]


# --------------------------------------------------------------------------- the cap threshold

def test_at_cap_is_a_threshold_and_not_an_equality():
    """**The bug this test exists for.** Every fan before session 150 pruned on ``speedF == 17.0``. The
    conversion that is the only way a herd reaches the cap lands speedF at **+17.6** (measured s148, and
    re-measured s150 at 17.183998 / 17.833548 on real rungs), so an equality would have thrown away the
    only states worth searching. What matters is the momentum the roll CARRIES."""
    from harness.tetrapush import entry_search as ES
    assert ON.at_cap(17.0)
    assert ON.at_cap(17.183998107910156), 'a measured conversion endpoint must count as at cap'
    assert ON.at_cap(17.833547592163086)
    assert not ON.at_cap(16.9)
    assert ES.roll_nspeed(16.9) < ES.ROLL_NSPEED
    assert 17.183998107910156 != ES.WALK_CAP, 'the equality prune would have refused this state'


def test_the_families_are_uniform_plus_the_l_switch_and_are_frame_exact():
    """Every family is one fleet, and every one of them delivers EXACTLY the walk it claims.

    ``len(lsched) == j + 1``: at ``input_delay = 1`` the endpoint a plan of j delivered frames rolls
    from is the state after j+1 steps, and the byte on that last step is inert."""
    for walk in (1, 2, 5):
        for n0 in range(walk):
            fams = ON._families(walk, n0, 32)
            j = walk - n0
            assert len(fams) == 2 + max(0, j - 1)
            assert {f['kind'] for f in fams} <= {'uniform', 'lswitch'}
            for f in fams:
                assert len(f['lsched']) == j + 1, (walk, n0, f['kind'])
                plan = f['label'](40, 50)
                assert ON.plan_frames(plan) == walk, (plan, walk)
            sw = [f for f in fams if f['kind'] == 'lswitch']
            assert all(f['lsched'][0] == 1 and f['lsched'][-1] == 0 for f in sw)


# --------------------------------------------------------------------------- the checkpoint layer

def test_a_claim_is_exclusive_and_a_manifest_is_what_resume_reads(tmp_path):
    d = str(tmp_path)
    assert IO.claim(d, 'rung05-w04', 'w00')
    assert not IO.claim(d, 'rung05-w04', 'w01'), 'two workers may not hold the same item'
    assert IO.claim(d, 'rung06-w04', 'w01')
    assert IO.completed(d) == set()
    IO.append(os.path.join(d, 'manifest.jsonl'), dict(item='rung05-w04', seconds=1.0))
    assert IO.completed(d) == {'rung05-w04'}
    assert set(IO.claims(d)) == {'rung05-w04', 'rung06-w04'}
    IO.beat(d, 'rung06-w04', 'w01', walk=4)
    assert IO.claims(d)['rung06-w04']['walk'] == 4


def test_the_incumbent_only_moves_down_and_round_trips(tmp_path):
    """Branch-and-bound crosses processes through this file, so a worse plan may never replace a better
    one and a reader may never see half of one."""
    d = str(tmp_path)
    assert IO.incumbent(d, 101) == (101, None)
    assert IO.offer(d, dict(total=98, unit='rung05', walk=4, thrust=13, resid=1e-5,
                            verdict=True, file='x.json', plan=[0]))
    assert IO.incumbent(d, 101)[0] == 98
    assert not IO.offer(d, dict(total=99, unit='rung06', walk=5, thrust=14, resid=1e-5,
                                verdict=True, file='y.json', plan=[0]))
    assert IO.incumbent(d, 101)[0] == 98
    assert IO.offer(d, dict(total=95, unit='rung04', walk=2, thrust=13, resid=1e-5,
                            verdict=True, file='z.json', plan=[0]))
    assert IO.incumbent(d, 101)[0] == 95


def test_a_torn_line_does_not_break_a_reader(tmp_path):
    """`status` reads files a worker is writing, so half a line is normal and must not raise."""
    p = os.path.join(str(tmp_path), 'progress.jsonl')
    IO.append(p, dict(unit='a', walk=1))
    with open(p, 'a') as fh:
        fh.write('{"unit": "b", "wal')
    rows = IO.read_jsonl(p)
    assert [r['unit'] for r in rows] == ['a']


def test_summarise_reports_coverage_and_never_hides_a_drop(tmp_path):
    d = str(tmp_path)
    IO.write_atomic(os.path.join(d, 'config.json'),
                    dict(run_id='t', t0=0.0, deadline=1e12, workers=2, incumbent0=101,
                         items=[dict(item='rung05-w03', unit='rung05', herd=73, floor=91)],
                         dropped=[dict(unit='rung49', floor=102, reason='cannot beat')]))
    IO.append(os.path.join(d, 'progress.jsonl'),
              dict(item='rung05-w03', walk=3, candidates=558, evaluations=75330, genuine=0, near=4))
    IO.append(os.path.join(d, 'manifest.jsonl'),
              dict(item='rung05-w03', seconds=120.0, dropped=False))
    s = IO.summarise(d)
    assert s['n_units'] == 1 and s['n_done'] == 1 and s['n_left'] == 0
    assert s['totals']['candidates'] == 558 and s['totals']['evaluations'] == 75330
    assert len(s['config']['dropped']) == 1
    assert s['per_unit'] == 120.0


@pytest.mark.parametrize('walk', [1, 4])
def test_the_pre_segment_is_only_ever_a_cone_clear_length(walk):
    """`PRE_FRAMES` is a knob, but a pre segment longer than the walk is not a plan."""
    assert all(p >= 1 for p in ON.PRE_FRAMES)
    assert ON.PRE_L == (0,), 'an L on the pre frame acquires the actor -- that is what it must avoid'
    keep, _d = ON.units()
    assert all(ON.max_walk(u['herd'], 13, O.TOTAL_INCUMBENT) >= walk or walk > 1 for u in keep[:1])
