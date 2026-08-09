"""Gates for the PUSH AXIS as a parameter of the plow regime (session 135).

The regime is asserted in three places -- `full_herd.in_pursuit_box`, `two_roll.alive` and
`full_herd._frontier_score` -- and each of them mixes a coordinate-free claim about the pair (Link
is 27-128 u behind her, in contact, pushing) with a claim about WHICH WAY the pair is pushing (down
the herd line). Session 134 measured the second one to be the cap on the whole plan: the
band-keeping cycle-2 beam reaches ``l0`` -51.75, past the -80.4 bar the endgame was reduced to, and
cycle 3 off it returns zero survivors with every child ``outbox`` at generation 1 -- failing ONLY
the direction clauses, at separations that sit dead centre in the human's own recorded plow band.

``reposition.AXIS_PAIR`` drops that one assumption and keeps every measured number. What has to
stay true, and is gated here rather than argued:

  * it is a RE-EXPRESSION, not a widening -- the collapsed fast form is exactly the shipped
    three-clause predicate evaluated about `reposition.pair_line`, over the real states and over a
    swept population;
  * the human is still inside it (`[[search-space-contains-human]]`), which is what says the freed
    box is his regime and not a new one;
  * it admits the states s134 measured it refusing, and refuses nothing the plan is built on -- and
    it is NOT a superset, which is a fact about the corners and belongs in a test, not a docstring;
  * and it is default-OFF at every seam, so every keep calibrated over sessions 63-134 is untouched.
"""
import json
import math
import os
import random
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import full_herd as F                        # noqa: E402
from harness.tetrapush import handoff as HO                         # noqa: E402
from harness.tetrapush import seeds as SD                           # noqa: E402
from harness.tetrapush import two_roll as T                         # noqa: E402
from harness.tetrapush.reposition import (AXIS_HERD, AXIS_PAIR,     # noqa: E402
                                          HerdLine, pair_line)
from harness.tetrapush.steered_reposition import _bearing, _s16     # noqa: E402

FIXTURE = os.path.join(_REPO, 'fixtures', 'courtyard_free_axis_states.json')

#: The bar the whole endgame was reduced to in session 126: what cycle 2 must hand over.
BAR = -80.4


class _Pair(object):
    """A Link/Tetra geometry, which is all a regime predicate reads. Not a `FreeRun`: these clauses
    are about two positions and a facing, and testing them through a simulator would measure the
    simulator."""

    class _Link(object):
        pass

    def __init__(self, lx, lz, tx, tz, facing=0):
        self.link = _Pair._Link()
        self.link.pos_x, self.link.pos_z, self.link.facing = lx, lz, int(facing)
        self.tx, self.tz = tx, tz


@pytest.fixture(scope='module')
def bank():
    """The banked cycle-2 states this is all about (`_notes/s135_free_axis_states.py`).

    Positions at full precision, because a regime verdict is a razor at the band edges
    (`[[full-fp-precision-coords]]`), plus one input log per KIND so the junction case can re-open a
    real node -- a node IS its log."""
    if not os.path.exists(FIXTURE):
        pytest.skip('free-axis states missing: %s' % FIXTURE)
    with open(FIXTURE) as fh:
        return json.load(fh)


@pytest.fixture(scope='module')
def geom():
    env = SD.load_env()
    hl = HerdLine.from_env(env)
    return env, hl, F.pursuit_box(env, hl)


def test_the_bank_is_not_vacuous(bank):
    """Read the population before every equality over it (the s129/s133 lesson): both sides of the
    bar are present, and the box it was measured against is the shipped one."""
    st = bank['states']
    assert len(st) >= 12
    assert sum(1 for d in st if d['l0'] >= BAR) >= 3, 'no state past the bar -- nothing to gate'
    assert sum(1 for d in st if d['l0'] < BAR) >= 3
    assert len({round(d['sep'], 2) for d in st}) >= 4, 'the states collapsed to one separation'
    assert bank['box']['max_delta'] == pytest.approx(3886.5)


