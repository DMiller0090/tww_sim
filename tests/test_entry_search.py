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

from tww_sim.core import mathlib as ML
from harness.rollstab import fast_shove as FS
from harness.rollstab import geometry_tetra as GT
from harness.rollstab import turnaround as TA
from harness.tetrapush import cross_engine as XE
from harness.tetrapush import entry_search as ES
from harness.tetrapush import roll_fidelity as RF
from harness.tetrapush import seeds as SD
from harness.tetrapush import two_roll as TR
from tww_sim.land.land import LandState


def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


LOCUS = json.load(open(_fx('courtyard_entry_locus_s79.json')))
SEED = ES.console_seed()
PLACEMENTS = SD.load_placements()[0]


def _s90_frame_minimal():
    """Row 0 of the current candidate list -- the 4-frame walk-up session 90 delivered to console."""
    return json.load(open(_fx('courtyard_entry_s90_hits.json')))['rows'][0]


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


# ------------------------------------------------------- the fidelity gate (session 80) and its fan
# What makes scoring a RESEEDED roll legitimate -- and what caught s79 feeding it the wrong point.

def _sample_roll(want_facing=40850, n_walk=12, force_m3570=None, b_step=TA.B_STEP):
    """A real from-rest walk + A-press turnaround roll aimed into the seam window, arriving near the
    usable locus. Returns `roll_fidelity.walk_then_roll`. A short ``n_walk`` arrives BELOW the walk
    cap; ``b_step`` is the UP+B roll-step index, which for schedule thrust T is ``T + 2``."""
    near = min((h for h in LOCUS['hits'] if h['follow_ok']),
               key=lambda h: math.hypot(h['entry'][0] - SEED['link'][0],
                                        h['entry'][1] - SEED['link'][1]))['entry']
    wfac, wb = RF.stick_for_facing(SEED['link_facing'], ES.CSANGLE)
    _, aim = RF.stick_for_facing(want_facing, ES.CSANGLE, msd_min=0.0)
    ux, uz = ML.cM_ssin_s16(wfac), ML.cM_scos_s16(wfac)
    start = (near[0] - 17.0 * (n_walk - 4) * ux, near[1] - 17.0 * (n_walk - 4) * uz)
    return RF.walk_then_roll(start, wb, aim, n_walk, b_step, ES.CSANGLE,
                             force_m3570=force_m3570)


def test_the_reseeded_roll_is_the_roll_a_real_a_press_does():
    """THE GATE THE s79 HANDOFF LEFT OPEN. `extract_schedule_at` starts a cold FRONT_ROLL at nspeed
    26; a real turnaround roll carries anim and pose history in. All nine baked tables are
    bit-identical -- so the whole locus is scored on the right roll."""
    rows, ent, real = _sample_roll()
    assert ent is not None and real['cut_step'] == 16
    base = TA.extract_schedule_at((ent['x'], ent['z']), ent['facing'], ent['m351C'],
                                  TA.GROUND_Y, FS.make_inputs(TA.THRUST))
    assert RF.table_diff(real, base) == []


def test_the_reseed_takes_the_post_entry_frame_state_not_the_walks():
    """WHICH state -- decided by measurement, not convention. The reseed's step 0 IS the roll's
    SECOND frame, so it must be handed the position and lean at the END of the entry frame. Feeding
    the pre-entry values (what the walk fan has in hand) mismatches the pose chain."""
    rows, ent, real = _sample_roll()
    wrong = TA.extract_schedule_at((ent['walk_x'], ent['walk_z']), ent['facing'],
                                   ent['m351C_walk'], TA.GROUND_Y, FS.make_inputs(TA.THRUST))
    assert sorted(RF.table_diff(real, wrong)) == ['chx', 'chz']


def test_the_roll_entry_is_the_walk_endpoint_plus_one_roll_step():
    """The correction the s79 fan was missing, bit-exact: `_roll_init` takes nspeed from the walk cap
    (17 * 1.5 + 0.5 == 26) and snaps travel to the commanded facing, so the entry frame moves Link one
    full roll step before the schedule starts. 26 u -- and in a direction the AIM chooses."""
    for want in (40617, 40850, 41037):
        for n_walk in (11, 12, 13):
            rows, ent, _ = _sample_roll(want_facing=want, n_walk=n_walk)
            assert ent['nspeed'] == ES.ROLL_NSPEED
            got = ES.roll_entry((ent['walk_x'], ent['walk_z']), ent['facing'])
            assert _bits(got[0]) == _bits(ent['x']) and _bits(got[1]) == _bits(ent['z'])
            assert ES.lean_at_roll(ent['m351C_walk']) == ent['m351C']
            assert math.hypot(ent['x'] - ent['walk_x'], ent['z'] - ent['walk_z']) == \
                pytest.approx(26.0, abs=1e-3)


