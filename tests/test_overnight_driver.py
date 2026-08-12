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

Fast by construction (`tests/conftest.py` enforces a 1.5 s per-test budget and a 120 s whole-selection
one): the only stepping here is the POSITIVE CONTROL's own herd replay and the camera trail beside it,
both module-scoped and paid once. The simulating end-to-end check is the driver's own
``verify-console`` command, which is a research run and not a gate.
"""
import json
import os

import pytest

from harness.tetrapush import entry_fan as EF
from harness.tetrapush import objective as O
from harness.tetrapush import overnight as ON
from harness.tetrapush import overnight_io as IO
from harness.tetrapush import seeds as SD

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


def test_the_fan_enumeration_contains_the_console_plan():
    """**THE SEARCH MUST BE ABLE TO GENERATE ITS OWN KNOWN ANSWER** (`[[search-must-rediscover-known-
    answer]]`) -- at the knobs the driver runs at, which is the whole point of the check.

    `test_the_walk_letters_are_in_the_fans_own_alphabet` above checks ``stick_alphabet(1)``, which is a
    FINER alphabet than `overnight.fan_exact` drew the PRE segment from at the s155-s159 knobs -- so
    twelve green containment checks coexisted with a fan that missed the console's own walk endpoint by
    0.213 u against a razor strip 1.9e-04 u wide (`_notes/s160_contain.py`). Session 161 paid the knobs
    (`LEGACY_PRE_STRIDE` / `LEGACY_PRE_FRAMES` are what they were), so this is now an equality and not
    an xfail -- and `tests/test_aimed_fan.py` carries the stronger form, the fan's own LEAF SET holding
    the endpoint bit-exactly."""
    k = ON.containment_knobs()
    assert k['split_ok'] is True, 'split %s not in PRE_FRAMES %s' % (k['splits'], ON.PRE_FRAMES)
    assert k['pre_ok'] is True and k['hold_ok'] is True


def test_the_legacy_knobs_are_still_the_ones_that_excluded_it():
    """The s160 DIAGNOSIS, kept as a measurement rather than a memory: the knobs the search ran at for
    five sessions exclude the console's plan on both axes, and the split is the half no alphabet can
    fix. This is what says the fix was the knobs and not a coincidence."""
    k = ON.containment_knobs(pre_stride=ON.LEGACY_PRE_STRIDE, pre_frames=ON.LEGACY_PRE_FRAMES)
    assert k['split_ok'] is False and k['pre_ok'] is False
    assert k['hold_ok'] is True, 'the HOLD letter was always in range -- only the pre and the split'
    assert k['pre_classes'] == 57


def test_pre_frames_all_is_every_split_a_walk_admits():
    """``PRE_FRAMES_ALL`` cannot be a tuple, because the set depends on the walk: a 4-frame plan can
    split 1+3, 2+2 or 3+1, and the console's is the middle one."""
    assert ON.pre_frames_for(4, ON.PRE_FRAMES_ALL) == (1, 2, 3)
    assert ON.pre_frames_for(1, ON.PRE_FRAMES_ALL) == ()
    assert ON.pre_frames_for(4, (1,)) == (1,)


def test_the_hold_alphabet_may_not_be_traded_for_the_leaf_budget():
    """**THE TRAP IN "JUST RAISE THE PRE RESOLUTION".** `fan_exact` sizes the hold alphabet to
    `LEAF_BUDGET`, so a 59x bigger pre makes the autoscaler coarsen the HOLD -- and the console's hold
    letter exists at stride 1 and nowhere else, so containment breaks the other way. Pinned, the item
    reports ``over_budget`` instead."""
    fleets = ON._fleet_estimate(4, True, ON.CONTAINED_PRE_STRIDE, (1, 2, 3), ON.PRE_L, atom=False)
    auto, over_auto = ON.alpha_for(fleets, ON.LEAF_BUDGET)
    pinned, over_pin = ON.alpha_for(fleets, ON.LEAF_BUDGET, ON.CONTAINED_ALPHA_STRIDE)
    assert auto > ON.CONTAINED_ALPHA_STRIDE and over_auto is False, 'the autoscaler coarsens the hold'
    assert pinned == ON.CONTAINED_ALPHA_STRIDE and over_pin is True, 'pinned, and it says so'
    k = ON.containment_knobs(contained=True, alpha_stride=auto)
    assert k['hold_ok'] is False, 'a coarsened hold loses the console letter -- that is the trade'


