"""THE SEPARATE ENTRY SEARCH (Dereck, session 60) -- the s45 fork, settled by measurement (s79).

The herd is finished and console-confirmed, so Tetra is a MEASURED CONSTANT and the free variable is
Link's ROLL ENTRY. That is the dual of `_generated/tetra_placements.tsv`, which sweeps Tetra at a
fixed entry, and it decides the fork that has been open since session 45:

  (A) walk Link to the tabulated `seeds.ENTRY_ROLL_POS` the coord list is valid for -- **DEAD**.
      The console's Tetra misses coord 274 by 0.4321 u and that miss is 0.4314 u PERPENDICULAR to the
      coord thread, so standing exactly on the tabulated entry puts the cut ray 0.3139 u from the
      seam vertex against a window ~1.2e-4 u wide -- a 2707x miss. Route (A) never needed the walk
      precision argument; its premise is false.
  (B) re-solve the clip at the herd's own endpoint -- **LIVE**. With Tetra pinned there are 1735
      genuine entries forming one thin curve 104 u long, all walkable; **856 of them sit inside the
      230 u follow bar** and are the usable target, the nearest 49.7 u from where the escape leaves
      Link -- and his own continued walk passes within 3.1 u of it.

The razor's smooth coordinate is `entry_search.resid_fn`: the cut segment's signed offset from the
seam vertex S. `genuine` is f32 dust inside a hair of resid == 0, so the acceptance window is
MEASURED off the 288 tabulated coords rather than assumed.

`fixtures/courtyard_entry_locus_s79.json` is DERIVED (regenerable by `python -m
harness.tetrapush.entry_search locus`, ~240 s) and pinned so these gates do not pay the sweep.

Offline: the native `ShoveCtx` + the 0-ULP `FreeRun` (no Dolphin).
"""
import json
import math
import os
import struct

import pytest

from harness.rollstab import turnaround as TA
from harness.tetrapush import entry_search as ES
from harness.tetrapush import seeds as SD


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


LOCUS = json.load(open(_fx('courtyard_entry_locus_s79.json')))
SEED = ES.console_seed()
PLACEMENTS = SD.load_placements()[0]


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


# --------------------------------------------------------------- the acceptance window is measured

def test_the_harness_reproduces_the_tabulated_coord_list_at_its_own_entry():
    """279 of the 288 tabulated coords still read genuine through `build_at` at the entry the tsv
    header names, and land on the seam vertex the tsv records. The 9 that do not are the boundary
    dust the window's overlap already says exists -- they are pinned so a real regression is visible."""
    ctx, sch, resid = ES.build_at()
    rows = ctx.sweep_par([(r['x'], r['z'], ES.TAB_ENTRY[0], ES.TAB_ENTRY[1]) for r in PLACEMENTS], 0)
    miss = [r['idx'] for r, o in zip(PLACEMENTS, rows) if not o[0]]
    assert miss == [20, 23, 80, 125, 148, 206, 209, 250, 287]
    assert sum(1 for o in rows if o[0]) == 279
    for o in rows:
        if o[0]:
            assert math.hypot(o[3] + 1727.17, o[4] + 990.46) < 0.01   # the tsv's own `new`


def test_the_acceptance_window_is_about_one_f32_ulp_wide():
    """The genuine band in `resid`, measured off those coords -- and it is ~one f32 ULP at this
    distance from the origin, which is why the tsv is dust and not a region."""
    w = ES.acceptance_window(PLACEMENTS)
    assert w['n_genuine'] == 279 and w['n_total'] == 288
    assert w['lo'] == pytest.approx(-2.515e-06, abs=1e-8)
    assert w['hi'] == pytest.approx(+1.134e-04, abs=1e-7)
    ulp = struct.unpack('<f', struct.pack('<I', _bits(1550.0) + 1))[0] - 1550.0
    assert w['width'] < 2.0 * ulp
    # the boundary overlaps: some non-genuine coords sit inside the genuine band
    assert w['miss_lo'] < w['hi']


# ------------------------------------------------------------------------------ the fork, measured

def test_the_console_tetra_does_not_clip_at_the_tabulated_entry():
    """ROUTE (A) FALSIFIED. Stand Link exactly on `seeds.ENTRY_ROLL_POS` and fire at the console's
    own Tetra: not genuine, and off by three orders of magnitude."""
    v = ES.tabulated_verdict(SEED, PLACEMENTS)
    assert v['genuine'] is False
    assert v['resid'] == pytest.approx(0.313863, abs=1e-5)
    w = ES.acceptance_window(PLACEMENTS)
    assert abs(v['resid']) / w['width'] > 1000.0