def test_the_armed_crash_latch_never_changes_this_roll():
    """The reseed forces ``_roll_m3570`` off and `ShoveCtx` has no crash branch, but a roll started in
    the open ARMS the mid-roll bonk and this one does hit the wall for ten frames. It never fires:
    the bonk cone does not line up before the B edge, so disarming it is exact, not an approximation."""
    rows, ent, real = _sample_roll()
    assert ent['m3570'] is True                              # started clear of the wall: armed
    assert any(r['wall_hit'] and r['proc'] == 30 for r in rows)   # and it does contact mid-roll
    _, _, forced = _sample_roll(force_m3570=False)
    assert RF.table_diff(real, forced) == []
    assert all(r['proc'] in (30, 66, 67) or r['k'] < ent['k'] for r in rows)   # no crash proc


_SCH_KEYS = RF.TABLE_KEYS + ('link_x0', 'link_z0', 'link_y', 'tet_seed')


@pytest.mark.slow
def test_the_analytic_schedule_is_the_simulated_one():
    """`fast_schedule` drops the 17-frame coupled roll for a direct evaluation and is 0-ULP identical
    over facing x lean x thrust. That is what makes 81 x 3 loci affordable: the 22 ms ctx build, not
    the size of the alphabet, was the search's whole budget."""
    for fac in (40617, 40835, 40884, 41037):
        for lean in (0, 1, 64, 65325, 65432, 65039):
            for thrust in ES.THRUSTS:
                base = TA.extract_schedule_at(ES.TAB_ENTRY, fac, lean, TA.GROUND_Y,
                                              FS.make_inputs(thrust))
                fast = ES.fast_schedule(fac, lean, thrust)
                assert [k for k in _SCH_KEYS if base[k] != fast[k]] == []


# ------------------------------------------------- the momentum axis (session 82): law, then value
# Generalizing the schedule off the walk cap is one thing; what that is WORTH is another. Gated apart.

def test_the_roll_momentum_is_the_walk_speed_not_the_cap():
    """THE LAW, against a REAL A-press out of a decelerating walk. `_roll_init` sets the roll's whole
    momentum once from the pre-roll speedF -- ``clamp(1.5 * speedF + 0.5, 5, 26)`` -- and the walk
    ENDPOINT the fan records is the speed it reads, even though the entry frame dispatches after it.

    The s80 fidelity gate only ever ran at the cap, where that clamp saturates and hides itself. Below
    it every walk speed is its own momentum, and `roll_entry` moves Link by THAT much."""
    seen = set()
    for n_walk in (2, 3, 4, 5, 12):
        rows, ent, _tab = _sample_roll(n_walk=n_walk)
        pre = rows[ent['k'] - 1]['speedF']
        assert _bits(ES.roll_nspeed(pre)) == _bits(ent['nspeed'])       # the clamp, bit-for-bit
        got = ES.roll_entry((ent['walk_x'], ent['walk_z']), ent['facing'], ent['nspeed'])
        assert _bits(got[0]) == _bits(ent['x']) and _bits(got[1]) == _bits(ent['z'])
        seen.add(ent['nspeed'])
    assert len(seen) == 5 and min(seen) < 6.0 and max(seen) == ES.ROLL_NSPEED
    # and the cap-assuming entry is not a rounding error away: it is a whole roll step out
    rows, ent, _t = _sample_roll(n_walk=2)
    capped = ES.roll_entry((ent['walk_x'], ent['walk_z']), ent['facing'])
    assert math.hypot(capped[0] - ent['x'], capped[1] - ent['z']) > 20.0


def test_a_sub_cap_roll_bakes_the_schedule_the_sweep_scores():
    """The s80 gate, re-run on the momentum axis: a REAL sub-cap A-press roll must bake the reseed's
    nine tables, and the analytic `fast_schedule(nspeed=)` must be the simulated one. The cap-assuming
    schedule differs in exactly `dx`/`dz` -- the momentum scales the travel and nothing else (the cut
    lunge is a constant root translate, the pose chain is frame- and lean-driven)."""
    for n_walk in (3, 5):
        for thrust in ES.THRUSTS:
            _rows, ent, real = _sample_roll(n_walk=n_walk, b_step=thrust + 2)
            assert ent['nspeed'] < ES.ROLL_NSPEED and real['cut_step'] == thrust + 2
            sim = TA.extract_schedule_at((ent['x'], ent['z']), ent['facing'], ent['m351C'],
                                         TA.GROUND_Y, FS.make_inputs(thrust), nspeed=ent['nspeed'])
            ana = ES.fast_schedule(ent['facing'], ent['m351C'], thrust, (ent['x'], ent['z']),
                                   nspeed=ent['nspeed'])
            assert RF.table_diff(real, sim) == []
            assert [k for k in _SCH_KEYS if sim[k] != ana[k]] == []
            old = ES.fast_schedule(ent['facing'], ent['m351C'], thrust, (ent['x'], ent['z']))
            assert [k for k in _SCH_KEYS if ana[k] != old[k]] == ['dx', 'dz']


