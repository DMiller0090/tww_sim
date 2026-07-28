"""THE TIER-2 GATE: does the sim predict node 1's CONSOLE trajectory, 0-ULP?

This is the goal-state test for the Courtyard push -- the thing future sessions work toward making pass.

Setup: `fixtures/courtyard_node1_console.json` locks node 1's 241-frame input log together with the
CONSOLE-MEASURED state at each truncate-and-read sample (session 54, delivered by
`harness/tetrapush/deliver.py`). For a FIXED input log the console result is ground truth, so the
expectation never moves and **the SIM is what must converge to it**. Never edit the fixture to make this
pass (`tests/dolphin/README.md#locked-tests-are-immutable-hard-rule`); fixing the push model is the work.

Where it stands (session 58): **bit-exact through plan frame 77**, then the next seed at n=78. The
frontier has moved 20 -> 38 (s55, the CC push's unfused `dist_sq`) -> 67 (s56, the signed s16
half-angle in `euler_to_quat`) -> 71 (s57, the attention RELEASE branch keying on `LockonTarget(0)`
rather than the front cone) -> 77 (s58, two faults in the pose stream the anim-driven frames finally
consumed: the sword-drawn WALKS/DASHS anim swap, and the end-of-frame draw base). Each of those was a
different KIND of fault; see the localization test.

Four captures feed it: the original 10-frame-stride samples, session 55's consecutive n=21..40,
session 56's n=61..70 + 80..200, and session 57's consecutive n=71..79 -- so a regression in a swept
band names its own frame instead of a 10-frame bracket. The captures overlap at n=30/40 and agree
bit-for-bit (`test_the_two_captures_agree_where_they_overlap`), which is what licenses treating any of
them as ground truth.

Diagnosis encoded by the assertions below: `proc` and `facing` match at EVERY sample (so the
procs/attention/foot direction are faithful), and the localization test states the CURRENT frontier's
signature -- which changes every time one is closed, so read it rather than assuming the last one. The
open samples are `xfail(strict=True)`, so the moment a model fix makes one exact, pytest reports XPASS
and the marker must be removed -- the frontier ratchets forward.

Offline: replays the locked log on the 0-ULP `FreeRun` (no Dolphin). The live delivery that produced the
fixture lives in `harness/tetrapush/deliver.py` (`divergence_curve` extends the curve, ~8 s per sample).
"""
import json
import math
import os
import struct

import pytest

from harness.tetrapush import seeds

def _fx(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', name)


FIX = json.load(open(_fx('courtyard_node1_console.json')))
DENSE = json.load(open(_fx('courtyard_node1_console_dense.json')))   # consecutive n=21..40
S56 = json.load(open(_fx('courtyard_node1_console_s56.json')))       # n=61..70, 80..200
S57 = json.load(open(_fx('courtyard_node1_console_s57.json')))       # consecutive n=71..79
SAMPLES = {s['n']: s for s in DENSE['samples']}
SAMPLES.update({s['n']: s for s in S56['samples']})
SAMPLES.update({s['n']: s for s in S57['samples']})
SAMPLES.update({s['n']: s for s in FIX['samples']})

# The 0-ULP frontier. Shrink it as the model is fixed -- never grow it; why each n is open is in
# `_OPEN_REASON`, and the out-of-regime subset is `OUT_OF_REGIME` below.
OPEN = {78, 79, 80, 100, 120, 160, 200}

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
                                tx=float(run.tx), tz=float(run.tz),
                                t1=tuple(L._foot.t1))   # the drawn toe pose (the speedF input stream)
    return snaps


_OPEN_REASON = (
    "known-open, and the seed is plan frame 78 -- the WALK RE-ENTRY OUT OF WAIT. Session 58 closed "
    "72..77 with two pose-stream fixes (the sword-drawn WALKS/DASHS anim swap that getAnmData makes "
    "while mEquipItem == SWORD, and the end-of-frame draw base: the model is drawn post-posMove with "
    "the proc-init lean rule, measured 0-ULP against the live mFootData toes). What is left at 78 is "
    "not rounding: Link STOPS at 76-77 (proc 4 WAIT) and the sim does not pose during those frames -- "
    "`FootSpeedF.step` early-returns at |mNormalSpeed| <= 0.001 -- so its toe stream still holds the "
    "walking poses from 74/75 and the re-walk's f31_2 is a walk-sized 2.617 where the console's is an "
    "idle-drift 0.379 (same direction, 6.9x long). The game keeps posing through procWait (its "
    "setBlendMoveAnime idle arm) and the ctrls keep advancing, which is exactly the WAIT/idle tier "
    "`foot_speedf`'s docstring lists as unmodeled ('re-entering idle after a stop'). From n=100 the "
    "console additionally leaves the modeled stt-3 plow regime (see OUT_OF_REGIME). STRICT -- when a "
    "model fix makes this exact it XPASSes and FAILS the suite; remove the n from OPEN then.")

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


