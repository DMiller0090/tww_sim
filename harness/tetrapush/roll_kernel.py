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

**Session 128 moved the two look models into the C frame as well** (`seeds.make_freerun_native_look`,
`knowledge/model/porting-the-look-pair.md`), which is what `self_eye_twin` now builds by default:
the same 143-aim fan is **0.057 s**. Everything below is unchanged -- the economy is the same, the
per-aim rollout just got 6.8x cheaper.

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
from harness.tetrapush.from_f0 import cam_pad
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


class _RecordLink(object):
    """The Link half of a `segment_record`, named the way a `FreeRun`'s is."""
    __slots__ = ('pos_x', 'pos_z', 'facing', 'travel', 'speedF', 'state')

    def __init__(self, t):
        (self.pos_x, self.pos_z, self.facing, self.travel, self.speedF, self.state) = t


class RecordRun(object):
    """**A `segment_record` in the shape a run is read in** -- what lets the search's SCREEN stage
    run off fan records without a live `FreeRun` behind each aim.

    The screen (`full_herd.roll_candidates`' R1) fires the whole aim fan, ranks it, keeps three, and
    THROWS EVERY RUN AWAY -- it carries only ``(want, aim, l_window)`` forward. What it reads in
    between is `two_roll.metrics`, `two_roll.alive`, `full_herd.frame_in_model` and the beam's
    `rank_key`, and between them they touch exactly nine fields: Link's XZ / facing / travel /
    speedF / proc, Tetra's XZ, the csangle and the follow flag. `segment_record` already carries all
    nine, so those functions run here unchanged rather than being re-expressed against records --
    which is the point: a second expression of a prune is a second thing to keep in step.

    Deliberately NOT a `FreeRun` stand-in. It cannot step, and any consumer that reaches for
    something a record does not carry raises `AttributeError` at that line instead of quietly
    reading a stale or defaulted value."""
    __slots__ = ('link', 'tx', 'tz', 'csangle', '_follow_warned', 'record')

    def __init__(self, rec):
        self.record = rec
        self.link = _RecordLink(rec['link'])
        self.tx, self.tz = rec['tetra']
        self.csangle = int(rec['exit_cs'])
        self._follow_warned = bool(rec['followed'])


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


def self_eye_twin(env, log, cs_trace, native_look=True):
    """A fully-native run at the state ``log`` reaches -- the fan's seed.

    ``native_look`` (session 128, the default) runs her look model and Link's neck INSIDE the C step
    instead of in Python beside it: **9279 -> 62682 steps/s**, the same answer 0-ULP
    (`tests/test_native_zl1_look.py`). Pass False for the s127 `make_freerun_self_eye` twin -- the
    gate below runs BOTH, because "the fast one is the slow one" is the claim this module rests on
    and it should be checked, not inherited.

    The camera is injected a frame late by construction: step ``i`` reads the csangle committed at
    the end of step ``i-1`` (`from_f0.FreeRun.step`'s own convention), which is why `wired_csangle_trace`
    records post-step values and this offsets them. Getting that off by one is silent -- the run still
    looks plausible -- so `tests/test_roll_kernel.py` checks the twin against the wired node 0-ULP
    before any fan runs off it."""
    from harness.tetrapush import seeds as SD
    run = (SD.make_freerun_native_look(env) if native_look else SD.make_freerun_self_eye(env))
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    for i, d in enumerate(log):
        run.step(d, csangle=(cs_trace[i - 1] if i else None))
    return run


