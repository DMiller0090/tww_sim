"""Gates for the TERMINAL AS A KEEP (session 145) -- `harness/tetrapush/terminal_keep.py`.

Session 144 measured what five sessions of ranking on `handoff.probe`'s ``resid`` produced: of 49
banked rungs, 4 satisfy the terminal's ``tetra_from_corner``, 0 its ``along``, 0 the seam's facing
window, and none more than one at a time. `terminal_keep` moves all three to the keep side. What has
to stay true, and is gated here rather than trusted:

  * **the keep contains its own generating set.** The eight banked unbroken hits are the family the
    box is READ FROM, so a screen that refuses them is broken whatever else it does
    (`[[search-space-contains-human]]`). Three of the eight failed the first version -- the extents
    are of grid-SAMPLED hits and the f32 basis lands a banked hit ~3e-5 u below its own integer
    coordinate -- which is why the window is the sampled extent widened by half a scan cell;
  * **the box cannot see the lateral, so ``l0`` is a SEPARATE axis and not a consequence** (session
    146). ``along`` / ``runway`` / ``tetra_from_corner`` are all projections on ``m``, so a lateral
    translation of both actors leaves the three of them bit-identical while ``l0`` moves -- gated
    directly, because that invariance is the reason a 130 u miss hid behind a 31.58 u one;
  * **the exact half is 0-ULP.** Re-probing a banked hit through the pooled ctx reproduces the
    scan's own signed residual bit-for-bit (`[[zero-ulp-tests-only]]`: ``==``, never a tolerance);
  * **the windows are the fixture's, not literals.** Every bound traces to
    `fixtures/courtyard_terminal_family.json` or `fixtures/courtyard_facing_window_s92.json`;
  * **an unmeasured terminal raises** rather than answering from a neighbour -- `clipping_family`'s
    contract kept, not softened;
  * **the column is ADDITIVE at `full_herd.roll_probe`**: unasked, the screen's row and result dicts
    do not gain a key, so every keep calibrated before this axis existed is untouched.
"""
import json
import math
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from harness.tetrapush import entry_search as ES            # noqa: E402
from harness.tetrapush import full_herd as F                # noqa: E402
from harness.tetrapush import handoff as HO                 # noqa: E402
from harness.tetrapush import seeds as SD                   # noqa: E402
from harness.tetrapush import terminal as TM                # noqa: E402
from harness.tetrapush import terminal_keep as TK           # noqa: E402
from harness.tetrapush.reposition import HerdLine           # noqa: E402
import tww_sim.core.mathlib as ML                           # noqa: E402

L0_FIXTURE = os.path.join(_REPO, 'fixtures', 'courtyard_l0_screen_nodes.json')
#: the 49 rungs' own roll entries per thrust (`_notes/s143_rolls.py`), gitignored and skipped if absent
ENTRIES = os.path.join(_REPO, '_generated', 's106', 's143_roll_entries.json')


@pytest.fixture(scope='module')
def keep():
    return TK.TerminalKeep()


@pytest.fixture(scope='module')
def family():
    with open(TM.FAMILY_FIXTURE) as fh:
        return json.load(fh)


def _entry_of(hit, keep):
    """A banked terminal hit as a `two_roll.roll_segment` ``entry`` record."""
    return dict(link=tuple(hit['entry']), tetra=tuple(hit['tetra']), facing=keep.box_facing,
                lean=keep.lean, nspeed=None)


# --------------------------------------------------------------------------- the seam window

def test_the_seam_window_is_the_measured_fixture():
    """`seam_window` is the s92 curve scan read back, not a restated range."""
    with open(TK.SEAM_FIXTURE) as fh:
        d = json.load(fh)
    sw = TK.seam_window()
    assert sw['cells'] == frozenset(r['cell'] for r in d['rows'] if r['live'])
    assert sw['cells'], 'the fixture has no live cell at all'
    assert sw['cell_bam'] == d['cell_bam'] == ES.SIN_CELL_BAM
    assert sw['lobes'] == tuple(tuple(l) for l in d['lobes'])
    assert sw['dead_gap'] == tuple(d['dead_gap'])


