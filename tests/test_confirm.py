"""`harness.tetrapush.confirm` -- the on-demand clip-viability gate and its branch-and-bound.

Session 142's lesson in one module: a precomputed genuine set is a table, and a table is only as good
as its grid, so viability is COMPUTED per candidate and cached on exact bits. These gate the two
properties that make the design sound rather than merely fast -- the cache cannot merge two distinct
Tetras, and the scan cannot stop early on a candidate that could still win.

Pure logic, no engine: `confirmed` is stubbed so the bound arithmetic and the stop rule are tested
directly (a functionality test does not take a second -- `tests/conftest.py`).
"""
import pytest

from harness.tetrapush import confirm as CF


class _PF(object):
    facing, thrust, lean, cut_step = 40660, 11, 0, 13


def test_the_cache_key_separates_tetras_a_razor_apart():
    """The confirmed band is ~7e-4 u wide, so rounding the key would merge two different questions
    (`[[full-fp-precision-coords]]`)."""
    pf, rw = _PF(), (160, 170)
    a = CF._key(pf, (-1615.514893, -887.797729), rw)
    b = CF._key(pf, (-1615.514893 + 1e-9, -887.797729), rw)
    assert a != b
    assert a == CF._key(pf, (-1615.514893, -887.797729), rw)
    # the terminal and the runway set are part of the question, not context
    assert a != CF._key(pf, (-1615.514893, -887.797729), (160, 170, 180))


def test_branch_and_bound_stops_only_when_nothing_left_can_win(monkeypatch):
    """``bound_lo`` (the roots bound) is an under-estimate by construction, so a candidate whose
    ``bound_lo`` already exceeds the best CONFIRMED bound cannot beat it -- and everything before that
    point must be confirmed, not skipped."""
    pf = _PF()
    # only the third candidate confirms, at a true bound well above its lower bound
    table = {3: (5, 40.0)}
    seen = []

    def _fake(pf_, tetra, link=None, runways=(), **kw):
        seen.append(tetra[0])
        n, gap = table.get(int(tetra[0]), (0, None))
        return dict(n=n, entries=[], gap=(float('inf') if not n else gap),
                    best=[0.0, 0.0, 0.0, 0.0, 0.0])

    monkeypatch.setattr(CF, 'confirmed', _fake)
    cands = [dict(label='c%d' % i, frames=70, bound_lo=80.0 + i, tetra=(float(i), 0.0),
                  link=(0.0, 0.0)) for i in range(1, 8)]
    best, scanned = CF.best_confirmed(pf, cands)
    assert best is not None and best['tetra'][0] == 3.0
    # 70 + 40/WALK_CAP + 13
    assert best['bound'] == pytest.approx(70 + 40.0 / CF.HO.WALK_CAP + 13)
    # it must have confirmed 1 and 2 (they could have won) and stopped once bound_lo >= best
    assert seen[:3] == [1.0, 2.0, 3.0]
    assert scanned == len([c for c in cands if c['bound_lo'] < best['bound']])


def test_nothing_confirming_is_a_measurement_not_an_error(monkeypatch):
    monkeypatch.setattr(CF, 'confirmed', lambda *a, **k: dict(n=0, entries=[], gap=float('inf')))
    cands = [dict(label='x', frames=70, bound_lo=80.0, tetra=(1.0, 0.0), link=(0.0, 0.0))]
    best, scanned = CF.best_confirmed(_PF(), cands)
    assert best is None and scanned == 1