def test_a_re_scheduled_ctx_is_a_freshly_built_one():
    """`CtxPool` is what makes the momentum affordable at all: the world compiles once per (facing,
    thrust) and only Link's schedule is swapped. A pooled ctx must sweep IDENTICALLY to one built at
    that configuration -- the genuine flag, the endpoint, the push, and the residual."""
    pool = ES.CtxPool()
    e = _ref_entry()
    for fac, lean, thrust, nsp in ((40820, 0, 15, 26.0), (40834, 64, 13, 22.673213958740234),
                                   (40841, 65432, 14, 8.3131036758422852), (40820, 0, 15, 26.0)):
        ctx, _s, resid = pool.get(fac, lean, thrust, nspeed=nsp)
        fresh, _s2, r2 = ES.build_fast(fac, lean, thrust, nspeed=nsp)
        a = ctx.sweep_par([(SEED['tetra'][0], SEED['tetra'][1], e[0], e[1])], 0)[0]
        b = fresh.sweep_par([(SEED['tetra'][0], SEED['tetra'][1], e[0], e[1])], 0)[0]
        assert a == b and _bits(resid(a)) == _bits(r2(b))
    assert pool.n_built == 3                     # three configurations, four gets


def test_the_uncapped_fan_is_the_capped_one_plus_its_sub_cap_endpoints():
    """Dropping the prune is additive, and the key grows a fourth element -- the endpoint's own
    speedF, because that is what picks the roll's schedule. Two candidates on the same point at
    different speeds are different draws, not a duplicate."""
    kw = dict(base_frames=(3,), stride=32, jmax=6)
    capped = ES.walk_fan(**kw)
    uncapped = ES.walk_fan(cap=None, **kw)
    assert all(len(k) == 3 for k in capped) and all(len(k) == 4 for k in uncapped)
    assert set(capped) <= set(k[:3] for k in uncapped)
    assert len(uncapped) > len(capped)
    assert all(k[3] == 17.0 for k in uncapped if k[:3] in capped)
    assert len(set(ES.roll_nspeed(k[3]) for k in uncapped)) > 1
    assert ES.candidate_nspeed(next(iter(capped))) == ES.ROLL_NSPEED


def test_the_aim_alphabet_is_every_angle_that_can_dispatch_not_the_octagon_boundary():
    """The alphabet sits between the two readings it has had. s79 read it as SIX wide off
    ``reachable_stick_fan(msd_min=1.0)``, the saturated boundary: too narrow, because the roll takes
    its speed from the walk cap and the aim needs no MAXIMAL magnitude. s79-s87 then read it as the
    whole 81-wide decoded grid: too wide, because a press below `LandState.ATTACK_MSD_MIN` is not a
    roll at all (session 88's console delivery -- `test_attack_threshold.py`). It is every angle with
    a representative deep enough to dispatch: 60 aims, of which the 11 saturated ones are a subset,
    and each fires the roll onto the facing it commands (read back, never assumed)."""
    wide = ES.aim_alphabet()
    saturated = [f for f, _ in ES.aim_alphabet(msd_min=1.0)]
    assert len(wide) == 60 and len(saturated) == 11
    assert len(ES.aim_alphabet(msd_min=0.0)) == 81            # the falsified reading, for diagnostics
    assert set(saturated) <= set(f for f, _ in wide)          # the narrow alphabet is a SUBSET
    for f, byts in wide[::12]:
        _, ent, _ = _sample_roll(want_facing=f)
        assert ent is not None and ent['facing'] == f
        assert TR.main_stick_decode(*byts)[1] > float(LandState.ATTACK_MSD_MIN)


def _sched_bits(facing, lean=0, thrust=15, nspeed=None):
    """Everything the facing reaches in a baked roll, as a comparable tuple."""
    s = ES.fast_schedule(facing, lean, thrust, nspeed=nspeed)
    return (tuple(s['dx']), tuple(s['dz']), tuple(s['cutx']), tuple(s['cutz']), s['nroot'],
            tuple(tuple(r) for r in s['chx']), tuple(tuple(r) for r in s['chz']))


