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


def test_endgame_report_scores_both_halves_of_the_joint_target(env, hl):
    """The coupled endgame metric (SESSION_PROMPT milestone 2) reports BOTH the placement distance
    (Tetra -> nearest genuine coord) and the final-clip ENTRY gap (Link -> `seeds.ENTRY_ROLL_POS/
    FACING`, the setup the coord list is valid for). This gates the metric's shape, not a search
    result: the entry gap is MEASURED off the named seed constant, never a magic number."""
    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    for k in range(1, 21):
        base.step(dtm(k))
    node = dict(run=base, log=[dtm(k) for k in range(1, 21)], frames=20)
    eg = F.endgame_report(node, hl)
    assert eg['placement']['dist'] >= 0.0
    assert 0 <= eg['placement']['nearest']['idx'] < 288
    # the entry gap is exactly the distance from Link's endpoint to the named entry constant
    import math
    erp = seeds.ENTRY_ROLL_POS
    assert eg['entry_dist'] == pytest.approx(
        math.hypot(base.link.pos_x - erp[0], base.link.pos_z - erp[1]))
    assert -0x8000 <= eg['entry_dfacing'] < 0x8000


def test_terminal_targeting_reduces_placement_distance_and_bit_confirms(env, hl, box):
    """The terminal cycle drives Tetra TOWARD a genuine coord (ranked by placement distance, not
    u/frame) and any survivor replays BIT-IDENTICALLY on a fresh `FreeRun`. Run off a cheap cycle-1
    node (far from the cluster, but it exercises the whole glide-steer + confirm path): a few glide
    frames must strictly reduce the Tetra-to-coord distance, staying in the plow regime, and the
    winner's own input log must confirm 0-ULP."""
    nodes = F.cycle1_nodes(env, hl, box, beam=3)
    start = min(F.placement_report(n)['dist'] for n in nodes)
    tt = F.terminal_targeting(nodes, hl, max_frames=4, beam=8)
    best = tt['best']
    assert tt['dist'] < start                          # the glide made real progress toward a coord
    assert best['frames'] >= nodes[0]['frames']        # it extended a start node
    c = F.confirm_plan(env, hl, best)
    assert c['bit_exact'], "the terminal plan did not replay 0-ULP"
    assert c['talk_safe'] and not best['run']._follow_warned


def test_separation_scan_reports_the_coupled_entry_barrier(env, hl, box):
    """The coupled-entry barrier metric (milestone 2b): from a placement state, `separation_scan`
    reports the deep-contact gap, the best one-step Tetra-still-on-coord placement, whether a CLEAN
    separation step exists, AND the decomp bar (session 46): `centre_feet` (exec Co-centre to Tetra),
    the `co_radii_bar` (80), the `deficit` below it, and `freeze_ok`. Gates the metric's SHAPE off a
    cheap synthetic placed node, not a search result -- the named fields are present, typed, and
    self-consistent (deficit == max(0, bar - centre_feet); freeze_ok == centre_feet >= bar)."""
    nodes = F.cycle1_nodes(env, hl, box, beam=2)
    placed = F.terminal_targeting(nodes, hl, max_frames=3, beam=6)['best']
    sc = F.separation_scan(placed, hl, n_dirs=16)
    assert sc['n_steps'] > 0
    assert sc['best_step_placement'] >= 0.0
    assert sc['start_dist'] >= 0.0 and sc['start_entry'] >= 0.0
    assert isinstance(sc['clean_separation'], bool)
    # the session-46 bar fields
    assert sc['co_radii_bar'] == F.CO_RADII_BAR == 80.0
    assert sc['centre_feet'] > 0.0
    assert sc['deficit'] == pytest.approx(max(0.0, sc['co_radii_bar'] - sc['centre_feet']))
    assert sc['freeze_ok'] == (sc['centre_feet'] >= sc['co_radii_bar'])


