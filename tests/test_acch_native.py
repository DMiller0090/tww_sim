"""`dBgS_Acch::CrrPos` in the native core vs `core.collision.acch_crr_pos` -- 0 ULP, not a tolerance.

`_anmc`'s `_acchc.pxi` is the wall pass `LandCore.step_courtyard` brackets both actors with, and it is
a transcription: Python is the ORACLE and every value has to come back `_bits`-equal. Per
`[[zero-ulp-tests-only]]` nothing here compares to a tolerance -- a 1-ULP wall brace is what turns a
razor clip into a block, and the port opened exactly one such gap while it was being written (the
entry `_f()` rounds of the two endpoints, which the console has no f64 to skip).

The sweep is a deterministic lattice over the real courtyard mesh at BOTH actors' cylinders (Link's
three 30.1/89.9/125.0 at R 35 with the gravity dip, Tetra's single 30.0 at R 50 with speed_y 0), sized
so a few hundred candidates genuinely correct against geometry -- a sweep that never touches a wall
proves nothing. It replays no search: the lattice is the fixture."""
import struct

import pytest

from tww_sim.core.collision import acch_crr_pos
from tww_sim.core.npc_zl1 import WALL_H as TETRA_WALL_H, WALL_R as TETRA_WALL_R
from tww_sim.land.walls import WALL_H as LINK_WALL_H, WALL_R as LINK_WALL_R, GRAVITY


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _f(x):
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


@pytest.fixture(scope='module')
def mesh():
    from tww_sim.core.anim import foot_fk          # noqa: F401  (arms init_atan_table)
    from tww_sim.core.anim import _anmc as N
    if not hasattr(N, 'WallMesh'):
        pytest.skip("native _anmc lacks WallMesh (stale build)")
    from harness.rollstab import turnaround as TA
    return N.WallMesh(TA.WALLS), TA.WALLS


def _lattice():
    """Old/new f32 pairs across the courtyard's walled quadrant: a 24x14 grid of `old`, each stepped
    by four 26 u roll-length moves (the clip roll's own displacement scale)."""
    for i in range(24):
        ox = _f(-2100.0 + 30.0 * i)
        for j in range(14):
            oz = _f(-1040.0 + 32.0 * j)
            for dx, dz in ((26.0, 0.0), (0.0, -26.0), (-18.5, -18.5), (18.5, 18.5)):
                yield (ox, oz, _f(ox + dx), _f(oz + dz))


@pytest.mark.parametrize('actor', ['link', 'tetra'])
def test_native_crr_pos_is_the_python_pass_bit_for_bit(mesh, actor):
    """Every corrected position, every hit flag and every wall angle, `_bits`-equal over the lattice."""
    wm, tris = mesh
    if actor == 'link':
        wh, wr, sy = LINK_WALL_H, LINK_WALL_R, GRAVITY
    else:
        wh, wr, sy = TETRA_WALL_H, TETRA_WALL_R, 0.0
    n = hits = 0
    for ox, oz, nx, nz in _lattice():
        old = (ox, 0.0, oz)
        new = (nx, _f(sy), nz)                 # the mid-frame dipped y CrrPos actually sees
        got, ginfo = wm.crr_pos(old, new, wh, wr, sy)
        want, winfo = acch_crr_pos(old, new, tris, speed_y=sy, wall_h=wh, wall_r=wr)
        n += 1
        hits += 1 if winfo['wall_hit'] else 0
        for ax in range(3):
            assert _bits(got[ax]) == _bits(want[ax]), (
                '%s axis %d at old=%r new=%r: native %r vs python %r (%d ULP)'
                % (actor, ax, old, new, got[ax], want[ax], _bits(got[ax]) - _bits(want[ax])))
        assert ginfo['wall_hit'] == winfo['wall_hit'], (old, new)
        assert ginfo['line_hit'] == winfo['line_hit'], (old, new)
        assert list(ginfo['cir_hit']) == list(winfo['cir_hit']), (old, new)
        assert list(ginfo['wall_angle']) == list(winfo['wall_angle']), (old, new)
    assert n >= 1000, 'the lattice shrank -- %d cases is not a sweep' % n
    assert hits >= 100, (
        'only %d of %d cases corrected against a wall: a pass that never braces proves nothing' % (hits, n))


def test_the_mesh_is_shared_not_copied(mesh):
    """The `WallMesh` is immutable dev data, so a beam shares ONE -- a per-node copy of 48 tris is
    what the `AnimData` contract exists to avoid, and `LandCore.clone` relies on it."""
    wm, tris = mesh
    from harness.tetrapush.from_f0 import _wall_mesh
    assert _wall_mesh(tris) is _wall_mesh(tris)
    assert _wall_mesh(None) is None
    assert wm.size == len(tris)
