"""**THE DUST DENSITY PER REACHABLE ENTRY** (`harness.tetrapush.entry_dust`, session 156).

Session 155 left the sweep barren with a named refusal -- every near-razor row's swept lunge path hits the
wall -- and a lever: the baked schedule is entry-position-independent, so the acceptance is a map over the
roll ENTRY. The entry is an f32 pair, so that map is sampled on a LATTICE, and these gates pin what the
lattice says:

  * the lattice pitch is one f32 ULP, bit-derived, and a sub-ULP arithmetic offset rounds back onto the
    same entry (which is why the older probes' sub-ULP sweeps re-tested one point ~12 times);
  * two facings inside one 16-BAM sine cell measure the SAME dust, so a cell is one probe;
  * s154's accepted 101 sits on a cell that carries dust, and cells 32 and 16 BAM away carry NONE over a
    300 u march -- the positive and the negative control of the session's headline, that the axis deciding
    whether any entry can clip is the roll FACING;
  * a configuration with no contact at the cut reports ``no leverage`` with ``tested = 0`` instead of a
    fabricated zero density (outside contact the razor's residual is a dead constant);
  * `needed_multiplier` refuses to put a number on a cell that measured no dust, and omits one that was
    never sampled.

Offline: the native `ShoveCtx` through `entry_search.build_fast` (no Dolphin). Every number here is a
MEASUREMENT of deterministic offline code, so it is pinned exactly.
"""
import json
import os
import struct

import pytest

from harness.tetrapush import entry_dust as ED
from harness.tetrapush import entry_search as ES


# s154's accepted 101 -- genuine, `confirm_entry`-confirmed, `cross_engine` deliverable at total 101.
# Inlined rather than read from the gitignored `_notes/` run that produced it.
FACING, LEAN, THRUST = 40727, 104, 15
CELL = 2545
TETRA = (-1654.9884033203125, -923.457763671875)
ENTRY = (-1591.7647705078125, -848.5638427734375)
WALK = (-1573.807861328125, -829.7609252929688)
DEAD_FACINGS = (40775, 40711)             # cells 2548 and 2544, +48 / -16 BAM off the accepted cell
LIVE_PAIR = (40817, 40823)                # two facings inside cell 2551
MARCH = dict(span=150.0, step=3.0, k=4)


def _bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


# ------------------------------------------------------------------- the lattice is the denominator

def test_the_entry_lattice_pitch_is_one_f32_ulp_and_bit_stepped():
    """`entry_ulp` / `lattice_step` are the f32 lattice, derived from the bit pattern -- and stepping
    NEGATIVE coordinates (the whole courtyard is negative) moves the right way."""
    u = ED.entry_ulp(ENTRY[0])
    assert u == 0.0001220703125                       # ULP at |x| in [1024, 2048)
    assert ED.lattice_step(ENTRY[0], 1) - ENTRY[0] == pytest.approx(u, abs=0.0)
    assert ED.lattice_step(ENTRY[0], -1) - ENTRY[0] == pytest.approx(-u, abs=0.0)
    assert _bits(ED.lattice_step(ENTRY[0], 3)) == _bits(ENTRY[0]) - 3      # negative: bits count down
    assert ED.lattice_step(ENTRY[0], 0) == ENTRY[0]


def test_a_sub_ulp_arithmetic_offset_rounds_back_onto_the_same_entry():
    """THE DEFECT THE LATTICE DENOMINATOR FIXES. `configuration_band` steps 1e-05 u and `locus_scan`
    2e-05 u, both far under the 1.22e-04 u pitch, so consecutive samples ARE the same f32 entry and
    their "N samples" is not N tests. Measured here rather than argued."""
    same = sum(1 for i in range(12)
               if _bits(struct.unpack('<f', struct.pack('<f', ENTRY[0] + i * 1e-05))[0])
               == _bits(ENTRY[0]))
    assert same >= 6, same
    assert _bits(struct.unpack('<f', struct.pack('<f', ENTRY[0] + 2e-05))[0]) == _bits(ENTRY[0])


def test_two_facings_in_one_cell_measure_the_same_dust():
    """A CELL IS ONE PROBE. Both facings of `LIVE_PAIR` are in cell 2551, so the whole march -- station
    set, lattice entries, genuine count -- must come back identical, not merely close."""
    a, b = LIVE_PAIR
    assert ES.aim_cell(a) == ES.aim_cell(b) == 2551
    da = ED.dust_density(TETRA, a, THRUST, LEAN, ENTRY, **MARCH)
    db = ED.dust_density(TETRA, b, THRUST, LEAN, ENTRY, **MARCH)
    for key in ('stations', 'tested', 'genuine', 'density', 'grad', 'zero_entry', 'cell'):
        assert da[key] == db[key], key