def test_her_miss_on_the_coord_is_perpendicular_to_the_thread_not_along_it():
    """WHY (A) fails, in one number: the 0.4321 u placement miss the objective scores is 0.4314 u
    ACROSS the coord thread and only 0.024 u along it. The placement metric is a distance to the
    nearest sample; the clip cares about the perpendicular half."""
    v = ES.tabulated_verdict(SEED, PLACEMENTS)
    assert v['coord_idx'] == 274
    assert v['miss'] == pytest.approx(SEED['placement_dist'], abs=1e-9)
    assert v['miss_perp'] == pytest.approx(0.4314, abs=1e-3)
    assert abs(v['miss_along']) < 0.05
    assert v['miss_perp'] > 15.0 * abs(v['miss_along'])


def test_the_cut_frame_push_is_what_moves_the_razor_and_it_is_zero_at_links_endpoint():
    """`old` is the same wall-braced point either way -- the entry only matters through the push
    Tetra is still delivering on the cut frame. At Link's own console endpoint she is out of Co
    range, the push is exactly zero, and the bare roll-stab lands 0.33 u short."""
    ctx, sch, resid = ES.build_at()
    tab, end = ctx.sweep_par([(SEED['tetra'][0], SEED['tetra'][1], ES.TAB_ENTRY[0], ES.TAB_ENTRY[1]),
                              (SEED['tetra'][0], SEED['tetra'][1], SEED['link'][0], SEED['link'][1])], 0)
    assert end[5] == 0.0 and end[6] == 0.0
    assert resid(end) == pytest.approx(-0.329385, abs=1e-5)
    assert tab[5] != 0.0
    assert math.hypot(tab[1] - end[1], tab[2] - end[2]) < 0.1      # same wall-braced `old`


# ------------------------------------------------------------------- what licenses sweeping entries

def test_the_baked_schedule_is_independent_of_the_entry_position():
    """One `ShoveCtx` may sweep entry POSITIONS -- the roll's displacement/cut/pose schedule is
    momentum-driven, so it is bit-identical wherever the roll starts. (It is NOT independent of the
    facing or of m351C; those need their own ctx.)"""
    base = TA.extract_schedule_at(ES.TAB_ENTRY, ES.TAB_FACING, 0, TA.GROUND_Y,
                                  TA.FS.make_inputs(TA.THRUST))
    for d in ((5.0, -7.0), (-30.0, 40.0), (60.0, 60.0), (-90.0, 25.0)):
        s = TA.extract_schedule_at((ES.TAB_ENTRY[0] + d[0], ES.TAB_ENTRY[1] + d[1]),
                                   ES.TAB_FACING, 0, TA.GROUND_Y, TA.FS.make_inputs(TA.THRUST))
        for k in ('dx', 'dz', 'cutx', 'cutz', 'is_pose', 'chx', 'chz', 'cut_step', 'nroot'):
            assert s[k] == base[k], k


def test_the_body_lean_is_not_free():
    """m351C is a parameter the search must CARRY, not assume: 0 and 1 clip the same entry, 64
    already does not. The replayed herd hands Link m351C -191 and a steady walk settles near -160,
    so a locus computed at m351C 0 is not the one his walk arrives on."""
    rows = {r['m351C']: r for r in LOCUS['m351c_sensitivity']}
    assert rows[0]['genuine'] is True and rows[1]['genuine'] is True
    assert rows[64]['genuine'] is False
    assert abs(rows[64]['resid']) > 50.0 * LOCUS['window']['width']


# ------------------------------------------------------------------------------- the locus, route B

def test_genuine_entries_exist_for_the_pinned_console_tetra():
    """ROUTE (B) VIABLE. Every entry the fixture records still reads genuine through a freshly built
    ctx, and every residual re-derives bit-for-bit."""
    ctx, sch, resid = ES.build_at(ES.TAB_ENTRY, LOCUS['facing'], LOCUS['m351c'])
    t = LOCUS['tetra']
    rows = ctx.sweep_par([(t[0], t[1], h['entry'][0], h['entry'][1]) for h in LOCUS['hits']], 0)
    assert len(rows) == 1735
    assert all(o[0] for o in rows)
    assert all(resid(o) == h['resid'] for h, o in zip(LOCUS['hits'], rows))


def test_the_genuine_band_is_a_dust_boundary_not_a_hard_edge():
    """The locus's own residuals run slightly WIDER than the band measured off the tabulated coords
    ([-4.10e-6, +1.34e-4] vs [-2.52e-6, +1.13e-4]). Both are samples of the same f32 dust edge, so
    the window is a filter to aim with, never an acceptance test -- only the sim's own `genuine` is."""
    lo, hi = LOCUS['resid_range']
    w = LOCUS['window']
    assert lo < w['lo'] and hi > w['hi']
    assert (hi - lo) < 1.4 * w['width']                     # same order: it is an edge, not a region


