"""Gates for the ``l0`` axis at the SCREEN and the POOL (session 134).

Session 126 reduced the whole remaining endgame to one number -- cycle 2 must hand over
``l0 >= -80.4``, her offset from the clip roll's approach line (`handoff.tetra_lateral`), against
the -183.41 it delivers -- and every measure of it lived at `full_herd.extend_cycle`'s
``handoff_keep``, which sits at the ENDPOINT and so can only reorder a survivor set the per-aim
screen already fixed (session 107's standing warning). ``l0`` is ONE DOT PRODUCT on a Tetra the
rollout already produced, so it is affordable at both cuts upstream of that, and session 134 moved
it there.

What has to stay true, and is gated here rather than trusted:

  * the column is ADDITIVE -- without a `handoff.PairFrame` the screen answers exactly as it did,
    field for field, so every keep calibrated before this change is untouched;
  * ``l0_max`` is the MAXIMUM over the surviving fan, not the last or the best-by-another-axis
    roll, and it agrees with the per-roll ``collect`` sink it is aggregated from;
  * the pool share is a SHARE -- inert when unasked, and when asked it reaches endpoints the
    flatness prefix structurally never shows the screen;
  * the herd-coordinate decomposition of ``l0`` is exact, since it is what says the axis is worth
    asking for at all (a unit of lateral buys 2.07x what a unit of down-herd buys).

Non-vacuity is asserted before every equality (the session-129/133 lesson: a thinned beam makes
every gate pass on an empty population).
"""
import json
import math
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import full_herd as F               # noqa: E402
from harness.tetrapush import handoff as HO                # noqa: E402
from harness.tetrapush import seeds as SD                  # noqa: E402
from harness.tetrapush.reposition import HerdLine          # noqa: E402

FIXTURE = os.path.join(_REPO, 'fixtures', 'courtyard_l0_screen_nodes.json')

#: The CONTACT fan, which is the one this screen is used on and the only one these seeds survive:
#: the roll-kernel fixture's endpoints all die ``followed`` (>230 u) under `roll_probe`'s prunes.
PROBE = dict(step=1, fan_center='tetra', half_window=0x600)

#: The herd-frame decomposition of ``l0``, pinned from `repr`: the endgame's axis is 64.25 deg off
#: the herd line, so down-herd buys 0.43 of it where the lateral buys 0.90.
D_ALONG = 0.4344838355514977
D_LAT = 0.900679541214783


def _bank():
    if not os.path.exists(FIXTURE):
        pytest.skip('l0-screen seeds missing: %s' % FIXTURE)
    with open(FIXTURE) as fh:
        return json.load(fh)


@pytest.fixture(scope='module')
def bank():
    """The banked artefact: four rolling endpoints, each with its probe record and every roll.

    The fan is the cost here and it is irreducible -- the contact screen at ``step=1`` is what these
    endpoints survive on (``step=4`` drops two of them to zero aims), and re-deriving it four times
    over is 6 s. So the AGGREGATION gates read the artefact and the RE-DERIVATION is one ``slow``
    case, which is what the two-minute rule asks for."""
    return _bank()


@pytest.fixture(scope='module')
def live():
    """The same four endpoints rebuilt as screen inputs (a node IS its log). No probing here."""
    rec = _bank()
    env = SD.load_env()
    hl = HerdLine.from_env(env)
    out = []
    for nd in rec['nodes']:
        run = SD.make_freerun(env)
        run.pre_seed_input(SD.dtm_input_at(env)(0))
        for d in nd['log']:
            run.step(d)
        assert int(run.csangle) == int(nd['csangle']), 'seed rebuilt to a different camera'
        out.append(dict(run=run, frames=nd['frames'], jf=nd['jf'], log=nd['log'], want=nd))
    return env, hl, out, HO.PairFrame()


def test_the_bank_is_not_vacuous(bank):
    """Every gate below reads this artefact, so what it contains is asserted first: four endpoints,
    three junction-frame bands, and a fan with a real choice in it (the s129/s133 lesson -- a thinned
    population makes every equality pass on nothing)."""
    nodes = bank['nodes']
    assert len(nodes) >= 4
    assert len({nd['jf'] for nd in nodes}) >= 3, 'the seeds collapsed to one junction-frame band'
    for nd in nodes:
        assert len(nd['rolls']) == int(nd['probe']['n']) >= 2
        assert len({r['aim'] for r in nd['rolls']}) == len(nd['rolls'])