def node_twin(env, log, native_look=True, check=None):
    """**The fan's seed for a search node, in one call** -- the wired camera replay plus the native
    twin it feeds (`wired_csangle_trace` + `self_eye_twin`).

    This is the stopgap the s128 handoff named: one WIRED replay of the node's log per node, where
    recording the csangle as the node steps would cost nothing. Session 129 measured what it is
    worth before building the recorder, and the answer is to keep the stopgap -- the replay is one
    log (~55 frames) against a screen of ~200 roll segments, so it is a few percent of the stage it
    feeds, and the recorder is a wide change to every log-append site for that.

    ``check`` -- the node's own wired run. Passing it turns the premise this rests on into a runtime
    assertion instead of a hope: a node whose log does not reconstruct it (a stage that touched its
    run outside the log, a truncated or re-based log) would otherwise hand the fan a twin at a
    DIFFERENT state, and every record would then be bit-exact about a state the search never
    reaches. It costs eight float comparisons against a replay that just ran."""
    twin = self_eye_twin(env, log, wired_csangle_trace(env, log), native_look=native_look)
    if check is not None:
        got = (twin.link.pos_x, twin.link.pos_z, int(twin.link.facing), int(twin.link.travel),
               twin.link.speedF, int(twin.link.state), twin.tx, twin.tz)
        want = (check.link.pos_x, check.link.pos_z, int(check.link.facing), int(check.link.travel),
                check.link.speedF, int(check.link.state), check.tx, check.tz)
        if got != want:
            raise ValueError("node twin is not at the node's state -- the log does not reconstruct "
                             "this run (%d frames)\n  twin %r\n  node %r" % (len(log), got, want))
    return twin


# --------------------------------------------------------------------------- the tcs family (R2)

class SharedBody(object):
    """**One aim's roll, up to the frame its camera target could first have changed it** -- the body
    a whole `target_cs` family shares, stepped once.

    `full_herd.roll_candidates`' R2 re-runs the same roll under ~25 camera targets, and
    `full_herd.target_cs_is_exit_only` already says what that buys: inside a roll the camera target
    changes nothing but the camera. Measured over the real grid (session 130) the physics is
    bit-identical for **17 of a 22-frame segment** and the first frame that differs is the first
    frame after the `FRONT_ROLL` block -- so ``branch`` is read off the roll's own end rather than
    set to a number, and the shared part is whatever this node's roll turns out to be.

    Carries the per-frame `LandCamera.step` arguments (`FreeRun.step`'s own ``sim_cam_in``), which
    are pose and physics and therefore shared, and one snapshot of the run at ``branch``.

    ``ok`` False means this aim has no shared body to offer -- it talks, or no roll ever fires, or
    the segment ended inside the roll -- and the caller runs the wired path for it."""
    __slots__ = ('stream', 'args', 'branch', 'snap', 'entry_cs', 'prev_raw', 'camera',
                 'roll_speedF', 'roll_facing', 'talk_unsafe', 'ok', 'refused')

    def __init__(self, run, aim, *, l_window=(5, 8), hold=1, a_hold=2, post=ESS_DOWN):
        self.stream = T.roll_stream(tuple(aim), hold=hold, a_hold=a_hold, l_window=l_window,
                                    post=post)
        self.entry_cs = int(run.csangle)
        self.prev_raw = run._prev_raw
        self.camera = run.camera
        self.args, self.branch, self.snap = [], None, None
        self.roll_speedF = self.roll_facing = None
        self.refused = refused_record(run)
        self.talk_unsafe = bool(S.a_press_is_talk(
            run, dict(self.stream(0), substickX=T.CSTICK_NEUTRAL, substickY=0)))
        self.ok = False
        if self.talk_unsafe or run.camera is None:
            return
        rr = run.clone()
        seen = False
        for k in range(T.MAX_ROLL_FRAMES + 1):
            prev = rr.clone()
            row = rr.step(dict(self.stream(k), substickX=T.CSTICK_NEUTRAL, substickY=0))
            self.args.append(row['sim_cam_in'])
            if rr.link.state == T.FRONT_ROLL:
                seen = True
                if self.roll_speedF is None:
                    self.roll_speedF, self.roll_facing = rr.link.speedF, rr.link.facing
            elif seen:
                self.branch, self.snap, self.ok = k, prev, True
                break