@pytest.fixture(scope='module')
def console_stepped():
    """The console's own two letters stepped through `overnight._fan` -- the fan's OWN primitive, the same
    base core, the same camera trail -- as the 2 + 2 split the fixture records."""
    from harness.tetrapush import entry_fan as EF
    env = SD.load_env()
    cc = ON.console_candidate()
    prep, hold, trail = ON.prepared(cc['unit'], env, O.courtyard_walls(), cc['walk'])
    plan = ON.from_triples(cc['plan'])
    csa = ON.aim_camera(plan, cc['walk'], trail)
    n0 = int(plan[0])
    segs = [(int(plan[i]), int(plan[i + 1]), int(plan[i + 2]), int(plan[i + 3]))
            for i in range(1, len(plan), 4)]
    base, _run = EF.base_core(n0, seed=prep['seed'], env=env, hold=hold)
    (sx1, sy1, l1, j1), (sx2, sy2, l2, j2) = segs
    jcs = ON._fan(base, [(sx1, sy1)], [l1] * j1, csa, trail, n0, 0)
    cores = ON._fan(jcs[0][1], [(sx2, sy2)], [l2] * (j2 + 1), csa, trail, n0 + j1, 0)
    return cc, prep, cores[0][1]


def test_the_fan_primitive_reaches_the_console_endpoint_bit_for_bit(console_stepped):
    """**THE MACHINERY REACHES IT; ONLY THE ENUMERATION DOES NOT.** This is what makes the xfail above a
    coverage gap rather than a modelling one: hand `_fan` the console's own letters at its own split and
    the walk endpoint comes back BIT-IDENTICAL to the locked fixture's ``hit['walk']``, at the cap, with
    the fixture's own roll lean -- and its roll entry is the delivered entry, 0-ULP
    (`[[zero-ulp-tests-only]]`)."""
    from harness.tetrapush import entry_aim as EA
    from harness.tetrapush import entry_fan as EF
    from harness.tetrapush import entry_search as ES
    cc, prep, c = console_stepped
    want = CC['walk']
    assert (ON._bits(c.pos_x), ON._bits(c.pos_z)) == (ON._bits(want[0]), ON._bits(want[1]))
    assert ON.at_cap(c.speedF) is True and EF._is_rollable(c) is True
    assert ES.lean_at_roll(int(c.m351C) & 0xFFFF) == cc['m351C']
    e = ES.roll_entry((c.pos_x, c.pos_z), cc['facing'], ES.ROLL_NSPEED)
    assert (ON._bits(e[0]), ON._bits(e[1])) == (ON._bits(cc['entry'][0]), ON._bits(cc['entry'][1]))
    p = EA.price(cc['facing'], cc['m351C'], cc['thrust'], e, tuple(prep['seed']['tetra']))
    assert p['genuine'] is True and p['offset_u'] == 0.0


def test_the_containment_gap_is_exactly_two_knobs_and_its_price_is_measured():
    """The DIAGNOSIS, pinned: which knobs excluded the console's plan, the stride each letter needs, and
    what containment costs in fleets. Facts, so they are asserted exactly -- if a knob moves, this test
    is what says the diagnosis above went stale.

    Asked at the LEGACY knobs, because that is what the diagnosis is about; s161 pays them, and the
    price it pays is the ``fleets_default -> fleets_contained`` ratio below."""
    k = ON.containment_knobs(pre_stride=ON.LEGACY_PRE_STRIDE, pre_frames=ON.LEGACY_PRE_FRAMES)
    assert k['splits'] == [(208, 110, 2), (169, 192, 2)] and k['n0'] == 0
    assert k['pre_stride_needed'] == 2, 'the pre letter exists at stride 1 and 2 and nowhere coarser'
    assert k['hold_stride_needed'] == 1, 'the HOLD letter needs stride 1 -- so the leaf budget cannot ' \
                                         'absorb a bigger pre by coarsening it'
    assert k['pre_classes'] == 57
    assert tuple(k['pre_frames_needed']) == (1, 2)
    assert (k['fleets_default'], k['fleets_contained']) == (353, 33563)
    assert 90.0 < k['factor'] < 100.0
    # and the SHIPPED set, whose price is bigger still because it enumerates EVERY split, not just the
    # console's own -- the number the README quotes and the aimed fan has to pay off
    assert k['fleets_shipped'] == 40274


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


