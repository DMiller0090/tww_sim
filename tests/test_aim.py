"""Gates for `harness/tetrapush/aim.py` -- the handoff AIM (session 67).

The endgame's shortfall is directional (s63), and sessions 63-66 read that direction as a lateral
DEFICIT. It is not: the target thread runs nearly parallel to the approach, so what a placement needs
is the push pointed inside a ~2 deg window, and the s66 handoffs aim 10-46 deg steeper than that.
Three properties hold that model up, gated in the order the rest depends on them:

  1. **The push law predicts Tetra's next position BIT-EXACTLY off the pre-step state** -- so an aim
     is an exact quantity, not a proxy, and Tetra's side of a placement needs no stepping.
  2. **The aim window is a razor, and the miss prices it in u** -- the geometry that makes squareness
     the binding constraint rather than lateral magnitude.
  3. **The terminal has no authority over Tetra** -- the input pipeline's 2-frame delay means a whole
     generation of the terminal alphabet moves her identically, which is why the endgame is decided
     at the cycle-3 endpoint and every terminal rank measured inert.
"""
import math

import pytest

from harness.tetrapush import seeds, full_herd as F, objective as O, aim as A
from harness.tetrapush import search as S, two_roll as T
from harness.tetrapush.reposition import HerdLine


@pytest.fixture(scope='module')
def env():
    return seeds.load_env()


@pytest.fixture(scope='module')
def hl(env):
    return HerdLine.from_env(env)


@pytest.fixture(scope='module')
def thread(hl):
    return O.placement_thread(hl, seeds.load_placements()[0])


def test_push_step_predicts_the_next_tetra_bit_exact(env, hl):
    """**0-ULP** (`[[zero-ulp-tests-only]]`): ``f32(Tetra + (CO_RADII_BAR - centre_feet)/2 *
    unit(Tetra - exec_centre))`` is `from_f0.FreeRun.step`'s next Tetra, bit for bit, on every
    contact frame -- and exactly zero at or past the bar.

    Whatever stick is delivered: the input pipeline acts 2 frames late, so the frame's push is
    already decided by the state. That is what makes `aim.aim_miss` exact for the next frame."""
    from tww_sim.land.plan_land._primitives import stick_for_bearing
    hb = hl.bearing_bam()
    contact = frozen = 0
    for feet in (48.0, 56.0, 64.0):
        node = F.synthetic_hot_arrival(env, hl, 287, d_short=30.0, feet=feet)
        for bear_off, msd in ((0, 1.0), (0x2000, 0.5), (0x8000, 0.35)):
            r = node['run'].clone()
            for _ in range(4):
                p = A.push_step(r)
                sx, sy = stick_for_bearing((hb + bear_off) & 0xFFFF, int(r.csangle), msd=msd)
                r.step(dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                            substickX=T.CSTICK_NEUTRAL, substickY=0))
                assert p['x'] == r.tx and p['z'] == r.tz, (
                    "push_step is not bit-exact at centre_feet %.4f: predicted (%r, %r) got (%r, %r)"
                    % (p['centre_feet'], p['x'], p['z'], r.tx, r.tz))
                if p['centre_feet'] >= A.CO_RADII_BAR:
                    assert p['mag'] == 0.0
                    frozen += 1
                else:
                    assert p['mag'] > 0.0
                    contact += 1
    assert contact >= 12 and frozen >= 1, (contact, frozen)


def test_the_aim_window_is_a_razor_and_the_miss_prices_it(env, hl, thread):
    """The thread sits 12.2 deg off the herd axis and the approach comes in 13-14 deg off it, so the
    directions that reach a 47.6 u segment span ~2 deg at the s66 handoff range -- and `aim_miss`
    reports that as a distance in u, comparable to `objective.PLACEMENT_BAND`.

    Both halves are asserted structurally (no literal from the beam): the window narrows as the
    approach lengthens, an aim inside it misses by less than the band, and one a few degrees steeper
    misses by many u. The corollary a plan lives by -- the LATER the handoff, the wider the window --
    is why the escape has to be handed a state ~44 u out and not 70."""
    assert thread['deg_off_axis'] > 5.0
    ta, tl = 881.6, 21.19                       # the s66 handoff, in herd coords
    w_near = A.aim_window(ta + 40.0, tl, thread)
    w_far = A.aim_window(ta, tl, thread)
    assert math.degrees(w_far['width']) < 2.5, math.degrees(w_far['width'])
    assert w_far['width'] < w_near['width']     # the further out, the narrower

    (p, q) = A._thread_ends(thread)
    mid = 0.5 * (w_far['lo'] + w_far['hi'])
    for (bearing, want) in ((mid, 'in'), (mid - math.radians(12.0), 'steep'),
                            (mid + math.radians(12.0), 'shallow')):
        u = (math.cos(bearing), math.sin(bearing))
        miss, t, _s = A._ray_segment_miss((ta, tl), u, p, q)
        if want == 'in':
            assert miss <= O.PLACEMENT_BAND, (miss, math.degrees(bearing))
            assert t > 40.0                     # she must still be pushed the distance
        else:
            assert miss > 5.0, (want, miss)