def test_the_aim_alphabet_resolves_to_the_sine_table_cell():
    """THE AIM'S REAL RESOLUTION IS 16 BAM, NOT 1. `cM_ssin_s16` is JMASSin --
    ``jmaSinTable[(u16)angle >> 4]``, 4096 entries, no interpolation -- and every term a facing
    reaches goes through it, so one cell is ONE draw, bit-for-bit: the same travel, the same cut
    rotation, the same Co pose chain, and the same 26 u entry step."""
    cell = ES.PRODUCTIVE_CELLS[0]
    lo = cell * ES.SIN_CELL_BAM
    base, ent = _sched_bits(lo), ES.roll_entry((0.0, 0.0), lo)
    for f in range(lo, lo + ES.SIN_CELL_BAM):
        assert ES.aim_cell(f) == cell
        assert _sched_bits(f) == base                              # 0-ULP, not a tolerance
        assert ES.roll_entry((0.0, 0.0), f) == ent
        assert (ML.cM_ssin_s16(f), ML.cM_scos_s16(f)) == (ML.cM_ssin_s16(lo), ML.cM_scos_s16(lo))
    nxt = lo + ES.SIN_CELL_BAM
    assert ES.aim_cell(nxt) == cell + 1
    assert _sched_bits(nxt) != base and ES.roll_entry((0.0, 0.0), nxt) != ent
    # and the alphabet collapses onto those atoms, siblings kept for `confirm_entry`
    aims, cells = ES.aim_alphabet(), ES.aim_cells()
    assert len(aims) == 60 and len(cells) == 45      # 81 / 49 before the session-88 ATTACK gate
    assert sum(len(sib) for _, _, sib in cells) == len(aims)
    assert len({ES.aim_cell(f) for f, _, _ in cells}) == len(cells)


def test_the_camera_cannot_add_an_aim_cell_inside_the_weak_form_window():
    """THE CAMERA AXIS, PRICED AT ZERO (session 83) -- **AND THE PRICE EXPIRES WITH ITS PREMISE.**

    Across `PRODUCTIVE_CELLS`, which is the 32 BAM the weak form reported, the frozen csangle already
    reaches every cell the range contains and no offset can add one, so the lever really is worth zero
    THERE. Session 88 halved the aim count without changing that: two of the four aims were
    representatives too shallow to dispatch a roll, so "four aims, two draws" became "two aims, two
    draws".

    What session 92 changed is the RANGE, not this arithmetic: the real window is 22 live cells in two lobes
    (`curve_scan`, `fixtures/courtyard_facing_window_s92.json`), several live cells are NOT aimable
    frozen, and one of those is the rightmost with a workable band -- so the camera is a live lever
    again. This test is kept scoped to `PRODUCTIVE_CELLS` on purpose: it is the historical marker's own
    arithmetic, and the name says so."""
    lo, hi = ES.PRODUCTIVE_CELLS[0] * ES.SIN_CELL_BAM, (ES.PRODUCTIVE_CELLS[-1] + 1) * ES.SIN_CELL_BAM - 1

    def in_window(cs):
        return {ES.aim_cell(f) for f, _ in ES.aim_alphabet(cs) if lo <= f <= hi}

    frozen = in_window(ES.CSANGLE)
    assert frozen == set(ES.PRODUCTIVE_CELLS)              # already every cell the window contains
    for d in range(ES.SIN_CELL_BAM):
        assert in_window(ES.CSANGLE + d) <= frozen         # a slew can only re-index, never add
    # the same two cells; one dispatching aim each now, and the shallow siblings that used to double
    # the count are still bit-identical within their cell -- the per-cell claim, on the wider set
    aims = sorted(f for f, _ in ES.aim_alphabet(ES.CSANGLE) if lo <= f <= hi)
    assert len(aims) == 2 and {ES.aim_cell(f) for f in aims} == set(ES.PRODUCTIVE_CELLS)
    e = _ref_entry()
    per_cell = {}
    for f in sorted(f for f, _ in ES.aim_alphabet(ES.CSANGLE, msd_min=0.0) if lo <= f <= hi):
        ctx, sch, resid = ES.build_fast(f, 0, 15)
        o = ctx.sweep_par([(SEED['tetra'][0], SEED['tetra'][1], *ES.roll_entry(e, f))], 0)[0]
        per_cell.setdefault(ES.aim_cell(f), []).append(resid(o))
    assert len(per_cell) == 2
    for rs in per_cell.values():
        assert len(rs) == 2 and rs[0] == rs[1]             # the same draw, counted twice