def test_the_families_are_uniform_and_are_frame_exact():
    """Every family is one fleet, and every one of them delivers EXACTLY the walk it claims.

    ``_families`` is uniform-only since session 151: the L-conversion recipe (`away_walk.escape_atom`'s
    L-press, release, rotate, backwards slam) needs a DIFFERENT stick per frame, derived per candidate,
    which no member of this dict-of-fleets shape can express -- see `_atom_junction` +
    `test_the_atom_junction_agrees_with_escape_atom_bit_for_bit` below, and the module docstring's
    headline for why the old ``lswitch`` shape (L-press + release, nothing after) was replaced rather
    than kept beside it.

    ``len(lsched) == j + 1``: at ``input_delay = 1`` the endpoint a plan of j delivered frames rolls
    from is the state after j+1 steps, and the byte on that last step is inert."""
    for walk in (1, 2, 5):
        for n0 in range(walk):
            fams = ON._families(walk, n0, 32)
            j = walk - n0
            assert len(fams) == 2
            assert {f['kind'] for f in fams} == {'uniform'}
            for f in fams:
                assert len(f['lsched']) == j + 1, (walk, n0, f['kind'])
                plan = f['label'](40, 50)
                assert ON.plan_frames(plan) == walk, (plan, walk)


# --------------------------------------------------------------------------- the atom conversion

@pytest.fixture(scope='module')
def atom_seed():
    """A real mid-herd backslide, off the locked console fixture's own frames -- the state the
    escape-atom conversion exists for (session 151). Truncated to 71 of the console's 78 herd frames,
    ONE FRAME BEFORE the console's own recorded play begins ITS version of this same recipe (frames
    71-77 of its herd; see `_notes/tetrapush-handoff-2026-08-11-session151.md`), so nothing here
    borrows the answer -- it is a genuine backslide the conversion has never seen."""
    env = SD.load_env()
    seed = dict(log=[dict(r) for r in FIX['log'][:71]])
    hold = ON.hold_row(seed)
    core, run = EF.base_core(0, seed=seed, env=env, hold=hold)
    return dict(env=env, seed=seed, hold=hold, core=core, run=run, cs0=int(run.csangle))


def test_the_atom_seed_is_a_genuine_backslide(atom_seed):
    """The premise both tests below rely on: if the seed were already at cap, converting it would
    prove nothing about the recipe."""
    assert not ON.at_cap(atom_seed['core'].speedF)
    assert atom_seed['core'].speedF < 0.0, 'the untarget backslide this recipe converts is negative'


def test_the_atom_junction_agrees_with_escape_atom_bit_for_bit(atom_seed):
    """`_atom_junction`'s rotate/slam formula IS `away_walk.escape_atom`'s (its module docstring, steps
    2-4), computed per candidate instead of off one shared flip -- so for a MATCHED knob set (same flip
    bearing, same frozen camera) the two must produce IDENTICAL stick bytes on all four frames.

    This is the gate session 151's own design correction needed: the first version compared against a
    stick-BYTE alphabet (any candidate draw, whatever its magnitude) and disagreed on every one of
    them, because `escape_atom` always drives the L-press at FULL deflection and a byte draw is not
    guaranteed to be. Swapping the flip axis for `away_walk.flip_arc`'s own bearings -- full deflection
    by construction, `stick_for_bearing(..., msd=1.0)` -- is what makes the two agree, and this pins
    that agreement so it cannot silently regress."""
    from harness.tetrapush import away_walk as AW
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(atom_seed['env'])
    core, run, cs0 = atom_seed['core'], atom_seed['run'], atom_seed['cs0']
    flips = AW.flip_arc(hl, step=ON.ATOM_FLIP_STEP)[:3]
    for flip in flips:
        for side in ON.ATOM_ROTATE_SIDES:
            for ro in ON.ATOM_ROTATE_OFFS:
                junc = ON._atom_junction(core, [flip], side, ro, cs0, None, 0, 0)
                assert len(junc) == 1, (flip, side, ro)
                r = junc[0]
                atom = AW.escape_atom(run, hl, turnaround_first=False, rotate_side=side,
                                      rotate_off=ro, flip_bearing=flip, exit_bearing=0, csangle=cs0,
                                      max_frames=4, exit_run=0)
                assert len(atom['log']) >= 4, (flip, side, ro)
                l_press = (atom['log'][0]['stickX'], atom['log'][0]['stickY'])
                release = (atom['log'][1]['stickX'], atom['log'][1]['stickY'])
                assert r['flip'] == l_press == release, (flip, side, ro, r['flip'], l_press, release)
                assert r['rot'] == (atom['log'][2]['stickX'], atom['log'][2]['stickY']), (flip, side, ro)
                assert r['slam'] == (atom['log'][3]['stickX'], atom['log'][3]['stickY']), (flip, side, ro)


