# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""The away-walk escape atom (session 65, Dereck's recipe): the herd junction's convert-to-positive
with the roll replaced by a backwards slam. Gated on the synthetic hot terminal
(`synthetic_hot_arrival`, coord 287); see `harness/tetrapush/away_walk.py` for the mechanics.
These pin the measured behaviour so a model change that moves the escape names itself.
"""
import warnings

import pytest

from harness.tetrapush import seeds
from harness.tetrapush import full_herd as FH
from harness.tetrapush import away_walk as AW
from harness.tetrapush.reposition import HerdLine

warnings.simplefilter('ignore')


#: The bed is SYNTHETIC: no roll paid its camera bill, so its own csangle fires NOTHING and the window
#: is handed over explicitly. The measurement is in `test_the_camera_bill_is_the_snap_windows_near_edge`.
_BED_CS = 'snap'


@pytest.fixture(scope='module')
def bed():
    env = seeds.load_env()
    hl = HerdLine.from_env(env)
    node = FH.synthetic_hot_arrival(env, hl, coord_idx=287, d_short=0.0, feet=64.0)
    return node['run'], hl


@pytest.fixture(scope='module')
def best(bed):
    run, hl = bed
    return AW.probe(run, hl, csangle=_BED_CS)


def test_the_conversion_goes_positive_with_one_l_frame_and_no_zero_crossing(best):
    """Dereck's recipe: ONE delivered L frame (the stick held one more) fires the DIR_BACKWARD
    negation -- the EBS converts -25.7 -> +17.6 POSITIVE -- and the backwards slam then halves a
    POSITIVE run onto the reversed travel, so the speed never crosses zero."""
    sp = [r['speedF'] for r in best['rows']]
    flip_f = next(i for i, v in enumerate(sp) if v > 0)
    assert sp[flip_f] == pytest.approx(17.614, abs=0.1)
    assert sp[flip_f - 1] < -20.0, "the frame before the negation is still the hot EBS"
    assert all(v > 0 for v in sp[flip_f:]), "no zero crossing after the conversion"
    assert sum(1 for d in best['log'] if d['buttons'] & 0x40) == 1, "exactly ONE L frame"


def test_the_slam_reverses_and_separates_on_the_same_frame(best):
    """The backwards slam (`procMoveTurn(1)`) is both the reversal and the separation: ground
    motion recedes from that frame on, Tetra is frozen from it, and her residual over the
    conversion frames is ~35-50 u almost entirely ALONG the corridor -- the terminal targeting's
    deterministic undershoot."""
    assert best['reversed_f'] is not None and best['reversed_f'] <= 7
    assert best['freeze_f'] == best['reversed_f']
    assert 25.0 < best['resid'] < 60.0
    assert abs(best['resid_lat']) < 10.0, "the residual should ride the corridor, not leave it"
    tres = [r['tres'] for r in best['rows']]
    assert max(tres) == pytest.approx(tres[best['freeze_f'] - 1], abs=1e-6), \
        "frozen means frozen: no push after the slam"


def test_the_escape_respects_dereck_s_rules(best):
    """No A press anywhere, no L acting with Tetra in the front cone, no lock acquired, and the
    follow shell (dist <= 230) never trips."""
    assert best['l_ok'] is True
    assert best['followed'] is False
    assert all(not (d['buttons'] & 0x100) for d in best['log'])


def test_the_dip_count_is_the_known_best(best):
    """Dereck's s65 bar, settled: the turnaround's dip is inherent (0 frames under 17 is not
    feasible), and his recipe's measured best is THREE post-separation frames under the walk cap
    (the MoveTurn halving + two accel frames), receding at the cap by ~f8-10. Pinned both ways:
    more dips = a regression in the atom; fewer = a model change worth a session."""
    assert len(best['dips']) == AW.DIP_BUDGET == 3
    assert best['rec17_f'] is not None and best['rec17_f'] <= 10


def test_the_atom_can_be_ranked_by_where_it_leaves_tetra_without_moving_the_acceptance(bed):
    """**The atom's own variant choice is placement authority, and the rank was spending it on the
    separate search** (session 71).

    Session 67 established that by the terminal nothing can move Tetra any more -- the input pipeline
    acts 2 frames late and a whole generation of the terminal alphabet moves her identically -- so the
    escape's conversion frames are the LAST inputs with authority over her. `probe` then ranked its ~8
    variants by ``d_e_end``, how far Link got toward `seeds.ENTRY_ROLL_POS`, which is the SEPARATE entry
    search (s60) and not this one's objective.

    The variants are not interchangeable: ``rotate_side`` decides which way Link steps before the slam,
    hence where he stands relative to her, hence which way the push ejects her. Measured over the
    atom's whole sweep, the residual's LATERAL tracks Link's lateral offset from her at about
    **-0.53 u per u (r -0.926)** while its ALONG collapses from 41.6 u when he is aligned to 6-15 u at
    30-47 u off -- so the corridor's single measured residual describes the aligned case only.

    Gated on the two properties that make the reorder safe rather than a preference: without ``thread``
    the rank is bit-identical to the s65 one, and with it the ACCEPTANCE is untouched -- `fires` is a
    hard term ahead of the landing, so a compliant variant can never lose to a non-compliant one."""
    from harness.tetrapush import objective as O
    from harness.tetrapush import aim as A
    run, hl = bed
    thread = O.placement_thread(hl, seeds.load_placements()[0])

    stock = AW.probe(run, hl, csangle=_BED_CS)
    ranked = AW.probe(run, hl, thread=thread, csangle=_BED_CS)
    assert stock is not None and ranked is not None
    assert AW.fires(stock) and AW.fires(ranked)          # the bar is met either way

    def miss(res):
        return A.landing_miss(run, hl, thread, (res['resid_along'], res['resid_lat']))['miss']

    # the landing rank never returns a worse landing than the stock pick, and it may return better
    assert miss(ranked) <= miss(stock) + 1e-12
    # ...and it is the best landing among everything `fires` accepts, which is the whole claim
    ex, ez = seeds.ENTRY_ROLL_POS
    b_entry = AW.world_angle_s16(ex - run.link.pos_x, ez - run.link.pos_z)
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    cs = AW.snap_csangle(run)
    seen = []
    for ta in (False, True):
        for side in (1, -1):
            for exb in (b_entry, up_herd):
                if ta and cs is None:
                    continue
                r = AW.escape_atom(run, hl, turnaround_first=ta, rotate_side=side, exit_bearing=exb,
                                   csangle=cs if cs is not None else int(run.csangle))
                if r is not None:
                    seen.append(r)
    assert len(seen) > 2
    ok = [r for r in seen if AW.fires(r)]
    assert ok, "no compliant variant on the bed the rest of this module gates"
    assert abs(miss(ranked) - min(miss(r) for r in ok)) < 1e-12
    # the acceptance is ahead of the landing, not traded against it: the pick is the best COMPLIANT
    # landing (above) and stays compliant, so it can only be beaten by variants `fires` rejects
    assert AW.fires(ranked)
    # ...and there is something to rank at all: the variants' lateral residuals genuinely differ,
    # which is `rotate_side` moving where Link stands and so which way the push ejects her
    assert max(r['resid_lat'] for r in seen) - min(r['resid_lat'] for r in seen) > 1.0


def test_the_flip_sweeps_span_is_a_budget_and_the_conversion_cone_is_not_a_bound(bed):
    """**The flip bearing has no static admissible arc, and session 72 measured the cost of assuming
    one.**

    The L conversion IS `getDirectionFromAngle`'s DIR_BACKWARD negation, whose cone is 90 deg wide
    about 180 (`DIR_BACKWARD_CONE`, the 0x6000 row of `knowledge/reference/constants.md`) -- so an arc
    of that half-width about ``travel + 0x8000`` looks like a derived bound on the flip stick. It is
    not: the cone is about ``travel`` AT THE CONVERSION FRAME, which the optional ESS snap and the L
    frame's own travel chase move. Measured on a real 71-frame arrival, the variant that lands
    **1.644 u** at the accepted 75-frame budget sits **61 deg** off the ARRIVAL's back-bearing --
    outside that cone -- where the best variant inside it lands 4.112.

    So `flip_arc`'s ``half`` is a BUDGET (`FLIP_SPAN`, wide enough for every firing variant s72 saw)
    and `fires` is the filter. Gated on the two properties a budget must have: the shipped default is
    in the swept set (so sweeping can never rank worse than not sweeping), and the set is ordered
    outward from it (so a truncated sweep degrades toward the default)."""
    run, hl = bed
    down = hl.bearing_bam()
    arc = AW.flip_arc(hl, step=0x400)
    assert arc[0] == down                     # the shipped default is the first member
    assert len(arc) > 8                       # ...and there is a real sweep around it

    def s16(v):
        v = int(v) & 0xFFFF
        return v - 0x10000 if v >= 0x8000 else v

    d = [abs(s16(b - down)) for b in arc]
    assert d == sorted(d)                     # ordered outward from the default
    assert max(d) <= AW.FLIP_SPAN
    assert AW.DIR_BACKWARD_CONE == 0x8000 - 0x6000
    # the span is WIDER than the conversion cone, which is the correction: a cone-width arc about the
    # arrival's travel would have excluded the measured winner
    assert AW.FLIP_SPAN > AW.DIR_BACKWARD_CONE
    # ...and widening to the full circle is available and strictly contains it (no hidden ceiling)
    full = AW.flip_arc(hl, step=0x400, half=0x8000)
    assert set(arc).issubset(set(full)) and len(full) > len(arc)


def test_sweeping_the_flip_and_rotate_knobs_can_only_improve_the_landing(bed):
    """**The two knobs `probe` was leaving at their defaults are the ones that STEER the placement**
    (session 72).

    Session 71 established that the atom's variant choice is placement authority (the test above),
    then swept 8 variants that between them decide WHEN the atom separates and where Link ends up --
    but not where its conversion frames push HER. ``flip_bearing`` is that direction and it sat at
    the herd's own down-bearing; ``rotate_off`` sat at 0x4000. Measured on four real 71-frame arrivals
    of the s71 full-resolution jf-7 band, sweeping them takes the landing from **4.90 to 0.33**,
    **4.99 to 0.01** and **8.23 to 0.00 u** and produces the first `aim.handoff_spec` True this work
    has seen.

    Gated as a DOMINANCE property rather than on those numbers (they belong to arrivals a test bed
    cannot cheaply rebuild): the swept probe's landing is never worse than the unswept one's, and it
    stays compliant -- the sweep widens the candidate set and the acceptance is unchanged."""
    from harness.tetrapush import objective as O
    from harness.tetrapush import aim as A
    run, hl = bed
    thread = O.placement_thread(hl, seeds.load_placements()[0])

    def miss(res):
        return A.landing_miss(run, hl, thread, (res['resid_along'], res['resid_lat']))['miss']

    stock = AW.probe(run, hl, thread=thread, csangle=_BED_CS)
    swept = AW.probe(run, hl, thread=thread, flip_step=0x800, rotate_offs=AW.ROTATE_OFFS,
                     csangle=_BED_CS)
    assert stock is not None and swept is not None
    assert AW.fires(stock) and AW.fires(swept)
    assert miss(swept) <= miss(stock) + 1e-12
    # the default is IN the swept set, so an unswept-equivalent call reproduces the stock pick
    only_default = AW.probe(run, hl, thread=thread, flip_step=None, rotate_offs=(0x4000,),
                            csangle=_BED_CS)
    assert miss(only_default) == miss(stock)
    # ...and the knobs genuinely move Tetra: the sweep reaches residuals the 8 variants cannot
    arc = AW.flip_arc(hl, step=0x800)
    cs = AW.snap_csangle(run)
    lats = []
    for flip in arc:
        r = AW.escape_atom(run, hl, flip_bearing=flip,
                           csangle=cs if cs is not None else int(run.csangle))
        if r is not None and AW.fires(r):
            lats.append(r['resid_lat'])
    assert len(lats) > 2 and max(lats) - min(lats) > 1.0


def test_the_frames_rank_prices_the_landing_against_what_the_separation_costs(bed):
    """**Sweeping the flip knob creates a trade, and a landing-only rank pays any number of frames
    for it** (session 72).

    Measured on one real arrival: the same state reaches a landing of **0.33 u at ``freeze_f`` 12**
    and **1.64 u at 4**. The objective allows `objective.TIMELOSS_BUDGET` = 2 frames over the floor,
    so buying 1.3 u with 8 frames is not a better plan -- it is an inadmissible one. ``rank='frames'``
    prices the landing in the objective's own currency instead: ``freeze_f +
    objective.thread_frames(landing)``, which is `full_herd.escape_probe`'s ``bound`` minus the
    arrival frames (constant across variants), with the miss kept as the tie-break. It was worth
    77.50 -> **75.13** of bound on the four measured arrivals.

    Gated on the property, not the numbers: the frames rank's pick is the best FRAMES cost among
    everything `fires` accepts, and the default rank is bit-identical to session 71's."""
    from harness.tetrapush import objective as O
    from harness.tetrapush import aim as A
    run, hl = bed
    thread = O.placement_thread(hl, seeds.load_placements()[0])

    def cost(res):
        lm = A.landing_miss(run, hl, thread, (res['resid_along'], res['resid_lat']))
        return (res['freeze_f'] or 0) + O.thread_frames(lm['along'], lm['lat'], thread)

    def miss(res):
        return A.landing_miss(run, hl, thread, (res['resid_along'], res['resid_lat']))['miss']

    kw = dict(flip_step=0x800, rotate_offs=AW.ROTATE_OFFS)
    by_miss = AW.probe(run, hl, thread=thread, csangle=_BED_CS, **kw)
    by_frames = AW.probe(run, hl, thread=thread, rank='frames', csangle=_BED_CS, **kw)
    assert by_miss is not None and by_frames is not None
    assert AW.fires(by_frames)
    assert cost(by_frames) <= cost(by_miss) + 1e-12

    # it is the best frames cost over the WHOLE compliant sweep, which is the claim
    cs = AW.snap_csangle(run)
    ex, ez = seeds.ENTRY_ROLL_POS
    b_entry = AW.world_angle_s16(ex - run.link.pos_x, ez - run.link.pos_z)
    up_herd = (hl.bearing_bam() + 0x8000) & 0xFFFF
    ok = []
    for flip in AW.flip_arc(hl, step=0x800):
        for ro in AW.ROTATE_OFFS:
            for ta in (False, True):
                for side in (1, -1):
                    for exb in (b_entry, up_herd):
                        if ta and cs is None:
                            continue
                        r = AW.escape_atom(run, hl, turnaround_first=ta, rotate_side=side,
                                           rotate_off=ro, flip_bearing=flip, exit_bearing=exb,
                                           csangle=cs if cs is not None else int(run.csangle))
                        if r is not None and AW.fires(r):
                            ok.append(r)
    assert ok
    assert abs(cost(by_frames) - min(cost(r) for r in ok)) < 1e-9
    # ...and the default rank is untouched: it is still the best compliant LANDING (session 71)
    assert abs(miss(by_miss) - min(miss(r) for r in ok)) < 1e-12