def camera_walks(body, target_css):
    """**Every camera target's own csangle, from ONE body's arguments** -- the camera model alone,
    no physics, walked as a PREFIX TREE.

    Two measured facts make this the whole of what a tcs costs before the branch. The camera's
    arguments are Link's pose and the attention, so they are the shared body's (session 130 gated
    the stronger form: they reproduce every target's committed csangle even PAST the divergence,
    which is `FreeRun`'s own "csangle is position-independent in this regime"). And two targets that
    have delivered the same C-stick bytes so far are at the same camera state, so they walk together
    and split only when `two_roll.slew_substick` first tells them apart -- 775 camera steps become
    529 on the shipped grid, and the group is one camera object, not one per member.

    (The tempting third cut is wrong and was measured wrong: a centred C-stick does NOT freeze
    csangle on the spot -- the camera keeps chasing for a few frames -- so a target whose stick has
    gone neutral still has to be stepped. `two_roll.slew_substick`'s "neutral FREEZES csangle" is
    the steady state, not the transient.)

    Returns ``{target_cs: (camera, csangle, substicks)}`` at the branch frame: the camera AFTER the
    body's last shared frame, the csangle it committed there, and the C-stick byte delivered on each
    shared frame."""
    D = int(body.branch)
    pads = {}

    def pad(k, sub):
        p = pads.get((k, sub))
        if p is None:
            p = pads[(k, sub)] = cam_pad(body.prev_raw if k < 0 else
                                         dict(body.stream(k), substickX=sub, substickY=0))
        return p

    groups = [dict(cam=body.camera.clone(), cs=body.entry_cs, prev=None,
                   mem=list(target_css), subs=[])]
    for k in range(D):
        nxt = []
        for g in groups:
            cs2 = int(g['cam'].step(pad(k - 1, g['prev']), *body.args[k]))
            by = {}
            for tcs in g['mem']:
                by.setdefault(T.slew_substick(g['cs'], tcs), []).append(tcs)
            first = True
            for sub, mem in by.items():
                cam = g['cam'] if first else g['cam'].clone()
                first = False
                nxt.append(dict(cam=cam, cs=cs2, prev=sub, mem=mem, subs=g['subs'] + [sub]))
        groups = nxt
    out = {}
    for g in groups:
        for tcs in g['mem']:
            out[tcs] = (g['cam'], g['cs'], tuple(g['subs']))
    return out


def tcs_segment(body, walk, tcs, *, log=None):
    """**`two_roll.roll_segment` for one camera target, off the shared body** -- the shared frames
    are not re-run, only the exit tail is.

    The branch swaps this target's camera into a clone of the body's snapshot, and with it the
    csangle and the delivered input the camera acts on next (it reads the pad one frame late). The
    stored state a wrong branch would carry is the stick want-angle `m34E8`, and it is recomputed
    from the stick and the csangle every non-neutral frame -- so the swap is complete, which is what
    session 130 measured: 250 of 250 branched records `==` the wired ones.

    Returns the `roll_segment` dict and the branched run; ``log`` is extended with every delivered
    input of the WHOLE segment, shared frames included, so the caller's node log is the same log the
    wired path would have appended."""
    cam, cs, subs = walk[tcs]
    D = int(body.branch)
    if log is not None:
        log.extend(dict(body.stream(k), substickX=subs[k], substickY=0) for k in range(D))
    rr = body.snap.clone()
    rr.camera = cam.clone()
    rr.csangle = cs
    rr._prev_raw = (dict(body.stream(D - 1), substickX=subs[D - 1], substickY=0) if D
                    else body.prev_raw)
    frames = D
    roll_speedF, roll_facing = body.roll_speedF, body.roll_facing
    for k in range(D, T.MAX_ROLL_FRAMES + 1):
        d = dict(body.stream(k), substickX=T.slew_substick(rr.csangle, tcs), substickY=0)
        if log is not None:
            log.append(dict(d))
        rr.step(d)
        frames += 1
        if rr.link.state == T.FRONT_ROLL:
            if roll_speedF is None:
                roll_speedF, roll_facing = rr.link.speedF, rr.link.facing
        elif rr.link.state == 6:
            break
    return dict(ok=True, talk_unsafe=False, roll_speedF=roll_speedF, roll_facing=roll_facing,
                frames=frames, exit_cs=rr.csangle), rr


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
            # record=False: the fan reads the endpoint off `rr`, never the row, and building it
            # costs three live reads of the C look state per frame (session 128).
            rr.step(stream(k), csangle=(cs0 if k == 0 else seg_cs[k - 1]), record=False)
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