def test_the_atom_conversion_reaches_at_cap_from_the_consoles_own_backslide(atom_seed):
    """**THE SEARCH SPACE MUST CONTAIN THE SHAPE OF SEQUENCE THAT PRODUCED THE 101**
    (`[[search-space-contains-human]]`; Dereck's own framing of this session's task).

    Session 150 found -- confirmed against the live sim in `_notes/s151_verify_atom_matches_console.py`,
    not just the stick-decode coincidence -- that the console's real 78-frame herd converts its
    untarget backslide to the walk cap using EXACTLY this recipe, at its own frames 71-77 (L-press,
    release, rotate, backwards slam, then a held exit stick). `_families`' old ``lswitch`` shape
    (L-press then release, nothing after) structurally could not express the rotate or the slam, so no
    pass built on it could ever have found this shape, on ANY herd.

    This seeds the state one frame before the console's own conversion begins and asserts
    `_atom_junction` -- the generator `fan_exact` now calls in its place -- converts it too: at least
    one knob combination lands a rollable, at-the-cap state. Off a REAL backslide the search could not
    convert at all before this session, not a synthetic or cherry-picked one."""
    from harness.tetrapush import away_walk as AW
    from harness.tetrapush.reposition import HerdLine
    hl = HerdLine.from_env(atom_seed['env'])
    core, cs0 = atom_seed['core'], atom_seed['cs0']
    flips = AW.flip_arc(hl, step=ON.ATOM_FLIP_STEP)
    hits = []
    for flip in flips:
        for side in ON.ATOM_ROTATE_SIDES:
            for ro in ON.ATOM_ROTATE_OFFS:
                for r in ON._atom_junction(core, [flip], side, ro, cs0, None, 0, 0):
                    c = r['core']
                    if EF._is_rollable(c) and ON.at_cap(c.speedF):
                        hits.append(dict(bearing=flip, side=side, ro=ro, **r))
    assert hits, ('no (flip, rotate_side, rotate_off) combination converts the consoles own recorded '
                 'backslide to a rollable at-cap state -- the search space does not contain it')


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
    """`PRE_FRAMES` is a knob, but a pre segment longer than the walk is not a plan -- and since s161 it
    is the `PRE_FRAMES_ALL` sentinel, so the length rule lives in `pre_frames_for` and is checked there
    rather than on a tuple that no longer exists."""
    assert all(1 <= p < walk for p in ON.pre_frames_for(walk, ON.PRE_FRAMES))
    assert ON.PRE_L == (0,), 'an L on the pre frame acquires the actor -- that is what it must avoid'
    assert ON.ATOM_FRAMES == 4, 'L-press, release, rotate, slam are the recipe -- never a budget knob'
    keep, _d = ON.units()
    assert all(ON.max_walk(u['herd'], 13, O.TOTAL_INCUMBENT) >= walk or walk > 1 for u in keep[:1])


# --------------------------------------------------------------------------- the positive control

def _console_candidate_for_score(prep):
    """The console clip as ONE candidate + its one configuration, the shape `overnight.score` takes."""
    from harness.tetrapush import entry_search as ES
    key = (CC['walk'][0], CC['walk'][1], CC['m351C_walk'], 17.0,
           prep['seed']['tetra'][0], prep['seed']['tetra'][1])
    quals = [dict(facing=CC['facing'], aim=list(CC['aim']), thrust=CC['thrust'],
                  cell=ES.aim_cell(CC['facing']), siblings=0)]
    return {key: ON.from_triples(CC['plan'])}, quals


@pytest.fixture(scope='module')
def console_scored():
    """The console's own clip through `overnight.score` -- the search's OWN scoring path.

    THE GATE THIS FILE WAS MISSING, and a 1.14e9-scoring run went out without it. The console's thrust 15
    is bound-excluded from the search (at walk 4 it totals 101, which cannot beat 101), so the run never
    scored a single configuration known to be genuine -- and a systematic defect in `score` would have
    looked exactly like the 0 genuine it reported. A search with no positive control cannot tell "the
    space is empty here" from "my scorer is broken"."""
    from harness.tetrapush import seeds as SD
    env = SD.load_env()
    prep = ON.prepare(ON.console_herd(), env)
    cands, quals = _console_candidate_for_score(prep)
    hits, st = ON.score(cands, quals)
    return hits, st, prep


