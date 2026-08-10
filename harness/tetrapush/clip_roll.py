"""**THE CLIP ROLL'S INPUTS, AND WHAT THE ROLL ACTUALLY COSTS IN FRAMES.**

Every bound in this module's neighbourhood has priced the clip roll as ``PairFrame.cut_step``
(`handoff.endpoint`: ``frames + gap / WALK_CAP + pf.cut_step``) and nothing has ever emitted its
bytes. Session 143 built the sequence and measured the cost, and the two answers disagree.

**THE ROLL COSTS ``cut_step + 2`` FRAMES, NOT ``cut_step``.** `entry_search.roll_entry` says the
entry frame runs one full roll step BEFORE the schedule's step 0, and
`rollstab.turnaround.extract_schedule_at` seeds a `LandState` already in FRONT_ROLL at ``entry`` and
calls its first STEPPED frame k=0 -- so schedule step ``k`` is roll frame ``k + 2`` and the cut at
step ``cut_step`` is roll frame ``cut_step + 2``. `roll_frames` is the number; nothing here restates
it. This is `entry_fan.plan_cost`'s ``plan_frames + thrust + 4`` seen from the roll's end
(`knowledge/mechanics/roll-cut-thrust-floor.md`) -- the fact was in the repo and `handoff.endpoint`
charges ``cut_step`` anyway, which is why it is gated here by SIMULATION rather than restated.

And the thrust it is charged at has to exist: `entry_search.cut_step_window` admits ``cut_step``
15..17 only, so the cheapest deliverable clip roll is **17 frames**.

**THE STREAM.** Three knobs and one rising edge, the `rollstab.turnaround.build_sticks` shape that
the live roll-stab clip was delivered on: the aim + A press, a NEUTRAL stick through the roll (a
PUSHED stick past `LandState.ROLL_EARLY` fires `_roll_exit` early and there is no cut), and ONE UP+B
rising edge at `b_index` -- ``cut_step + 1`` frames after the A. That index is `build_sticks`'
``B_STEP`` re-derived rather than re-stated: its 16 is measured from the frame AFTER the A press,
so it is ``cut_step + 1`` counted from the press itself, and its own note ("b_step=15 fires it a
frame early -> no lunge") is the same off-by-one from the other side. UP, not neutral: a neutral B
out of a roll is a side slash, not the in-line CUT_F whose root translate IS the 23.22 u lunge.

**WHERE IT CAN BE FIRED FROM -- two traps, both measured on real herd logs (session 143):**

  * The A-roll dispatches only from ``WAIT``/``FREE_WAIT``/``MOVE``/``ATN_MOVE`` (`LandState.step`'s
    ``grounded``). A herd roll EXITS into ``ATN_ACTOR_MOVE`` while the actor lock is live, and an A
    press on that frame does nothing at all -- so the frame that looks like the natural chain point
    is the one frame that refuses.
  * `_roll_init` takes the roll's whole momentum from the PRE-ROLL speedF. One frame later the
    untarget flip has run (speedF -25.72) and `entry_search.roll_nspeed` clamps that to **5.0** -- a
    65 u roll against a runway grid that starts at 160. `dispatchable` reports both, because a plan
    that fires the clip roll off the flip is not slow, it is geometrically impossible.

**AND IT CANNOT BE STEPPED ON THE NATIVE CORE.** `_anmc._proc_roll` omits the ``b_trig`` arm of the
Python `_proc_roll`, so the C courtyard engine has no cut at all: a B press mid-roll is ignored and
the roll runs to its ordinary exit. Build the herd on the native step, then `fire` the clip roll on a
Python-path run (`beam_io.rebuild_beam(native=False)`), which is gated 0-ULP against it.

    python -m harness.tetrapush.clip_roll stream [cut_step]
"""
import os
import sys

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.tetrapush import entry_search as ES
from harness.tetrapush import search as S
from harness.tetrapush import two_roll as TR
from tww_sim.land.constants import CUT_A, CUT_F, FRONT_ROLL, ROLL_FROM