def test_the_freed_box_is_the_shipped_box_about_the_pair_axis(geom, bank):
    """**The whole claim: same predicate, different frame.**

    In the pair's own frame ``lead`` is minus the separation and both the lateral and the bearing
    terms are zero by construction, so the three clauses collapse to the human's measured SEPARATION
    band -- which is why `in_pursuit_box` spends one hypot there instead of building a `HerdLine` per
    frame. That collapse is the thing that could rot silently, so it is checked against the full
    three-clause form evaluated about `reposition.pair_line`, on the real states and on a swept
    population that reaches both band edges."""
    _env, hl, box = geom
    for d in bank['states']:
        (lx, lz), (tx, tz) = d['link'], d['tetra']
        r = _Pair(lx, lz, tx, tz)
        assert F.in_pursuit_box(r, hl, box, AXIS_PAIR) is d['in_box_pair']
        assert F.in_pursuit_box(r, pair_line(lx, lz, tx, tz), box) is d['in_box_pair']
    rng = random.Random(7)
    seen = [0, 0]
    for _ in range(50000):
        tx, tz = rng.uniform(-2200.0, -1200.0), rng.uniform(-1400.0, 200.0)
        d, a = rng.uniform(0.5, 200.0), rng.uniform(0.0, 2.0 * math.pi)
        lx, lz = tx + d * math.cos(a), tz + d * math.sin(a)
        r = _Pair(lx, lz, tx, tz)
        fast = F.in_pursuit_box(r, hl, box, AXIS_PAIR)
        assert fast is F.in_pursuit_box(r, pair_line(lx, lz, tx, tz), box)
        seen[fast] += 1
    assert min(seen) > 1000, 'the sweep never straddled the band -- an equality over one answer'


def test_alive_is_the_same_prune_about_the_pair_axis(geom, bank):
    """`two_roll.alive`'s two geometric clauses, re-read in the pair frame: "never overtake her"
    becomes "stay off her", and "stay near the line" is satisfied by construction. Checked against
    `two_roll.metrics` computed on `reposition.pair_line`, not against its collapsed form."""
    _env, hl, _box = geom
    for d in bank['states']:
        (lx, lz), (tx, tz) = d['link'], d['tetra']
        r = _Pair(lx, lz, tx, tz)
        r._follow_warned = False
        pl = pair_line(lx, lz, tx, tz)
        m_herd = T.metrics(r, hl, d['frames'])
        m_pair = T.metrics(r, pl, d['frames'])
        assert T.alive(m_herd, axis=AXIS_PAIR) is T.alive(m_pair, axis=AXIS_HERD)
        assert T.alive(m_herd, axis=AXIS_PAIR) is True          # every banked state is in contact
        assert abs(m_pair['lat']) < 1e-9 and m_pair['lead'] == pytest.approx(-d['sep'])
    # ...and it is still a prune: `followed` is the clause that never depended on a direction
    dead = dict(followed=True, lead=-50.0, lat=0.0, dist=50.0)
    assert not T.alive(dead, axis=AXIS_PAIR) and not T.alive(dead, axis=AXIS_HERD)
    assert not T.alive(dict(dead, followed=False, dist=1.0), axis=AXIS_PAIR), 'overtaken == on top'


def test_the_human_is_inside_the_freed_box_on_every_frame(geom):
    """Containment (`[[search-space-contains-human]]`): the box is read off the recorded human, so a
    re-expression of it that excluded him would be a new constraint wearing his numbers. His own
    separation never leaves 40.4-85.2 u, inside the 26.8-127.8 u band the freed clauses keep."""
    env, hl, box = geom
    assert F.human_in_box(env, hl, box)['ok'], 'the shipped containment broke'
    got = F.human_in_box(env, hl, box, axis=AXIS_PAIR)
    assert got['ok'], 'the human leaves the freed box at frames %s' % (got['outside'],)


