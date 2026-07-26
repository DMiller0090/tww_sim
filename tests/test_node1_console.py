"""THE TIER-2 GATE: does the sim predict node 1's CONSOLE trajectory, 0-ULP?

This is the goal-state test for the Courtyard push -- the thing future sessions work toward making pass.

Setup: `fixtures/courtyard_node1_console.json` locks node 1's 241-frame input log together with the
CONSOLE-MEASURED state at each truncate-and-read sample (session 54, delivered by
`harness/tetrapush/deliver.py`). For a FIXED input log the console result is ground truth, so the
expectation never moves and **the SIM is what must converge to it**. Never edit the fixture to make this
pass (`tests/dolphin/README.md#locked-tests-are-immutable-hard-rule`); fixing the push model is the work.

Where it stands (session 55): **bit-exact through plan frame 38**, then the next seed at frame 39.
Session 54 opened this gate exact only through n=20; the divergence was root-caused to the CC push's
FP shape -- `dist_sq` must be UNFUSED, and the sqrt is the game's `std::sqrtf` (see the FP note in
`tww_sim/core/cc_push.py` and `knowledge/mechanics/actor-push.md`) -- which closed everything to 38.

Two fixtures feed it: the original 10-frame-stride samples plus session 55's CONSECUTIVE sweep
(n=21..40), so a regression anywhere in 21..38 names its own frame instead of a 10-frame bracket. The
two captures overlap at n=30/40 and agree bit-for-bit (`test_the_two_captures_agree_where_they_overlap`),
which is what licenses treating either as ground truth.

Diagnosis encoded by the assertions below: `proc` and `facing` match at EVERY sample (so the
procs/attention/foot direction are faithful) and the Link and Tetra position errors are EQUAL, the CC
push split's signature -- the fault is push MAGNITUDE, not Link's foot term. The open samples are
`xfail(strict=True)`, so the moment a model fix makes one exact, pytest reports XPASS and the marker
must be removed -- the frontier ratchets forward.

Offline: replays the locked log on the 0-ULP `FreeRun` (no Dolphin). The live delivery that produced the
fixture lives in `harness/tetrapush/deliver.py` (`divergence_curve` extends the curve, ~8 s per sample).
"""
import json
import os
import struct

import pytest

from harness.tetrapush import seeds

def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


FIX = json.load(open(_fx('courtyard_node1_console.json')))
DENSE = json.load(open(_fx('courtyard_node1_console_dense.json')))   # consecutive n=21..40
SAMPLES = {s['n']: s for s in DENSE['samples']}
SAMPLES.update({s['n']: s for s in FIX['samples']})

# The 0-ULP frontier (see the module docstring). Shrink it as the model is fixed -- never grow it.
OPEN = {39, 40, 45, 50, 55, 60}


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _ulp(a, b):
    return abs(_bits(a) - _bits(b))


def _ulp_size(x):
    """The width of one f32 ULP at ``x`` -- the granularity a stored position can carry."""
    b = _bits(x)
    return abs(struct.unpack('<f', struct.pack('<I', b + 1))[0] - float(x))


@pytest.fixture(scope="module")
def rollout():
    """Replay the locked log once and snapshot every sampled frame.

    One rollout serves all samples: the sim is deterministic and a truncated delivery keeps frames
    0..n-1 byte-identical (gated by `test_tetrapush_deliver.py::
    test_truncating_the_plan_leaves_alignment_untouched`), so the state after `step(log[n-1])` is what
    the n-frame movie halts on."""
    run = seeds.make_freerun(seeds.load_env())
    run.pre_seed_input(seeds.dtm_input_at(seeds.load_env())(0))
    want = max(SAMPLES)
    snaps = {}
    for i, d in enumerate(FIX['log'][:want]):
        run.step(d)
        if (i + 1) in SAMPLES:
            L = run.link
            snaps[i + 1] = dict(x=float(L.pos_x), z=float(L.pos_z), facing=int(L.facing) & 0xFFFF,
                                proc=int(L.state), speedF=float(L.speedF),
                                tx=float(run.tx), tz=float(run.tz))
    return snaps


_XFAIL = pytest.mark.xfail(strict=True, reason=(
    "known-open CC-push divergence: after session 55's un-fusing fix the sim is bit-exact through plan "
    "frame 38 and the next seed is frame 39 (1 ULP on Link's z, equal-and-opposite on Tetra -- still the "
    "push split's signature), amplifying ~1.4x/contact-frame from there. STRICT -- when a model fix "
    "makes this exact it XPASSes and FAILS the suite; remove the n from OPEN then."))


def _case(n):
    """strict-xfail the known-open samples, so progress cannot pass unnoticed (an imperative
    `pytest.xfail()` can never XPASS, which would silently swallow a fix)."""
    return pytest.param(n, marks=[_XFAIL]) if n in OPEN else n


@pytest.mark.parametrize("n", [_case(n) for n in sorted(SAMPLES)])
def test_sim_predicts_the_console_position_bit_exact(n, rollout):
    """0-ULP on BOTH actors' positions at the console-measured frame (no tolerance -- see
    `[[zero-ulp-tests-only]]`; the fixture rows are deterministic PauseMovie halts, not single-steps)."""
    s, sim = SAMPLES[n], rollout[n]
    assert _bits(sim['x']) == _bits(s['link']['x']), "Link x off %d ULP" % _ulp(sim['x'], s['link']['x'])
    assert _bits(sim['z']) == _bits(s['link']['z']), "Link z off %d ULP" % _ulp(sim['z'], s['link']['z'])
    assert _bits(sim['tx']) == _bits(s['tetra']['x']), "Tetra x off %d ULP" % _ulp(sim['tx'], s['tetra']['x'])
    assert _bits(sim['tz']) == _bits(s['tetra']['z']), "Tetra z off %d ULP" % _ulp(sim['tz'], s['tetra']['z'])