def test_the_dead_gap_is_refused_and_both_lobes_are_kept():
    """The window is TWO lobes with a measured dead gap between them, and the keep honours it.

    Sessions 81-91 saw only the first lobe because one ``no leverage at the seed`` reading was
    recorded as a verdict on the configuration; a keep that smeared the gap shut would re-make that
    mistake in the other direction."""
    sw = TK.seam_window()
    for cell in range(sw['dead_gap'][0], sw['dead_gap'][1] + 1):
        assert not TK.in_seam_window(cell * ES.SIN_CELL_BAM), 'cell %d is the dead gap' % cell
    for lo, hi in sw['lobes']:
        for cell in (lo, hi):
            assert TK.in_seam_window(cell * ES.SIN_CELL_BAM), 'cell %d is a lobe edge' % cell


def test_the_console_delivered_clip_facing_is_inside_the_window():
    """Containment on the one facing that is known to clip on CONSOLE -- the s90 delivery.

    `[[search-space-contains-human]]` at its sharpest: the window is a model output, and the single
    facing a real clip was delivered at must be a member of it or the window is wrong."""
    with open(TK.SEAM_FIXTURE) as fh:
        d = json.load(fh)
    assert TK.in_seam_window(d['delivered']['facing'])
    assert ES.aim_cell(d['delivered']['facing']) == d['delivered']['cell']


def test_the_window_reports_its_own_scan_edges():
    """The top of the window is where the sweep STOPPED, not where the seam closes -- both edge
    cells are live. A caller that treats it as a boundary must be able to see that
    (`[[infeasible-needs-proof]]`)."""
    sw = TK.seam_window()
    assert max(sw['cells']) == sw['scanned'][1], 'the top scanned cell is live: the edge is the scan'
    assert min(sw['cells']) == sw['scanned'][0], 'the bottom scanned cell is live likewise'


# --------------------------------------------------------------------------- the box

def test_the_keep_windows_are_the_banked_family(keep, family):
    """Every bound is the fixture's ``un_*`` extent widened by exactly half a scan cell."""
    rec = [r for r in family['records']
           if (r['facing'], r['thrust'], r['lean']) == (keep.box_facing, keep.thrust, keep.lean)][0]
    box = family['scan_box']
    assert keep.step['along'] == box['along'][2] == TM.ALONG[1] - TM.ALONG[0]
    assert keep.step['runway'] == box['runway'][2] == TM.RUNWAY[1] - TM.RUNWAY[0]
    assert keep.step['tetra_from_corner'] == math.gcd(keep.step['along'], keep.step['runway'])
    for attr, field in (('along', 'un_along'), ('runway', 'un_runway'),
                        ('tfc', 'un_tetra_from_corner')):
        lo, hi = rec[field]
        step = keep.step['tetra_from_corner' if attr == 'tfc' else attr]
        assert getattr(keep, attr) == (lo - 0.5 * step, hi + 0.5 * step)
    assert keep.lat == tuple(rec['un_lat'])
    assert keep.cut_step == rec['cut_step'] and keep.roll_frames == rec['roll_frames']


def test_the_keep_contains_every_hit_it_was_built_from(keep):
    """**THE gate.** All eight banked unbroken hits pass all three windows.

    They ARE the family the box is read off, so a screen refusing them is refusing its own generating
    set -- and the first version did refuse three, at ~3e-5 u, because a grid extent is not a
    boundary. Non-vacuity is asserted first: an empty hit list would pass this silently."""
    hits = keep.rec['unbroken_hits']
    assert len(hits) == keep.rec['unbroken'] == 8
    for h in hits:
        s = keep.screen(_entry_of(h, keep))
        assert s['ok'], 'banked unbroken hit refused: %s (%r)' % (s['why'], h)
        assert s['exact'], 'the hits are the box facing itself'


def test_the_screen_names_the_first_axis_that_refused(keep):
    """``why`` is a diagnosis, not a bool: each axis can be provoked on its own."""
    h = keep.rec['unbroken_hits'][0]
    base = _entry_of(h, keep)
    assert keep.screen(base)['ok']
    m = (math.sin(math.radians(0)), 0.0)                  # placeholders; the moves are along m/q
    assert m is not None
    off = keep.screen(dict(base, facing=(keep.box_facing + 0x2000) & 0xFFFF))
    assert off['why'] == 't_facing'
    far = keep.screen(dict(base, link=(base['link'][0] + 400.0, base['link'][1] + 400.0)))
    assert far['why'] in ('t_l0', 't_along', 't_runway', 't_tfc')


# --------------------------------------------------------------------------- her side of the line

