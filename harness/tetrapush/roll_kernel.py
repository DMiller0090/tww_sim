# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""**The herd roll as a FAN, evaluated on the native engine** (session 127).

84% of a search stage is roll rollouts and the search fires them one at a time through the wired
Python `FreeRun`. This module is the fast path, and its unit is deliberately the FAN rather than the
roll: everything a roll needs from the camera is a property of the NODE, not of the aim, so a fan of
143 aims pays for one camera and 143 physics rollouts, not 143 of each. Measured on a real junction
endpoint's own 143-aim fan: **1.05 s -> 0.29 s (3.6x)**, 3.2x including the per-node setup.

WHAT THE PORT RESTS ON, all measured in session 127 and all gated in `tests/test_roll_kernel.py`
rather than trusted:

  * **The native engine IS the wired one** when csangle and the proc-9 re-aim eye are injected --
    0-ULP over whole banked node logs. `seeds.make_freerun_self_eye` supplies the eye from inside the
    C engine (`LandCore.head_top_exec`/`head_mtx_exec`), so only the camera is left outside it.
  * **The csangle sequence through a roll segment is aim-independent** -- bit-identical across a full
    143-aim fan, on every node and every C-stick mode tried. So the fan evolves the camera ONCE.
  * **Her eyePos is NOT** (143 distinct sequences), and neither is Link's head-top Y that feeds it
    (41 classes). The eye is required: falling back to her feet moves the proc-9 re-aim 180 BAM and
    a node log by 123 u. So the eye chain runs per aim -- it is the part that cannot be shared.
  * **A cycle TERMINAL cannot roll at all** -- `a_press_is_talk` is a property of (node, first
    delivered input) rather than of the aim, so with Link ending a cycle facing her at contact range
    the whole circle refuses (143 of 143). The fan handles that without tracing a camera.

