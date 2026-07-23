"""The Courtyard Tetra push law, gated against the DETERMINISTIC RAM ground truth -- 0-ULP.

Tetra's per-frame displacement IS the CC push (she has no foot term -- stt-3, speedF 0, the whole
window), so this file isolates the push law from Link's own physics. The law is
`from_f0.cc_push_pair` (`cc_push.co_move_pair` = `dCcS::SetPosCorrect`): the decomp 50/50 rank split
of the Co overlap, computed from Link's EXECUTE-pass Co centre (session 27, bug-#1 fix). It replaced
the session-8/9 DERIVED full-depth-from-SETTLED law (`tetra_plow.plow_step`, now retired), which was
only ~1e-5 u equal to the console (1-9 ULP off ΔTetra).

TEST-RIGOR POLICY (`[[zero-ulp-tests-only]]`): fidelity is asserted at the 0-ULP bar
(`_bits(sim) == _bits(live)`), against DETERMINISTIC breakpoint captures only:
  * `test_console_push_bit_exact_vs_deterministic` -- the push LAW gate: `cc_push_pair` on the
    setCollision EXEC centre (`courtyard_push_setcol.json`, f1..12) reproduces the per-op ΔTetra
    (`courtyard_push_perop.json`) BIT-FOR-BIT. Two deterministic captures, no model, no
    single-stepped data. The f13+ frames (needing the model's computed exec centre) are gated by
    `test_from_f0.py::test_tetra_push_bit_exact_from_exact_state`; f1's push comes from f0's exec
    centre, a static-initial-condition boundary the seed frame does not carry.

The one non-fidelity check is the REGIME discriminator `test_tetra_absorbs_full_overlap` (frac ==
1.0, not 0.5): it distinguishes the full ejection (measured against the SETTLED centre) from a 50/50
split -- a qualitative finding, so a loose bound is correct and it is explicitly NOT a 0-ULP gate.
See harness/tetrapush/README.md "The CC split (Courtyard push)".
"""
import json
import math
import os
import struct

import pytest

from harness.tetrapush.tetra_plow import plow_depth
from harness.tetrapush.from_f0 import cc_push_pair
from tww_sim.core.fp import f32


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIX = os.path.join(_ROOT, 'fixtures', 'courtyard_push_cyl.json')
_PEROP = os.path.join(_ROOT, 'fixtures', 'courtyard_push_perop.json')
_SETCOL = os.path.join(_ROOT, 'fixtures', 'courtyard_push_setcol.json')


def _dedup(frames):
    """Drop single-step DOUBLE-READ frames (the capture re-sampling one game frame -- e.g. cyc2
    f44==f45, [[run-dtm-1frame-jitter]]): a frame bit-identical to its predecessor in BOTH Link's Co
    centre and Tetra's pos is the same game frame read twice, not a real (0-displacement) frame."""
    out = [frames[0]]
    for f in frames[1:]:
        p = out[-1]
        if f['link']['cyl'] == p['link']['cyl'] and f['tetra']['pos'] == p['tetra']['pos']:
            continue
        out.append(f)
    return out


@pytest.fixture(scope='module')
def cyl():
    if not os.path.exists(_FIX):
        pytest.skip("courtyard_push_cyl.json not captured (needs a live slot-2 capture)")
    d = json.load(open(_FIX))
    d['frames'] = _dedup(d['frames'])
    return d


def _push_frames(frames):
    """Frames where Link's Co cylinder overlaps Tetra (depth > 0) AND she is being plowed (stt 3,
    speedF 0 -- no self-locomotion), so her move is pure plow. That is the whole state-2 push."""
    out = []
    for i in range(len(frames) - 1):
        f = frames[i]
        if f['tetra']['stt'] != 3 or abs(f['tetra']['speedF']) > 1e-6:
            continue
        if plow_depth(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2])) > 0.1:
            out.append(i)
    return out


