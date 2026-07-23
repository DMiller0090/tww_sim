"""The Courtyard Tetra-plow law, live-gated against the RAM ground truth.

`harness/tetrapush/tetra_plow` encodes the measured push law -- Tetra's per-frame displacement is the
FULL Co-cylinder overlap depth computed from Link's animated mCyl centre (Tetra takes 100 %, Link's
share 0). This gate feeds the law the RAM-captured Link Co centres (fixtures/courtyard_push_cyl.json,
single-stepped from slot 2).

TEST-RIGOR POLICY (`[[zero-ulp-tests-only]]`): the plow LAW's fidelity is asserted at the 0-ULP bar
(`_bits(sim) == _bits(live)`), never a `err < eps` tolerance. Because the only fixture here is the
SINGLE-STEPPED cyl capture (which by policy may not set the position bar), the per-frame law gate is
`xfail(strict)` -- 0-ULP is the target, blocked on the two open push bugs + a deterministic per-op
`m_cc_move` capture (README `## Plan / status`). Its clean twin against the buggy replay wrapper is
`test_from_f0.py::test_tetra_push_bit_exact_from_exact_state`.

The one non-fidelity check that survives is the REGIME discriminator `test_tetra_absorbs_full_overlap`
(frac == 1.0, not 0.5): it distinguishes the full-depth ejection from a 50/50 split -- a qualitative
finding, so a loose bound is correct and it is explicitly NOT a 0-ULP gate.

This isolates the Tetra side of the coupled dynamics (the plow) from Link's own physics, and is the
predictor the planner uses once Link's mCyl-centre path is modelled offline. See harness/tetrapush/README.md.
"""
import json
import math
import os
import struct

import pytest

from harness.tetrapush.tetra_plow import plow_depth, plow_step


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]

_FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'fixtures', 'courtyard_push_cyl.json')


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
    correct and intended. The plow LAW's 0-ULP fidelity is `test_plow_step_bit_exact_vs_live` below."""
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


@pytest.mark.xfail(strict=True, reason="OPEN 0-ULP gap (session 24), BUG #1: the standalone plow law. "
                   "One plow_step from each frame's live Tetra pos + Link centre must reproduce the "
                   "NEXT frame's live Tetra pos BIT-FOR-BIT (0 ULP). It diverges by a few ULP -- the "
                   "push/recoil law bug (two separate fsqrt; the push-vector fp order). The clean f32 "
                   "formulation lives here (vs the buggy f64-delta wrapper the replay uses -- see "
                   "test_from_f0::test_tetra_push_bit_exact_from_exact_state). ALSO: the cyl fixture is "
                   "SINGLE-STEPPED (may not set the position bar); true validation needs the "
                   "deterministic per-op m_cc_move capture (README ## Plan / status).")
def test_plow_step_bit_exact_vs_live(cyl):
    """THE plow-LAW 0-ULP gate: one plow step from each frame's live Tetra pos + Link centre must
    reproduce the NEXT frame's live Tetra pos bit-for-bit (isolates the law from drift accumulation).
    Currently XFAILS (bug #1). Collects the whole divergent set into the message."""
    frames = cyl['frames']
    diverged = []
    for i in _push_frames(frames):
        f, n = frames[i], frames[i + 1]
        tx, tz = plow_step(f['link']['cyl'], (f['tetra']['pos'][0], f['tetra']['pos'][2]))
        ex = abs(_bits(tx) - _bits(n['tetra']['pos'][0]))
        ez = abs(_bits(tz) - _bits(n['tetra']['pos'][2]))
        if ex or ez:
            diverged.append((i, ex, ez))
    assert not diverged, "plow_step != live (0 ULP required); frames [f,xULP,zULP]: " \
        + ", ".join("[f%d x%d z%d]" % d for d in diverged)