def test_the_camera_bill_is_the_snap_windows_near_edge_and_the_atom_never_pays_it(bed):
    """**The snap window is ~80 deg wide, the scan returned its FAR edge, and that value is the csangle
    every atom result from session 65 to 72 was computed at** (session 73).

    `snap_csangle` used to walk ``range(0, 0x10000)`` and return the first member. Measured over 112 real
    arrivals the window holds 28-30 members on the 512 grid -- **78.8-81.6 deg** -- so which member the
    scan returns is not cosmetic: the first-in-absolute-order sat **91.3-113.8 deg** off the live csangle
    on every one of them, where the NEAREST member is **15.3-37.8 deg** (median 21.0). The atom cannot
    slew either distance (its C-stick is neutral and ~470 BAM/frame makes 15-38 deg cost 6-15 frames
    against `objective.TIMELOSS_BUDGET` 2), so the bill belongs to the last roll's ``target_cs``
    (`full_herd.camera_probe_key`) -- and only the near edge is inside that roll's -46.6..+40.7 deg reach.

    Gated as the three properties that make the atom's numbers replayable: the window is wide (so the
    scan order matters), ``near`` is never further than the legacy order, and the DEFAULT atom commands
    the arrival's own live csangle -- bill 0 -- so a billed variant can only arise from an explicit ask
    and always says so."""
    run, hl = bed
    live = int(run.csangle)

    def off(cs):
        return abs(AW._s16(cs - live))

    # the window is WIDE, which is why the scan order decides the bill
    hits = [cs for cs in range(0, 0x10000, 512) if AW.snaps_at(run, cs)]
    assert len(hits) > 8, "a one-member window would make the scan order irrelevant"
    near, far = AW.snap_csangle(run), AW.snap_csangle(run, near=False)
    assert near in hits and far in hits
    assert off(near) == min(off(cs) for cs in hits)     # `near` IS the nearest member
    assert off(near) < off(far)                         # ...and the legacy order was not

    # the bill: this synthetic bed owes one (no roll paid it), and it is the near edge's distance
    bill = AW.snap_bill(run)
    assert bill['free'] is False and bill['csangle'] == near
    assert bill['bam'] == AW._s16(near - live)
    assert bill['deg'] == pytest.approx(off(near) * AW._BAM_DEG)

    # the DEFAULT is replay-faithful: the camera holds what the arrival brought, so nothing is owed
    faithful = AW.escape_atom(run, hl)
    assert faithful['csangle'] == live and faithful['cs_bill'] == 0
    # ...and an explicitly billed variant self-reports, so it can never pass as faithful
    billed = AW.escape_atom(run, hl, csangle=near)
    assert billed['cs_bill'] == bill['bam'] != 0
    assert AW.probe(run, hl, csangle='live')['cs_bill'] == 0
    assert AW.probe(run, hl, csangle='snap')['cs_bill'] == bill['bam']

    # and the bed itself is the reason a synthetic terminal cannot gate the faithful path: at its own
    # live csangle the L locks in every variant, because no roll ever steered the camera for it
    assert not AW.snaps_at(run, live)
    assert not AW.fires(AW.probe(run, hl, csangle='live', flip_step=0x1000,
                                 rotate_offs=AW.ROTATE_OFFS))