def test_the_cameras_only_remaining_reach_is_the_walk_and_it_is_a_few_percent():
    """Where a csangle slew still does something: the WALK. A held stick's world direction is
    ``decoded + 0x8000 + csangle``, quantized to the same cell, and the decoded grid is not uniform,
    so a few cells are unreachable at one camera and reachable at another. It is a candidate axis
    worth ~7%, not a configuration axis -- and s81 measured 1.6x candidates buying zero draws."""
    angs = [a for a, _ in TR.reachable_stick_fan(msd_min=0.0)]
    frozen = {((a + 0x8000 + ES.CSANGLE) & 0xFFFF) >> 4 for a in angs}
    union = set(frozen)
    for d in range(ES.SIN_CELL_BAM):
        union |= {((a + 0x8000 + ES.CSANGLE + d) & 0xFFFF) >> 4 for a in angs}
    assert len(frozen) < 4096                              # the grid does NOT cover every direction
    assert 1.0 < len(union) / len(frozen) < 1.2            # and the slew is a few percent, not 8x


def test_each_thrust_step_bakes_its_own_locus():
    """13/14/15 all dispatch a CUT, land it on a different step, and read a different residual at one
    entry -- three independent draws of the same lottery, not one."""
    e = tuple(min((h for h in LOCUS['hits'] if h['follow_ok']),
                  key=lambda h: math.hypot(h['entry'][0] - SEED['link'][0],
                                           h['entry'][1] - SEED['link'][1]))['entry'])
    seen = {}
    for thrust in ES.THRUSTS:
        ctx, sch, resid = ES.build_fast(40884, 0, thrust)
        assert sch['cut_step'] == thrust + 2
        o = ctx.sweep_par([(SEED['tetra'][0], SEED['tetra'][1], e[0], e[1])], 0)[0]
        seen[thrust] = resid(o)
    vals = sorted(seen.values())
    assert min(abs(a - b) for a, b in zip(vals, vals[1:])) > 0.1   # genuinely different razors


def _ref_entry():
    return tuple(min((h for h in LOCUS['hits'] if h['follow_ok']),
                     key=lambda h: math.hypot(h['entry'][0] - SEED['link'][0],
                                              h['entry'][1] - SEED['link'][1]))['entry'])


def test_the_acceptance_band_is_per_configuration_not_the_fixture_window():
    """THE CORRECTION THAT EXPLAINS A THOUSAND NEAR-MISSES AND ZERO CLIPS. The fixture's window was
    measured at ONE configuration (facing 40835, thrust 14) off the tabulated coords, so it is a
    UNION. A single configuration's own band is narrower and offset -- and all of them sit on the
    POSITIVE side, so a search centred on resid 0 aims between them."""
    w = LOCUS['window']
    b = ES.configuration_band(SEED['tetra'], LOCUS['facing'], TA.THRUST, 0, _ref_entry())
    assert b['productive'] and b['n_genuine'] > 0
    assert b['lo'] > 0.0 and b['hi'] <= w['hi']              # inside the union, on its positive half
    assert b['width'] <= w['width']


@pytest.mark.slow
def test_no_leverage_is_a_property_of_the_seed_entry_not_of_the_configuration():
    """WHAT "MOST CONFIGURATIONS HAVE NO LOCUS" ACTUALLY MEANT (corrected, session 92).

    Measured from ONE `ref_entry`, two thirds of the configurations read `grad ~ 0` -- the measurable
    form of "the pushed actor is out of Co range on the cut frame, so no knob moves the razor". That
    reading was taken as a property of the CONFIGURATION and became the search's scope: a ~21 BAM
    productive facing window, cells 2551-2552.

    It is a property of the ENTRY. `resid` crosses zero somewhere in the reachable box for every cell
    in the seam's window, and seeded off its own curve the same configuration has walkable live
    stations. So the no-leverage reading survives here as a fact about this seed, and the productive
    facings reach well outside the old window -- see
    [../knowledge/history/entry-search-one-seed-negative.md]."""
    ref = _ref_entry()
    facings = [40773, 40820, 40834, 40925, 41037]
    weak = ES.qualify(SEED['tetra'], ref, facings=facings, thrusts=(14, 15), escalate=False)
    assert sum(1 for q in weak if q['productive']) < len(weak) / 2
    assert any(q['reason'] == 'no leverage' and q['grad'] < 1e-3
               for q in weak if not q['productive'])

    strong = ES.qualify(SEED['tetra'], ref, facings=facings, thrusts=(14, 15))
    prod = [q for q in strong if q['productive']]
    assert prod, "the tabulated facing must still qualify"
    assert len(prod) > sum(1 for q in weak if q['productive'])
    assert any(q['facing'] > 40860 for q in prod), "the window is not the old 21 BAM band"