#: The sword button. `LandState._b_trig` is a RISING edge on this bit, so the stream presses it once.
PAD_B = 0x200
#: The thrust's stick. Full UP makes the roll exit a CUT_F (`_roll_exit`: ``aim = self.target`` while
#: the stick is pushed and L is off); neutral would take the side-slash branch.
CUT_STICK = (128, 255)
NEUTRAL = (128, 128)
#: The C-stick the herd's own tail rows hold. Physics-inert; it only has to not steer the camera
#: between the aim and the entry frame (`[[tetrapush-dtm-delivery]]`).
SUBSTICK = (128, 0)
#: Procs an A press can roll out of -- `LandState.step`'s ``grounded`` set is wider, but the roll arm
#: re-tests ``state in ROLL_FROM``, and ATN_ACTOR_MOVE is in neither (see the module docstring).
ROLL_DISPATCH_PROCS = ROLL_FROM


def roll_frames(cut_step):
    """**Frames from the roll's dispatch to the cut, inclusive** -- the clip roll's real cost.

    ``cut_step + 2``: the entry frame (one full roll step, `entry_search.roll_entry`), then schedule
    steps 0..``cut_step``, the last of which IS the cut."""
    return int(cut_step) + 2


def b_index(cut_step):
    """Raw-stream index of the UP+B rising edge, counted from the A press at index 0."""
    return int(cut_step) + 1


def clip_stream(aim_bytes, cut_step, *, a_hold=2, hold=1, substick=SUBSTICK, tail=2):
    """The clip roll's raw controller rows: aim + A, neutral through the roll, ONE UP+B at
    `b_index`, then ``tail`` neutral rows.

    ``hold`` frames of the aim (1 = the A frame only) and ``a_hold`` frames of A are the human's own
    knobs from `two_roll.roll_stream`; the stick MUST fall to neutral before `LandState.ROLL_EARLY`
    or the roll exits without a cut. There is no L window -- this roll is not exiting into an
    untarget EBS, and a live lock would route the exit to CUT_A (the vertical slash) instead."""
    n = b_index(cut_step) + 1 + int(tail)
    out = []
    for k in range(n):
        sx, sy = aim_bytes if k < int(hold) else NEUTRAL
        buttons = S.PAD_A if k < int(a_hold) else 0
        if k == b_index(cut_step):
            sx, sy = CUT_STICK
            buttons = PAD_B
        out.append(dict(stickX=int(sx), stickY=int(sy), buttons=buttons, triggerL=0,
                        substickX=int(substick[0]), substickY=int(substick[1])))
    return out


def aim_bytes_for(facing, csangle, msd_min=None):
    """The fan member that rolls Link onto ``facing`` from this camera, and how far it misses.

    `entry_search.aim_alphabet`'s map inverted: a fan angle ``ang`` gives roll facing
    ``(ang + 0x8000 + csangle) & 0xFFFF``. The fan is the whole reachable byte grid
    (`two_roll.roll_aim_fan`), so the miss is the controller's own angular resolution and not a
    search window -- but it is a MISS, and at a razor 1e-4 u wide the caller has to know it: the
    schedule is quantized to `entry_search.aim_cell`, so what actually matters is whether
    ``err`` moves the facing into a different sine cell."""
    want = (int(facing) - 0x8000 - int(csangle)) & 0xFFFF
    best = None
    for ang, byts in (TR.roll_aim_fan() if msd_min is None else TR.reachable_stick_fan(msd_min)):
        d = ((ang - want + 0x8000) & 0xFFFF) - 0x8000
        if best is None or abs(d) < abs(best[2]):
            best = (tuple(byts), (ang + 0x8000 + int(csangle)) & 0xFFFF, d)
    got = best[1]
    return dict(bytes=best[0], facing=got, err=best[2], cell=ES.aim_cell(got),
                cell_ok=(ES.aim_cell(got) == ES.aim_cell(int(facing) & 0xFFFF)))