def test_freeze_bar_is_the_co_radii_sum(env, hl, box):
    """**The session-46 pivot, gated decomp-exact**: the plow ejects Tetra by `CO_RADII_BAR -
    centre_feet` (halved by the 50/50 `cc_push_pair` split), so she is FROZEN on her coord exactly
    when Link's exec Co-centre sits >= the 80 u Co-radii sum from her. This is the whole reason the
    coupled entry is a GRAZING problem: place her with `centre_feet >= 80` and separation ejects zero.

    Self-contained: take any placed node, translate Link along the Tetra->Link line to a centre_feet
    below the bar and one above it (recomputing the pending push from the moved pose, as `step` does),
    take one neutral step, and assert the measured ejection tracks `(80 - centre_feet)/2` below the
    bar and is ZERO at/above it. No tuned constant -- the bar IS `LINK_CO_R + TETRA_CO_R`."""
    import math
    from harness.tetrapush import from_f0

    nodes = F.cycle1_nodes(env, hl, box, beam=2)
    placed = F.terminal_targeting(nodes, hl, max_frames=3, beam=6)['best']

    def place_link(feet):
        """Move a fresh clone's Link to `feet` u from Tetra along the current line, recompute the
        pending push from the moved pose (as `step` does). Returns the clone + its centre_feet."""
        r = placed['run'].clone()
        tx, tz = r.tx, r.tz
        d0 = math.hypot(r.link.pos_x - tx, r.link.pos_z - tz)
        ux, uz = (r.link.pos_x - tx) / d0, (r.link.pos_z - tz) / d0
        r.link.pos_x, r.link.pos_z = tx + ux * feet, tz + uz * feet
        cx = from_f0._computed_center(r.link, init_frame=False)
        r.pend_link, r.pend_tetra = from_f0.cc_push_pair(cx, (r.tx, r.tz))
        return r, F._centre_feet(r)

    def at_cf(target):
        """Binary-search feet (centre_feet is monotone in feet) so centre_feet == target, then step
        once neutral. Returns (centre_feet, ejection)."""
        lo, hi = 20.0, 160.0
        for _ in range(40):
            mid = (lo + hi) / 2
            _r, cf = place_link(mid)
            if cf < target:
                lo = mid
            else:
                hi = mid
        r, cf = place_link((lo + hi) / 2)
        bx, bz = r.tx, r.tz
        r.step(dict(stickX=111, stickY=111, buttons=0, triggerL=0,
                    substickX=T.CSTICK_NEUTRAL, substickY=0))
        return cf, math.hypot(r.tx - bx, r.tz - bz)

    # sample centre_feet on both sides of the 80 u bar and assert the LAW: the neutral-step ejection
    # is exactly max(0, bar - centre_feet) / 2 (the depth, halved by the 50/50 split), zero at/above.
    samples = [at_cf(t) for t in (60.0, 70.0, 78.0, 80.0, 85.0, 95.0)]
    for cf, ej in samples:
        assert ej == pytest.approx(max(0.0, F.CO_RADII_BAR - cf) / 2.0, abs=1e-2)
    assert any(cf < F.CO_RADII_BAR for cf, _ in samples)                       # ejecting regime
    assert any(cf >= F.CO_RADII_BAR and ej == pytest.approx(0.0, abs=1e-3)     # frozen regime
               for cf, ej in samples)


def test_entry_targeting_stays_in_regime_and_bit_confirms(env, hl, box):
    """The coupled-entry reposition machinery: `entry_targeting` steers Link toward the final-clip
    entry within the plow regime + genuine band, and any survivor replays BIT-IDENTICALLY on a fresh
    `FreeRun` (the whole state-2 -> placement -> reposition log). Structural gate off a cheap synthetic
    placed node -- the reposition never leaves the regime and always confirms 0-ULP; it does not
    assert an entry distance (that awaits the grazing-arrival chain, route a)."""
    nodes = F.cycle1_nodes(env, hl, box, beam=2)
    placed = F.terminal_targeting(nodes, hl, max_frames=3, beam=6)['best']
    et = F.entry_targeting(placed, hl, max_frames=4, beam=16, band_tol=6.0)
    b = et['best']
    assert et['dist'] >= 0.0 and et['placement'] >= 0.0
    assert -0x8000 <= et['entry_dfacing'] < 0x8000
    c = F.confirm_plan(env, hl, b)
    assert c['bit_exact'], "the reposition plan did not replay 0-ULP"
    assert c['talk_safe'] and not b['run']._follow_warned


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