def test_the_search_scoring_path_calls_the_known_clip_genuine(console_scored):
    """The positive control, and it is an equality on the razor's own coordinate, not a tolerance."""
    hits, st, _prep = console_scored
    assert st['genuine'] == 1, 'the search scores the delivered console clip as NOT genuine'
    assert hits[0]['resid'] == CC['resid'], (
        'resid %r, the delivery %r' % (hits[0]['resid'], CC['resid']))
    assert hits[0]['push'] == CC['push']


def test_a_scored_row_carries_the_acceptances_own_three_terms(console_scored):
    """**A ROW MUST SAY WHY IT IS NOT GENUINE.** `_shovec`'s acceptance is
    ``(not blocked) and in_front(old) and crossed(new)`` and it reports only the AND, so ``genuine = 0``
    beside a ``|resid|`` of 2e-5 reads as a mystery -- and answering it used to mean re-running the item.

    Session 155 measured what it hides: every near-razor row across walks 7-9 of the re-run sweep is
    refused at the FIRST test, the swept lunge path hitting the wall
    (`_notes/s155_why_not_genuine.py`, 24/24), which ``resid`` structurally cannot see -- it is the cut
    RAY's offset from the seam vertex, and a ray can aim through a wall. So every row `score` singles out
    now carries ``pred`` (the seam-plane values) and ``why``.

    This is the positive control for that diagnostic: on the ONE clip known to be genuine, all three
    terms must read clear and both plane values must be negative. A diagnostic that called the delivered
    clip blocked would be worse than none."""
    hits, _st, _prep = console_scored
    w = hits[0]['why']
    assert w == dict(blocked=False, line_hit=False, wall_hit=False, in_front=True, crossed=True), w
    assert hits[0]['pred'][0] < 0.0 and hits[0]['pred'][1] < 0.0, (
        'the delivered clip crossed BOTH seam planes; pred %r' % (hits[0]['pred'],))


def test_the_lean_and_the_entry_the_search_predicts_are_the_delivered_ones(console_scored):
    """Two links in the chain that turn a walk endpoint into a razor sample, checked against console."""
    from harness.tetrapush import entry_search as ES
    assert ES.lean_at_roll(CC['m351C_walk']) == CC['m351C']
    ent = ES.roll_entry(tuple(CC['walk']), CC['facing'], ES.ROLL_NSPEED)
    assert [ent[0], ent[1]] == CC['entry']


def test_the_clip_band_is_where_the_delivered_clip_actually_sits(console_scored):
    """`CLIP_BAND` is a measurement, so it must contain the one clip that exists.

    And `best_overlap` must mean NEAREST the band, never the maximum: a run that reports max overlap as
    progress reports +63 u -- Link buried 62 u past the grazing touch the clip needs -- as its best."""
    hits, st, _prep = console_scored
    assert ON.CLIP_BAND[0] <= hits[0]['overlap'] <= ON.CLIP_BAND[1]
    assert abs(ON.CLIP_TARGET - hits[0]['overlap']) < 1e-3
    assert st['band_draws'] == 1 and st['band_share'] == 1.0


# ------------------------------------------------------------------- the plan's own aim camera

class _StubTrail:
    """A `entry_camera.CamTrail` stand-in whose value ENCODES which corrections it carries, so the
    lookup can be gated without replaying a camera: ``[i]`` is ``1000 * (1 + len(l_frames)) + i``."""

    def __init__(self, l_frames=()):
        self.l_frames = tuple(int(x) for x in l_frames)

    def __getitem__(self, i):
        return 1000 * (1 + len(self.l_frames)) + int(i)

    def from_l(self, lf):
        return _StubTrail(self.l_frames + (int(lf),))


def test_l_press_frames_reads_every_rising_edge_of_the_real_plan_shapes():
    """The blip's edges, off the shapes `fan_exact` actually enumerates.

    `hold_row` releases L on the base frames deliberately, so a plan's first L segment is always a
    rising edge; a segment holding it for j frames is ONE edge, and the atom's release-then-continue
    shape can raise a SECOND (`_atom_candidates`' own reason for composing its trail)."""
    assert ON.l_press_frames((0, 208, 110, 0, 4)) == ()                    # uniform, L up
    assert ON.l_press_frames((3, 208, 110, 1, 4)) == (3,)                  # uniform, L held from n0
    atom = (2, 176, 247, 1, 1, 176, 247, 0, 1, 195, 14, 0, 1, 77, 3, 0, 1, 241, 59, 0, 5)
    assert ON.l_press_frames(atom) == (2,)                                 # the conversion's own press
    cont = atom[:-4] + (241, 59, 1, 5)                                     # ... + an L_AXIS l=1 tail
    assert ON.l_press_frames(cont) == (2, 2 + ON.ATOM_FRAMES), (
        'the continuation re-presses L after the junction released it -- a second, independent edge')