THE THREE THINGS A PORT MUST NOT DROP (the s126 handoff's warning, all reproduced here):
  * the **exit csangle** -- the C-stick is live through the roll and the next junction's whole aim
    alphabet is placed against the exit value, so a kernel can look 0-ULP on one roll and corrupt
    every chain of two;
  * **`talk_unsafe`** -- an A-press that talks to her kills the run, and at a cycle TERMINAL the whole
    circle is unsafe (measured 143/143), so this is a real branch and not an edge case;
  * **`ok` / `roll_speedF`** -- arming predicates the fan prunes on, not diagnostics.

`reference_fan` is the slow path stated exactly once, so the gate compares two implementations of one
contract instead of a kernel against a hand-copied expectation.
"""
from harness.tetrapush import search as S
from harness.tetrapush import two_roll as T
from harness.tetrapush.reposition import ESS_DOWN


def segment_record(seg, run):
    """One roll segment's full contract: what `roll_segment` returns PLUS the endpoint state the
    search reads off the run afterwards. Positions are raw floats -- the comparison is `==`, never a
    tolerance (`[[zero-ulp-tests-only]]`).

    ``followed`` is in here for the same reason `talk_unsafe` is: `two_roll.metrics` reads
    ``run._follow_warned`` and `two_roll.alive` PRUNES on it, so a kernel that reproduced the
    endpoint but not the flag would quietly change which rolls survive the stage."""
    return dict(ok=bool(seg['ok']), talk_unsafe=bool(seg['talk_unsafe']),
                roll_speedF=seg['roll_speedF'], roll_facing=seg['roll_facing'],
                frames=int(seg['frames']), exit_cs=int(seg['exit_cs']),
                link=(run.link.pos_x, run.link.pos_z, int(run.link.facing),
                      int(run.link.travel), run.link.speedF, int(run.link.state)),
                tetra=(run.tx, run.tz), followed=bool(run._follow_warned))


def reference_fan(run, aims, *, l_window=(5, 8), target_cs=None, hold=1, a_hold=2, post=ESS_DOWN):
    """**The contract, stated slowly**: `two_roll.roll_segment` on a fresh clone per aim.

    This is what the search does today and what the kernel must reproduce bit-for-bit. Returns one
    `segment_record` per aim, in the order given."""
    out = []
    for aim in aims:
        rr = run.clone()
        seg = T.roll_segment(rr, tuple(aim), target_cs=target_cs, l_window=l_window,
                             hold=hold, a_hold=a_hold, post=post)
        out.append(segment_record(seg, rr))
    return out


def talk_screen(run, aims, *, l_window=(5, 8), hold=1, a_hold=2, post=ESS_DOWN, target_cs=None):
    """Which aims of a fan would TALK -- the refusal, before any physics.

    `roll_segment` tests this on the A-delivery frame and returns without stepping, so it is a pure
    predicate on (node, first delivered input) and costs nothing. Separated out because the kernel
    must reproduce the refusal exactly and because a caller that only wants the live aims should not
    pay a rollout to find them."""
    sub = T.slew_substick(run.csangle, target_cs)
    out = []
    for aim in aims:
        stream = T.roll_stream(tuple(aim), hold=hold, a_hold=a_hold, l_window=l_window, post=post)
        out.append(bool(S.a_press_is_talk(run, dict(stream(0), substickX=sub, substickY=0))))
    return out


def refused_record(run):
    """The record `roll_segment` returns for a talk-unsafe aim: no step, so the endpoint is the
    node's own state and ``frames`` is 0."""
    return dict(ok=False, talk_unsafe=True, roll_speedF=None, roll_facing=None, frames=0,
                exit_cs=int(run.csangle),
                link=(run.link.pos_x, run.link.pos_z, int(run.link.facing),
                      int(run.link.travel), run.link.speedF, int(run.link.state)),
                tetra=(run.tx, run.tz), followed=bool(run._follow_warned))


def camera_trace(run, aim, *, l_window=(5, 8), target_cs=None, hold=1, a_hold=2, post=ESS_DOWN,
                 frames=None):
    """**The per-node camera**: the csangle this node's roll segment commits, frame by frame.

    Measured aim-independent over a full fan (see the module doc), which is the whole economy of the
    fan API -- and the reason the gate checks the invariance itself and not only the endpoints.
    Traced past any single segment's exit (``frames``, default `two_roll.MAX_ROLL_FRAMES` + 2) so one
    trace serves the short and long aims alike."""
    n = (T.MAX_ROLL_FRAMES + 2) if frames is None else int(frames)
    stream = T.roll_stream(tuple(aim), hold=hold, a_hold=a_hold, l_window=l_window, post=post)
    rr = run.clone()
    cs, subs = [], []
    for k in range(n):
        sub = T.slew_substick(rr.csangle, target_cs)
        subs.append(sub)
        rr.step(dict(stream(k), substickX=sub, substickY=0))
        cs.append(int(rr.csangle))
    return dict(csangle=cs, substick=subs)


def wired_csangle_trace(env, log):
    """The per-frame csangle a wired `FreeRun` commits while replaying ``log`` -- what a self-eye
    twin has to be handed to reach the same state, since it carries no camera.

    One wired replay per NODE (not per aim), and the search already pays an equivalent one to have
    the node at all; `full_herd` can record this as it steps instead of replaying."""
    from harness.tetrapush import seeds as SD
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    out = []
    for d in log:
        run.step(d)
        out.append(int(run.csangle))
    return out


def self_eye_twin(env, log, cs_trace):
    """A `make_freerun_self_eye` run at the state ``log`` reaches -- the fan's seed.

    The camera is injected a frame late by construction: step ``i`` reads the csangle committed at
    the end of step ``i-1`` (`from_f0.FreeRun.step`'s own convention), which is why `wired_csangle_trace`
    records post-step values and this offsets them. Getting that off by one is silent -- the run still
    looks plausible -- so `tests/test_roll_kernel.py` checks the twin against the wired node 0-ULP
    before any fan runs off it."""
    from harness.tetrapush import seeds as SD
    run = SD.make_freerun_self_eye(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    for i, d in enumerate(log):
        run.step(d, csangle=(cs_trace[i - 1] if i else None))
    return run


def roll_fan(run, aims, *, l_window=(5, 8), target_cs=None, hold=1, a_hold=2, post=ESS_DOWN,
             fast=None, entry_cs=None):
    """**The fast path**: `reference_fan`'s records, on the native engine, one camera per fan.

    ``run``   -- the wired node. Used for the talk screen and for the camera trace, never stepped.
    ``fast``  -- a `seeds.make_freerun_self_eye` run at the SAME state (`self_eye_twin`). Required:
                 falling back to the slow path silently would make a "kernel" that is sometimes the
                 reference and sometimes not, and the whole risk here is a port that quietly changes
                 which endpoints exist.
    ``entry_cs`` -- the csangle the node's own last frame committed (defaults to ``run.csangle``,
                 which is that value); the first segment frame reads it.

    The economy: ONE `camera_trace` for the whole fan, because the csangle a roll segment commits does
    not depend on the aim (measured across full fans, gated). Everything else is per aim -- the C
    step, her look model and the neck -- and the fan clones ``fast`` rather than re-seeding it."""
    aims = [tuple(a) for a in aims]
    talks = talk_screen(run, aims, l_window=l_window, hold=hold, a_hold=a_hold, post=post,
                        target_cs=target_cs)
    if fast is None:
        raise ValueError("roll_fan needs a self-eye twin (`fast=`); see `self_eye_twin`")
    refused = refused_record(run)
    out = [None] * len(aims)
    live = [i for i, t in enumerate(talks) if not t]
    for i, t in enumerate(talks):
        if t:
            out[i] = dict(refused)
    if not live:
        return out
    cs0 = int(run.csangle) if entry_cs is None else int(entry_cs)
    seg_cs = camera_trace(run, aims[live[0]], l_window=l_window, target_cs=target_cs,
                          hold=hold, a_hold=a_hold, post=post)['csangle']
    for i in live:
        stream = T.roll_stream(aims[i], hold=hold, a_hold=a_hold, l_window=l_window, post=post)
        rr = fast.clone()
        frames = 0
        roll_speedF = roll_facing = None
        seen = False
        for k in range(T.MAX_ROLL_FRAMES + 1):
            rr.step(stream(k), csangle=(cs0 if k == 0 else seg_cs[k - 1]))
            frames += 1
            if rr.link.state == T.FRONT_ROLL:
                seen = True
                if roll_speedF is None:
                    roll_speedF, roll_facing = rr.link.speedF, rr.link.facing
            elif seen and rr.link.state == 6:
                break
        out[i] = dict(ok=seen, talk_unsafe=False, roll_speedF=roll_speedF,
                      roll_facing=roll_facing, frames=frames, exit_cs=int(seg_cs[frames - 1]),
                      link=(rr.link.pos_x, rr.link.pos_z, int(rr.link.facing),
                            int(rr.link.travel), rr.link.speedF, int(rr.link.state)),
                      tetra=(rr.tx, rr.tz), followed=bool(rr._follow_warned))
    return out