def test_tetra_absorbs_full_overlap(cyl):
    """REGIME DISCRIMINATOR (not a fidelity gate, `[[zero-ulp-tests-only]]` category (a)):
    frac = tetra_move / depth == 1.0 on every push frame, i.e. Tetra takes the FULL Co overlap depth
    (Link's push share is 0), the opposite of the 50/50 following-Tetra split. This is a QUALITATIVE
    finding -- a 50/50 split would read ~0.5 -- so the loose bound distinguishing 1.0 from 0.5 is
    correct and intended (the full ejection is the SETTLED-centre framing of the console's half-depth-
    from-EXEC split). The push LAW's 0-ULP fidelity is `test_console_push_bit_exact_vs_deterministic`
    below."""
    frames = cyl['frames']
    push = _push_frames(frames)
    assert len(push) >= 30, "expected the full ~40-frame push, got %d plow frames" % len(push)
    for i in push:
        f, n = frames[i], frames[i + 1]
        depth = plow_depth(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2]))
        move = math.hypot(n['tetra']['pos'][0] - f['tetra']['pos'][0],
                          n['tetra']['pos'][2] - f['tetra']['pos'][2])
        frac = move / depth
        assert abs(frac - 1.0) < 0.01, "frame %d: Tetra frac %.4f != 1.0 (depth %.3f move %.3f)" % (
            i, frac, depth, move)


@pytest.fixture(scope='module')
def perop():
    if not os.path.exists(_PEROP):
        pytest.skip("per-op posMove-breakpoint capture not present")
    return {r['idx']: r['entry'] for r in json.load(open(_PEROP))['rows'] if r.get('entry')}


@pytest.fixture(scope='module')
def setcol():
    if not os.path.exists(_SETCOL):
        pytest.skip("setCollision breakpoint fixture not present (session-14 probe)")
    return {s['f']: s for s in json.load(open(_SETCOL))['frames']}


def test_console_push_bit_exact_vs_deterministic(perop, setcol):
    """THE push-LAW 0-ULP gate (session 27; flipped from the session-24 `plow_step` xfail). The
    console CC push -- `cc_push_pair` (`cc_push.co_move_pair` = `dCcS::SetPosCorrect`) on the
    DETERMINISTIC setCollision EXEC centre -- reproduces the DETERMINISTIC per-op ΔTetra
    BIT-FOR-BIT (0 ULP) on every frame an exec centre is captured (f1->f2 .. f12->f13). Tetra has no
    foot term, so her per-frame move IS the push, isolating the law with no foot confound.

    Two deterministic breakpoint captures only (`[[zero-ulp-tests-only]]`): the exec centre from
    `courtyard_push_setcol.json` (JP setCollision 0x8011a670, f1..12) and both actors' `current.pos`
    from `courtyard_push_perop.json` (JP posMove 0x80106514, f0..43). No model, no single-stepped
    data. This is the standalone twin of `test_from_f0.py::test_tetra_push_bit_exact_from_exact_state`
    (which drives the MODEL's computed exec centre to cover f13..f43). f1's push comes from f0's exec
    centre -- a static-initial-condition boundary the seed frame does not carry (README `## Plan /
    status`), so it is not covered by either gate.

    This overturns the session-24 framing: the push law is NOT a few ULP off; it is EXACT. The
    session-24 residual was `full_depth_push` on the SETTLED centre (the retired derived law), only
    ~1e-5 u equal to this half-depth-from-EXEC split."""
    diverged = []
    for k in sorted(setcol):
        if (k + 1) not in perop:
            continue
        ex = setcol[k]['cyl_exec']
        tk = perop[k]['tetra']['pos']
        tk1 = perop[k + 1]['tetra']['pos']
        (_link), (tdx, tdz) = cc_push_pair((ex[0], ex[2]), (tk[0], tk[2]))
        sim_tx = f32(f32(tk[0]) + tdx)
        sim_tz = f32(f32(tk[2]) + tdz)
        exu = abs(_bits(sim_tx) - _bits(tk1[0]))
        ezu = abs(_bits(sim_tz) - _bits(tk1[2]))
        if exu or ezu:
            diverged.append((k, exu, ezu))
    assert len(setcol) >= 10, "expected the f1..12 setCollision exec centres"
    assert not diverged, "console push != deterministic ΔTetra (0 ULP required); " \
        "frames [exec_k,xULP,zULP]: " + ", ".join("[f%d x%d z%d]" % d for d in diverged)