def test_the_escapes_own_frames_are_worth_less_than_a_ceiling_frame_and_one_is_dead(bed, best):
    """**WHERE THE FRONTIER'S 2-FRAME TIMELOSS ACTUALLY GOES, and why no search axis has moved it**
    (session 74).

    The frontier has read 75 frames against a floor of 73 since session 71, and s72 (the atom's flip
    and rotate knobs), s73 (the camera's snap window) and s74 (a 2.4x finer camera grid) each widened a
    different axis and left it there. `away_walk.push_profile` prices the escape's frames in the
    currency the floor is built from -- `objective.PUSH_CEILING`, the sustained plow rate -- and the
    answer is structural: the escape's frames simply are not worth a ceiling frame.

    Measured on the shipped 75-frame plan (`fixtures/courtyard_plan_s73.json`), the LAST ROLL pushes
    Tetra 12.911 u/frame over all 19 of its frames -- **99.3%** of the ceiling, i.e. the herd loses
    nothing -- while the escape's 4 frames to separation push **9.177 u/frame, 70.6%**, costing 1.18
    frames on their own. The mechanism is one frame: the proc-7 NEGATION frame plows **0.000 u**,
    because the flip has Link receding while the conversion has not yet fired. It is the recipe's shape
    (`away_walk`'s module docstring), not a knob -- so what a plan's frame rung costs is decided by its
    ARRIVAL, and the escape can only be charged for what it pushes.

    Gated on the bed as the three properties a search may rely on: ``tstep`` is her own per-frame
    displacement (not a `tres` difference, which under-reads a turning plow), the negation frame is the
    dead one, and the recovery a search may credit the escape with is BOUNDED by that push -- which is
    what makes the rung ledger admissible rather than optimistic."""
    run, hl = bed
    rows, _ = seeds.load_placements()
    prof = AW.push_profile(best)

    # (1) the window priced is the one the frame count is charged for: up to separation
    assert prof['frames'] == best['freeze_f'] == len(prof['plow'])
    assert AW.push_profile(best, upto=2)['frames'] == 2
    # ``tstep`` is a PATH, so it can only exceed the straight-line residual `tres` reports
    assert sum(r['tstep'] for r in best['rows']) >= best['rows'][-1]['tres'] - 1e-9
    assert prof['total'] == pytest.approx(sum(prof['plow']))

    # (2) the negation frame plows NOTHING, and it is inside the charged window
    assert prof['dead'] == [2], "the dead push frame is the proc-7 negation frame"
    assert best['rows'][1]['proc'] == 7 and best['rows'][1]['speedF'] < 0.0
    assert best['rows'][0]['tstep'] > 10.0, "...and frame 1 is the biggest push of the whole plan"

    # (3) so the escape's frames are worth well under a ceiling frame, and that IS the timeloss
    assert 0.0 < prof['saturation'] < 0.85
    assert prof['rate'] < prof['ceiling']
    assert prof['frames_lost'] > 0.5
    assert prof['frames_lost'] == pytest.approx(
        prof['frames'] * (prof['ceiling'] - prof['rate']) / prof['ceiling'])

    # (4) the bound that makes the rung ledger admissible: moving her by `total` can close at most
    # `total` of her distance to a FIXED coord, whatever the flip/rotate/camera do
    pd0 = FH._placement_dist(run, rows)
    pd1 = FH._placement_dist(best['run'], rows)
    assert pd0 - pd1 <= prof['total'] + 1e-6