def test_the_aim_camera_reads_the_aim_frame_index_through_the_plans_own_blips():
    """Two failure modes in one lookup, both gated here without a camera replay.

    The INDEX is `entry_camera.aim_frame`'s ``walk + 1`` -- the A-press is delivered on index ``walk``
    and the target is computed when it is ACTED, one frame later (measured s95, re-measured s154 at
    walk 2..5 off the herd-71 seed where the chase is still climbing: 18/18 unanimous). And the
    CORRECTIONS are the plan's own L edges, composed in order."""
    from harness.tetrapush import entry_camera as EC
    walk = 11
    assert EC.aim_frame(walk) == walk + 1
    assert ON.aim_camera((0, 208, 110, 0, 11), walk, _StubTrail()) == 1000 + walk + 1
    assert ON.aim_camera((3, 208, 110, 1, 8), walk, _StubTrail()) == 2000 + walk + 1
    atom = (2, 176, 247, 1, 1, 176, 247, 0, 1, 195, 14, 0, 1, 77, 3, 0, 1, 241, 59, 1, 5)
    assert ON.aim_camera(atom, walk, _StubTrail()) == 3000 + walk + 1, (
        'a plan pressing L twice must read the second blip through the first one own settle')
    # a plain sequence cannot correct a blip, and must say so rather than return the wrong camera
    with pytest.raises(TypeError):
        ON.aim_camera(atom, walk, tuple(range(20)))
    assert ON.aim_camera((0, 208, 110, 0, 11), walk, tuple(range(20))) == walk + 1


def test_plan_from_rows_round_trips_the_console_conversion():
    """`plan_from_rows` is `plan_rows` inverted, and the round trip IS the containment question:
    the console's own conversion off ``log[:71]`` must be expressible in this driver's encoding.

    Its SHAPE is the finding (session 154): four atom frames -- L+flip, flip, rotate, slam -- and then
    a THREE-segment continuation, where `_families` offers exactly one held stick. So the human's own
    11-frame answer at walk 11 is not a member of the enumerated set, whatever the camera does."""
    herd = 71
    rows = [dict(r) for r in FIX['log'][herd:FIX['plan']['a_i']]]
    plan = ON.plan_from_rows(rows)
    hold = dict(rows[0], stickX=FIX['log'][herd - 1]['stickX'], stickY=FIX['log'][herd - 1]['stickY'],
                buttons=0, triggerL=0)
    assert ON.plan_rows(hold, plan) == rows
    assert ON.plan_frames(plan) == FIX['plan']['a_i'] - herd
    segs = [tuple(plan[i:i + 4]) for i in range(1, len(plan), 4)]
    assert [s[3] for s in segs[:ON.ATOM_FRAMES]] == [1] * ON.ATOM_FRAMES
    assert segs[0][2] == 1 and segs[1][2] == 0 and segs[0][:2] == segs[1][:2]
    assert len(segs) - ON.ATOM_FRAMES == 3, (
        'the human continuation is 3 held sticks; `_families` enumerates 1, so this plan is outside '
        'the fan own reach and a 0-genuine sweep off this herd says nothing about the herd')


# ------------------------------------------------------- steering after the ATOM conversion (s155)

def test_the_prefix_trail_carries_the_blips_the_prefix_itself_delivered():
    """`_trail_for`: a prefix's continuation reads the camera its OWN L presses left behind.

    `_fan` corrects for the edges inside its own schedule and nothing corrected for an edge a PREVIOUS
    segment delivered -- which is every steered frame after an atom junction (its first act is an
    L-press) and every one after a `_families` L_AXIS hold. Same class of defect as the aim camera
    s154 fixed: a per-item constant standing in for a per-candidate truth."""
    plain = (0, 208, 110, 0, 4)
    atom = (2, 176, 247, 1, 1, 176, 247, 0, 1, 195, 14, 0, 1, 77, 3, 0, 1)
    assert ON._trail_for(None, atom) is None
    assert ON._trail_for(_StubTrail(), plain)[7] == 1000 + 7, 'an L-free prefix must not be corrected'
    assert ON._trail_for(_StubTrail(), atom)[7] == 2000 + 7, 'the atom press is one edge'
    assert ON._trail_for(_StubTrail(), atom + (241, 59, 1, 3))[9] == 3000 + 9, (
        'a continuation re-pressing L after the junction released it is a second edge')
    assert ON._trail_for(_StubTrail(), (3, 208, 110, 1, 4))[8] == 2000 + 8, (
        'an L_AXIS uniform hold presses L too -- it was reading the L-free trail as well')