def dispatchable(link):
    """**Can a clip roll be fired from this state, and what momentum would it carry?**

    ``ok`` is the proc half (`ROLL_DISPATCH_PROCS`); ``nspeed`` is `entry_search.roll_nspeed` of the
    pre-roll speedF, which is what `terminal.RollFrame` has to be built at -- the razor engine bakes
    `entry_search.ROLL_NSPEED` (26.0) by default and a sub-cap roll is a DIFFERENT locus, not a worse
    one. ``at_cap`` is the only case the banked terminals were solved for."""
    nspeed = ES.roll_nspeed(link.speedF)
    return dict(ok=(link.state in ROLL_DISPATCH_PROCS), proc=int(link.state),
                speedF=float(link.speedF), nspeed=float(nspeed),
                at_cap=(nspeed == ES.ROLL_NSPEED),
                reason=('' if link.state in ROLL_DISPATCH_PROCS
                        else 'proc %d cannot dispatch an A-roll' % int(link.state)))


def fire(run, aim_bytes, cut_step, *, frame0=0, log=None, **kw):
    """Step ``run`` through the clip roll and report where the roll entered and where it cut.

    ``run`` is a `from_f0.FreeRun` on the PYTHON path (the native core has no cut -- see the module
    docstring); it is advanced in place. ``frame0`` is the frame number already on the clock, so
    ``entry_frame``/``cut_frame`` come back in the plan's own numbering. ``log`` collects the emitted
    rows for a delivery splice.

    Returns ``dict(ok, entry_frame, cut_frame, frames, entry, cut_type, dispatch, rows)``; ``ok`` is
    False with ``entry_frame`` None when the press never rolled (the `dispatchable` traps) and with
    ``cut_frame`` None when the roll exited before the thrust."""
    disp = dispatchable(run.link)
    stream = clip_stream(aim_bytes, cut_step, **kw)
    entry_frame = cut_frame = entry = cut_type = None
    rows = []
    for k, d in enumerate(stream):
        run.step(d)
        if log is not None:
            log.append(dict(d))
        f = int(frame0) + k + 1
        lk = run.link
        rows.append(dict(frame=f, proc=int(lk.state), speedF=float(lk.speedF),
                         facing=int(lk.facing), pos=(float(lk.pos_x), float(lk.pos_z)),
                         tetra=(float(run.tx), float(run.tz))))
        if lk.state == FRONT_ROLL and entry_frame is None:
            entry_frame, entry = f, (float(lk.pos_x), float(lk.pos_z))
        if lk.state in (CUT_F, CUT_A) and cut_frame is None:
            cut_frame, cut_type = f, int(lk.state)
    return dict(ok=(entry_frame is not None and cut_frame is not None), dispatch=disp,
                entry_frame=entry_frame, cut_frame=cut_frame, entry=entry, cut_type=cut_type,
                frames=(None if entry_frame is None or cut_frame is None
                        else cut_frame - entry_frame + 1), rows=rows)


# --------------------------------------------------------------------------- CLI

def main(argv=None):
    import warnings
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'stream'
    if cmd != 'stream':
        raise SystemExit(__doc__)
    cut_step = int(argv[0]) if argv else 13
    print("clip roll at cut_step %d: %d frames (cut_step + 2), B rising edge at raw index %d"
          % (cut_step, roll_frames(cut_step), b_index(cut_step)))
    for k, d in enumerate(clip_stream((128, 255), cut_step)):
        print("  %2d  stick (%3d, %3d)  buttons %#05x%s"
              % (k, d['stickX'], d['stickY'], d['buttons'],
                 '   <- A' if d['buttons'] & S.PAD_A else
                 ('   <- UP+B (the thrust)' if d['buttons'] & PAD_B else '')))


if __name__ == '__main__':
    main()