def test_the_box_is_blind_to_the_lateral_and_l0_is_not(keep):
    """**Why ``l0`` had to be its own axis.** Slide BOTH actors along ``q`` and the three box axes
    come back bit-identical while ``l0`` moves by exactly the slide.

    That invariance is not a quirk: ``along = (T-L).m``, ``runway = -(L-brace).m`` and
    ``tetra_from_corner = runway - along`` are all projections on ``m``, so no amount of sideways
    displacement registers in any of them. Session 145 read a 31.58 u ``tetra_from_corner`` miss off a
    population sitting at ``side`` -59..-226, and the axis that refuses that population could not be
    seen from inside the box."""
    h = keep.rec['unbroken_hits'][0]
    base = _entry_of(h, keep)
    b = keep.screen(base)
    assert b['ok'] and b['l0'] > 0.0
    q = (-ML.cM_scos_s16(keep.box_facing), ML.cM_ssin_s16(keep.box_facing))
    for d in (-200.0, +37.5):
        slid = dict(base,
                    link=(base['link'][0] + d * q[0], base['link'][1] + d * q[1]),
                    tetra=(base['tetra'][0] + d * q[0], base['tetra'][1] + d * q[1]))
        s = keep.screen(slid)
        for a in ('along', 'runway', 'tetra_from_corner', 'lat'):
            assert s[a] == b[a], '%s moved under a pure lateral slide of %+.1f u' % (a, d)
        assert s['l0'] != b['l0'], 'l0 must move with the slide -- it is the lateral axis'
        if d < 0:
            assert s['why'] == 't_l0', 'slid to her wrong side and only l0 refused it'


def test_l0_is_a_sign_and_the_family_band_is_only_reported(keep):
    """The refusal is ``l0 > 0`` (measured over two independent scans); the ~2.2 u ``un_lat`` band is
    REPORTED as ``l0_miss`` and never refuses.

    A band that narrow would drop a genuine terminal at a ``side`` nobody has scanned, and the family
    has no ``side`` axis to scan it on (`[[infeasible-needs-proof]]`)."""
    h = keep.rec['unbroken_hits'][0]
    base = _entry_of(h, keep)
    assert keep.l0_band == tuple(keep.rec['un_lat'])
    assert keep.side_scanned == 0.0, 'the family is a side=0 slice; see terminal.RollFrame.item'
    q = (-ML.cM_scos_s16(keep.box_facing), ML.cM_ssin_s16(keep.box_facing))
    # +40 u sideways: OUTSIDE the 2.2 u band, still on her genuine side -> kept, with the miss shown
    wide = dict(base, link=(base['link'][0] + 40.0 * q[0], base['link'][1] + 40.0 * q[1]),
                tetra=(base['tetra'][0] + 40.0 * q[0], base['tetra'][1] + 40.0 * q[1]))
    s = keep.screen(wide)
    assert s['l0'] > keep.l0_band[1] and s['l0_miss'] > 0.0
    assert s['ok'], 'a 40 u side offset is unscanned, not refused'
    assert not s['exact_side'], 'and it must SAY that the scanned side is not this one'
    assert keep.screen(base)['l0_miss'] == 0.0 and keep.screen(base)['exact_side']


def test_the_banked_ladder_is_refused_on_l0_not_on_the_box(keep):
    """The 49 rungs' own last-roll entries, off the banked s143 artefact: every one of them fails.

    Asserted against a banked artefact rather than re-flown, per the two-minute rule. The point is
    WHICH axis: session 145 reported ``t_along`` for all 528 seam-window aims because ``l0`` was not
    an axis yet, and the miss it could not see is an order of magnitude larger."""
    if not os.path.exists(ENTRIES):
        pytest.skip('banked roll entries missing: %s' % ENTRIES)
    with open(ENTRIES) as fh:
        rows = [r for r in json.load(fh)['rows'] if r['thrust'] == keep.thrust]
    last = {}
    for r in rows:
        if r['rank'] not in last or r['frame'] > last[r['rank']]['frame']:
            last[r['rank']] = r
    assert len(last) == 49, 'the ladder is 49 rungs; got %d' % len(last)
    l0s = []
    for r in last.values():
        s = keep.screen(dict(link=tuple(r['entry']), tetra=tuple(r['tetra']),
                             facing=keep.box_facing, lean=keep.lean, nspeed=r['nspeed']))
        assert not s['ok'], 'rung %d passed the completed keep' % r['rank']
        assert s['why'] == 't_l0', 'rung %d refused on %s, not on l0' % (r['rank'], s['why'])
        l0s.append(s['l0'])
    assert max(l0s) < 0.0 and min(l0s) < -100.0, 'l0 spans %.2f..%.2f' % (min(l0s), max(l0s))