# --------------------------------------------------- the facing is the axis, positive + negative control

def test_the_accepted_101s_own_cell_carries_dust():
    """POSITIVE CONTROL: the configuration that produced a deliverable 101 measures dust on ~1 in 23 of
    the f32 entries its own locus passes through."""
    d = ED.dust_density(TETRA, FACING, THRUST, LEAN, ENTRY, **MARCH)
    assert d['cell'] == CELL and d['reason'] == ''
    assert (d['stations'], d['tested'], d['genuine']) == (65, 5265, 228)
    assert d['density'] == pytest.approx(0.04330484, abs=1e-8)
    assert d['dust'] and all(x['walkable'] for x in d['dust'])


def test_the_neighbouring_cells_carry_none_over_the_same_march():
    """NEGATIVE CONTROL, and the session's headline: 48 and 16 BAM off the accepted cell the dust is
    GONE -- 0 genuine over ~4800 lattice entries each -- while the residual still zeroes and the
    gradient is the same order. So the facing decides whether any entry can clip, and `resid` cannot
    see it."""
    for fac in DEAD_FACINGS:
        d = ED.dust_density(TETRA, fac, THRUST, LEAN, ENTRY, **MARCH)
        assert d['reason'] == '' and d['stations'] > 50
        assert d['tested'] > 4500
        assert d['genuine'] == 0 and d['density'] == 0.0
        assert 0.3 < d['grad'] < 1.0                  # not an artefact of a dead or steep razor


def test_the_richest_cell_is_an_order_of_magnitude_denser_than_the_delivered_one():
    """Cell 2551 carries 719 of 4617 (1 in 6) against the accepted cell's 1 in 23 -- the spread across
    ADJACENT cells is what makes a per-cell prefilter worth computing before a fan."""
    live = ED.dust_density(TETRA, LIVE_PAIR[0], THRUST, LEAN, ENTRY, **MARCH)
    assert (live['cell'], live['tested'], live['genuine']) == (2551, 4617, 719)
    assert live['density'] > 3.0 * 0.04330484


def test_the_live_dead_verdict_survives_reseeding_the_march():
    """The marched ARC depends on the seed entry, so the counts move; the live/dead VERDICT does not.
    Seeded from each cell's own `roll_entry` off the walk endpoint (what `cell_dust(walk=...)` does),
    the dead cells stay empty and the live ones stay live. A shorter march than `MARCH` on purpose --
    the claim is the verdict, and four full 300 u marches cost more than the per-test budget."""
    cd = ED.cell_dust(TETRA, THRUST, LEAN, ENTRY, [2544, CELL, 2548, 2551], walk=WALK,
                      span=90.0, step=3.0, k=3)
    assert cd[2544]['genuine'] == 0 and cd[2548]['genuine'] == 0
    assert cd[2544]['tested'] > 1800 and cd[2548]['tested'] > 1800
    assert cd[CELL]['genuine'] > 0 and cd[2551]['genuine'] > 0
    assert [c for c, _d in ED.live_cells(cd)] == [2551, CELL]          # richest first


# ------------------------------------------------------------------- what a barren reading may claim

def test_an_off_contact_configuration_reports_no_leverage_not_a_zero_density():
    """Outside contact the razor's residual is a DEAD CONSTANT, so a zero density there would be a
    fabricated measurement. The console seed's Tetra at the accepted row's own facing is that case:
    ``grad`` collapses, nothing is tested, and the reason says so."""
    d = ED.dust_density(ES.console_seed()['tetra'], FACING, THRUST, LEAN, ENTRY, span=24.0, step=3.0,
                        k=2)
    assert d['reason'] == 'no leverage at the seed'
    assert d['tested'] == 0 and d['stations'] == 0 and d['density'] == 0.0
    assert d['grad'] == 0.0


def test_needed_multiplier_will_not_number_an_unmeasured_cell():
    """An unbounded multiplier is not a number: a cell with no dust maps to None (never `inf`, which
    would sort into a rank), and a cell that was never sampled is omitted rather than called sparse."""
    cd = {1: dict(tested=400, genuine=8, density=0.02),
          2: dict(tested=400, genuine=0, density=0.0),
          3: dict(tested=0, genuine=0, density=0.0)}
    m = ED.needed_multiplier(cd, 0.04)
    assert m == {1: 2.0, 2: None}
    assert 3 not in m