def test_the_freed_box_admits_the_states_that_capped_the_plan(bank):
    """**The measured cap, pinned (session 134).**

    Every banked state past the -80.4 bar is REFUSED by the shipped box and admitted by the freed
    one, and every state the shipped box admits is 89-109 u short of the bar. They fail on direction
    alone: separations 58.8-64.6 u, dead centre in the human's own recorded 40.4-85.2 u plow band,
    against herd laterals of -35.5..-58.6 (``max_lat`` 17.99) and bearing deltas of -37..-67 deg
    (``max_delta`` 21.35). Ordinary plow pairs pointing 37-67 deg off the herd line."""
    st = bank['states']
    assert all(d['in_box_pair'] for d in st), 'the freed box refuses a state the plan is built on'
    over = [d for d in st if d['l0'] >= BAR]
    under = [d for d in st if d['l0'] < BAR]
    assert over and not any(d['in_box_herd'] for d in over)
    assert under and all(d['in_box_herd'] for d in under)
    assert max(d['l0'] for d in under) < BAR - 60.0, 'the shipped box is not that far short'
    for d in over:
        assert 40.4 <= d['sep'] <= 85.2, 'not a plow separation -- the claim would be different'
        assert abs(d['herd_lat']) > bank['box']['max_lat']
        assert abs(d['delta_deg']) > bank['box']['max_delta'] * 360.0 / 65536.0


def test_the_freed_box_is_not_a_superset(geom):
    """It is a different frame, not a relaxation, and the corners prove it: a state at the far end of
    the lead band with a full 18 u of herd lateral is 129 u apart, past the separation band the freed
    clauses keep. Measured over the same sweep at ~0.06% -- small, real, and not to be assumed away
    by a session reading "freed" as "strictly more"."""
    _env, hl, box = geom
    lo, hi, lat = box['lead_lo'] * 0.999, box['lead_hi'], box['max_lat'] * 0.99
    hb = hl.bearing_bam()
    # the corner, constructed just inside both edges: Link at the far lead with the full lateral
    lx = hl.dx * lo + hl.px * lat
    lz = hl.dz * lo + hl.pz * lat
    r = _Pair(lx, lz, 0.0, 0.0)
    assert math.hypot(lx, lz) > -box['lead_lo'], 'the corner is inside the band -- claim is empty'
    assert abs(_s16(_bearing((lx, lz), (0.0, 0.0)) - hb)) <= box['max_delta']
    assert F.in_pursuit_box(r, hl, box) and not F.in_pursuit_box(r, hl, box, AXIS_PAIR)
    assert hi < 0.0 and lo < hi, 'the lead band is the negative side -- Link BEHIND her'


def test_the_frontier_second_order_is_the_endgame_axis_when_asked(geom, bank):
    """`_frontier_score`'s first order is the talk cone and never moves -- arming is what a junction
    is for. Its second was "hug the herd line", which has no customer once the direction is freed, so
    with a `handoff.PairFrame` it becomes her ``l0``. Gated as a RANK change on the banked states,
    where the two orders provably disagree: the flattest state there is 100 u the wrong side of the
    bar and the one that crosses it is 49 u off Tetra's lateral."""
    _env, hl, _box = geom
    pf = HO.PairFrame()
    a, b = F._frontier_score(hl), F._frontier_score(hl, pf)
    nodes = []
    for d in bank['states']:
        (lx, lz), (tx, tz) = d['link'], d['tetra']
        # facing straight away from her, so the cone order ties and the second one decides
        nodes.append(dict(run=_Pair(lx, lz, tx, tz,
                                    facing=_s16(_bearing((lx, lz), (tx, tz)) + 0x8000))))
    assert {a(n)[0] for n in nodes} == {0}, 'the cone order is not tied -- it would decide alone'
    assert [a(n)[0] for n in nodes] == [b(n)[0] for n in nodes], 'the cone order moved'
    assert [b(n)[1] for n in nodes] == [-HO.tetra_lateral(pf, (n['run'].tx, n['run'].tz))
                                        for n in nodes]
    assert min(nodes, key=a) is not min(nodes, key=b), 'the two orders never disagree'
    assert HO.tetra_lateral(pf, (min(nodes, key=b)['run'].tx, min(nodes, key=b)['run'].tz)) >= BAR