def test_an_unmeasured_terminal_raises_rather_than_answering(keep):
    """`clipping_family`'s contract kept: a neighbouring thrust's box is never quoted.

    Thrust 13 is the case that matters -- it DISPATCHES its cut (it is inside `cut_step_window`) and
    converts 2390 razor roots into zero clips, so it has a scan and no family."""
    with pytest.raises(ValueError):
        TK.TerminalKeep(facing=(keep.box_facing + 0x100) & 0xFFFF)      # never scanned
    with pytest.raises(ValueError):
        TK.TerminalKeep(thrust=13)                                      # scanned, no family
    assert TM.clipping_family(keep.box_facing, 13, keep.lean)['genuine'] == 0
    assert TM.clipping_family(keep.box_facing, 13, keep.lean)['roots'] > 2000


def test_the_delivered_lean_is_the_default(keep):
    """The keep defaults to the state the herd DELIVERS (lean 648), not the state the family was
    first scanned at (0) -- session 144's correction, and worth 11 of the 51 genuine cells."""
    assert keep.lean == TK.DELIVERED_LEAN == 648
    assert keep.thrust == TK.DEFAULT_THRUST == 14
    scanned0 = TM.clipping_family(keep.box_facing, keep.thrust, 0)
    assert scanned0['genuine'] > keep.rec['genuine'] and scanned0['unbroken'] > keep.rec['unbroken']


# --------------------------------------------------------------------------- the exact half

def test_the_pooled_probe_reproduces_the_scan_residual_bit_for_bit(keep):
    """0-ULP through the whole chain: banked world pair -> pooled ctx -> `handoff.probe`."""
    hits = keep.rec['unbroken_hits']
    assert hits
    for h in hits:
        p = keep.probe(_entry_of(h, keep))
        assert p['resid'] == h['resid'], 'residual drifted at %r' % (h,)
        assert p['genuine'] is True
        assert p['overlap'] == h['overlap']


def test_the_pooled_frame_is_a_freshly_built_one(keep):
    """`_PooledPair` on a shared `entry_search.CtxPool` sweeps IDENTICALLY to a fresh `PairFrame`.

    The pool is what makes the keep affordable (0.13 ms against 17 ms), so "identical" has to be
    bit-for-bit and not nearly."""
    h = keep.rec['unbroken_hits'][0]
    e = _entry_of(h, keep)
    fresh = HO.PairFrame(keep.box_facing, keep.thrust, keep.lean)
    a = HO.probe(fresh, e['link'], e['tetra'])
    b = keep.probe(e)
    for k in ('runway', 'side', 'along', 'lat', 'resid', 'overlap', 'push', 'brace_dist'):
        assert a[k] == b[k], 'field %s differs pooled vs freshly built' % k
    assert a['genuine'] == b['genuine']


def test_the_coords_are_the_pair_frames_own(keep):
    """The cheap projection is `handoff.PairFrame.coords`, not an approximation of it."""
    h = keep.rec['unbroken_hits'][-1]
    e = _entry_of(h, keep)
    fresh = HO.PairFrame(keep.box_facing, keep.thrust, keep.lean)
    assert keep.coords(keep.box_facing, e['link'], e['tetra']) == fresh.coords(e['link'], e['tetra'])


def test_the_momentum_axis_is_carried_and_defaults_to_the_cap():
    """``nspeed`` reached the tracked frames in session 145 (it lived in a `_notes` subclass). It
    scales the roll's per-frame travel and nothing else, so a sub-cap roll is a DIFFERENT locus."""
    assert TM.RollFrame(lean=TK.DELIVERED_LEAN).nspeed == ES.ROLL_NSPEED
    assert HO.PairFrame(lean=TK.DELIVERED_LEAN).nspeed == ES.ROLL_NSPEED
    slow = TM.RollFrame(lean=TK.DELIVERED_LEAN, nspeed=13.0)
    fast = TM.RollFrame(lean=TK.DELIVERED_LEAN)
    assert slow.nspeed == 13.0
    assert slow.sch['dx'] != fast.sch['dx'] and slow.sch['cut_step'] == fast.sch['cut_step']


# --------------------------------------------------------------------------- the screen wiring

