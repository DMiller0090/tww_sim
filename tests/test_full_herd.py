"""Gates for `harness/tetrapush/full_herd.py` -- the N-cycle chain to the genuine-coord cluster (s43).

Three properties, in the order the search depends on them:

  1. **CLONE INDEPENDENCE** (the s43 harness bug): a `FreeRun` branch must not leak state into its
     parent or its siblings. `LandState` shared its `AttentionLock` -- the machine that routes a
     roll exit to proc 9 vs 6 -- across every clone, so search branches silently corrupted each
     other. Every beam in this harness rests on this, so it is gated first and at the bottom layer.
  2. **SEPARABILITY**: inside a roll, `target_cs` moves only the camera (the C-stick counterpart of
     s41's main-stick inertness). This is what lets a cycle factor into an aim sweep and a much
     cheaper camera sweep.
  3. **CONTAINMENT** (`[[search-space-contains-human]]`): the derived pursuit box must contain the
     recorded human on every frame, and the junction beam must be able to express a real reposition
     (which `two_roll`'s single-swing-stick family provably cannot).
"""
import pytest

from harness.tetrapush import seeds, two_roll as T, full_herd as F
from harness.tetrapush.reposition import HerdLine


@pytest.fixture(scope='module')
def env():
    return seeds.load_env()


@pytest.fixture(scope='module')
def hl(env):
    return HerdLine.from_env(env)


@pytest.fixture(scope='module')
def box(env, hl):
    return F.pursuit_box(env, hl)


def _fingerprint(r):
    return (r.link.pos_x, r.link.pos_z, r.link.facing, r.link.speedF, r.link.state,
            r.tx, r.tz, int(r.csangle))


def test_clone_is_independent_of_sibling_branches(env):
    """THE s43 harness bug, pinned 0-ULP: replaying one input sequence from a clone must give the
    bit-identical result no matter how many unrelated branches ran from the same parent in between.

    Before the fix `LandState.clone` shared the mutable `AttentionLock` (and the `visited` set), so
    a sibling's lock-on state machine wrote through to the parent -- and since that machine decides
    whether a roll exits into proc 9 or proc 6, branches diverged by whole procs (facing 16138 vs
    34819 on the very case below), silently and permanently."""
    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    for k in range(1, 21):
        base.step(dtm(k))
    phases = T._fit_phases([dtm(k) for k in range(21, 28)])

    def run(ph):
        r = base.clone()
        T.run_junction(r, ph)
        return _fingerprint(r)

    first = run(phases)
    assert run(phases) == first                       # back-to-back
    for _ in range(25):                               # 25 unrelated sibling branches
        run([(3, (145, 146), 0), (2, (145, 146), 1)])
    assert run(phases) == first, "a sibling branch leaked state into the parent"

    fresh = seeds.make_freerun(env)                   # and it matches a never-branched run
    fresh.pre_seed_input(dtm(0))
    for k in range(1, 21):
        fresh.step(dtm(k))
    r = fresh.clone()
    T.run_junction(r, phases)
    assert _fingerprint(r) == first


def test_attention_lock_clone_is_a_real_copy():
    """The bottom layer of the same bug: mutating a cloned lock must not touch the original."""
    from tww_sim.land.attention import AttentionLock
    a = AttentionLock()
    a.update(True, True)                              # -> LOCK
    b = a.clone()
    assert (b.state, b._fade, b._l_prev, b.list_present) == \
           (a.state, a._fade, a._l_prev, a.list_present)
    b.update(False, True)                             # -> RELEASE on the copy only
    assert b.state != a.state


def test_target_cs_only_moves_the_camera_inside_a_roll(env):
    """SEPARABILITY: with the aim fixed, the roll is bit-identical under any `target_cs` -- Tetra's
    whole trajectory, the roll's speedF and its locked facing -- and nothing diverges before the
    exit. This is what lets `roll_candidates` sweep the aim once and the camera separately instead
    of paying the full cross product."""
    r = F.target_cs_is_exit_only(env)
    assert r['tetra_identical'], "target_cs changed the push -- the roll stage cannot be factored"
    assert r['first_diverge'] >= r['roll_frames']
    assert r['roll_speedF'] == 26.0
    assert r['ok']