@pytest.mark.slow
def test_the_bank_is_still_what_the_screen_produces(live, bank):
    """**The artefact re-derived, 0-ULP.** Everything else here is arithmetic over the bank; this is
    the one case that re-runs the fan, and without it the bank could drift from the code silently.

    ``slow`` because it re-runs a fan at test time (6 s), which is exactly the shape the two-minute
    rule sends here -- it still runs under ``pytest -m slow``."""
    _env, hl, ends, pf = live
    for e in ends:
        nd = e['want']
        sink = []
        p = F.roll_probe(e, hl, pf=pf, collect=sink, **PROBE)
        assert p is not None
        assert {k: repr(v) for k, v in sorted(p.items())} == nd['probe']
        assert [{k: repr(r[k]) for k in row} for r, row in zip(sink, nd['rolls'])] == nd['rolls']
        assert repr(F.roll_probe(e, hl, **PROBE)) is not None
        bare = F.roll_probe(e, hl, **PROBE)
        assert {k: repr(v) for k, v in sorted(bare.items())} == nd['probe_bare']


def test_the_l0_column_is_additive(live, bank):
    """**Without a `PairFrame` the screen is byte-for-byte what it was.**

    The column rides on a rollout that already happened, so turning it on may not perturb a single
    field the existing keeps read -- ``rate``, ``off``, ``arrive``, ``land`` and the cloud pair are
    what sessions 68-120 calibrated, and a screen that answered differently with the axis on would
    invalidate all of them silently.

    Run LIVE on one seed rather than off the bank, because this is a claim about two code paths and
    two banked dicts agreeing would not be one. The live half runs on a DECIMATED fan (``step=4``):
    additivity needs one surviving roll, not a populated one, and the full fan costs 4x for nothing
    this case asserts. The other three seeds are covered by the banked pair at full resolution,
    which the ``slow`` case re-derives."""
    _env, hl, ends, pf = live
    cheap = dict(PROBE, step=4)
    a = F.roll_probe(ends[0], hl, **cheap)
    b = F.roll_probe(ends[0], hl, pf=pf, **cheap)
    assert a is not None and b is not None
    assert a['l0_max'] is None and b['l0_max'] is not None
    for k in a:
        if not k.startswith('l0_'):
            assert a[k] == b[k], k
    # ...and the same equality over every banked seed, which is where the population is
    for nd in bank['nodes']:
        for k, v in nd['probe_bare'].items():
            if not k.startswith('l0_'):
                assert nd['probe'][k] == v, k
        assert nd['probe_bare']['l0_max'] == 'None' and nd['probe']['l0_max'] != 'None'


def test_l0_max_is_the_maximum_over_the_surviving_fan(bank):
    """**The aggregate is the MAX, and it agrees with the sink it came from.**

    Every other axis on this screen minimises (``off``, ``arrive``, ``land``, ``cloud_bound``); this
    one maximises, because the genuine side of the approach line is the POSITIVE one. An aggregate
    that silently took the first or the last surviving roll would still look like a plausible
    number, and the keep reading it would rank on noise."""
    for nd in bank['nodes']:
        sink = [{k: float(r[k]) for k in ('l0', 'off', 'along')} for r in nd['rolls']]
        assert nd['probe']['l0_max'] == repr(max(r['l0'] for r in sink))
        # ...and the companions are the DELIVERING roll's own, not another aim's
        win = max(sink, key=lambda r: r['l0'])
        assert nd['probe']['l0_off'] == repr(win['off'])
        assert nd['probe']['l0_along'] == repr(win['along'])
        # the max is a real choice here, not a one-element fan
        assert min(r['l0'] for r in sink) < max(r['l0'] for r in sink)


def test_l0_max_reads_the_delivered_tetra(bank):
    """The column is `handoff.tetra_lateral` of the Tetra the roll actually left, not the endpoint's.

    Session 126's trap is that an endpoint's own ``l0`` does not predict its roll's (two cycle-2
    nodes at an identical -183.41 reach -27.10 and +19.65), which is exactly why the screen has to
    fire the roll and the pool share may only ever be a share."""
    for nd in bank['nodes']:
        entry = float(nd['entry_l0'])
        assert float(nd['probe']['l0_max']) > entry, 'the roll must CARRY her, not report the entry'
        # and it is the roll that does it, by 78-116 u -- not a rounding difference
        assert float(nd['probe']['l0_max']) - entry > 50.0