@pytest.mark.parametrize("n", sorted(SAMPLES))
def test_proc_facing_and_regime_match_the_console_everywhere(n, rollout):
    """These are faithful at EVERY sample, including where position is ~2e5 ULP out, so they are a live
    gate now -- and they localize the bug: the dispatched proc, the attention-driven facing and Tetra's
    stt-3 plow regime are all right, so the divergence is confined to the position/push term."""
    s, sim = SAMPLES[n], rollout[n]
    assert sim['proc'] == s['link']['proc']
    assert sim['facing'] == s['link']['facing']
    assert s['tetra']['stt'] == 3, "fixture row left the stt-3 plow regime the model covers"


_SYMMETRY_FLOOR = 0.05      # below this the f32 position storage perturbs the equality


@pytest.mark.parametrize("n", sorted(n for n in SAMPLES if n in OPEN))
def test_the_open_error_is_equal_on_both_actors_the_push_split_signature(n, rollout):
    """The CC push is a 50/50 split, so a push-magnitude error displaces Link and Tetra by EQUAL amounts
    in opposite directions. Measured in world units that equality is EXACT once the error clears the f32
    storage noise (n=50/55/60: identical to the last bit). Compared as distances, NOT in ULP -- ULP
    spacing depends on magnitude, and Link's z and Tetra's z sit at different exponents, so equal
    displacement gives unequal ULP counts.

    This is what exonerates Link's foot term (his speedF matches too) and keeps the remaining open
    samples pointed at the push. Pinned so a 'fix' that breaks the symmetry -- i.e. one that moves the
    foot term instead of the push -- is caught rather than mistaken for progress.

    Near the floor the comparison is bounded by STORAGE, not by the model: each actor's x/z is an f32
    field, so a residual of a few ULP can differ between the two purely from where each coordinate
    falls in its own bin. There the test asserts only that the two agree to that storage quantum,
    derived from the sample's own magnitudes rather than a tuned tolerance."""
    s, sim = SAMPLES[n], rollout[n]
    import math
    dl = math.hypot(sim['x'] - s['link']['x'], sim['z'] - s['link']['z'])
    dt = math.hypot(sim['tx'] - s['tetra']['x'], sim['tz'] - s['tetra']['z'])
    if max(dl, dt) < _SYMMETRY_FLOOR:
        # one f32 ULP at each actor's own coordinate magnitude, added in quadrature per actor
        def _quantum(x, z):
            return math.hypot(_ulp_size(x), _ulp_size(z))
        q = _quantum(s['link']['x'], s['link']['z']) + _quantum(s['tetra']['x'], s['tetra']['z'])
        assert abs(dl - dt) <= q, ("push symmetry lost beyond the f32 storage quantum: Link %.9f, "
                                   "Tetra %.9f, quantum %.9f" % (dl, dt, q))
    else:
        assert dl == dt, "push split is not symmetric: Link moved %.12f, Tetra %.12f" % (dl, dt)


def test_the_frontier_is_contiguous_and_the_exact_region_is_not_silently_shrinking():
    """Guard the ratchet: the exact region must be a PREFIX of the samples. If a model change makes an
    early sample regress, OPEN stops being a suffix and this fails -- so progress cannot be faked by
    swapping which samples are excused."""
    ns = sorted(SAMPLES)
    exact = [n for n in ns if n not in OPEN]
    assert exact, "no sample is bit-exact any more -- the push model regressed"
    assert exact == ns[:len(exact)], "OPEN must be a suffix; the exact region is a prefix of the samples"


def test_the_two_captures_agree_where_they_overlap():
    """n=30 and n=40 were measured independently in session 54 and session 55 (separate Dolphin
    launches, separately authored movies). They must agree BIT-FOR-BIT: that is what licenses
    treating either capture as ground truth, and it is the check that would catch a delivery whose
    alignment silently shifted between sessions."""
    dense = {s['n']: s for s in DENSE['samples']}
    for s in FIX['samples']:
        if s['n'] in dense:
            d = dense[s['n']]
            for who in ('link', 'tetra'):
                for ax in ('x', 'z'):
                    assert _bits(s[who][ax]) == _bits(d[who][ax]), \
                        "session 54 and 55 disagree at n=%d on %s.%s" % (s['n'], who, ax)


def test_the_plan_and_its_console_endpoint_are_locked():
    """The fixture carries the plan itself (241 frames) plus the reproduced full-delivery endpoint, so
    neither depends on gitignored scratch. Also records WHY this gate exists: the endpoint is 113 u from
    the target coord, i.e. the plan as computed does not work on console."""
    assert len(FIX['log']) == FIX['plan_frames'] == 241
    assert FIX['coord_idx'] == 287
    e = FIX['endpoint']
    assert e['tetra']['stt'] == 3 and e['link']['proc'] == 4
    miss = ((e['tetra']['x'] - FIX['coord'][0]) ** 2 + (e['tetra']['z'] - FIX['coord'][1]) ** 2) ** 0.5
    assert miss > 100.0, "console endpoint no longer misses -- if a delivery now lands, re-mint deliberately"