@pytest.fixture(scope='module')
def endpoints():
    """The banked l0-screen seeds rebuilt as `roll_probe` inputs -- an endpoint IS its log."""
    if not os.path.exists(L0_FIXTURE):
        pytest.skip('l0-screen seeds missing: %s' % L0_FIXTURE)
    with open(L0_FIXTURE) as fh:
        rec = json.load(fh)
    env = SD.load_env()
    hl = HerdLine.from_env(env)
    out = []
    for nd in rec['nodes'][:1]:
        run = SD.make_freerun(env)
        run.pre_seed_input(SD.dtm_input_at(env)(0))
        for d in nd['log']:
            run.step(d)
        out.append(dict(run=run, frames=nd['frames'], jf=nd['jf']))
    return hl, out


def test_the_terminal_column_is_additive(endpoints, keep):
    """**Unasked, the screen does not gain a key.** Every keep calibrated on `roll_probe`'s dicts
    predates this axis, and a banked row shape that silently grew a field would invalidate them."""
    hl, ends = endpoints
    cheap = dict(step=4, fan_center='tetra', half_window=0x600)
    sink = []
    p = F.roll_probe(ends[0], hl, collect=sink, **cheap)
    assert p is not None and sink, 'the seed stopped rolling: this gate is vacuous'
    assert 'terminal' not in p and 't_resid' not in p and 't_genuine' not in p
    assert all('terminal' not in r for r in sink)
    q = F.roll_probe(ends[0], hl, terminal=keep, **cheap)
    assert q is None or 'terminal' in q, 'asked for, the axis must be present'


def test_a_kept_aim_satisfies_all_three_windows(endpoints, keep):
    """Whatever survives the keep satisfies every axis -- and whatever does not is COUNTED by the
    axis that refused it, so a stalled sweep reads as a diagnosis (session 144's lesson: a bare zero
    cannot separate absent geometry from a thin scan)."""
    hl, ends = endpoints
    dead, sink, rows = {}, [], []
    F.roll_probe(ends[0], hl, step=4, fan_center='tetra', half_window=0x600, terminal=keep,
                 dead=dead, collect=rows, terminal_sink=sink)
    assert sink, 'no aim fired a roll: this gate is vacuous'
    for r in sink:
        if r['ok']:
            assert TK.in_seam_window(r['facing'])
            assert keep.along[0] <= r['along'] <= keep.along[1]
            assert keep.runway[0] <= r['runway'] <= keep.runway[1]
            assert keep.tfc[0] <= r['tetra_from_corner'] <= keep.tfc[1]
            assert r['l0'] > 0.0
        else:
            assert r['why'] in ('t_facing', 't_l0', 't_along', 't_runway', 't_tfc')
    kept = [r for r in rows if r.get('terminal', {}).get('ok')]
    assert sum(dead.get(w, 0) for w in ('t_facing', 't_l0', 't_along', 't_runway', 't_tfc')) \
        == sum(1 for r in sink if not r['ok'] and r['dead_why'] is None)
    assert len(kept) == sum(1 for r in sink if r['ok'] and r['dead_why'] is None)


def test_the_sink_records_aims_that_died_a_herd_death(endpoints, keep):
    """``terminal_sink`` takes EVERY aim whose roll fired, including the ones a herd prune killed.

    That is the whole point of it: the seam-window aims all die ``followed`` from a banked junction
    (a corner-aimed roll stops plowing her), so a sink that only saw survivors would report the
    terminal geometry of exactly the aims that are not pointed at the corner."""
    hl, ends = endpoints
    dead, sink = {}, []
    # a DECIMATED wide fan: the claim is that a dead-but-fired aim still reaches the sink, which
    # needs one such aim and not a populated fan (the two-minute rule's shape)
    F.roll_probe(ends[0], hl, step=24, fan_center='tetra', half_window=0x2800, terminal=keep,
                 dead=dead, terminal_sink=sink)
    fired = [r for r in sink if r['dead_why'] is not None]
    assert fired, 'no aim died after firing its roll: this gate is vacuous'
    assert all('runway' in r and 'along' in r for r in fired), 'a dead aim still has its geometry'
    for w in set(r['dead_why'] for r in fired):
        seam = sum(1 for r in fired if r['dead_why'] == w and TK.in_seam_window(r['facing']))
        assert dead.get(w + '@seam', 0) == seam, 'the %s cross-tab disagrees with the sink' % w
