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

from harness.tetrapush import seeds, two_roll as T, full_herd as F, objective as O, search as S
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


def test_a_frontier_generation_is_one_physics_state_so_every_rank_ties(env, hl, box):
    """**The session-68 root cause, structural and exact.** The input pipeline acts a frame late, so
    every child of a frontier node has IDENTICAL physics -- the stick just delivered has not moved
    Link yet, it has only entered the buffer. So any frontier key computed on that physics (which is
    every key: cone deficit, lateral, aim) is the SAME NUMBER for the whole alphabet, and a stable
    sort keeps the first ``beam`` of them: `beam` pending-input variants of ONE state.

    That is why `junction_beam` was a greedy single-trajectory walk for twenty-five sessions while
    reporting hundreds of "distinct" endpoints. Both halves are gated here -- the tie, and that
    `_mixed_beam`'s ``per_group`` cap is what breaks it -- because the fix is worthless if a later
    change lets the frontier fill with one state again."""
    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    for k in range(1, 21):
        base.step(dtm(k))

    kids = []
    for (sx, sy) in F.junction_alphabet(base, hl, ess_step=2, aim_step=32):
        for l in (0, 1):
            r = base.clone()
            d = dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                     triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL, substickY=0)
            r.step(d)
            kids.append(dict(run=r, log=[d], jf=1))
    assert len(kids) > 100
    # the tie: one physics state, hence one value of every frontier key
    assert len({F._physics_tag(n['run']) for n in kids}) == 1
    score = F._frontier_score(hl)
    assert len({score(n) for n in kids}) == 1
    aim_only, aim_cone = F._armable_square(hl, O.push_corridor(hl))
    assert len({round(aim_only(n), 9) for n in kids}) == 1
    assert len({round(aim_cone(n), 9) for n in kids}) == 1

    # ...so an uncapped keep takes `beam` variants of that one state, and the cap does not
    def ident(n):
        return (F._physics_tag(n['run']), n['log'][-1]['stickX'], n['log'][-1]['stickY'],
                bool(n['log'][-1]['triggerL']))

    order = sorted(kids, key=score)
    assert len(F._mixed_beam([order], 8, ident=ident)) == 8
    capped = F._mixed_beam([order], 8, ident=ident, group=lambda n: F._physics_tag(n['run']),
                           per_group=1)
    assert len(capped) == 1