def test_the_aim_and_the_centre_lateral_are_the_same_statement(env, hl, thread):
    """`centre_lat_needed` inverts the aim: moving Link's exec centre to the lateral it names puts
    the ejection bearing inside `aim_window`. Asserted by construction on a real arrival -- the
    algebra, not a rollout -- because that number is what an upstream keep would have to buy."""
    node = F.synthetic_hot_arrival(env, hl, 287, d_short=30.0, feet=56.0)
    run = node['run']
    cl = A.centre_lat_needed(run, hl, thread)
    ta, tl = hl.along(run.tx, run.tz), hl.lateral(run.tx, run.tz)
    w = A.aim_window(ta, tl, thread)
    for lat in (cl['lat_lo'], cl['lat_hi'], 0.5 * (cl['lat_lo'] + cl['lat_hi'])):
        bearing = math.atan2(tl - lat, cl['gap'])         # the aim from a centre at that lateral
        assert w['lo'] - 1e-9 <= bearing <= w['hi'] + 1e-9, (math.degrees(bearing),
                                                             math.degrees(w['lo']),
                                                             math.degrees(w['hi']))
    assert cl['gap'] > 0.0                                # the centre is behind her


@pytest.mark.slow
def test_the_terminal_alphabet_cannot_move_tetra_for_two_frames(env, hl):
    """**Why every terminal rank measured inert.** The input pipeline acts 2 frames late, so a whole
    generation of `full_herd._terminal_alphabet` (290 sticks x L) puts Tetra in the SAME place for
    two frames -- spread exactly 0. On the real s66 cycle-3 endpoint it holds for FOUR frames,
    because by then the actors have separated and no stick re-establishes contact; that part is bed
    geometry, so only the universal two are gated here.

    The consequence is structural: the endgame is decided at the cycle-3 endpoint, and the only
    input sequence with authority left is the escape's own conversion (`away_walk`)."""
    node = F.synthetic_hot_arrival(env, hl, 287, d_short=30.0, feet=56.0)
    walls = O.courtyard_walls()
    live = [node['run']]
    for f in range(2):
        nxt = []
        for r0 in live:
            for (sx, sy) in F._terminal_alphabet(r0, hl):
                for l in (0, 1):
                    r = r0.clone()
                    r.step(dict(stickX=sx, stickY=sy, buttons=S.PAD_L if l else 0,
                                triggerL=255 if l else 0, substickX=T.CSTICK_NEUTRAL,
                                substickY=0))
                    if F.frame_in_model(r, walls):
                        nxt.append(r)
        assert len(nxt) > 50
        assert len({(r.tx, r.tz) for r in nxt}) == 1, (
            "frame %d: %d distinct Tetra positions -- the 2-frame input delay is not holding"
            % (f + 1, len({(r.tx, r.tz) for r in nxt})))
        live = nxt[:24]