def test_the_steered_tail_steers_off_the_atom_conversion_and_not_only_a_uniform_walk(atom_seed):
    """**THE AXIS THE HEADLINE ALWAYS CLAIMED.** `_steered_tail` built its prefixes from `_families`/PRE
    only, so "per-frame steering after the conversion" could steer only after a UNIFORM walk -- and the
    conversion a real backslide reaches the cap through is `_atom_junction`'s (L-press, release, rotate,
    backwards slam). Handed ``flips``, the prefixes are atom junctions too.

    Deliberately tiny (2 flip bearings, a 15-draw alphabet, a 16-prefix cap): this gates the SHAPE and
    the plumbing, not a search result. Both branches must fire -- ``remaining == 1`` at ``n0 = 0`` (a
    uniform continuation between the slam and the steering) and ``remaining == 0`` at ``n0 = 1`` (steering
    straight off the slam) -- and every plan must deliver exactly the walk it claims."""
    from harness.tetrapush import away_walk as AW
    from harness.tetrapush.reposition import HerdLine
    env, seed, hold, cs0 = atom_seed['env'], atom_seed['seed'], atom_seed['hold'], atom_seed['cs0']
    flips = AW.flip_arc(HerdLine.from_env(env), step=ON.ATOM_FLIP_STEP)[:2]
    alpha = EF.stick_alphabet(64)
    walk, k = 6, 1

    def tail(use_flips):
        out, st = {}, dict(raw=0, sub_cap=0, fleets=0)
        ON._steered_tail(out, st, seed, env, walk, cs0, None, hold, alpha, EF.CHUNK, 0, 32,
                         ON.PRE_STRIDE, (), ON.PRE_L, (k,), 400, None, flips=use_flips,
                         prefix_cap=16)
        return out, st

    out, st = tail(flips)
    assert st['tail_atom_prefixes'] > 0 and st['tail_prefixes'] > 0
    assert out, 'the atom-prefixed tail produced no at-cap rollable candidate at all'
    shapes = set()
    for plan in out.values():
        segs = [tuple(plan[i:i + 4]) for i in range(1, len(plan), 4)]
        assert ON.plan_frames(plan) == walk, (plan, ON.plan_frames(plan))
        assert ON.l_press_frames(plan) == (plan[0],), (
            'every one of these converts through the atom, whose first act is the L-press')
        assert [s[2] for s in segs[:ON.ATOM_FRAMES]] == [1, 0, 0, 0], plan
        assert segs[0][:2] == segs[1][:2], 'the press and the release hold the same full-deflection stick'
        assert [s[3] for s in segs[-k:]] == [1] * k, 'the steered frames are one delivered byte each'
        shapes.add(len(segs))
    assert shapes == {ON.ATOM_FRAMES + k, ON.ATOM_FRAMES + 1 + k}, (
        'both prefix depths must fire -- a uniform continuation after the slam AND steering straight '
        'off it; got segment counts %s' % sorted(shapes))

    bare, st0 = tail(())
    assert st0['tail_atom_prefixes'] == 0 and not bare, (
        'without flips the same call reaches nothing at the cap -- which is the gap: off a real '
        'backslide the uniform families do not convert, so the tail axis had nothing to steer from')