def test_the_axis_is_default_off_at_every_seam():
    """The knob is additive: every predicate and every stage defaults to the shipped herd frame, so
    nothing calibrated over sessions 63-134 moves unless a caller asks. Read off the signatures,
    because a default that drifts is exactly the failure mode a docstring cannot catch (s133: a stale
    default left the campaign's dominant stage on the Python step for two sessions)."""
    import inspect
    assert inspect.signature(F.in_pursuit_box).parameters['axis'].default == AXIS_HERD
    assert inspect.signature(F.human_in_box).parameters['axis'].default == AXIS_HERD
    assert inspect.signature(F.junction_beam).parameters['axis'].default == AXIS_HERD
    assert inspect.signature(F.junction_beam).parameters['pf'].default is None
    assert inspect.signature(F.junction_quality).parameters['axis'].default == AXIS_HERD
    assert inspect.signature(F.roll_probe).parameters['axis'].default == AXIS_HERD
    assert inspect.signature(F.roll_candidates).parameters['axis'].default == AXIS_HERD
    assert inspect.signature(F._frontier_score).parameters['pf'].default is None
    assert inspect.signature(T.alive).parameters['axis'].default == AXIS_HERD
    assert inspect.signature(T.junction_gates).parameters['axis'].default == AXIS_HERD
    assert inspect.signature(F.extend_cycle).parameters['free_axis'].default is False
    # ...and the stage wires ONE axis into all three of its prune sites, not two of them
    src = inspect.getsource(F.extend_cycle)
    assert 'jaxis = AXIS_PAIR if free_axis else AXIS_HERD' in src
    assert src.count('axis=jaxis') == 3, 'the junction, the screen and the roll stage'


@pytest.mark.slow
def test_the_shipped_box_kills_the_band_keeping_state_at_generation_1(bank):
    """**The refusal itself, re-run on a real node** -- the one case here that steps the simulator.

    Session 134's cycle 3 off these states returned zero survivors with every child ``outbox`` at
    generation 1, which is a claim about the PRUNE and needs only two generations to test. On the
    herd frame the node's own shared frame fails the box, so the whole alphabet dies without a single
    child being materialised; freed, the children exist and are judged by the junction gates.

    ``slow`` because it expands a real alphabet (the two-minute rule); it still runs under
    ``pytest -m slow``."""
    seed = next((d for d in bank['states'] if 'log' in d and not d['in_box_herd']), None)
    assert seed is not None and seed['l0'] >= BAR
    env = SD.load_env()
    hl = HerdLine.from_env(env)
    box = F.pursuit_box(env, hl)
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    for d in seed['log']:
        run.step(d)
    assert run.link.pos_x == seed['link'][0] and run.tx == seed['tetra'][0], 'seed rebuilt wrong'
    node = dict(run=run, log=list(seed['log']), frames=seed['frames'], jf=0)
    stock, freed = {}, {}
    F.junction_beam(node, hl, box, max_frames=2, beam=8, ess_step=8, aim_step=64, dead=stock)
    F.junction_beam(node, hl, box, max_frames=2, beam=8, ess_step=8, aim_step=64, dead=freed,
                    axis=AXIS_PAIR)
    assert set(stock) == {'outbox'} and stock['outbox'] > 1, stock
    assert 'outbox' not in freed or freed['outbox'] < stock['outbox']
    assert sum(v for k, v in freed.items() if k != 'outbox') > 0, 'freed produced no child at all'