def test_a_rolls_lateral_outcome_is_its_aim_on_the_humans_own_rolls(env, hl):
    """**Straightness is the ROLL ENTRY's squareness, not the roll's stick** -- gated on the recorded
    human (`[[search-space-contains-human]]`: he is the control, and his window is tracked fixture
    data, so this needs no beam).

    The push law integrates: Tetra's displacement over a contact phase is the sum of its per-frame
    ejections, so the direction a roll carries her IS the mean of its aims. What makes that a usable
    KEEP rather than a tautology is that the aim does not swing much inside a roll -- so the entry
    state predicts the outcome. Both halves are asserted on both recorded rolls.

    Also pinned: the aim is set by Link's exec CENTRE, and his FEET are a different quantity (they
    disagree by ~9 u of lateral at the s66 roll-2 entry, which is why an align keep on the feet
    measures inert)."""
    from tww_sim.land.land import FRONT_ROLL
    dtm = seeds.dtm_input_at(env)
    run = seeds.make_freerun(env)
    run.pre_seed_input(dtm(0))
    rows = []
    for k in range(1, 45):
        run.step(dtm(k))
        ev = A.eject_unit(run, hl)
        rows.append(dict(state=run.link.state,
                         ta=hl.along(run.tx, run.tz), tl=hl.lateral(run.tx, run.tz),
                         bear=None if ev is None else math.degrees(math.atan2(ev[1], ev[0])),
                         feet_lat=(hl.lateral(run.link.pos_x, run.link.pos_z)
                                   - hl.lateral(run.tx, run.tz))))
    spans, cur = [], None
    for i, r in enumerate(rows):
        if r['state'] == FRONT_ROLL and cur is None:
            cur = i
        elif r['state'] != FRONT_ROLL and cur is not None:
            spans.append((cur, i - 1))
            cur = None
    if cur is not None:                                 # the window ends mid-roll
        spans.append((cur, len(rows) - 1))
    assert len(spans) >= 2, spans                       # the recorded window's two rolls
    for (s, e) in spans[:2]:
        pre = rows[max(0, s - 1)]
        da = rows[e]['ta'] - pre['ta']
        dl = rows[e]['tl'] - pre['tl']
        travel = math.degrees(math.atan2(dl, da))
        bs = [r['bear'] for r in rows[s:e + 1] if r['bear'] is not None]
        assert len(bs) > 8 and math.hypot(da, dl) > 50.0
        assert abs(sum(bs) / len(bs) - travel) < 4.0, (        # the mean aim IS the travel
            "roll %s: mean aim %.2f vs travel %.2f" % ((s, e), sum(bs) / len(bs), travel))
        assert abs(pre['bear'] - travel) < 15.0, (             # and the entry predicts it
            "roll %s: entry aim %.2f vs travel %.2f" % ((s, e), pre['bear'], travel))
        # the centre's lateral and the feet's are NOT the same quantity
        assert abs(pre['bear'] - math.degrees(math.atan2(-pre['feet_lat'], 55.0))) > 1e-6


def test_handoff_target_is_the_coord_minus_the_escape(env, hl, thread):
    """The chain's target is NOT a coord: the escape's conversion frames push Tetra ~44 u further, so
    the state it must be handed is the thread point minus the measured residual (`handoff_target`),
    and `landing_miss` is the exact verdict that inverts it.

    Gated as a round trip on the real escape probed off an on-line arrival: aim the handoff at
    `handoff_target` and the landing lands on the thread; aim it at the coord itself and it does
    not."""
    from harness.tetrapush import away_walk as AW
    # ``snap_camera``: a relocated bed has no roll to have paid the escape's camera bill (s73), so the
    # bed fabricates the camera a real arrival brings -- else nothing fires and there is no residual
    node = F.synthetic_hot_arrival(env, hl, 287, d_short=30.0, feet=56.0, snap_camera=True)
    res = AW.probe(node['run'], hl)
    assert res is not None and AW.fires(res)
    resid = (res['resid_along'], res['resid_lat'])
    assert math.hypot(*resid) > 20.0                      # the escape is a placement phase
    tgt = A.handoff_target(thread, resid)
    (p, _q) = A._thread_ends(thread)
    assert tgt[0] < p[0] - 20.0                           # up-herd of the near end by the residual
    # the round trip: a handoff AT the target lands on the thread, one at the coord overshoots
    lm_target = math.hypot(tgt[0] + resid[0] - p[0], tgt[1] + resid[1] - p[1])
    lm_coord = math.hypot(resid[0], resid[1])
    assert lm_target <= 1e-9 and lm_coord > 20.0
    # and the exact form agrees with itself on the real state
    lm = A.landing_miss(node['run'], hl, thread, resid)
    sp = A.handoff_spec(node['run'], hl, thread, 69, resid=resid)
    assert sp['exact'] and sp['landing_miss'] == lm['miss']
    assert sp['aim_ok'] == (lm['miss'] <= sp['band'])


