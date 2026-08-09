"""`stick_for_bearing`'s memo returns what the uncached inverse returns -- everywhere it is asked.

The inverse falls into a byte-neighborhood scan of up to 529 clamped decodes when the octagon clamp
moves its analytic candidate (2.8 ms a call, measured), and `full_herd.junction_alphabet` re-asks the
same fixed bearing ladder once per node per generation. Memoising it is only safe because the
function is pure, so this gates purity the way it can actually fail: the cached result must equal a
FRESH computation over a sweep that spans both branches -- the analytic hit and the clamp search --
and at partial magnitudes as well as full.
"""
from tww_sim.land.plan_land import _primitives as P


def _uncached(*a, **kw):
    return P.stick_for_bearing.__wrapped__(*a, **kw)


def test_the_memo_is_the_function():
    """Every cell, both branches, `==` and never a tolerance (`[[zero-ulp-tests-only]]`)."""
    n = 0
    for theta in range(0, 0x10000, 1973):             # a prime-ish stride: no alignment to the octagon
        for cs in (0, 0x4321, 0xC000):
            for msd in (1.0, 0.06):
                assert P.stick_for_bearing(theta, cs, msd) == _uncached(theta, cs, msd)
                n += 1
    assert n > 150


def test_the_sweep_reaches_the_clamp_search():
    """Non-vacuity: if every cell above took the analytic path the gate would say nothing about the
    branch that costs 2.8 ms and is the reason the memo exists."""
    from tww_sim.core.mathlib import main_stick_decode
    searched = 0
    for theta in range(0, 0x10000, 1973):
        b = _uncached(theta, 0x4321, 1.0)
        ang, _m = main_stick_decode(*b)
        stick_s16 = ((theta - 0x4321) & 0xFFFF) - 0x8000
        if ang is not None and (((ang - stick_s16 + 0x8000) & 0xFFFF) - 0x8000) != 0:
            searched += 1
    assert searched > 0


def test_a_second_call_is_the_same_object():
    """It is a cache and not a re-run: the tuple is returned, not rebuilt."""
    P.stick_for_bearing.cache_clear()
    a = P.stick_for_bearing(0x2345, 0x1111, 1.0)
    b = P.stick_for_bearing(0x2345, 0x1111, 1.0)
    assert a is b
    assert P.stick_for_bearing.cache_info().hits >= 1