def test_pursuit_box_contains_the_human_every_frame(env, hl, box):
    """CONTAINMENT for the regime gate: the box is measured off the recorded window, so the human
    must sit inside it on every frame. A margin that inverted (or a sign slip in `lead_hi`) would
    show up here rather than as a mysteriously empty beam."""
    h = F.human_in_box(env, hl, box)
    assert h['outside'] == [] and h['ok']
    assert box['lead_lo'] < box['lead_hi'] < 0        # Link is always BEHIND Tetra
    assert box['max_lat'] > 0 and box['max_delta'] > 0


def test_junction_beam_gives_far_more_endpoints_than_the_family(env, hl, box):
    """The s43 search-space finding, gated as MEASURED: from the human's own cycle-1 exit the
    per-frame junction beam returns an order of magnitude more distinct gate-passing in-box
    endpoints than `two_roll.junction_variants` does, at no worse flatness. Diversity is the point
    -- roll survival off an endpoint is razor-thin, so a handful of endpoints is not enough."""
    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    for k in range(1, 21):
        base.step(dtm(k))
    node = dict(run=base, log=[dtm(k) for k in range(21)], frames=20)

    ends = F.junction_beam(node, hl, box, max_frames=8, beam=16, ess_step=2, aim_step=32,
                           keep=10 ** 6)
    assert ends, "the junction beam found no usable endpoint from the human's own entry"
    for e in ends:                                    # every endpoint really passes the gates
        assert T.junction_gates(e['run'], hl, e['frames']) is None
        assert F.in_pursuit_box(e['run'], hl, box)

    kept, _dead = T.junction_endpoints(base, node['log'], hl, 20, jn_keep=10 ** 6,
                                       swing_step=2, n_swings=(2, 3, 4, 5, 6))
    fam = [j for j in kept if F.in_pursuit_box(j['run'], hl, box)]
    assert len(ends) > 10 * max(1, len(fam))
    assert min(abs(e['m']['lat']) for e in ends) <= min(abs(j['m']['lat']) for j in fam)


def test_derived_target_css_is_entry_relative(env):
    """`[[no-overtuned-constants]]`: the camera grid is derived from the roll's OWN entry csangle,
    never a constant carried from another cycle (the s42 winner's 38812 is entry-state-specific)."""
    run = seeds.make_freerun(env)
    grid = F.derived_target_css(run)
    assert len(grid) == 2 * F.TCS_SPAN // F.TCS_STEP + 1
    assert int(run.csangle) in grid
    run.csangle = (int(run.csangle) + 4096) & 0xFFFF
    assert int(run.csangle) in F.derived_target_css(run)


@pytest.mark.slow
def test_cycle_unit_chains_from_the_recorded_entry_and_bit_confirms(env, hl, box):
    """What IS established (s43): the generic cycle unit -- junction beam then roll -- chains a
    SECOND roll off the recorded human's own cycle-1 exit, on-line and talk-safe, and the result
    replays BIT-IDENTICALLY on a fresh self-contained `FreeRun` (`confirm_plan`).

    This gates the machinery, not the full herd: chaining a THIRD cycle off the search's OWN
    cycle-1 exit is still open (see the module docstring / README `## Plan / status` s43) -- every
    junction endpoint reached from it has zero surviving roll aims. Pinning the working case here
    keeps that blocker honest: if this ever fails, the unit itself regressed."""
    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    for k in range(1, 21):
        base.step(dtm(k))
    # the log holds the inputs actually STEPPED (f0 is the pre-seed, not a step)
    node = dict(run=base, log=[dtm(k) for k in range(1, 21)], frames=20)

    ends = F.junction_beam(node, hl, box, max_frames=8, beam=16, ess_step=2, aim_step=32, keep=40)
    best = None
    for e in ends:
        for cand in F.roll_candidates(e, hl, box, step=6, aim_keep=2, tcs_keep=1,
                                      require_quality=False):     # terminal roll
            if best is None or cand['m']['per_frame'] > best['m']['per_frame']:
                best = cand
    assert best is not None, "the cycle unit chained no roll off the recorded entry"
    assert best['knobs']['roll_speedF'] >= 20.0
    assert best['m']['per_frame'] > T.human_baseline(env, hl)['per_frame']
    c = F.confirm_plan(env, hl, best, want_rolls=2)
    assert c['bit_exact'] and c['talk_safe'] and c['rolls'] == 2 and c['ok']
    assert c['per_frame'] == best['m']['per_frame']    # same log, same frames -- exact
