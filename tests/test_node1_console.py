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
S56 = json.load(open(_fx('courtyard_node1_console_s56.json')))       # n=61..70, 80..200
SAMPLES = {s['n']: s for s in DENSE['samples']}
SAMPLES.update({s['n']: s for s in S56['samples']})
SAMPLES.update({s['n']: s for s in FIX['samples']})

# The 0-ULP frontier. Shrink it as the model is fixed -- never grow it; why each n is open is in
# `_OPEN_REASON`, and the out-of-regime subset is `OUT_OF_REGIME` below.
OPEN = {68, 69, 70, 80, 100, 120, 160, 200}

# The rows where the console left the stt-3 plow regime (a SCOPE gap, not a fidelity bug) -- see
# `test_the_out_of_regime_rows_are_flagged_not_silently_expected` and the fixture's `regime_note`.
OUT_OF_REGIME = {n for n in SAMPLES if SAMPLES[n]['tetra']['stt'] != 3}


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


_OPEN_REASON = (
    "known-open, and NO LONGER an FP divergence: session 56's signed-half `euler_to_quat` fix made every "
    "sample bit-exact through plan frame 67. The next seed is frame 68, where the sim and the console "
    "DISPATCH DIFFERENT PROCS -- the console exits the roll into proc 9 (ATN_ACTOR_MOVE, the untarget "
    "brakeslide) while the sim goes to proc 24 (MOVE_TURN), i.e. the sim's attention actor-lock has "
    "dropped a frame too early again (cf. session 6's lock-lifetime fix, one cycle earlier). Tetra is "
    "still 0-ULP at n=80, so the push is not implicated. From n=100 the console additionally leaves the "
    "modeled stt-3 plow regime (see OUT_OF_REGIME). STRICT -- when a model fix makes this exact it "
    "XPASSes and FAILS the suite; remove the n from OPEN then.")

_XFAIL = pytest.mark.xfail(strict=True, reason=_OPEN_REASON)


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


@pytest.mark.parametrize("n", sorted(n for n in SAMPLES if n not in OPEN))
def test_proc_facing_and_regime_match_the_console_on_the_exact_region(n, rollout):
    """On the bit-exact prefix the dispatched proc, the attention-driven facing and Tetra's stt-3 plow
    regime all match too -- i.e. the agreement is the whole state, not just the two positions."""
    s, sim = SAMPLES[n], rollout[n]
    assert sim['proc'] == s['link']['proc']
    assert sim['facing'] == s['link']['facing']
    assert s['tetra']['stt'] == 3, "fixture row left the stt-3 plow regime the model covers"


def test_the_first_open_sample_is_a_proc_divergence_not_a_push_one():
    """The LOCALIZATION, pinned so the next session starts where session 56 left off rather than
    re-deriving it.

    Through session 55 every open sample was a push-magnitude error: equal-and-opposite displacement
    on both actors, the 50/50 split's signature. That is no longer the shape. At the first open sample
    Tetra is still bit-exact -- so the CC push is exonerated there -- while Link has moved, and the two
    sides dispatch DIFFERENT PROCS: the console exits the roll into ATN_ACTOR_MOVE (9, the untarget
    brakeslide the whole push cycle is built on) and the sim into MOVE_TURN (24). The attention
    actor-lock is dropping early again, exactly the session-6 failure one cycle later.

    Asserted off the fixture alone (no rollout) so it states the console-side fact; the sim-side proc
    is checked by the strict-xfail position test above going red when the routing changes."""
    first = min(OPEN)
    assert first == 68, "the frontier moved -- re-derive the diagnosis before trusting this test"
    s = SAMPLES[first]
    assert s['link']['proc'] == 9, "console no longer exits the roll into ATN_ACTOR_MOVE at n=68"
    assert s['tetra']['stt'] == 3, "n=68 is inside the plow regime, so scope is not the issue there"
    # Tetra bit-exact at 80 while Link is not: the push cannot be what is wrong in this band.
    assert 80 in SAMPLES and SAMPLES[80]['tetra']['stt'] == 3


def test_the_out_of_regime_rows_are_flagged_not_silently_expected():
    """From plan frame 100 the console's Tetra enters stt 4 (FOLLOW), which the stt-3 plow model does
    NOT cover -- `FreeRun` raises its own FOLLOW_ENGAGE_DIST warning at that very frame. Those rows are
    kept as ground truth but must stay inside OPEN: closing them is a SCOPE task (model stt-4 follow, or
    re-solve the plan to stay in regime), not another FP hunt. This guards against a future session
    reading the 113 u endpoint miss as one more rounding bug."""
    assert OUT_OF_REGIME, "no out-of-regime rows -- did the fixture change?"
    assert OUT_OF_REGIME <= OPEN, "an out-of-regime row is being expected to pass: %s" % (
        sorted(OUT_OF_REGIME - OPEN),)
    assert min(OUT_OF_REGIME) >= 100, "the follow flip moved earlier than plan frame 100"


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