def test_the_usable_locus_is_the_subset_inside_the_follow_bar():
    """The 230 u bar is not decoration: past it Tetra leaves stt 3 and MOVES, so an entry out there is
    not an entry. Half the curve is out -- 856 of 1735 -- and that subset is what a search may aim at."""
    m, mu = LOCUS['metrics'], LOCUS['metrics_usable']
    assert m['n'] == 1735 and mu['n'] == LOCUS['n_usable'] == 856
    assert m['d_tetra'][1] > LOCUS['follow_bar'] > mu['d_tetra'][1]
    assert mu['follow_ok'] == mu['n']
    assert sum(1 for h in LOCUS['hits'] if h['follow_ok']) == 856


def test_the_locus_is_one_thin_walkable_curve():
    for m in (LOCUS['metrics'], LOCUS['metrics_usable']):
        assert m['thickness'] < 2.0 and m['extent'] > 90.0     # one curve, not a spread
        assert m['walkable'] == m['n']                          # Tetra never falls OOB en route
        assert m['d_link'][0] < 55.0                            # the nearest is 49.7 u out


def test_the_entry_precision_the_search_must_hit_is_about_one_f32_ulp():
    """window / |grad resid| -- the tolerance a walk has to land inside. It is ~1e-4 u, i.e. the f32
    ULP at this distance from the origin, so the search is a DENSITY problem (enough distinct
    reachable entries), not an accuracy one."""
    assert LOCUS['gradient']['grad'] == pytest.approx(1.196, abs=0.05)
    assert LOCUS['entry_precision'] == pytest.approx(9.7e-05, rel=0.1)
    ulp = struct.unpack('<f', struct.pack('<I', _bits(1550.0) + 1))[0] - 1550.0
    assert LOCUS['entry_precision'] < 2.0 * ulp


def test_the_locus_fixture_is_seeded_from_the_locked_console_read():
    """The seed is a MEASURED state, not a simulated one (the s78 handoff's instruction)."""
    assert LOCUS['tetra'] == list(SEED['tetra'])
    assert LOCUS['link_endpoint']['x'] == SEED['link'][0]
    assert LOCUS['link_endpoint']['z'] == SEED['link'][1]
    assert LOCUS['link_endpoint']['speedF'] == 17.0            # already at the walk cap the clip wants
    assert LOCUS['facing'] == ES.TAB_FACING


# -------------------------------------------------------------------------------- reachability

def test_links_own_escape_walk_passes_within_a_few_units_of_the_locus():
    """The console-confirmed log, continued with its own last stick held, walks to 3.1 u of the
    USABLE locus by frame 85; four other steady sticks pass within 3.8-13.1 u. The target is inside
    his reachable set, so the open work is landing ON it, not getting there."""
    r = {x['stick']: x for x in LOCUS['reachability']}
    assert r['hold_last']['d_usable'] < 3.2 and r['hold_last']['frame'] == 85
    assert min(x['d_usable'] for x in LOCUS['reachability']) < 3.2
    assert all(x['speedF'] == 17.0 for x in LOCUS['reachability'])   # the roll wants the 17 cap
    assert all(abs((x['m351C'] & 0xFFFF) - 65536) > 0 for x in LOCUS['reachability'])


def test_continuing_the_console_log_reproduces_the_measured_endpoint_bit_exactly():
    """The replay this search seeds from IS the console's own state -- guarded here so a model
    change that moves it fails loudly rather than silently re-aiming the locus."""
    run, rows = ES.continue_walk([])
    assert _bits(run.link.pos_x) == _bits(SEED['link'][0])
    assert _bits(run.link.pos_z) == _bits(SEED['link'][1])
    assert (run.link.facing & 0xFFFF) == SEED['link_facing']
    assert run.link.speedF == SEED['link_speedF']
    assert (run.link.m351C & 0xFFFF) == 65345          # -191: NOT the m351C 0 the locus assumes
    assert (run.link.csangle & 0xFFFF) == 34325        # frozen by the atom's neutral C-stick


@pytest.mark.slow
def test_the_locus_regenerates_from_a_small_box():
    """The fixture is derived, so it must be reproducible: re-map a 12 u box around the nearest
    genuine entry and confirm the sweep finds genuine entries there again."""
    near = min(LOCUS['hits'], key=lambda h: math.hypot(h['entry'][0] - SEED['link'][0],
                                                       h['entry'][1] - SEED['link'][1]))
    hits = ES.genuine_entries(SEED['tetra'], centre=tuple(near['entry']), half=6.0)
    assert hits
    known = set((round(h['entry'][0], 6), round(h['entry'][1], 6)) for h in LOCUS['hits'])
    assert any((round(h['entry'][0], 6), round(h['entry'][1], 6)) in known for h in hits)