def test_the_probe_pool_is_a_prefix_by_default_and_a_keep_when_asked():
    """**The cap the session-68 frontier fix ran into, and the measurement that kept it a prefix.**

    `extend_cycle` roll-probes at most ``probe_cap`` endpoints, in COLLECTION order -- the earliest
    junction frames. That hides real coverage (4158 armed endpoints off cycle-1 node 1, **932 within
    5 deg of the corridor, every one past index 250**), but buying them back cost more than it paid:
    a squareness share took cycle 2 from **8 survivors to ZERO**, twice, because the rollable-AND-
    continuable endpoints are concentrated in a few early states and only some pending inputs of those
    states roll at all. So the prefix is the DEFAULT and the keep is a knob (``square_pool``).

    Gated as pure selection (no simulator), which is the level both behaviours live at, so a future
    session cannot flip the default without noticing what it costs."""
    ends = [dict(run=None, sq=90.0 - i * 0.02, st=i // 100) for i in range(4000)]
    # the default: a prefix, exactly the cap, in order
    assert F._probe_pool(ends, 250) == ends[:250]
    assert all(e['sq'] > 80.0 for e in F._probe_pool(ends, 250))
    # asked for: the squarest survive, spread over states, early share still present
    pool = F._probe_pool(ends, 250, lambda e: e['sq'], tag=lambda e: e['st'])
    assert 200 <= len(pool) <= 250
    assert ends[-1] in pool
    assert min(e['sq'] for e in pool) == min(e['sq'] for e in ends)
    assert len({e['st'] for e in pool}) > 10
    assert any(e['sq'] > 80.0 for e in pool)
    # under the cap it is the identity, in order, either way
    assert F._probe_pool(ends[:100], 250) == ends[:100]
    assert F._probe_pool(ends[:100], 250, lambda e: e['sq'], tag=lambda e: e['st']) == ends[:100]


def test_the_exit_probes_pool_is_the_uncapped_mix_not_the_carry_pool():
    """**The two pools are different jobs, and the session-69 one must NOT inherit the s68 cap.**

    `_probe_pool`'s default spreads its slots over physics states because it is choosing endpoints to
    CARRY, and a state-spread carry pool was measured to stall the chain. `junction_square_probe` is
    choosing nothing -- it is SCORING an exit -- and there the cap is what lies: on three real exits the
    uncapped mix read ``1.34 / 141.83 / 14.67`` where the capped one read ``none / 141.83 / 25.89``,
    reporting an exit as unrollable that reaches 1.34 u.

    Gated as pure selection (no simulator), the level both behaviours live at: ``spread=False`` keeps
    the early share AND the squarest without capping per state, and the default still caps."""
    ends = [dict(run=None, sq=90.0 - i * 0.02, st=i // 100) for i in range(4000)]
    mix = F._probe_pool(ends, 250, lambda e: e['sq'], tag=lambda e: e['st'], spread=False)
    assert len(mix) == 250
    assert ends[0] in mix and ends[-1] in mix                  # both ends of both orders
    assert min(e['sq'] for e in mix) == min(e['sq'] for e in ends)
    # uncapped: the prefix share is a RUN of consecutive early endpoints, not one per state
    per_state = {}
    for e in mix:
        per_state[e['st']] = per_state.get(e['st'], 0) + 1
    assert max(per_state.values()) > 50
    capped = F._probe_pool(ends, 250, lambda e: e['sq'], tag=lambda e: e['st'])
    assert max(sum(1 for e in capped if e['st'] == s) for s in {e['st'] for e in capped}) < 20
    # under the cap, and with no key, both are the identity prefix
    assert F._probe_pool(ends[:100], 250, lambda e: e['sq'], spread=False) == ends[:100]
    assert F._probe_pool(ends, 250, None, spread=False) == ends[:250]


def test_the_endpoint_probe_reports_the_arrival_its_rolls_deliver(env, hl, box):
    """**The OVERSHOOT as the endpoint probe's third axis** (session 70). A cycle's roll is a ~205 u
    atom that cannot stop short, so WHERE a plan finishes is decided when its last endpoint is chosen
    -- and nothing ranked that: the s69 cycle-3 stage kept endpoints landing Tetra at along 947 against
    a `aim.handoff_target` of 894, ~4 frames of push spent going past and then paid back in lateral,
    which is that run's whole 78-80 against a 75-frame budget.

    `roll_probe` already fires the entire aim fan, so the along its rolls DELIVER costs nothing to
    report. Gated as PURELY ADDITIVE (asking for the arrival cannot change rollability, the rate or the
    delivered offset -- a keep must never perturb the rank it shares) plus the two identities that make
    ``arrive`` usable as a keep: it is the |signed overshoot| of the same roll, and it is the MINIMUM
    over the surviving rolls, so it is never worse than the straightest roll's own arrival.

    The last assertion pins WHERE the keep applies, which is why `chain_herd` wires it on the last
    cycle only: from a cycle-2-range endpoint every surviving roll UNDERSHOOTS the handoff target by
    ~300 u, so there "arrive" and "get as far as possible" are the same ask and the keep is inert. It
    can only bite where a roll can go past."""
    from harness.tetrapush import aim as A
    rows = seeds.load_placements()[0]
    cor = A.handoff_corridor(env, hl, O.placement_thread(hl, rows), rows=rows)
    tgt = cor['target'][0]

    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    for k in range(1, 21):
        base.step(dtm(k))
    node = dict(run=base, log=[dtm(k) for k in range(21)], frames=20)
    ends = F._dedup_endpoints(F.junction_beam(node, hl, box, max_frames=8, beam=16, ess_step=2,
                                              aim_step=32, keep=10 ** 6, corridor=cor))
    assert ends

    got = 0
    for e in ends[:60]:
        blind = F.roll_probe(e, hl, corridor=cor)
        aware = F.roll_probe(e, hl, corridor=cor, target_along=tgt)
        assert (blind is None) == (aware is None)
        if blind is None:
            continue
        got += 1
        assert blind['arrive'] is None and blind['over'] is None      # not asked, not reported
        for f in ('rate', 'off', 'off_rate', 'along', 'n'):           # purely additive
            assert blind[f] == aware[f], f
        assert abs(aware['arrive'] - abs(aware['over'])) < 1e-12
        assert aware['arrive'] <= abs(aware['along'] - tgt) + 1e-12   # the min over the fan
        assert aware['over'] < 0.0                    # cycle-2 range: every roll falls short
    assert got, "no endpoint off the human's own cycle-1 exit was rollable at all"


def test_the_probe_pool_is_a_flatness_prefix_and_the_band_share_is_what_covers_the_arrival(env, hl,
                                                                                          box):
    """**The false assumption that starved the arrival keep** (session 70). `_probe_pool`'s note said
    `extend_cycle` probes the first ``cap`` "in COLLECTION order (generation order), i.e. the earliest
    junction frames". It does not: with ``keep`` unbounded `junction_beam` RETURNS its endpoints sorted
    by ``(|Link - Tetra lateral|, jf)``, so the prefix is a FLATNESS prefix.

    That is why the session-70 arrival keep came out byte-identical to the stage without it. Off a real
    cycle-2 exit the beam returns 4622 armed endpoints spread over jf 5..12 and the 250 probed were
    **entirely jf 8 and jf 10** -- and the junction frame IS the arrival, because the roll's length is
    fixed (~223 u) while the junction pushes ~11-12 u/frame: jf 6 lands Tetra at along 887 against a
    `aim.handoff_target` of 894, jf 12 at 947. So the keep had two arrivals to choose between, both
    ~53 u past the target, and a band-spread pool finds a rollable jf-6 endpoint delivering 886.81.

    Gated on the two halves that make it a bug rather than a preference: the returned order really is
    non-decreasing in |lat| (so any prefix of it is a flatness sample), and the band share really does
    cover strictly more junction frames at the same pool size -- while still filling the pool, since a
    coverage fix that shrank it would trade one blind spot for another."""
    rows = seeds.load_placements()[0]
    cor = O.push_corridor(hl, rows)
    dtm = seeds.dtm_input_at(env)
    base = seeds.make_freerun(env)
    base.pre_seed_input(dtm(0))
    for k in range(1, 21):
        base.step(dtm(k))
    node = dict(run=base, log=[dtm(k) for k in range(21)], frames=20)
    ends = F._dedup_endpoints(F.junction_beam(node, hl, box, max_frames=8, beam=16, ess_step=2,
                                              aim_step=32, keep=10 ** 6, corridor=cor))
    assert len({e['jf'] for e in ends}) > 1, "this exit's endpoints are all at one junction frame"

    lat = [abs(e['m']['lat']) for e in ends]
    assert all(lat[i] <= lat[i + 1] + 1e-12 for i in range(len(lat) - 1)), \
        "junction_beam's return is no longer the flatness order this prefix was blind to"

    cap = max(8, len(ends) // 8)                    # small enough that the prefix cannot cover both
    prefix = F._probe_pool(ends, cap)
    banded = F._probe_pool(ends, cap, jf_spread=True)
    assert prefix == ends[:cap]                     # the default really is that prefix
    assert len(banded) == cap                       # ...and the fix does not shrink the pool
    assert len({e['jf'] for e in banded}) > len({e['jf'] for e in prefix})
    # the band share must not inherit the squareness pool's per-state cap (that returns one pending
    # variant per physics state, which is a different and much smaller pool)
    assert len(F._probe_pool(ends, cap, jf_spread=True, spread=True)) == cap


def test_the_last_cycles_camera_cut_prices_the_escape_the_thread_rank_pays_for(env, hl):
    """**The last cycle's `target_cs` cut was ranked by a question it does not have** (session 70).

    `junction_quality` asks whether the NEXT junction can continue from a roll's exit. The last cycle
    has no next junction -- `extend_cycle` already turns the GATE off (``require_quality=False``) and
    the s43-s69 stage then left the ORDER ranked by it anyway. Its exit IS the handoff state, so what
    it is worth is where the escape lands from it (`landing_key`).

    The contrast is gated on real arrivals at four along offsets from the same coord, because the
    stock last-cycle rank is measurably PAID for overshooting: `objective.thread_frames` charges
    nothing for along anywhere inside the thread's 47.6 u, so `rank_key('thread')` scores an arrival
    sitting ON the coord -- 44 u past the state the escape needs -- as its BEST (0.00 frames) and one
    at the handoff target as 3.36 worse. `landing_key` reverses that, and `aim.landing_miss` says which
    of the two is right: the escape from the coord-position overshoots the thread by ~14.5 u, from the
    handoff-target one by ~5.5."""
    from harness.tetrapush import aim as A
    rows = seeds.load_placements()[0]
    th = O.placement_thread(hl, rows)
    cor = A.handoff_corridor(env, hl, th, rows=rows)
    resid = cor['resid']
    assert resid is not None
    near = min(rows, key=lambda p: hl.along(p['x'], p['z']))
    nodes = {d: F.synthetic_hot_arrival(env, hl, near['idx'], d_short=d, feet=56.0)
             for d in (0.0, resid[0])}
    lk = F.landing_key(hl, th, resid)
    stock = F.rank_key('thread', rows, hl)
    shifted = F.rank_key('thread', rows, hl, resid=resid)

    def rk(key, nd):
        return key(nd['run'], nd['frames'], T.metrics(nd['run'], hl, nd['frames']))

    at_coord, at_handoff = nodes[0.0], nodes[resid[0]]
    # the stock rank PAYS for the overshoot; the escape-aware key and the shifted rank do not
    assert rk(stock, at_coord) < rk(stock, at_handoff) - 0.5
    assert lk(at_coord) > lk(at_handoff)
    assert rk(shifted, at_coord) > rk(shifted, at_handoff)
    # ...and the exact landing says which ranking is right
    miss = {d: A.landing_miss(nd['run'], hl, th, resid)['miss'] for d, nd in nodes.items()}
    assert miss[0.0] > 2.0 * miss[resid[0]]
    # without a residual the key degrades to the exit's own position, i.e. the stock thread cost
    plain = F.landing_key(hl, th, None)
    assert plain(at_coord) < plain(at_handoff)


@pytest.mark.slow
def test_a_cheap_aim_key_ranks_the_dead_exits_first_and_the_cheap_probe_does_not(env, hl, box):
    """**The session-70 calibration, which overturned the plan it was measuring.** Session 69 left
    `roll_candidates`' ``tcs_keep`` ranked by `junction_quality` (frames in the pursuit box) at every
    cycle and handed over "give that glide an AIM-aware key -- report the corridor aim it reaches
    instead of only frames-in-box". Cycle 1's grid is fully probed, so the proxy could be calibrated
    against the truth before being wired, and the answer is that an aim key is not merely no better,
    it is the WORST of the candidates: over the 25-exit grid, a keep of 3 by the stock key delivers
    14.67 u of corridor offset, by the glide's aim 116.93, and by the exit's own aim NOTHING AT ALL.

    The reason is structural, and it is what this gates: the exits with the SMALLEST aim error are the
    ones whose junction arms nothing. Eighteen of the 25 sit at |aim| 1.26-2.05 deg and not one of them
    can roll; every exit that delivers anything measures |aim| >= 3.0. So the cheapest scalar that
    looks like squareness ranks the dead ones first.

    What IS affordable is the same PROBE at a coarser budget (`CHEAP_PROBE`, ~2.7 s against ~21 s).
    Coarseness costs recall, not precision: it declines most exits, and where it answers it agrees with
    the full probe -- gated here as bit-equality on the exit it picks, which is also the exit the FULL
    probe picks and one the stock quality order ranks fifth."""
    from harness.tetrapush import aim as A
    rows = seeds.load_placements()[0]
    cor = O.push_corridor(hl, rows)
    cheap = F.square_probe_key(hl, box, cor)

    grid = F.cycle1_nodes(env, hl, box, placements=rows, square_keep=False, tcs_keep=10 ** 6,
                          beam=10 ** 6)
    aims = [(abs(A.corridor_aim_error(n['run'], hl, cor)), n) for n in grid
            if A.corridor_aim_error(n['run'], hl, cor) is not None]
    assert len(aims) > 10
    aims.sort(key=lambda t: t[0])
    # the smallest-aim exits arm NOTHING -- an aim-ranked keep of 3 would deliver nothing at all
    for _v, n in aims[:3]:
        assert cheap(n) is None

    # the cheap probe over the stock order: where it answers, that answer is real
    scored = [(cheap(n), n) for n in grid[:12]]
    live = [(v, n) for v, n in scored if v is not None]
    assert live, "the cheap probe scored none of the stock order's first 12 exits"
    best_v, best_n = min(live, key=lambda t: t[0])
    full = F.junction_square_probe(best_n, hl, box, cor)
    assert full is not None and abs(full['off'] - best_v) < 1e-9      # coarse == full where it fires
    # ...and it is NOT what the stock quality order puts first, so the keep adds something
    assert F._state_tag(best_n['run']) != F._state_tag(grid[0]['run'])
    assert abs(A.corridor_aim_error(best_n['run'], hl, cor)) > aims[0][0]


@pytest.mark.slow
def test_the_cycle_1_squareness_keep_takes_the_exit_the_quality_rank_cuts(env, hl, box):
    """**The session-69 result: cycle 1 chooses ONE roll's CAMERA, and the rank it was choosing with
    is anti-correlated with the thing that matters.**

    Measured, the whole cycle-1 candidate set is a single roll aim swept over the 25-value
    `derived_target_css` grid -- every candidate scores `plan_bound` 71.90, so the frame rank cannot
    separate them at all -- and the old ``tcs_keep=3`` cut them by `junction_quality`, which counts
    frames in the pursuit box. What actually differs between them is the squareness their junction can
    still deliver (`junction_square_probe`), and it ranges over two orders of magnitude: the
    quality-best exit reaches **141.83 u** off the corridor while the best available reaches **11.20**
    at quality rank 5.

    Asserted as a CONTRAST plus the two structural facts behind it (bound-tied, camera-distinct), and
    on the exit IDENTITY rather than on literal offsets: the squarest exit of those probed is one the
    default (cheap) stage drops and the keep keeps. A literal would pin a search budget; the identity
    pins the finding.

    The keep is opt-in because it costs ~308 s over 21 exits, so this gate also pins the two call
    shapes: the bare defaults are the cheap s43-s68 stage (what every other test wants), and
    ``square_keep=True`` + an uncut ``tcs_keep`` is what `chain_herd`'s ``c1_square`` asks for."""
    rows = seeds.load_placements()[0]
    cor = O.push_corridor(hl, rows)
    probe_n = 8

    wide = F.cycle1_nodes(env, hl, box, placements=rows, square_keep=False, tcs_keep=10 ** 6,
                          beam=10 ** 6)
    assert len(wide) > probe_n, "the cycle-1 candidate set is not wider than the beam"
    bounds = [O.plan_bound(n['frames'], F._placement_dist(n['run'], rows)) for n in wide]
    assert max(bounds) - min(bounds) < 0.5      # bound-tied: the frame rank cannot choose
    assert len({int(n['run'].csangle) for n in wide}) > 4    # ...and they differ in the camera

    probes = [(F.junction_square_probe(n, hl, box, cor), n) for n in wide[:probe_n]]
    got = [(p, n) for p, n in probes if p is not None]
    assert got, "no cycle-1 exit could deliver a roll at all"
    best_p, best_n = min(got, key=lambda t: t[0]['off'])
    top_p = probes[0][0]                        # what `junction_quality` ranked first
    assert top_p is None or top_p['off'] > 2.0 * best_p['off'], (
        "the quality rank's own pick is already the squarest -- the keep would be inert")

    old = F.cycle1_nodes(env, hl, box, placements=rows, beam=8)          # the cheap default stage
    new = F.cycle1_nodes(env, hl, box, placements=rows, square_keep=True, tcs_keep=10 ** 6,
                         sq_cap=probe_n, beam=4)                         # what `chain_herd` asks for
    tag = F._state_tag(best_n['run'])
    assert tag not in {F._state_tag(n['run']) for n in old}, \
        "the old cut already kept the squarest exit"
    assert tag in {F._state_tag(n['run']) for n in new}, "the keep did not keep the squarest exit"
    assert any(n.get('square') is not None for n in new)     # and it carries its measurement


@pytest.mark.slow
def test_the_frontier_fix_squares_an_exit_the_stock_frontier_cannot(env, hl, box):
    """**The session-68 fix, gated against the frontier it replaces, on a state minted from state 2**
    (no dumped beam -- `cycle1_nodes` reproduces it in ~12 s).

    The stock frontier walks the fastest turn out of the talk cone, and the turn is what rotates
    Link's ~17 u exec-centre lead: off a real cycle-1 exit its armed endpoints all land 15-36 deg off
    the push corridor, which is the whole of the roll-2 excursion the chain then spends two cycles
    undoing. With the slot cap per physics state and the squareness shares, the same budget finds an
    armed endpoint essentially ON the corridor.

    Asserted as a CONTRAST, not a literal, and asserted per EXIT rather than on one of them: some
    exits cannot be squared at all (measured -- the cycle-1 beam's node 0 stays at -33 deg under a
    frontier four times as wide), which is precisely why squareness has to be a keep at the CYCLE cut
    too (`extend_cycle`'s ``square_keep``) and not only inside the junction. So: walk the exits the
    stock frontier leaves unsquare and require the fix to square at least one of them -- and require
    every endpoint it returns to still pass the junction gates, since a keep that smuggled in unarmed
    endpoints would look like progress and be worthless."""
    from harness.tetrapush import aim as A
    rows = seeds.load_placements()[0]
    cor = O.push_corridor(hl, rows)
    cfg = dict(max_frames=8, beam=16, ess_step=2, aim_step=32, keep=10 ** 6, corridor=cor)

    def squarest(node, **kw):
        got = []
        F.junction_beam(node, hl, box, collect=got, **cfg, **kw)
        u = F._dedup_endpoints(got)
        errs = [A.corridor_aim_error(e['run'], hl, cor) for e in u]
        errs = [v for v in errs if v is not None]
        return (min(errs, key=abs) if errs else None), u

    nodes = F.cycle1_nodes(env, hl, box, placements=rows)
    assert nodes, "cycle 1 minted no nodes"
    seen = won = None
    for nd in nodes:
        stock_sq, _u = squarest(nd, per_state=10 ** 6, aim_share=False)
        if stock_sq is None or abs(stock_sq) < 12.0:
            continue                                  # already square (or unarmable): nothing to fix
        seen = stock_sq
        fixed_sq, ends = squarest(nd, per_state=4, aim_share=True)
        if fixed_sq is not None and abs(fixed_sq) <= 5.0:
            won = (stock_sq, fixed_sq, ends)
            break
    assert seen is not None, "no cycle-1 exit is left unsquare by the stock frontier"
    assert won is not None, (
        "the fixed frontier squared none of the exits the stock one left unsquare (last %+.2f)"
        % seen)
    stock_sq, fixed_sq, ends = won
    assert abs(fixed_sq) < abs(stock_sq) / 2.0
    for e in ends[:40]:
        assert T.junction_gates(e['run'], hl, e['frames']) is None
        assert F.in_pursuit_box(e['run'], hl, box)


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


def test_the_wall_prune_bites_on_the_locked_plan_and_is_inert_on_a_clean_one(env, hl, box):
    """**Session 61: the wall half of the objective, wired into the search.**

    Session 60 found the Courtyard `FreeRun` models no BG collision at all and that the regime half
    (`_follow_warned`) was enforced everywhere while the wall half was enforced NOWHERE. Both halves
    now go through `frame_in_model`, and `confirm_plan` measures the clearance on every frame with the
    exact metric. Two things are gated, because a prune that never fires and a prune that fires on
    everything look identical from the pass/fail line:

      * it BITES: node 1's locked plan walks Link ~34 u through the courtyard back wall, so its
        confirm reports `wall_ok=False` (and `ok=False`) even though the replay is still bit-exact --
        the plan is faithful to the model and the MODEL is what is out of bounds;
      * it is INERT on a real search node: a cycle-1 plan runs hundreds of u from anything.
    """
    import json
    import os
    import warnings

    fx = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'fixtures', 'courtyard_node1_console.json')
    log = json.load(open(fx))['log']
    run = seeds.make_freerun(env)
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    with warnings.catch_warnings():         # the follow guard fires; that is the OTHER half
        warnings.simplefilter('ignore')
        for d in log:
            run.step(d)
        c = F.confirm_plan(env, hl, dict(run=run, log=log))
    assert c['bit_exact'], "the replay itself must still be exact -- the plan is model-faithful"
    assert not c['wall_ok'] and c['wall_margin'] < -1.0
    assert c['wall_margin_at'] is not None and not c['ok']

    clean = F.cycle1_nodes(env, hl, box, beam=2)
    assert clean, "cycle 1 found nothing -- the wall prune should be inert here"
    cc = F.confirm_plan(env, hl, clean[0])
    assert cc['wall_ok'] and cc['wall_margin'] > 50.0 and cc['ok']
    # and the shared predicate agrees with the per-frame metric it stands in for
    assert F.frame_in_model(clean[0]['run'])
    assert not F.frame_in_model(run)


def test_the_frame_bound_rank_and_the_budget_cut(env, hl, box):
    """**Session 61: the objective as the search's rank.** `rank_key('bound')` orders by
    `objective.plan_bound` (frames spent + the steady-state remainder), which is what makes the beam
    frame-minimal AND makes it pay for lateral drift; `_budget_cut` drops nodes whose bound is already
    past the frame budget.

    The substantive difference is gated where it actually lives: a herd RATE is a down-herd
    projection, so it cannot see a lateral miss at all, while the bound counts it as the frames it
    will cost. (On cycle 1 the two happen to produce the same ORDER -- the nodes barely differ
    laterally there -- which is exactly why the difference has to be gated on the definition rather
    than on a beam's ordering.)"""
    nodes = F.cycle1_nodes(env, hl, box, beam=6)
    kb, kr = F.rank_key('bound'), F.rank_key('rate')
    vb = [kb(n['run'], n['frames'], n['m']) for n in nodes]
    assert vb == sorted(vb), "cycle 1 must come back ordered by the rank it was given"
    with pytest.raises(ValueError):
        F.rank_key('whatever')

    n = nodes[0]
    on_line, off_line = n['run'].clone(), n['run'].clone()
    off_line.tx += hl.px * 30.0          # 30 u PURELY lateral: the same down-herd progress
    off_line.tz += hl.pz * 30.0
    assert hl.along(off_line.tx, off_line.tz) == pytest.approx(hl.along(on_line.tx, on_line.tz))
    assert kr(on_line, n['frames'], n['m']) == kr(off_line, n['frames'], n['m']), \
        "the rate is supposed to be blind to lateral offset -- that is the point being made"
    assert kb(on_line, n['frames'], n['m']) < kb(off_line, n['frames'], n['m'])

    # the cut keeps what can still finish and drops what cannot; it is monotone in the budget
    assert F._budget_cut(nodes, kb, None) == nodes
    assert F._budget_cut(nodes, kb, 10 ** 6) == nodes
    assert F._budget_cut(nodes, kb, 0.0) == []
    mid = sorted(vb)[len(vb) // 2]
    assert len(F._budget_cut(nodes, kb, mid)) == sum(1 for v in vb if v <= mid)


def test_the_lateral_rate_is_the_measured_plow_authority(env, hl):
    """**Session 62: `objective.LATERAL_RATE` is a MEASUREMENT, and this is the measurement.**

    `plan_bound` divides the straight distance to a coord by `PUSH_CEILING`, i.e. it prices a unit of
    lateral exactly like a unit of along. `lateral_authority` holds each stick of the terminal
    alphabet for six frames and reads the SPREAD of Tetra laterals reached -- how far apart two
    plans' lateral outcomes can be per frame of glide. It is several times smaller than the along
    ceiling, which is the fact the last cycle's rank exists to use.

    The constant is pinned only as an INEQUALITY against the measurement (it is the worst of the
    measured beds, so it must not exceed this one), because pinning a float here would gate the
    synthetic bed's exact geometry rather than the property."""
    a = F.lateral_authority(F.synthetic_hot_arrival(env, hl, 287, d_short=40.0)['run'], hl)
    assert a is not None and a['n'] > 100, "the alphabet should mostly survive a 6-frame glide"
    assert a['hi'] > a['lo'], "no lateral authority at all would make the rank meaningless"
    assert 2.0 < a['per_frame'] < 6.0, \
        "the measured lateral authority moved (%.2f u/f) -- re-derive LATERAL_RATE" % a['per_frame']
    assert O.LATERAL_RATE <= a['per_frame'] + 1e-9, \
        "LATERAL_RATE must not be more optimistic than the worst measured bed"
    # the point of the whole thing: lateral is several times dearer than along
    assert a['along_max'] / a['frames'] > 3.0 * a['per_frame']


def test_glide_probe_ranks_an_endpoint_by_what_its_terminal_reaches(env, hl):
    """**Session 62: the last cycle's keep is GLIDE-ABILITY, one stage on from `roll_probe`.**

    `roll_probe` exists because the endpoints that look best are measurably not the ones a roll can
    fire from. The last cycle has the same bug against the TERMINAL: `objective.thread_cost` scores a
    post-roll endpoint on where TETRA is and says nothing about how much push LINK has left -- which
    is what decides the handoff.

    Gated on two synthetic arrivals that make the disagreement unambiguous: the same Tetra, the same
    coord, but Link either in contact behind her or parked outside the freeze bar with nothing left
    to give. Tetra-only ranks them EQUAL; the glide probe does not."""
    contact = F.synthetic_hot_arrival(env, hl, 287, d_short=40.0, feet=64.0)
    spent = F.synthetic_hot_arrival(env, hl, 287, d_short=40.0, feet=150.0)
    th = O.placement_thread(hl)
    rows, _ = seeds.load_placements()

    def tetra_only(nd):
        return O.thread_cost(nd['frames'], hl.along(nd['run'].tx, nd['run'].tz),
                             hl.lateral(nd['run'].tx, nd['run'].tz), th,
                             ready=F._terminal_ready(nd['run'])['ready'])

    assert tetra_only(contact) == pytest.approx(tetra_only(spent)), \
        "same Tetra: a Tetra-only rank cannot tell these apart -- that is the gap being closed"
    assert F._centre_feet(contact['run']) < F.CO_RADII_BAR < F._centre_feet(spent['run'])

    g_contact = F.glide_probe(contact['run'], 0, hl, rows, th)
    g_spent = F.glide_probe(spent['run'], 0, hl, rows, th)
    assert g_contact['bound'] < g_spent['bound'], \
        "the endpoint with push left must hand the terminal a better finish"
    assert g_contact['along'] > g_spent['along'] + 10.0, "the contact endpoint should herd further"
    # the probe never reports worse than doing nothing: the start state is its own floor
    assert g_spent['bound'] <= O.thread_frames(hl.along(spent['run'].tx, spent['run'].tz),
                                               hl.lateral(spent['run'].tx, spent['run'].tz), th)


def test_the_thread_rank_is_wired_without_moving_the_budget_cut_off_the_bound(env, hl, box):
    """A WIRING gate (reproducing the measurement costs ~8 min of search). Two things have to hold
    together for the session-62 last-cycle rank to be safe:

      * `rank_key('thread')` is available, needs the `HerdLine` (it is a herd-frame metric), and
        orders by `objective.thread_cost`;
      * the hard `_budget_cut` keeps cutting on `plan_bound`, NOT on the thread cost. `plan_bound` is
        admissible at the steady state; the thread cost deliberately is not (`LATERAL_RATE` is a
        SUSTAINED rate a single frame can beat), so cutting on it could drop a node that would have
        finished. Rank on it; never prune on it."""
    with pytest.raises(ValueError):
        F.rank_key('thread')                       # no HerdLine
    with pytest.raises(ValueError):
        F.rank_key('whatever', hl=hl)
    rows, _ = seeds.load_placements()
    th = O.placement_thread(hl, rows)
    key = F.rank_key('thread', rows, hl)
    nodes = F.cycle1_nodes(env, hl, box, beam=4)
    for n in nodes:
        assert key(n['run'], n['frames'], n['m']) == pytest.approx(
            O.thread_cost(n['frames'], hl.along(n['run'].tx, n['run'].tz),
                          hl.lateral(n['run'].tx, n['run'].tz), th,
                          ready=F._terminal_ready(n['run'])['ready']))

    seen = []
    real_cut = F._budget_cut
    try:
        F._budget_cut = lambda ns, k, b, label='', verbose=False: (seen.append(k), ns)[1]
        F.cycle1_nodes(env, hl, box, beam=2, rank='thread', budget=10 ** 6)
    finally:
        F._budget_cut = real_cut
    assert seen, "the budget cut was not reached"
    n = nodes[0]
    for k in seen:
        assert k(n['run'], n['frames'], n['m']) == pytest.approx(
            O.plan_bound(n['frames'], F._placement_dist(n['run'], rows))), \
            "the budget cut must stay on the admissible bound even under the thread rank"


def test_the_frame_minimal_terminal_stops_at_the_first_placement_with_link_moving(env, hl, box):
    """**Session 61: the re-aimed terminal.** Rule 3 replaced the near-rest arrival, so the terminal
    stops the moment Tetra is inside the placement band with Link STILL MOVING (`_terminal_ready`) --
    "the placement rides the last push" -- instead of spending further frames polishing a distance
    already inside it.

    Gated on the CLOSING synthetic arrival (`synthetic_hot_arrival` -- Link hot behind Tetra, a few
    tens of u short of a coord). Since session 65 the per-frame `_terminal_ready` is the cheap
    scalar (MOVING -- `objective.terminal_moving`; the s64 measurement falsified the old 180-snap
    form), and the exact rule 3 is the escape atom, probed on winners rather than per frame -- this
    test pins the non-atom stop rule's shape. Synthetic, so no bit-confirm -- the same
    convention as the s49-s51 recipe gates; the band is widened because a sub-unit placement is the
    search problem, not the stop rule under test here.

    EARLIEST is gated by construction: with the horizon cut one frame shorter, nothing is placed."""
    hot = F.synthetic_hot_arrival(env, hl, 241, d_short=40.0, feet=64.0)
    assert F._approach_rate(hot['run']) > 10.0, "the arrival must be CLOSING for rule 3 to apply"

    def terminal(max_frames):
        return F.terminal_targeting([F.synthetic_hot_arrival(env, hl, 241, d_short=40.0, feet=64.0)],
                                    hl, max_frames=max_frames, beam=16,
                                    objective='frame_minimal', band=6.0)

    tt = terminal(8)
    p = tt['placed']
    assert p is not None, "no in-band state reached -- the stop rule cannot be observed"
    assert p['dist'] <= 6.0 and tt['band'] == 6.0
    assert F._terminal_ready(p['run'])['ready'], "rule 3: the placement frame must be MOVING"
    assert p['score'] == pytest.approx(O.plan_bound(p['frames'], p['dist']))
    assert p['frames'] == len(p['log'])
    assert terminal(p['frames'] - 1)['placed'] is None, \
        "an earlier in-band ready state existed -- the stop is not returning the first one"

    # the placement-ranked terminal is UNCHANGED by any of this (score == distance, s44)
    nodes = F.cycle1_nodes(env, hl, box, beam=2)
    tt_p = F.terminal_targeting(nodes, hl, max_frames=4, beam=12, objective='placement')
    assert tt_p['best']['score'] == tt_p['best']['dist'] == tt_p['dist']


def test_the_atom_wired_terminal_places_post_atom_at_the_slam(env, hl):
    """**Session 66: the terminal is wired to the escape atom's residual.** The atom's conversion
    frames keep pushing Tetra ~35-45 u down-corridor after the glide hands off, so in atom mode
    (the ``'thread'`` objective's default) "placed" is a POST-atom fact read at the slam frame,
    and the target the glide aims at is coord-minus-residual -- with the residual PROBED off the
    terminal state (`objective.escape_ready` -> `_atom_place`), never a constant.

    Gated the way the recipe says to use it: probe the bed's own residual first, then start Tetra
    exactly that far short of the coord -- the atom must then land her ON it (band widened to the
    synthetic convention; sub-unit placement is the search's problem, the mechanism is what is
    pinned). Frames count to the SLAM (where the herd ends); the log carries the whole atom
    through the receding-at-cap handoff for the entry leg."""
    node0 = F.synthetic_hot_arrival(env, hl, 287, d_short=0.0, feet=64.0)
    r0 = O.escape_ready(node0['run'], hl)
    assert r0['ready'], "the atom must fire from the s65 bed"

    node = F.synthetic_hot_arrival(env, hl, 287, d_short=r0['resid_along'], feet=64.0)
    tt = F.terminal_targeting([node], hl, max_frames=2, beam=6, objective='thread', band=6.0)
    p = tt['placed'] or tt['closest_atom']
    assert p is not None and p.get('atom') is not None, "no atom placement was even probed"
    assert p['dist'] <= 6.0, \
        "starting the probed residual short must land Tetra on the coord post-atom (%.2f u)" % p['dist']
    assert p['frames'] == p['pre_frames'] + p['atom']['freeze_f'], "frames must count to the SLAM"
    assert len(p['log']) == p['pre_frames'] + len(p['atom']['log']), \
        "the log must carry the whole atom through the handoff"
    # rule 3 exact rode in with the placement: the atom that placed her is an accepted escape
    from harness.tetrapush import away_walk as AW
    assert AW.fires(p['atom'])
    # and the pre-atom candidate is preserved for the acceptance replay / confirm
    assert p['pre_run'] is not None and p['pre_frames'] == len(p['pre_log'])


def test_a_dumped_beam_rebuilds_bit_exact_from_its_input_logs(env, hl, box, tmp_path):
    """**The cheap-iteration path, gated** (`beam_io`, session 61): a node's identity IS its delivered
    input log, so a beam round-trips through JSON and comes back BIT-IDENTICAL -- both actors'
    positions, Link's facing and the camera -- which is what makes it legitimate to iterate on cycle N
    from a dump instead of re-running the ~475 s stages that produced it.

    Gated on a cheap cycle-1 beam; the property is the same at any depth (session 61 verified it over
    all 7 real cycle-2 nodes), and it is exactly `confirm_plan`'s own convention."""
    from harness.tetrapush import beam_io

    nodes = F.cycle1_nodes(env, hl, box, beam=2)
    assert nodes
    p = str(tmp_path / 'beams.json')
    beam_io.dump_beams(p, [nodes], hl)
    back = beam_io.rebuild_beam(env, beam_io.load_beams(p), cycle=1, hl=hl)

    assert len(back) == len(nodes)
    for orig, reb in zip(nodes, back):
        assert _fingerprint(reb['run']) == _fingerprint(orig['run']), "the rebuild is not bit-exact"
        assert reb['frames'] == orig['frames'] and reb['log'] == orig['log']
        assert reb['m']['per_frame'] == pytest.approx(reb['dumped']['per_frame'])
        assert F._placement_dist(reb['run'], seeds.load_placements()[0]) == \
            pytest.approx(reb['dumped']['placement_dist'])
    # a rebuilt node is a usable search node, not just a comparison target
    assert F.confirm_plan(env, hl, back[0])['ok']


def test_the_chain_does_not_require_its_LAST_cycle_to_be_continuable(env, hl):
    """**The session-61 stall, gated.** `junction_quality` asks whether the NEXT junction could
    continue from a roll's endpoint -- so requiring it on the FINAL cycle demands continuability from
    a junction that never runs, and the terminal glide that actually follows needs contact and the
    regime, not a junction posture.

    Measured cost of getting this wrong: from the real cycle-2 beam, `require_quality=True` produced
    **zero** cycle-3 survivors -- which is what "the chain stalls at cycle 3" was -- where False
    produced **7**, at 69-70 frames and `plan_bound` 74.4-74.7, inside the 75-frame budget.

    This gates the WIRING (a spy on `extend_cycle`), because reproducing the measurement itself costs
    ~15 minutes of search: the last cycle must be asked with `require_quality=False` and every earlier
    cycle with True."""
    seen = []
    real = F.extend_cycle
    fake = [dict(run=None, log=[], frames=0, m=dict(per_frame=0.0), plan=[])]
    try:
        F.extend_cycle = lambda nodes, hl_, box_, **kw: (seen.append(kw['require_quality']), fake)[1]
        F.chain_herd(env, hl, ncycles=4, nodes=fake, box={}, verbose=False)
    finally:
        F.extend_cycle = real
    assert seen == [True, True, False], \
        "cycles 2..N-1 must require continuability and the LAST must not (got %s)" % (seen,)

    # and the flag really reaches the roll stage rather than being accepted and dropped
    import inspect
    assert 'require_quality' in inspect.signature(F.extend_cycle).parameters
    assert 'require_quality=require_quality' in inspect.getsource(F.extend_cycle)


def test_the_cycle_beam_keeps_the_corridor_branch_the_frame_bound_ranks_away(env, hl):
    """**Session 63: the beam KEEPS by the push corridor as well as by the rank** -- because a lateral
    excursion's bill arrives two cycles after the rank that took it.

    The measurement behind it (`reach2.py`/`reach3.py`, ~20 min of search, so gated here as the
    selection logic plus a wiring spy): at the cycle-2 stage the beam kept an endpoint **45.5 u** off
    the corridor and `plan_bound` ranked it BEST (72.94) with a **7.0 u**-off endpoint 0.12 frames
    behind (73.06); at cycle 3 only SEVEN roll endpoints are reachable at all, and the one **0.95 u**
    off the corridor (along 875.9, lat +8.90) is ranked 0.33 frames worse than the 13-17 u-off ones the
    beam took. The excursion then cost the plan 21.5 u of sideways push -- ~1.7 frames -- in the last
    roll and the terminal (`objective.push_budget`).

    A KEEP and not a rank, deliberately: `_mixed_beam`'s first order is the rank, so whatever was best
    by frames is still kept, and the s61 warning holds -- the mid-chain lateral oscillates, so the
    branch that comes back must stay in the beam."""
    import types
    cor = O.push_corridor(hl)

    def node(along, lat, tag):
        run = types.SimpleNamespace(
            tx=hl.ox + hl.dx * along + hl.px * lat, tz=hl.oz + hl.dz * along + hl.pz * lat,
            csangle=tag, link=types.SimpleNamespace(pos_x=float(tag), pos_z=0.0, facing=0,
                                                    speedF=0.0))
        return dict(run=run, frames=46, m=dict(per_frame=0.0), name=tag)

    off, on = node(590.7, -40.49, 1), node(585.9, -2.02, 2)
    assert cor['offset'](hl.along(off['run'].tx, off['run'].tz),
                         hl.lateral(off['run'].tx, off['run'].tz)) == pytest.approx(45.5, abs=0.2)
    # a rank order that puts the off-corridor branch first, as `plan_bound` measurably does
    ranked = [off] + [node(590.0, -40.0 - k, 10 + k) for k in range(6)] + [on]
    order_cor = sorted(ranked, key=lambda n: cor['offset'](hl.along(n['run'].tx, n['run'].tz),
                                                           hl.lateral(n['run'].tx, n['run'].tz)))

    rank_only = F._mixed_beam([ranked], 4)
    assert [n['name'] for n in rank_only] == [n['name'] for n in ranked[:4]], \
        "one order must behave exactly like the plain rank cut"
    assert on not in rank_only, "the corridor branch is what a rank-only cut loses"

    mixed = F._mixed_beam([ranked, order_cor], 4)
    assert off is mixed[0], "the rank's best must survive the mixed keep (it is a keep, not a rank)"
    assert on in mixed, "the corridor branch must make the beam"
    assert len(mixed) == 4 and len(set(id(n) for n in mixed)) == 4, "no duplicates, beam respected"
    # and it degrades gracefully: a beam of 1 is the rank's own pick
    assert F._mixed_beam([ranked, order_cor], 1) == [off]

    # the wiring: every cycle is asked with both keeps on
    seen = []
    real = F.extend_cycle
    fake = [dict(run=None, log=[], frames=0, m=dict(per_frame=0.0), plan=[])]
    try:
        F.extend_cycle = lambda nodes, hl_, box_, **kw: (
            seen.append((kw['corridor_keep'], kw.get('align_keep', True))), fake)[1]
        F.chain_herd(env, hl, ncycles=3, nodes=fake, box={}, verbose=False)
    finally:
        F.extend_cycle = real
    assert seen == [(True, True), (True, True)], \
        "both keeps must reach every chained cycle (got %s)" % (seen,)
    import inspect
    src = inspect.getsource(F.extend_cycle)
    assert 'corridor_keep' in inspect.signature(F.extend_cycle).parameters
    assert 'align_keep' in inspect.signature(F.extend_cycle).parameters
    assert '_mixed_beam(orders, beam)' in src
    # ...and the same diversity at the aim cut (keeping it at the beam alone was measured inert)
    r1src = inspect.getsource(F.roll_candidates)
    assert 'mixed_aims' in inspect.signature(F.roll_candidates).parameters
    assert '_mixed_beam(' in r1src and "abs(t['m']['lat'])" in r1src


def test_the_terminal_reports_the_rule_3_frontier_as_well_as_the_closest(env, hl, box):
    """**`closest` is rule-3-blind, and session 63 measured the two disagreeing.** The same chain under
    two different cycle-3 keeps ends either 31.406 u out with `ready=False` or 33.482 u out at 74 frames
    with `ready=True` -- and the second is the one a frame of herding from a PASS, so a solve that
    reports only the smaller number hides the better plan. `closest_ready` is that second frontier.

    Gated on the invariant rather than on a beam's numbers: whatever it returns must satisfy rule 3,
    must be no closer than `closest` (which is unconstrained), and must be absent only when no state in
    the whole glide was ready."""
    nodes = F.cycle1_nodes(env, hl, box, beam=1)
    tt = F.terminal_targeting(nodes, hl, max_frames=3, beam=12, objective='placement')
    assert 'closest_ready' in tt
    cr, cl = tt['closest_ready'], tt['closest']
    if cr is not None:
        assert F._terminal_ready(cr['run'])['ready'], "closest_ready must satisfy rule 3"
        assert cr['dist'] >= cl['dist'] - 1e-9, "the unconstrained frontier cannot be the worse one"


def test_the_roll_endpoint_alignment_is_the_humans_envelope_not_alives_60_u(env, hl, box):
    """**Session 63: what a terminal recovers is set by LINK's lateral offset from Tetra**, and the
    search admits five times the offset the human ever takes.

    `two_roll.metrics['lat']` already IS that offset (Link's lateral minus Tetra's). It is the push's
    squareness: the plow ejects her along the line from Link's exec Co-centre to her feet, so an
    off-line Link spends the push sideways -- which `objective.push_budget` measures as the whole of the
    s61/s62 shortfall. Across the three cycle-3 endpoints whose terminals were actually run, the
    placement distance the terminal recovers is monotone in it: **16.6 u off -> 39.0 u recovered,
    22.8 -> 14.0, 47.0 -> 7.6**. All seven endpoints reachable at that stage sit 16.6-56.7 u off, i.e.
    entirely outside the envelope the human holds -- and `alive` waves every one of them through.

    Gated here as the CONTAINMENT gap, since reproducing the reachable set costs ~20 minutes of
    search: the human's own envelope, the box read off it, and what `alive` admits instead."""
    from harness.tetrapush import search as S
    rows = S.rollout_recorded(env, upto=45)['rows']
    worst = max(abs(hl.lateral(r['link'][0], r['link'][-1])
                    - hl.lateral(r['tetra'][0], r['tetra'][-1])) for r in rows)
    assert worst < 13.0, "the human's Link-Tetra lateral envelope moved (%.2f u)" % worst
    assert box['max_lat'] == pytest.approx(worst * 1.5, rel=1e-6), \
        "the pursuit box's lateral half is that envelope widened -- they must stay tied"

    # `alive`'s default admits ~5x the human, and it is the ROLL ENDPOINT that goes through it
    hostile = dict(followed=False, lead=-40.0, lat=55.0)
    assert T.alive(hostile), "the gap being stated: a 55 u off-line roll endpoint is 'alive'"
    assert not T.alive(hostile, max_lat=box['max_lat']), "...and outside the human's own envelope"
    assert T.alive(dict(followed=False, lead=-40.0, lat=worst))
    # metrics['lat'] is the LINK-minus-TETRA lateral, not Tetra's own offset from the herd line
    n = F.cycle1_nodes(env, hl, box, beam=1)[0]
    m = T.metrics(n['run'], hl, n['frames'])
    assert m['lat'] == pytest.approx(hl.lateral(n['run'].link.pos_x, n['run'].link.pos_z)
                                     - hl.lateral(n['run'].tx, n['run'].tz))


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


def test_walk_to_entry_is_clean_from_rest_and_flags_a_hot_arrival(env, hl):
    """**Milestone-2b piece 2, gated (session 47): the Link-only WALK to the final-clip entry is
    CLEAN above the bar from a near-rest arrival, and freeze_ok alone is NOT enough.**

    On a SYNTHETIC frozen arrival (`synthetic_frozen_arrival`, not chain-reachable so no bit-confirm)
    at a fixed `centre_feet >= 80`, the same POSITION walks two ways depending on ARRIVAL MOMENTUM:

      * from REST (`momentum='rest'`, the clean route-(a) arrival) the walk drives Link toward the
        entry with Tetra bit-frozen (max displacement 0 u) and never leaves the follow regime;
      * from a hot down-herd EBS (`momentum='ebs'`) the SAME freeze_ok position re-plows Tetra tens
        of u -- the walk is flagged unclean.

    This is the session-47 finding as a gate: the s46 `freeze_ok` (centre_feet >= 80) is positional
    and necessary but not sufficient; the grazing chain must also control the arrival momentum."""
    rest = F.synthetic_frozen_arrival(env, hl, 241, target_cf=88.0, momentum='rest')
    ebs = F.synthetic_frozen_arrival(env, hl, 241, target_cf=88.0, momentum='ebs')

    # both are the SAME freeze_ok position (centre_feet ~ target, above the 80 u bar)
    for placed in (rest, ebs):
        sc = F.separation_scan(placed, hl)
        assert sc['freeze_ok'] and sc['centre_feet'] >= F.CO_RADII_BAR

    import math
    erp = seeds.ENTRY_ROLL_POS
    entry0 = math.hypot(rest['run'].link.pos_x - erp[0], rest['run'].link.pos_z - erp[1])
    wr = F.walk_to_entry(rest, hl)
    assert wr['max_tetra_disp'] < 1e-6 and wr['clean'], "the from-rest walk plowed Tetra"
    assert not wr['followed']                              # stayed inside the follow shell
    assert wr['dist'] < entry0                             # it made real progress toward the entry
    assert wr['dist'] < 12.0                               # to within a few u (facing set by the clip)

    we = F.walk_to_entry(ebs, hl)
    assert we['max_tetra_disp'] > 10.0 and not we['clean'], \
        "freeze_ok position with a HOT arrival must be flagged (momentum is the other half)"


def test_arrival_quality_gates_position_and_momentum(env, hl):
    """**Route a, piece 1 -- the CHEAP arrival gate (session 48).** `arrival_quality` is the monotone
    predictor a grazing-chain candidate is rejected by BEFORE paying `walk_to_entry` / the 800 s
    chain. It must reproduce the session-47 finding as a scalar off the placed state alone: at the
    SAME `freeze_ok` position, a REST arrival is `arrival_ok` and a hot down-herd EBS is not -- the
    momentum half, `approach_rate` (Link's velocity component toward Tetra), is what separates them.

    Gated on the two synthetic frozen arrivals (not chain-reachable, so no bit-confirm -- this gates
    the PREDICTOR's shape + agreement with the expensive walk, not a search result). The fields are
    self-consistent and the verdict agrees with `walk_to_entry`'s measured plow."""
    rest = F.synthetic_frozen_arrival(env, hl, 241, target_cf=88.0, momentum='rest')
    ebs = F.synthetic_frozen_arrival(env, hl, 241, target_cf=88.0, momentum='ebs')
    qr = F.arrival_quality(rest, hl)
    qe = F.arrival_quality(ebs, hl)

    # both are the SAME freeze_ok position; the fields are self-consistent
    for q in (qr, qe):
        assert q['freeze_ok'] and q['centre_feet'] >= F.CO_RADII_BAR
        assert q['co_radii_bar'] == F.CO_RADII_BAR == 80.0
        assert q['deficit'] == pytest.approx(max(0.0, q['co_radii_bar'] - q['centre_feet']))
        assert q['receding'] == (q['approach_rate'] <= 0.0)

    # POSITION is identical; MOMENTUM is what differs and what the verdict keys on
    assert qr['approach_rate'] < 1.0 and qr['receding']          # near-rest / receding
    assert qe['approach_rate'] > 10.0 and not qe['receding']     # closing on Tetra at EBS speed
    assert qr['arrival_ok'] and not qe['arrival_ok']

    # the cheap verdict AGREES with the expensive walk (the predictor it stands in for)
    assert F.walk_to_entry(rest, hl)['clean'] == qr['arrival_ok']
    assert F.walk_to_entry(ebs, hl)['clean'] == qe['arrival_ok']


def test_terminal_grazing_objective_seeks_freeze_ok_without_breaking_placement_mode(env, hl, box):
    """**The re-ranked terminal (session 48), gated structurally.** `terminal_targeting`'s default
    `objective='placement'` (the s44 nearest-coord rank) must be byte-for-byte unchanged, and the new
    `objective='grazing'` must seek an endpoint that is ALSO `freeze_ok` and receding -- the arrival
    `walk_to_entry` needs -- trading a little placement distance for it. Off cheap cycle-1 nodes (far
    from the cluster, but the rank behaviour is what is gated); the grazing winner bit-confirms."""
    nodes = F.cycle1_nodes(env, hl, box, beam=3)
    tt_p = F.terminal_targeting(nodes, hl, max_frames=4, beam=8, objective='placement')
    tt_g = F.terminal_targeting(nodes, hl, max_frames=4, beam=8, objective='grazing')
    bp, bg = tt_p['best'], tt_g['best']

    # placement mode: the rank key IS the placement distance (existing behaviour preserved)
    assert bp['score'] == bp['dist'] == tt_p['dist']
    # grazing mode: an endpoint closer to the bar AND less closing than the deep-contact lander
    qp, qg = F.arrival_quality(bp, hl), F.arrival_quality(bg, hl)
    assert qg['deficit'] <= qp['deficit']
    assert qg['approach_rate'] <= qp['approach_rate']
    assert bg['score'] <= bg['dist']                 # grazing score credits the freeze/momentum terms

    c = F.confirm_plan(env, hl, bg)
    assert c['bit_exact'], "the grazing terminal plan did not replay 0-ULP"
    assert c['talk_safe'] and not bg['run']._follow_warned


def test_place_on_thread_freezes_tetra_on_the_thread_from_an_online_rest_arrival(env, hl):
    """**The clean grazing-arrival recipe, gated (session 49).** Session 49 ran route (a) piece 1 (the
    grazing terminal off the regenerated chain) and found it reaches `freeze_ok` + receding but lands
    Tetra 10.85 u off a coord -- the deep->freeze_ok separation of the hot -23 EBS glide drags her
    ~10 u LATERALLY off the thin thread. The fix is geometric: from a near-REST arrival behind the
    coord a single gentle down-line push ejects Tetra ALONG the line, so she freezes ON-thread.

    Gated on a SYNTHETIC frozen arrival (not chain-reachable, so no bit-confirm -- this gates the
    FREEZE/PLACEMENT physics + the recipe, like the walk gate): from rest, `place_on_thread` reaches
    `arrival_ok` with pd < 1 and ~0 lateral drift, at `centre_feet >= 80`. This makes the session-49
    target concrete: the chain must deliver Link on-line-behind + near-rest, not the hot EBS glide."""
    for cf in (74.0, 76.0, 78.0):
        arr = F.synthetic_frozen_arrival(env, hl, 241, target_cf=cf, lat_off=0.0, momentum='rest')
        # the arrival itself is below the bar (a placement push is still needed to freeze her)
        assert F._centre_feet(arr['run']) < F.CO_RADII_BAR
        p = F.place_on_thread(arr, hl)
        assert p['freeze_ok'] and p['centre_feet'] >= F.CO_RADII_BAR   # the push reaches the bar
        assert p['pd'] < 1.0                                           # ON the thread, not 10.85 off
        assert abs(p['lat_drift']) < 1.0                              # ejected ALONG the line
        assert p['approach'] <= 3.0 and p['arrival_ok']              # near-rest -> arrival_ok
        # the log carries the arrival + the push (bit-confirmable only for a chain-reachable arrival)
        assert p['frames'] == len(p['log'])


def test_decel_place_beats_the_hot_glide_with_an_on_line_near_rest_arrival(env, hl):
    """**Route (a), piece 1 -- the DECELERATING on-line placement approach, gated (session 50).**
    Session 49 proved the hot -23 EBS glide places Tetra on a coord only at deep contact then drags
    her ~10 u LATERALLY off the thin thread as it separates to freeze_ok (the miss is lateral).
    `decel_place` inverts that: kill the EBS (reverse-brake -> Link near-rest up-herd, plow on-line so
    Tetra freezes with ~0 lateral drift), then an on-line proportional forward glide herds her DOWN
    the thread onto the coord, so the residual is a clean sub-unit ALONG-line miss.

    Gated on a SYNTHETIC hot arrival (`synthetic_hot_arrival`, the deep-contact hot state the chain
    terminal produces -- not chain-reachable, so no bit-confirm: this gates the RECIPE's physics, like
    the walk/place gates). Across d_short (chain-endpoint variability) the decel approach must reach
    `arrival_ok` with ~0 lateral drift, and it must land Tetra strictly closer than the raw hot glide
    fed the same arrival. A coarser `backs`/`gains` sweep than the CLI default keeps the gate fast."""
    backs = tuple(float(x) for x in range(44, 78, 4))
    for d_short in (35.0, 55.0):
        hot = F.synthetic_hot_arrival(env, hl, 241, d_short=d_short, feet=64.0)
        # the seed IS the s49 hostile arrival: below the bar (deep contact), hot, closing on Tetra
        assert F._centre_feet(hot['run']) < F.CO_RADII_BAR
        assert F._approach_rate(hot['run']) > 10.0

        raw = F.place_on_thread(dict(run=hot['run'].clone(), log=[], frames=0), hl)
        r = F.decel_place(hot, hl, coord_idx=241, backs=backs, gains=(0.3, 0.2))

        assert r['arrival_ok'], "decel_place did not reach an arrival_ok placement"
        assert r['pd'] < 1.0                                   # ON the coord (along-line residual)
        assert abs(r['lat_drift']) < 0.5                      # ~0 lateral drift (the s49 fix)
        assert r['centre_feet'] >= F.CO_RADII_BAR             # freeze_ok
        assert r['approach'] <= 3.0                            # near-rest
        assert r['pd'] < raw['pd']                             # strictly beats the raw hot glide
        # the log carries the full brake -> glide -> place sequence (bit-confirmable when chain-real)
        assert r['frames'] == len(r['log']) and r['brake_frames'] > 0


def test_homing_place_corrects_an_off_thread_lateral_offset(env, hl):
    """**Route (a), piece 1 -- the HOMING placement terminal, gated (session 51).** `decel_place`
    (s50) herds Tetra straight DOWN the line (lat_drift ~0), so it needs her already on the thread; run
    on the REAL 3-cycle chain endpoint it stalled at pd ~41 because the chain leaves Tetra ~28 u OFF
    the thread laterally (s44's offset), which the on-line herd cannot pull her onto from behind.
    `homing_place` fixes exactly that: it aims Link each frame at a moving standoff BEHIND Tetra
    RELATIVE TO THE COORD, so the plow (which ejects Tetra away from Link's exec centre) pushes her
    TOWARD the coord in along AND lateral.

    Gated on the off-thread `synthetic_hot_arrival(lat_off=+-28)` (the s44 offset; synthetic, so no
    bit-confirm -- gates the recipe physics like decel/walk/place). For BOTH offset signs the homing
    terminal must land Tetra `arrival_ok` ON a coord, freeze_ok, with the lateral offset NULLED (the
    net Tetra lateral move `lat_drift` cancels the seeded ~28 u), where `decel_place`'s on-line herd
    provably cannot (the s50 chain result). A coarse standoff/gain sweep keeps the gate fast."""
    standoffs = tuple(float(x) for x in range(42, 70, 8))
    for lat_off in (28.0, -28.0):
        hot = F.synthetic_hot_arrival(env, hl, 241, d_short=40.0, feet=64.0, lat_off=lat_off)
        # the seed is off-thread: Tetra sits ~|lat_off| u laterally off the genuine thread
        assert abs(hl.lateral(hot['run'].tx, hot['run'].tz)
                   - hl.lateral(env['cyl'][0]['tetra']['pos'][0],
                                env['cyl'][0]['tetra']['pos'][2])) > 20.0

        r = F.homing_place(hot, hl, coord_idx=241, standoffs=standoffs, gains=(0.5, 0.25))

        assert r['arrival_ok'], "homing_place did not reach an arrival_ok placement"
        assert r['pd'] <= 2.0                                  # ON a genuine coord
        assert r['centre_feet'] >= F.CO_RADII_BAR             # freeze_ok
        assert r['approach'] <= 3.0                            # near-rest
        # the lateral offset is corrected: Tetra's net lateral move cancels the seeded offset
        assert abs(r['lat_drift'] + lat_off) < 6.0
        # the log carries the full brake -> homing sequence (bit-confirmable when chain-real)
        assert r['frames'] == len(r['log']) and r['brake_frames'] > 0


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


def test_junction_authority_is_real_and_cannot_be_armed(env, hl, box):
    """**Session 64: session 63's next step, retired by measurement.** It asked to correct Tetra's
    lateral in the JUNCTION rather than the roll, on the premise that Link repositions there in
    single frames. The premise is true; the conclusion is false, and the two halves are what this
    pins so neither gets re-paid.

    AUTHORITY IS REAL. Holding one `junction_alphabet` member for 5 frames spans several units of
    Tetra's `objective.push_corridor` offset -- the same order as `LATERAL_RATE` -- and reaches
    branches far closer to the corridor than the entry, all of them surviving the box, the walls and
    the regime (`junction_authority`).

    AND IT CANNOT BE SPENT: a constant stick NEVER arms. Zero held families produce a gate-passing
    `two_roll.junction_gates` endpoint (measured with the pursuit box on and off), because arming
    needs a VARYING sequence -- clear the +-90 deg cone, then L plus a toward-Tetra stick on the
    delay-1 timing. Steering Tetra and arming Link are mutually exclusive inside the junction, which
    is why a corridor term in `_frontier_score`'s cut is inert (session 63's move 2) and why running
    the shipped `junction_beam` from a corridor-good steered state yields 0 armed endpoints.

    Cheap by construction: one `cycle1_nodes` node, held sticks, no chain."""
    n = F.cycle1_nodes(env, hl, box, beam=1)[0]
    a = F.junction_authority(n, hl, box=box)
    assert a is not None, "the junction must have SOME surviving held branch"

    # the authority half
    assert a['n_alive'] > 20, "too few surviving branches to call it authority (%d)" % a['n_alive']
    assert a['spread'] > 5.0, \
        "the junction's lateral authority over Tetra collapsed (%.2f u over %d frames)" \
        % (a['spread'], a['frames'])
    assert a['per_frame'] > 0.5 * O.LATERAL_RATE, \
        "junction authority %.2f u/f is no longer the order of LATERAL_RATE %.2f" \
        % (a['per_frame'], O.LATERAL_RATE)
    assert a['lo'] < a['entry_off'], \
        "the junction must be able to IMPROVE the corridor offset (%.2f vs entry %.2f)" \
        % (a['lo'], a['entry_off'])

    # the half that retires the move: none of it can be armed
    assert a['armed'] == 0, \
        "a held junction family now ARMS (%d gate-passing) -- session 63's move 2 is back on the " \
        "table and the steer-then-arm probe should be re-run" % a['armed']
    off = F.junction_authority(n, hl, box=None)
    assert off['armed'] == 0, "still zero armed with the pursuit box removed -- the box is not the blocker"