def test_handoff_rows_are_the_targets_the_herd_must_deliver_and_price_the_overshoot(env, hl, thread):
    """**The rank-side twin of `handoff_corridor`** (session 70): the whole placement set translated
    up-herd by the escape's measured residual, so a rank measures the distance to the state the HERD
    must deliver instead of to the coord the ESCAPE lands on.

    Two things are gated. That it is an exact TRANSLATION -- the thread rebuilt from the shifted rows
    keeps its slope, length, off-axis angle and chord deviation, its along ends move by exactly
    ``resid_along`` and its laterals by exactly ``resid_lat``, and its near end IS `handoff_target`
    (the two must agree or a plan would be ranked against one target and scored against another).

    And WHY a rank needs it: the thread is 47.6 u of along slack, so `objective.thread_frames` charges
    NOTHING for along anywhere inside it -- the session-69 cycle-3 endpoints sat at along 947, 53 u past
    the handoff target, and the real thread priced that as CHEAPER than arriving on target (2.34 frames
    against 3.35). It is not cheaper: it is ~4 frames of push spent going somewhere the plan then has to
    come back from, and it is the whole of that run's 78-80 frames against a 75-frame budget. Against
    the shifted thread the same two states price 0.54 and 0.00."""
    resid = (43.65, 5.47)                       # the measured atom (`handoff_corridor`, s69)
    rows = seeds.load_placements()[0]
    sh = O.placement_thread(hl, A.handoff_rows(rows, hl, resid))
    # an exact translation in herd coordinates, shape untouched
    assert abs((thread['along_lo'] - sh['along_lo']) - resid[0]) < 1e-9
    assert abs((thread['along_hi'] - sh['along_hi']) - resid[0]) < 1e-9
    assert abs((thread['lat_at'](thread['along_lo']) - sh['lat_at'](sh['along_lo'])) - resid[1]) < 1e-9
    for f in ('slope', 'length', 'deg_off_axis', 'max_chord_dev'):
        assert abs(thread[f] - sh[f]) < 1e-9, f
    # ...and it agrees with the single-point form, which the chain's keeps ride
    tgt = A.handoff_target(thread, resid)
    assert abs(tgt[0] - sh['along_lo']) < 1e-9
    assert abs(tgt[1] - sh['lat_at'](sh['along_lo'])) < 1e-9

    # the pricing: on the shifted line, arriving ON target is free and the s69 overshoot is not --
    # while the real thread has it the other way round
    def price(along, th):
        return O.thread_frames(along, sh['lat_at'](min(along, sh['along_hi'])), th)

    on, past = price(tgt[0], sh), price(947.4, sh)
    assert on < 1e-9 and past > 0.3
    assert price(947.4, thread) < price(tgt[0], thread) - 0.5      # the inversion it removes


def test_the_handoff_corridor_is_a_different_ask_than_the_coord_corridor(env, hl, thread):
    """**The mid-chain bias the chain was carrying** (session 69): every keep that reads a corridor was
    reading the line to the nearest COORD, but the state the chain has to deliver is that coord minus
    the escape's residual, so the two lines ask for different aims -- and the difference is of the
    same order as the whole `aim_window` the plan must hit at the end.

    Gated as the comparison that makes it worth correcting, in the units the window is measured in
    (degrees of asked-for aim from an on-line Tetra), plus the two properties that keep it honest: the
    residual is MEASURED (the corridor reports the atom's own numbers, and reports ``ok=False`` rather
    than guessing if the atom does not fire), and the ``feet`` depth is a knob inside the noise --
    moving it across the whole measured handoff band changes the ask by a small fraction of what
    ignoring the escape does.

    The last pair of assertions is what riding the right line BUYS, and it reframes the razor: the
    0.53 deg window belongs to WHERE the s66 handoff sat (along 881.6, lat +21.19 -- short AND
    off-line, so the 47.6 u segment is seen nearly end-on and the 0.68 deg bias alone overshoots it),
    while from the handoff target itself the segment subtends ~10 deg. `aim_window`'s width is a
    subtended angle and NOT monotone in the lateral offset (10.04 deg on line, 3.25 at +10, 3.18 at
    +20, 8.37 at +30), so these are two measured points and a trend would be wrong to assert."""
    cor = A.handoff_corridor(env, hl, thread, feet=56.0)
    pc = O.push_corridor(hl)
    assert cor['ok'] and cor['resid'] is not None
    # the target is the coord pulled back by the escape, and the line still starts at Tetra's start
    assert cor['target'][0] < pc['target'][0] - 20.0
    assert abs(cor['lat_at'](0.0)) < 1e-12 and abs(pc['lat_at'](0.0)) < 1e-12
    assert cor['offset'](cor['target'][0], cor['target'][1]) < 1e-9

    def ask(c, along):                       # the aim an on-line Tetra is being told to point at
        return math.degrees(math.atan2(c['target'][1], c['target'][0] - along))

    # the divergence, at the cycle-1 exit and at cycle-2 range (measured 0.46 / 0.68 deg), and it
    # GROWS as the plan closes -- the wrong way round for a bias to be left in
    diffs = [abs(ask(pc, a) - ask(cor, a)) for a in (275.8, 500.0, 700.0)]
    assert min(diffs) > 0.4
    assert diffs[0] < diffs[1] < diffs[2]
    # ...while the depth inside the handoff band is immaterial next to that
    shallow = A.handoff_corridor(env, hl, thread, feet=52.0)
    assert abs(ask(shallow, 500.0) - ask(cor, 500.0)) < 0.1 * diffs[1]
    # what riding the right line BUYS: the razor belongs to WHERE the handoff sits, not to the thread
    # (two measured points, not a trend -- the width is non-monotone in the offset; see the docstring)
    on = math.degrees(A.aim_window(*cor['target'], thread=thread)['width'])
    s66 = math.degrees(A.aim_window(881.6, 21.19, thread)['width'])
    assert s66 < diffs[1]
    assert on > 8.0 and on > 10.0 * s66