def test_the_first_open_sample_is_the_walk_re_entry_out_of_wait(rollout):
    """The LOCALIZATION, pinned so the next session starts where session 58 left off rather than
    re-deriving it.

    Each frontier has had its own signature, and reading the new one off the old one is how sessions
    get lost. Through s55 it was push MAGNITUDE (equal displacement on both actors, the 50/50 split).
    At s56 it was a PROC divergence. At s57/s58 it was the POSE STREAM feeding an anim-driven speedF
    (the sword anim swap, then the draw base). Now it is a MISSING PROC BEHAVIOUR, and it is 7x, not
    a rounding: Link stops into WAIT at 76-77 and the sim stops posing there, so the toe stream it
    re-walks from at 78 is the one it stopped with.

    The evidence, all of it here: proc and facing MATCH the console at 78 and Tetra is 0-ULP (so
    neither the procs nor the CC push are implicated), the sim's step is ~6.9x the console's, and the
    sim's own stored toe pose is IDENTICAL at 75, 76 and 77 -- the stream never advanced across the
    stop. The game keeps drawing through procWait -- setBlendMoveAnime's idle arm re-poses on the
    stop frame (procWait_init, morf 2.4) and the frame controllers keep advancing after it -- so the
    console's re-walk delta is the idle drift (0.379) and the sim's is the last walking step (2.617).

    The direction is NOT implicated: the two steps are parallel to 0.7 BAM, which is inside what the
    console's own 0.379-u step can resolve (a position ULP at this magnitude is ~1.2e-4 u, i.e. ~1.7
    BAM of direction). Do not read a travel bug into that -- and do not derive one by comparing
    atan2(step) against `travel` either: cM_ssin/cM_scos are jmaSinTable lookups, so a step taken
    along `travel` returns an atan2 up to ~15 BAM away from it. Closing 78 is the WAIT/idle tier
    `foot_speedf` lists as unmodeled ('re-entering idle after a stop');
    `enter_subjectivity`/`step_subjectivity` are the same shape (the C-up freeze is a WAIT whose anim
    keeps running) and are the pieces to reuse."""
    first = min(OPEN)
    assert first == 78, "the frontier moved -- re-derive the diagnosis before trusting this test"
    s, sim = SAMPLES[first], rollout[first]
    assert s['tetra']['stt'] == 3, "n=78 is inside the plow regime, so scope is not the issue there"
    assert sim['proc'] == 6 and s['link']['proc'] == 6, "n=78 is no longer the re-walk frame"
    assert SAMPLES[76]['link']['proc'] == 4 and SAMPLES[77]['link']['proc'] == 4, \
        "the console no longer stops into WAIT before n=78 -- re-diagnose"
    assert sim['facing'] == s['link']['facing'], "n=78 grew a facing divergence -- re-diagnose"
    assert _bits(sim['tx']) == _bits(s['tetra']['x']) and _bits(sim['tz']) == _bits(s['tetra']['z']), \
        "Tetra is no longer bit-exact at n=78 -- the push IS implicated again, re-diagnose"

    # The sim takes a walking stride where the console idles forward -- same direction, 6.9x the step.
    p = SAMPLES[first - 1]['link']
    cdx, cdz = s['link']['x'] - p['x'], s['link']['z'] - p['z']
    sdx, sdz = sim['x'] - p['x'], sim['z'] - p['z']
    assert math.hypot(sdx, sdz) / math.hypot(cdx, cdz) > 5.0, \
        "the sim no longer overshoots the console's re-walk step several-fold -- re-diagnose"
    sine = abs(cdx * sdz - cdz * sdx) / (math.hypot(cdx, cdz) * math.hypot(sdx, sdz))
    assert sine < 3e-4, \
        "the steps are no longer parallel (%.1f BAM apart) -- travel is implicated now, re-diagnose" \
        % (sine * 65536.0 / (2.0 * math.pi))

    # The cause, stated in sim-side state: the toe stream is frozen from the last WALKING frame
    # (75) through both WAIT frames -- the sim draws neither the stop frame nor the holds.
    assert rollout[75]['t1'] == rollout[76]['t1'] == rollout[77]['t1'], \
        "the sim now advances its toe stream across the WAIT stop -- the tier may be modeled; re-check"


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
