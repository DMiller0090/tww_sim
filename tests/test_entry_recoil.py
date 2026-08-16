"""THE ENTRY-FRAME CC RECOIL LAW (s168) -- the fan's entry prediction in the in-contact regime.

The s167rung06 overnight scored 9.4M candidates with `roll_entry` alone and produced 4 fictional
genuine plus an untrustworthy zero: on the roll-dispatch frame the engine resolves the Link<->Tetra
Co pair off Link's WALK-END exec Co centre (the 1-frame pose lag) at the walk-end positions, and
the halves land on the post-roll-step Link and on Tetra. `overnight.entry_recoil` /
`entry_corrected` / `tetra_corrected` model that; the fixture rows are ENGINE-MEASURED (the wired
native replay's first FRONT_ROLL frame) off the converted rung06-w05 herd, so these are 0-ULP
gates against ground truth, pure arithmetic, no engine in the loop.
"""
import json
import os
import struct

from harness.tetrapush import overnight as ON

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIX = os.path.join(_HERE, '..', 'fixtures', 'courtyard_entry_recoil_s168.json')

_bits = lambda x: struct.unpack('<Q', struct.pack('<d', float(x)))[0]


def _rows():
    return json.load(open(_FIX))['rows']


def test_entry_recoil_reproduces_the_engine_bit_exact():
    """entry_corrected == the engine's measured entry, all 5 ground truths, 0-ULP."""
    for r in _rows():
        k = tuple(r['key'])
        rec = ON.entry_recoil(k)
        assert rec is not None, '%s: expected entry-frame contact' % r['name']
        e = ON.entry_corrected((k[0], k[1]), r['facing'], rec)
        want = r['entry_measured']
        assert (_bits(e[0]), _bits(e[1])) == (_bits(want[0]), _bits(want[1])), \
            '%s: entry %r != measured %r' % (r['name'], e, want)


def test_tetra_push_half_reproduces_the_engine_bit_exact():
    """tetra_corrected == the engine's measured post-entry Tetra, all 5 ground truths, 0-ULP."""
    for r in _rows():
        k = tuple(r['key'])
        rec = ON.entry_recoil(k)
        t = ON.tetra_corrected(k, rec)
        want = r['tetra_measured']
        assert (_bits(t[0]), _bits(t[1])) == (_bits(want[0]), _bits(want[1])), \
            '%s: tetra %r != measured %r' % (r['name'], t, want)


def test_recoil_is_aim_independent():
    """The pair is a function of the key alone: entry_corrected at two other facings shifts by
    exactly the SAME recoil vector (the s168 validation's cross-cell result, in arithmetic form)."""
    from tww_sim.core.fp import fadds
    from harness.tetrapush import entry_search as ES
    r = _rows()[0]
    k = tuple(r['key'])
    rec = ON.entry_recoil(k)
    for fac in (r['facing'] + 16, r['facing'] - 32):
        e0 = ES.roll_entry((k[0], k[1]), fac & 0xFFFF, ES.ROLL_NSPEED)
        e = ON.entry_corrected((k[0], k[1]), fac & 0xFFFF, rec)
        assert (_bits(e[0]), _bits(e[1])) == \
            (_bits(fadds(e0[0], rec[0][0])), _bits(fadds(e0[1], rec[0][1])))


def test_out_of_contact_is_a_byte_identical_noop():
    """A key whose centre sits past CO_R_SUM from Tetra: rec is None and both corrections return
    the pre-s168 values EXACTLY -- the console regime (broken contact at entry) is untouched."""
    from harness.tetrapush import entry_search as ES
    r = _rows()[0]
    k = list(r['key'])
    k[6] += 500.0                                  # move Tetra far out of the Co disc
    k = tuple(k)
    assert ON.entry_recoil(k) is None
    e = ON.entry_corrected((k[0], k[1]), r['facing'], None)
    e0 = ES.roll_entry((k[0], k[1]), r['facing'], ES.ROLL_NSPEED)
    assert (_bits(e[0]), _bits(e[1])) == (_bits(e0[0]), _bits(e0[1]))
    assert ON.tetra_corrected(k, None) == (k[-2], k[-1])