@pytest.mark.slow
def test_the_search_spends_candidates_only_where_a_locus_exists():
    """`search` qualifies before it sweeps, which is what makes the fan the remaining budget rather
    than the alphabet: the same candidates cost 6 configurations instead of 243. Slow because it
    qualifies the whole alphabet (~135 s), which is the point."""
    fan = ES.walk_fan(base_frames=(3,), stride=64, jmax=6)
    r = ES.search(candidates=fan)
    assert 0 < r['n_configurations'] <= 12
    assert all(q['lo'] is not None and q['lo'] > 0.0 for q in r['configurations'])
    assert all(h['walkable'] for h in r['hits'])


def test_the_rank_is_the_signed_distance_to_the_window_not_the_absolute_residual():
    """s79's best candidate was -5.45e-5: smaller in |resid| than the window is WIDE, and on the
    blocked side of the gap. `window_gap` is 0 only inside the window and scores that candidate as the
    miss it is."""
    w = LOCUS['window']
    assert ES.window_gap(0.5 * (w['lo'] + w['hi']), w) == 0.0
    assert ES.window_gap(w['lo'], w) == 0.0 and ES.window_gap(w['hi'], w) == 0.0
    blocked = ES.window_gap(-5.45e-05, w)
    assert blocked > 0.0 and blocked > w['width'] * 0.4
    assert ES.window_gap(w['hi'] + 1e-6, w) == pytest.approx(1e-6, rel=1e-6)


@pytest.mark.slow
def test_the_fan_labels_a_plan_the_a_press_reproduces():
    """The fan never presses A, it PREDICTS. `confirm_entry` replays a plan and presses A for real.

    Two things this pins. The plan label is off-by-one against the fan's own step count
    (`INPUT_DELAY` again) and is now measured, not assumed. And the prediction is not universal: when
    the aim swings far from travel the entry frame BRAKES before the roll dispatches, so nspeed lands
    under 26 and the predicted entry is wrong. Most confirm; the rest are why every hit owes a
    `confirm_entry` before it is quoted."""
    fan = ES.walk_fan(base_frames=(3,), stride=32, jmax=8)
    fac, byts = ES.aim_alphabet()[40]
    ok, rolled, checked = 0, 0, 0
    for k, plan in sorted(fan.items())[:24]:
        h = dict(plan=list(plan), aim=list(byts), facing=fac, walk=[k[0], k[1]],
                 m351C=ES.lean_at_roll(k[2]), entry=list(ES.roll_entry((k[0], k[1]), fac)))
        r = ES.confirm_entry(h)
        checked += 1
        rolled += r['ok']['rolled']
        ok += r['all_ok']
        if r['ok']['rolled']:
            # whenever it DOES roll, the walk endpoint, facing and lean are exactly what was labelled
            assert r['ok']['walk_matches'] and r['ok']['facing'] and r['ok']['lean']
    assert ok >= 0.75 * checked and rolled >= 0.8 * checked


def test_the_walk_fan_keeps_only_capped_pinned_candidates():
    """The two hard prunes: speedF exactly 17.0 (the roll takes its whole nspeed from the cap) and
    inside the 230 u follow bar on every frame -- one frame outside and Tetra is not a constant."""
    fan = ES.walk_fan(base_frames=(3,), stride=64, jmax=6)
    assert fan
    run, _ = ES.continue_walk([])
    tx, tz = SEED['tetra']
    for (x, z, lean), plan in fan.items():
        assert math.hypot(x - tx, z - tz) <= ES.FOLLOW_BAR
        assert 1 <= plan[3] <= 6 and plan[0] == 3


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


# ------------------------------------- the exit angle: the cell is the atom, and the cut is PINNED

def test_the_exit_direction_is_quantized_to_the_sine_table_cell():
    """WHY THE EXIT ANGLE IS COUNTED IN CELLS (Dereck's session-91 objective term). What carries Link
    downstream out of the clip is `travel` -- equal to `facing` through the roll -- and every use of it
    goes through `cM_ssin_s16`/`cM_scos_s16`, which are `jmaTable[(u16)angle >> 4]` with no
    interpolation. So two facings in one 16 BAM cell leave Link on a BIT-IDENTICAL heading, and the
    exit angle has a hard 0.087891 deg quantum. Asking for "the rightmost facing" is asking for the
    rightmost CELL."""
    for cell in (2552, 2553, 2561):
        base = (ML.cM_ssin_s16(cell << 4), ML.cM_scos_s16(cell << 4))
        for k in range(16):
            f = (cell << 4) + k
            assert (ML.cM_ssin_s16(f), ML.cM_scos_s16(f)) == base
            assert _bits(ML.cM_ssin_s16(f)) == _bits(base[0])
        nxt = (ML.cM_ssin_s16((cell + 1) << 4), ML.cM_scos_s16((cell + 1) << 4))
        assert nxt != base
    step = math.degrees(math.atan2(*(ML.cM_ssin_s16(2553 << 4), ML.cM_scos_s16(2553 << 4)))) \
        - math.degrees(math.atan2(*(ML.cM_ssin_s16(2552 << 4), ML.cM_scos_s16(2552 << 4))))
    assert step == pytest.approx(16 / 65536 * 360, rel=1e-3)