def test_the_corridor_is_a_ONE_POINT_line_and_thread_miss_is_what_the_escape_needs(env, hl, thread):
    """**Why the endpoint keep could not buy squareness at an arrival that was not on target**
    (session 71), and the axis that replaces it.

    `handoff_corridor` is a line from the origin through ONE point -- the thread's near end minus the
    escape's residual -- so `full_herd.roll_probe`'s ``off``, the quantity ``square_keep`` ranks on,
    is the distance from that line. The TARGET, though, is a segment whose lateral falls 0.215 u per u
    of along, **78x** the corridor's own slope, so the two agree only where the arrival is exactly on
    target. Past it the corridor's lateral ask is wrong at the thread's slope, and a roll is a ~223 u
    atom that cannot stop short, so every arrival the last cycle chooses between is past it: the
    session-70 survivors sat at ``over`` +18.8 (the squarest one measured) and +55.6, where the
    corridor is wrong by 4.11 u and 10.18 u against a `objective.PLACEMENT_BAND` of 1.0.

    Short of the target the two DO agree, because the near end clamps the escape's landing -- which is
    why this never showed up while the chain was undershooting.

    `thread_miss` is the correction and it is not a combination of anything: it computes the landing
    point and measures it against the segment, exact given the residual. Gated against `landing_miss`
    (one implementation, so a keep and the verdict it predicts cannot disagree by arithmetic)."""
    cor = A.handoff_corridor(env, hl, thread, rows=seeds.load_placements()[0])
    ra, rl = cor['resid']
    lo, hi = thread['along_lo'], thread['along_hi']
    th_slope = (thread['lat_at'](hi) - thread['lat_at'](lo)) / (hi - lo)
    assert abs(th_slope) > 50.0 * abs(cor['slope'])

    def needs(along):        # the lateral an arrival HERE must have for the escape to land on line
        return thread['lat_at'](min(hi, max(lo, along + ra))) - rl

    # on target the two agree; short of it they still agree (the near end clamps); past it they do not
    assert abs(cor['lat_at'](cor['target'][0]) - needs(cor['target'][0])) < 1e-9
    assert abs(cor['lat_at'](860.0) - needs(860.0)) < 0.2
    over18 = abs(cor['lat_at'](912.7) - needs(912.7))
    over55 = abs(cor['lat_at'](949.5) - needs(949.5))
    assert over18 > 4.0 * O.PLACEMENT_BAND and over55 > 2.0 * over18

    # ...and the correction: `thread_miss` IS `landing_miss`, so the keep rides the verdict's own line
    nd = F.synthetic_hot_arrival(env, hl, min(seeds.load_placements()[0],
                                              key=lambda p: hl.along(p['x'], p['z']))['idx'])
    run = nd['run']
    lm = A.landing_miss(run, hl, thread, cor['resid'])
    tm = A.thread_miss(hl.along(run.tx, run.tz) + ra, hl.lateral(run.tx, run.tz) + rl, thread)
    assert lm['miss'] == tm['miss'] and lm['seg_s'] == tm['seg_s']
