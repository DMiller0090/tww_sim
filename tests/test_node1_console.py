"""THE TIER-2 GATE: does the sim predict node 1's CONSOLE trajectory, 0-ULP?

This is the goal-state test for the Courtyard push -- the thing future sessions work toward making pass.

Setup: `fixtures/courtyard_node1_console.json` locks node 1's 241-frame input log together with the
CONSOLE-MEASURED state at each truncate-and-read sample (session 54, delivered by
`harness/tetrapush/deliver.py`). For a FIXED input log the console result is ground truth, so the
expectation never moves and **the SIM is what must converge to it**. Never edit the fixture to make this
pass (`tests/dolphin/README.md#locked-tests-are-immutable-hard-rule`); fixing the push model is the work.

Where it stands (session 54): the sim is bit-exact through plan frame 20 and then diverges --
2-3 ULP by n=30, ~150 by n=40, ~2e5 by n=60 -- until the 4th roll passes to Tetra's LEFT and misses her,
leaving her 113 u from the target coord instead of 0.011. Diagnosis encoded by the assertions below:
`proc` and `facing` match at EVERY sample (so the procs/attention/foot direction are faithful) and the
Link and Tetra position errors are EQUAL, which is the CC push split's signature -- the fault is push
MAGNITUDE, not Link's foot term. The open samples are `xfail(strict=True)`, so the moment a model fix
makes one exact, pytest reports XPASS and the marker must be removed -- the frontier ratchets forward.

Offline: replays the locked log on the 0-ULP `FreeRun` (no Dolphin). The live delivery that produced the
fixture lives in `harness/tetrapush/deliver.py` (`divergence_curve` extends the curve, ~8 s per sample).
"""
import json
import os
import struct

import pytest

from harness.tetrapush import seeds

_FIX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'fixtures', 'courtyard_node1_console.json')
FIX = json.load(open(_FIX_PATH))
SAMPLES = {s['n']: s for s in FIX['samples']}

# The 0-ULP frontier as of session 54. n=20 PASSES (a real gate protecting the exact region); the rest
# are the known-open push divergence. Shrink this set as the model is fixed -- never grow it.
OPEN = {30, 40, 45, 50, 55, 60}


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _ulp(a, b):
    return abs(_bits(a) - _bits(b))


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
    "known-open CC-push divergence (session 54): the push magnitude is slightly too strong, seeding by "
    "plan frame ~30 and amplifying ~1.4x/contact-frame. STRICT -- when a model fix makes this exact it "
    "XPASSes and FAILS the suite; remove the n from OPEN then."))


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


_SYMMETRY_FLOOR = 0.05      # below this the f32 position storage perturbs the equality (n=30: 2.6e-4)


@pytest.mark.parametrize("n", sorted(n for n in SAMPLES if n in OPEN))
def test_the_open_error_is_equal_on_both_actors_the_push_split_signature(n, rollout):
    """The CC push is a 50/50 split, so a push-magnitude error displaces Link and Tetra by EQUAL amounts
    in opposite directions. Measured in world units that equality is EXACT once the error clears the f32
    storage noise (n=45/50/55/60: identical to the last bit; n=30/40 agree to 6%/0.5% at 2.6e-4/1.1e-2 u).
    Compared as distances, NOT in ULP -- ULP spacing depends on magnitude, and Link's z and Tetra's z sit
    at different exponents, so equal displacement gives unequal ULP counts.

    This is what exonerates Link's foot term (his speedF matches too) and points the fix at the push
    depth / animated exec Co-centre. Pinned so a 'fix' that breaks the symmetry -- i.e. one that moves the
    foot term instead of the push -- is caught rather than mistaken for progress."""
    s, sim = SAMPLES[n], rollout[n]
    import math
    dl = math.hypot(sim['x'] - s['link']['x'], sim['z'] - s['link']['z'])
    dt = math.hypot(sim['tx'] - s['tetra']['x'], sim['tz'] - s['tetra']['z'])
    if max(dl, dt) < _SYMMETRY_FLOOR:
        assert abs(dl - dt) <= 0.10 * max(dl, dt), "push symmetry lost near the f32 noise floor"
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