def test_the_entry_does_not_move_links_cut_position_it_is_the_wall_brace():
    """THE CLIP MAP'S PREMISE, FALSIFIED (session 92). `_generated/viz/tetra_clip_map.json` sweeps
    `old` -- Link's position at the CUT -- and session 91 read its spread as a steering wheel worth
    +126 BAM if Link cut from 0.44 u away. He cannot: the roll drives him into the corner and
    `CrrPos` pins him at exactly `WALL_R` from wall A, an attractor with a 30 u basin. Slide the entry
    a whole roll step and `old` does not move one f32 ULP.

    What the entry DOES move is the cut-frame PUSH (Tetra is plowed differently on the way in), and
    that is the only term with leverage on the razor -- which is why `resid` slides smoothly while
    `old` stays frozen."""
    hit = _s90_frame_minimal()
    e = (hit['entry'][0], hit['entry'][1])
    ctx, sch, resid = ES.build_fast(hit['facing'], hit['m351C'], hit['thrust'], e,
                                    nspeed=hit['nspeed'])
    sx, cz = ML.cM_ssin_s16(hit['facing']), ML.cM_scos_s16(hit['facing'])
    ts = [-1.0, -0.5, -0.1, 0.0, 0.1, 0.5, 1.0]
    rows = ctx.sweep_par([(SEED['tetra'][0], SEED['tetra'][1], e[0] + t * sx, e[1] + t * cz)
                          for t in ts], 0)
    olds = set((_bits(o[1]), _bits(o[2])) for o in rows)
    assert len(olds) == 1, "the cut position is the wall brace, not a free variable"
    resids = [resid(o) for o in rows]
    assert resids == sorted(resids, reverse=True)       # smooth in the entry, through the PUSH alone
    assert abs(resids[0] - resids[-1]) > 1e-2           # and it really does move the razor

    for o in rows:                                     # and the pinned point IS wall A's 35.0 brace
        assert abs(GT.wA.pla.func((o[1], GT.LINK_Y, o[2]))) == pytest.approx(35.0, abs=1e-3)


# ----------------------------------- a NEGATIVE about a configuration is argued from the WHOLE curve

@pytest.mark.slow
def test_the_escalation_recovers_the_cell_one_station_reads_barren():
    """THE GATE SESSION 91 OWED. `configuration_band` sweeps ACROSS the locus at ONE station, so a
    configuration whose genuine dust has slid ALONG the curve reads barren. Cell 2553 (facings
    40848..40863) is exactly that: barren here, and richly live under `locus_scan` -- so every pass
    from session 81 to 89 silently excluded the righter third of the seam's own facing window."""
    ref = _ref_entry()
    b = ES.configuration_band(SEED['tetra'], 40850, 15, 0, ref)
    assert not b['productive'] and b['reason'] == 'no genuine on the residual zero'
    sc = ES.locus_scan(SEED['tetra'], 40850, 15, 0, ref)
    assert sc['live'] > 0 and sc['walkable'] > 0
    re_seeded = ES.configuration_band(SEED['tetra'], 40850, 15, 0, sc['walkable_at'][0])
    assert re_seeded['productive']


@pytest.mark.slow
def test_the_second_lobe_needs_the_curve_to_find_its_own_seeds():
    """THE SAME TRAP ONE LEVEL DEEPER (session 92), and it was hiding the whole exit-angle axis.

    `locus_scan` is the strong form, but it MARCHES from one Newton solve at `ref_entry` and returns
    nothing at all when THAT point has no leverage -- having sampled the locus nowhere. Leverage is a
    property of the ENTRY (whether the plowed Tetra is still in Co range on the cut frame), so a
    righter facing, whose roll leaves her behind from this seed, reads `no leverage at the seed` and is
    dropped. `curve_scan` seeds off the residual-zero curve's own crossings instead.

    Cell 2561 is +144 BAM of exit angle over the delivered clip (`courtyard_clip_s90_console.json`)
    and reads barren under BOTH weaker forms."""
    ref = _ref_entry()
    for facing in (40978, 40994):
        b = ES.configuration_band(SEED['tetra'], facing, 15, 0, ref)
        ls = ES.locus_scan(SEED['tetra'], facing, 15, 0, ref)
        assert not b['productive'] and b['reason'] == 'no leverage'
        assert ls['reason'] == 'no leverage at the seed' and ls['stations'] == 0
        cs = ES.curve_scan(SEED['tetra'], facing, 15, 0, ref)
        assert cs['n_seeds'] > 0 and cs['stations'] > 0
        assert cs['live'] > 0 and cs['walkable'] > 0
        assert ES.configuration_band(SEED['tetra'], facing, 15, 0, cs['walkable_at'][0])['productive']


