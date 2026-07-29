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
    node = F.synthetic_hot_arrival(env, hl, 287, d_short=30.0, feet=56.0)
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