def test_the_pool_share_is_inert_unless_asked_and_reaches_past_the_prefix():
    """**The pool decides what the screen ever sees, and it was blind to this axis.**

    Measured off a real cycle-1 parent, 250 of **4292** endpoints are screened (5.8%), chosen by
    flatness and junction-frame band. Gated as pure selection with no simulator -- the level both
    behaviours live at -- so a future session cannot drop the share without seeing what it costs."""
    ends = [dict(run=None, sq=90.0 - i * 0.02, st=i // 100, l0=-300.0 + i * 0.05)
            for i in range(4000)]
    key = lambda e: -e['l0']                                            # noqa: E731
    assert F._probe_pool(ends, 250) == ends[:250]
    assert F._probe_pool(ends, 250, l0_key=None) == ends[:250]
    pool = F._probe_pool(ends, 250, l0_key=key)
    assert 200 <= len(pool) <= 250
    # the prefix alone can never contain the l0-best endpoint; with the share it must
    assert max(e['l0'] for e in ends[:250]) < max(e['l0'] for e in ends)
    assert max(e['l0'] for e in pool) == max(e['l0'] for e in ends)
    assert any(e in ends[:250] for e in pool), 'the share ate the whole pool'
    # under the cap it is the identity either way
    assert F._probe_pool(ends[:100], 250, l0_key=key) == ends[:100]


def test_l0_decomposes_exactly_in_herd_coordinates():
    """**Why the axis is worth asking for: the herd line is not it.**

    ``l0`` is linear in her herd coordinates, and the two gradients differ by 2.07x -- so a unit of
    LATERAL push buys twice what a unit of down-herd push buys, and the herd's whole keep stack
    (`objective.push_corridor`, ``corridor_keep``, ``align_keep``) is calibrated to drive the lateral
    to zero. That was correct while the plan was to park her on a tabulated coord (the 288 of them
    sit at herd lat -2.3..+7.9); sessions 123/125 replaced that target with a HALF-PLANE, and a
    half-plane is reached fastest along its own normal.

    Gated as the identity rather than as the conclusion, so the numbers stay checkable."""
    env = SD.load_env()
    hl = HerdLine.from_env(env)
    pf = HO.PairFrame()
    assert (hl.dx * pf.q[0] + hl.dz * pf.q[1]) == D_ALONG
    assert (hl.px * pf.q[0] + hl.pz * pf.q[1]) == D_LAT
    assert D_LAT / D_ALONG > 2.0
    c = -(D_ALONG * hl.along(*pf.brace) + D_LAT * hl.lateral(*pf.brace))
    for t in ((-1616.8218994140625, -780.3568115234375),
              (-1606.7857666015625, -888.6373291015625)):
        want = D_ALONG * hl.along(*t) + D_LAT * hl.lateral(*t) + c
        assert abs(HO.tetra_lateral(pf, t) - want) < 1e-9
    # the axis the endgame is denominated in is 64 deg off the one the herd pushes along
    ang = math.degrees(math.acos(hl.dx * pf.m[0] + hl.dz * pf.m[1]))
    assert 25.0 < ang < 26.5


def test_extend_cycle_builds_no_pair_frame_unless_a_customer_asks():
    """``l0_keep`` off and ``handoff_keep`` off = the pre-s134 stage, including its cost.

    A `PairFrame` compiles a `terminal.RollFrame`, and this stage runs per parent per cycle; the
    flag has to be genuinely inert, not merely unused. Read off the source so the gate cannot pass
    by the object happening to be cheap today."""
    import inspect
    src = inspect.getsource(F.extend_cycle)
    assert 'if (handoff_keep or l0_keep) else None' in src
    assert 'pf=(pf_j if l0_keep else None)' in src
    assert 'l0_key=l0_key' in src
    sig = inspect.signature(F.extend_cycle).parameters
    assert sig['l0_keep'].default is False


def test_the_axis_reaches_all_three_cuts():
    """**A keep that reaches two of three cuts is one the third undoes** -- session 134, measured.

    A chained re-cut carrying the axis at the POOL and the SCREEN only handed over **-160.62** where
    the same stage's screened population reaches **-90.39**. The roll stage was exonerated by
    re-opening every kept node at its own pre-roll endpoint: `roll_candidates` delivered exactly what
    that endpoint's screen promised (0.00 u lost at three of four, one node +4.73 u on the wider
    fan). What dropped the high-``l0`` survivors was the FINAL beam cut, which sorts on the frame
    rank -- the kept nodes' own endpoints screened at ``l0_max`` -165..-269, so the beam was carrying
    LOW-``l0`` endpoints rather than high-``l0`` ones whose rolls under-delivered.

    Gated by source because that is where the claim lives -- a cut silently losing its share is
    exactly the failure this cost a run to find, and it does not show up as an exception."""
    import inspect
    src = inspect.getsource(F.extend_cycle)
    assert src.count('if l0_keep and scored:') == 1, 'the SCREEN share'
    assert src.count('if l0_keep and out:') == 1, 'the BEAM-cut share'
    assert 'l0_key=l0_key' in src, 'the POOL share'
    # the beam-cut share must sit in the same ``orders`` list the other keeps share
    tail = src[src.index('orders = [out]'):]
    assert 'if l0_keep and out:' in tail
    assert tail.index('if l0_keep and out:') < tail.index('if handoff_keep and out:')