@pytest.mark.slow
def test_the_recovered_dust_is_a_real_clip_and_not_the_refusal_shape():
    """A `genuine` verdict is only worth spending a delivery on if Link actually goes THROUGH the seam:
    session 88's expensive rejection class is `ShoveCtx` scoring ~49.9 u where the composite refuses to
    move him at all (~0.15 u). Every recovered second-lobe station lunges the real distance, and the
    lunge GROWS to the right -- which is session 91's "the lunge buys angle", falling out of the same
    geometry rather than being a second lever."""
    ref = _ref_entry()
    lunges = {}
    for facing in (40834, 40978, 41058):
        cs = ES.curve_scan(SEED['tetra'], facing, 15, 0, ref)
        stations = cs['walkable_at'] or cs['live_at']
        assert stations, "facing %d must have live dust to check" % facing
        best = 0.0
        for st in stations:
            g = ES.entry_gradient(SEED['tetra'], st, facing=facing, m351c=0, thrust=15)
            if g['grad'] == 0.0:
                continue
            ux, uz = g['gx'] / g['grad'], g['gz'] / g['grad']
            pts = [(st[0] + (2.0 * i / 2000 - 1.0) * 0.02 * ux,
                    st[1] + (2.0 * i / 2000 - 1.0) * 0.02 * uz) for i in range(2001)]
            ctx, _sch, _r = ES.build_fast(facing, 0, 15, ref)
            for o in ctx.sweep_par([(SEED['tetra'][0], SEED['tetra'][1], p[0], p[1]) for p in pts], 0):
                if o[0]:
                    best = max(best, math.hypot(o[3] - o[1], o[4] - o[2]))
            if best > XE.CLIP_LUNGE_MIN:
                break
        lunges[facing] = best
        assert best > XE.CLIP_LUNGE_MIN, "facing %d: lunge %.4f is the refusal shape" % (facing, best)
    assert lunges[41058] > lunges[40834]


@pytest.mark.slow
def test_the_facing_window_fixture_is_two_lobes_with_a_dead_gap():
    """THE MEASURED WINDOW, pinned so the two-lobe shape cannot silently narrow back to one (session
    92). The fixture is a MODEL output and cheap to re-derive per cell, so this checks its structure
    against the claims the strategy page makes AND re-measures one cell from each side of the gap so it
    cannot rot: the dead gap has to stay dead and the second lobe has to stay live."""
    fx = json.load(open(_fx('courtyard_facing_window_s92.json')))
    rows = {r['cell']: r for r in fx['rows']}
    assert fx['delivered']['cell'] == ES.aim_cell(_s90_frame_minimal()['facing'])
    assert fx['cell_bam'] == ES.SIN_CELL_BAM

    for lo, hi in fx['lobes']:
        assert all(rows[c]['live'] > 0 for c in range(lo, hi + 1)), "lobe %d-%d" % (lo, hi)
    for c in range(fx['dead_gap'][0], fx['dead_gap'][1] + 1):
        assert rows[c]['live'] == 0 and rows[c]['n_curve_seeds'] > 20   # a covered curve, no dust
    assert fx['delivered']['cell'] in range(fx['lobes'][0][0], fx['lobes'][0][1] + 1)

    right = max(c for c, r in rows.items() if r['live'] > 0)
    assert (right - fx['delivered']['cell']) * 16 >= 144            # the axis, in BAM to the right
    for r in fx['rows']:
        if r['sample_lunge'] is not None:
            assert r['sample_lunge'] > XE.CLIP_LUNGE_MIN            # never the refusal shape

    ref = tuple(fx['ref_entry'])
    dead = ES.curve_scan(SEED['tetra'], rows[fx['dead_gap'][0]]['facing'], fx['thrust'],
                         fx['lean'], ref, nspeed=fx['nspeed'])
    live = ES.curve_scan(SEED['tetra'], rows[fx['lobes'][1][0] + 1]['facing'], fx['thrust'],
                         fx['lean'], ref, nspeed=fx['nspeed'])
    assert dead['n_seeds'] > 20 and dead['live'] == 0
    assert live['live'] > 0 and live['walkable'] > 0