def test_the_steered_tail_shape_contains_the_console_conversion():
    """**CONTAINMENT, and no simulation in it.** The console's own 11 delivered frames are the atom
    recipe EXACTLY plus a THREE-segment continuation, so they are not a member of the `_families` set at
    any camera (`test_plan_from_rows_round_trips_the_console_conversion`). The shape that DOES contain
    them is this axis: an atom junction, a uniform continuation, then ``tail_frames=(4,)`` steering the
    last four frames -- prefix = atom + 3x(241,59), steered = 208,110 / 208,110 / 169,192 / 169,192.

    Built from the console's OWN rows and checked back against them row for row, so it is the recorded
    input that is shown to be expressible, not a plausible-looking tuple. The steered frames are drawn
    from the item's own ``alpha``, so containment is exact at stride 1 and a COARSENED stride quantises
    these bytes onto a neighbouring class -- that is the discretisation each item logs as ``alpha_stride``,
    not a property of this shape.

    The axis also FILTERS its pool on `overnight.at_cap` at ``walk - k``, so the shape containing the plan
    is not the same claim as the filter admitting it. Measured on the wired engine
    (`_notes/s155_atcap_through_the_console_conversion.py`): the console's own conversion DIPS below the
    cap on its slam and the two frames after it (nspeed 13 / 15 / 18 at delivered frames 3-5) and holds
    17.0 / nspeed 26 from frame 6 on -- so the prefix frame is at the cap for every ``k <= 5``, the dip
    sits inside the prefix where nothing filters it, and k=4 is admitted."""
    herd, k = 71, 4
    rows = [dict(r) for r in FIX['log'][herd:FIX['plan']['a_i']]]
    hold = dict(rows[0], stickX=FIX['log'][herd - 1]['stickX'], stickY=FIX['log'][herd - 1]['stickY'],
                buttons=0, triggerL=0)
    plan = ON.plan_from_rows(rows)
    segs = [tuple(plan[i:i + 4]) for i in range(1, len(plan), 4)]
    w0 = len(rows) - k
    # the axis's own template at this walk: the atom's four frames, ONE held continuation to w0, then k
    # single steered frames -- each field taken from the recording, none of them authored
    cont = w0 - ON.ATOM_FRAMES
    assert cont >= 1 and segs[ON.ATOM_FRAMES][3] >= cont, (
        'the recorded continuation is shorter than the prefix this k needs')
    template = (0,) + tuple(x for s in segs[:ON.ATOM_FRAMES] for x in s) \
        + (segs[ON.ATOM_FRAMES][0], segs[ON.ATOM_FRAMES][1], 0, cont) \
        + tuple(x for r in rows[w0:] for x in (int(r['stickX']), int(r['stickY']), 0, 1))
    assert ON.plan_frames(template) == len(rows) == FIX['plan']['a_i'] - herd
    assert ON.plan_rows(hold, template) == rows, (
        'the axis shape does not deliver the console conversion row for row')
    tsegs = [tuple(template[i:i + 4]) for i in range(1, len(template), 4)]
    assert len(tsegs) == ON.ATOM_FRAMES + 1 + k
    assert [s[3] for s in tsegs] == [1] * ON.ATOM_FRAMES + [cont] + [1] * k
    assert ON.l_press_frames(template) == (0,)
    assert len({(s[0], s[1]) for s in tsegs[ON.ATOM_FRAMES + 1:]}) > 1, (
        'the point of the steering is that the last frames are NOT one held stick')


def test_the_scoring_path_prices_the_console_clip_at_its_own_aim_camera(console_scored):
    """The positive control again, through the ``cam`` path this time: the recorded (facing, aim) pair
    must be resolved at the plan's OWN camera and must still be the console's own, bit for bit.

    A cell is one razor draw at any camera, so switching the pair may not move the razor: same resid,
    same push, same overlap as the single-configuration control above."""
    from harness.tetrapush import entry_camera as EC
    from harness.tetrapush import entry_search as ES
    from harness.tetrapush import seeds as SD
    hits0, _st0, prep = console_scored
    env = SD.load_env()
    hold = ON.hold_row(prep['seed'])
    trail = EC.CamTrail(int(hold.get('substickX', 128)), CC['frames'] + ON.TRAIL_PAD,
                        prep['seed'], env)
    cands, quals = _console_candidate_for_score(prep)
    hits, st = ON.score(cands, quals, cam=lambda p: ON.aim_camera(p, CC['frames'], trail))
    assert st['cameras'] == 1 and st['unaimable'] == 0
    got = [h for h in hits if h['cell'] == ES.aim_cell(CC['facing'])]
    assert len(got) == 1, 'the console own cell is not genuine on the per-camera path'
    assert got[0]['facing'] == CC['facing'] and got[0]['aim'] == list(CC['aim'])
    assert got[0]['csangle'] == EC.aim_camera(trail, CC['frames'])
    assert (got[0]['resid'], got[0]['push'], got[0]['overlap']) == (
        hits0[0]['resid'], hits0[0]['push'], hits0[0]['overlap'])
