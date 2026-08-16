"""**THE OVERNIGHT SEARCH: a frame-optimal, branch-and-bounded pass for a Courtyard plan that beats
the banked console 101** (session 150).

WHAT THIS IS. Every herd in the repo, handed to the terminal machinery that actually produced the
console clip, ordered so the cheapest possible plan is tried first, run in parallel to a deadline,
checkpointed per line so it survives being killed, and reporting its own coverage rather than only its
answers. It is a ONE-TIME search for the real run, not a general solver.

WHY THIS SHAPE, and not the two-stage beam session 149 ran. The pipeline that has ever delivered a
console clip is `entry_fan.iter_fan2` (the OpenMP `prange` fleet, ~1M steps/s) -> `ShoveCtx.sweep_par`
(75 k scorings/s) -> `entry_search.confirm_entry` (a REAL A-press) -> `cross_engine.agree` (the walled
composite, frame for frame). It had only ever been pointed at ONE herd -- the console arrival -- and
three of its stages silently replayed that arrival's own log whatever seed they were handed
(`walk_fan`, `confirm_entry`, `cam_trail`; all three fixed this session, all three inert at the
default). Pointing it at the 49 banked rungs is the search this session owes, and it is 250x the
throughput of a Python walled beam.

THE ONE MODEL GENERALIZATION IT NEEDED. Every pass before this scored a whole fan against ONE pinned
Tetra, which is only true while Link has broken contact -- true of the console arrival, false of a herd
end still plowing her. `entry_fan` now carries her tracked feet in the fan key (``with_tetra``) and the
razor takes her per item, so the stay-in-contact and walk-away regimes are ONE population here instead
of two searches with two ranks (session 149's open axis).

THE OBJECTIVE, EXECUTABLE (`objective.py` owns the rules):

    total = herd frames + walk frames + roll_frames(thrust),  roll_frames = thrust + 4 counted to the
    cut (`entry_fan.plan_cost`), i.e. 17 / 18 / 19 for thrust 13 / 14 / 15.

Work is ordered by ``floor = herd + 1 + roll_frames(cheapest thrust)`` ASCENDING and, inside a unit, by
WALK LENGTH ascending -- so the first hit a unit reports is the best that unit can produce, and once a
plan lands at total T every unit whose floor is >= T is skipped (the s142 branch-and-bound, crossing
processes through ``incumbent.json``). **It does not stop at the first hit**: a run that returns 99 when
97 was reachable has failed the objective, so the deadline is the only stop.

WHAT COUNTS. Nothing is reported as a plan until `cross_engine.agree` says ``deliverable`` -- the razor
called it genuine, a real A-press reproduced the entry it was scored at, and the WALLED composite
reproduces the cut bit-for-bit. `objective.score_plan` / `verdict` are recorded beside it. A bound is
not a plan.

THE PHASE RULE (Dereck, s149) is respected by construction: the herd is a banked log replayed unwalled
and CHECKED against `objective.frame_is_wall_free`, and the terminal composite runs with both actors'
`dBgS_Acch::CrrPos` wired (`cross_engine.composite_rollout`). A herd that is not wall-inert -- one whose
walled and unwalled replays part before it ends -- violated rule 4, and that single check both
configures and validates the unit.

    python -m harness.tetrapush.overnight units
    python -m harness.tetrapush.overnight verify-console
    python -m harness.tetrapush.overnight items [head=N]
    python -m harness.tetrapush.overnight item <id|unit> [walk=N] [seconds=S]
    python -m harness.tetrapush.overnight run [workers=11] [hours=7] [id=<run>] [resume=1]
                                              [only=rung03,rung17] [leaf=40000000] [pre=16]
                                              [tail=1,2] [tbeam=400] [pcap=20000]
    python -m harness.tetrapush.overnight status [id=<run>] [full=1]
"""
import json
import math
import os
import struct
import subprocess
import sys
import time
import traceback
import warnings

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.tetrapush import away_walk as AW
from harness.tetrapush import cross_engine as XE
from harness.tetrapush import entry_camera as EC
from harness.tetrapush import entry_fan as EF
from harness.tetrapush import entry_search as ES
from harness.tetrapush import objective as O
from harness.tetrapush import overnight_io as IO
from harness.tetrapush import seeds as SD
from harness.tetrapush.from_f0 import cc_push_pair
from tww_sim.core.fp import fadds
from tww_sim.land.plan_land._primitives import stick_for_bearing

REPO = _rb
LADDER = os.path.join(REPO, 'fixtures', 'courtyard_candidate_ladder.json')
CONSOLE_CLIP = os.path.join(REPO, 'fixtures', 'courtyard_clip_s90_console.json')

#: The shortest plan the space contains: one delivered walk frame (`entry_fan.iter_fan`'s own minimum)
#: at the cheapest roll `entry_search.cut_step_window` admits. ADMISSIBLE, so a cut on it proves a drop.
WALK_FLOOR = 1
THRUST_FLOOR = EF.THRUST_FLOOR

#: How far past the plan the camera trail is measured. The fan reads index ``n0 + j1 + j2`` and the aim
#: frame one past the walk, so this is slack, not a limit.
TRAIL_PAD = 12

#: Genuine rows per item pushed through the acceptance stack. A real bound on coverage, so every row
#: logs ``genuine`` and ``n_ranked`` beside ``confirmed`` -- never a silent cap.
MAX_ACCEPT = 48


def roll_frames(thrust):
    """Frames the clip roll spends from the A-press to the cut, inclusive: ``thrust + 4``.

    `entry_fan.plan_cost`'s own arithmetic, named so the floors below read as frames. The A frame, the
    entry frame, the schedule out to ``cut_step = thrust + 2``, and the cut."""
    return int(thrust) + 4


def total_frames(herd, walk, thrust):
    """A plan's whole cost from the state-2 seed to the cut."""
    return int(herd) + int(walk) + roll_frames(thrust)


def unit_floor(herd):
    """The cheapest total any plan off this herd could reach -- the branch-and-bound key."""
    return total_frames(herd, WALK_FLOOR, THRUST_FLOOR)


def max_walk(herd, thrust, incumbent):
    """The longest walk that could still BEAT ``incumbent`` at this thrust (0 = the thrust is out)."""
    return int(incumbent) - 1 - int(herd) - roll_frames(thrust)


# --------------------------------------------------------------------------- the herds

def console_herd():
    """The console solution's own herd, off the LOCKED delivery fixture: its log up to the walk-up.

    This is what puts the incumbent inside the search's own range rather than beside it
    (`[[search-space-contains-human]]`, and `tests/test_console_solution_in_search_space.py` one stage
    down). ``n_console`` is the fixture's own field -- the frame count its walk plan was measured from --
    so the herd here is exactly the herd the 101 was found off."""
    d = json.load(open(CONSOLE_CLIP))
    n = int(d['plan']['n_console'])
    return dict(unit='console', source='courtyard_clip_s90_console.json', rank=None,
                herd=n, log=[dict(r) for r in d['log'][:n]])


def ladder_herds():
    """The 49 banked rungs. Their ORDER on the ladder is not used: it was ranked to hand over to a
    terminal that is not the one being solved (thrust 11 / facing 40660 / cut_step 13, its own
    ``terminal`` block) and no rung has a confirmed genuine entry (its own ``CONFIRMATION_WARNING``).
    The herd LOG is banked data and is what this reads."""
    d = json.load(open(LADDER))
    return [dict(unit='rung%02d' % c['rank'], source='courtyard_candidate_ladder.json',
                 rank=c['rank'], herd=int(c['herd']), log=[dict(r) for r in c['log']])
            for c in d['candidates']]


def units(incumbent=None, trunc=0):
    """Every work unit, ordered by ``floor`` ascending, with the DROPPED ones carried beside them.

    ``trunc`` also enumerates each herd cut short by 1..trunc frames -- a shorter herd has a lower
    floor, and nothing has ever asked whether Tetra is clippable a frame or two before the banked herd
    ends. Off by default: it multiplies the unit count and the banked ends are where she was aimed.

    Dropping is on the ADMISSIBLE floor only, so a drop is a proof and not a heuristic: a unit whose
    every thrust admits a walk of 0 delivered frames cannot produce a plan that beats the incumbent,
    because the fan's shortest plan is one frame."""
    inc = O.TOTAL_INCUMBENT if incumbent is None else int(incumbent)
    src = [console_herd()] + ladder_herds()
    out = []
    for h in src:
        for cut in range(0, int(trunc) + 1):
            u = dict(h)
            if cut:
                u = dict(h, unit='%s-c%d' % (h['unit'], cut), herd=h['herd'] - cut,
                         log=h['log'][:h['herd'] - cut], truncated=cut)
            u['floor'] = unit_floor(u['herd'])
            u['walks'] = {t: max_walk(u['herd'], t, inc) for t in ES.THRUSTS}
            u['thrusts'] = sorted(t for t, w in u['walks'].items() if w >= WALK_FLOOR)
            out.append(u)
    keep = [u for u in out if u['thrusts']]
    drop = [dict(unit=u['unit'], herd=u['herd'], floor=u['floor'],
                 reason='floor %d cannot beat incumbent %d at any thrust' % (u['floor'], inc))
            for u in out if not u['thrusts']]
    keep.sort(key=lambda u: (u['floor'], u['herd'], u['unit']))
    return keep, drop


def items(incumbent=None, trunc=0):
    """The work queue: one item per ``(herd, walk length)``, ordered by the TOTAL it could produce.

    This is the objective as a schedule. Ordering unit-major searches one herd to its budget before
    touching the next, which spends the early hours on 100-frame plans off the first rung while a 91-frame
    plan sits unexamined on the ninth. Ordering by ``total = herd + walk + roll_frames(cheapest admissible
    thrust)`` makes the run globally best-first: at any moment the cheapest unexplored plan shape in the
    whole space is the next thing claimed, so a deadline cuts the EXPENSIVE end and a plan found early is
    already near-optimal.

    Returns ``(items, dropped)``. Each item carries its herd's log, so a worker needs nothing else."""
    inc = O.TOTAL_INCUMBENT if incumbent is None else int(incumbent)
    us, drop = units(incumbent=inc, trunc=trunc)
    out = []
    for u in us:
        top = max(u['walks'][t] for t in u['thrusts'])
        for walk in range(WALK_FLOOR, top + 1):
            ts = sorted(t for t in u['thrusts'] if u['walks'][t] >= walk)
            if not ts:
                continue
            out.append(dict(item='%s-w%02d' % (u['unit'], walk), unit=u['unit'], herd=u['herd'],
                            log=u['log'], walk=walk, thrusts=ts,
                            floor=min(total_frames(u['herd'], walk, t) for t in ts),
                            truncated=u.get('truncated', 0)))
    out.sort(key=lambda x: (x['floor'], x['walk'], x['herd'], x['unit']))
    return out, drop


# --------------------------------------------------------------------------- per-unit setup

def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def prepare(unit, env, walls=None):
    """Replay a unit's herd and return the seed the terminal machinery consumes, plus the VALIDITY of
    the herd itself.

    Two replays, unwalled (native) and walled, and the check is that they are bit-identical for every
    frame: **a herd that diverges walled-vs-unwalled IS a herd that violated rule 4**, because the only
    thing the wall pass can do is push an actor that reached geometry. So this one step both configures
    the unit and validates it, and `objective.frame_is_wall_free` is evaluated per frame beside it as
    the rule's own predicate.

    Returns ``dict(seed, ok, reason, ...)``; ``seed`` carries the herd log, Tetra's frozen point, and
    Link's endpoint, in `entry_search.console_seed`'s own shape so every downstream stage takes it."""
    walls = O.courtyard_walls() if walls is None else walls
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        plain = SD.make_freerun(env, native=True)
        plain.pre_seed_input(SD.dtm_input_at(env)(0))
        walled = SD.wall_for_terminal(SD.make_freerun(env, native=True))
        walled.pre_seed_input(SD.dtm_input_at(env)(0))
        first_part = None
        refused = []
        for i, d in enumerate(unit['log']):
            plain.step(d, record=False)
            walled.step(d, record=False)
            same = ((_bits(plain.link.pos_x), _bits(plain.link.pos_z),
                     _bits(plain.tx), _bits(plain.tz))
                    == (_bits(walled.link.pos_x), _bits(walled.link.pos_z),
                        _bits(walled.tx), _bits(walled.tz)))
            if first_part is None and not same:
                first_part = i
            if not O.frame_is_wall_free(plain.link.pos_x, plain.link.pos_z,
                                        plain.tx, plain.tz, walls):
                refused.append(i)
            rows.append(dict(i=i, x=plain.link.pos_x, z=plain.link.pos_z,
                             tx=plain.tx, tz=plain.tz))
        lk = plain.link
        seed = dict(tetra=(plain.tx, plain.tz), link=(lk.pos_x, lk.pos_z),
                    link_facing=int(lk.facing) & 0xFFFF, link_speedF=float(lk.speedF),
                    log=[dict(r) for r in unit['log']], n_scored=len(unit['log']),
                    n_last=len(unit['log']))
    ok = first_part is None and not refused
    return dict(seed=seed, ok=ok, wall_inert=first_part is None, first_divergence=first_part,
                refused=refused[:12], n_refused=len(refused),
                csangle=int(plain.csangle) & 0xFFFF, followed=bool(plain._follow_warned),
                proc=int(lk.state) & 0xFF, speedF=float(lk.speedF),
                feet=math.hypot(lk.pos_x - plain.tx, lk.pos_z - plain.tz),
                reason=('' if ok else
                        ('herd diverges walled-vs-unwalled at frame %s (rule 4: it reached geometry)'
                         % first_part if first_part is not None else
                         'herd refused by frame_is_wall_free at frames %s' % refused[:6])))


def configurations(csangle, thrusts):
    """Every (facing, thrust) the camera can AIM at, with the aim bytes that reach it.

    Deliberately NOT `entry_score.qualified`: that filter is measured at one Tetra and one reference
    station, and sessions 89, 90, 92 and 94 each found it silently excluding productive cells (the whole
    second lobe of the seam window, in s92's case). `genuine` off the sweep is ground truth and needs no
    band, so the honest thing on a run this long is to score the whole aimable set and let the razor
    speak. One configuration per sine-table CELL (`entry_search.aim_cells`) -- aims inside a cell are
    the same draw."""
    return [dict(facing=f, aim=list(byts), thrust=t, cell=ES.aim_cell(f), siblings=len(sib))
            for (f, byts, sib) in ES.aim_cells(int(csangle) & 0xFFFF) for t in sorted(thrusts)]


# --------------------------------------------------------------------------- the fan, per walk length

#: `search.PAD_L` and the analog trigger, together: the attention reads `mDoCPd_L_LOCK_BUTTON` and the
#: physics reads the trigger, so a half-pressed L is not a state a DTM delivers.
PAD_L = 0x40
TRIG_L = 255

#: The per-frame alphabet is ``(stick class, L)``: without the L bit no herd reaches the roll cap at all,
#: since only the DIR_BACKWARD negation turns the untarget backslide into +17 -- see `_families`.
L_AXIS = (0, 1)


def plan_frames(plan):
    """Delivered walk frames of an L-capable plan ``(n0, sx, sy, l, j, ...)``: the base hold plus every
    segment's own hold. The stride is 4, not `entry_fan.plan_frames`' 3, because each segment carries
    its L bit -- see `plan_rows`."""
    return int(plan[0]) + sum(int(x) for x in plan[4::4])


def l_press_frames(plan):
    """**Every frame index this plan presses L on a RISING EDGE**, earliest first -- the blip's own
    edges, which is what `entry_camera.aim_camera` needs to know which camera the aim frame reads.

    A segment holding L for ``j`` frames is ONE edge (at its start); consecutive L segments are one
    edge too. The base ``n0`` frames never press it (`hold_row` releases the button and the trigger
    deliberately), so a plan's first L segment is always a rising edge."""
    k, prev, out = int(plan[0]), 0, []
    for i in range(1, len(plan), 4):
        _sx, _sy, l, j = plan[i:i + 4]
        if int(l) and not prev:
            out.append(k)
        prev = int(l)
        k += int(j)
    return tuple(out)


def aim_camera(plan, walk, cs_trail):
    """The csangle THIS plan's A-press frame decodes against: `entry_camera.aim_camera` at the plan's
    own L edges. What `score` resolves each candidate's (facing, aim byte) pair at."""
    return EC.aim_camera(cs_trail, walk, l_press_frames(plan))


def aim_cell_map(csangle):
    """``cell -> (facing, aim bytes)`` at one camera: `configurations` without the thrust cross
    product, for a caller that already has its thrusts and needs the CELL's own byte."""
    return dict((ES.aim_cell(f), (f, list(b))) for (f, b, _s) in ES.aim_cells(int(csangle) & 0xFFFF))


def entry_recoil(k):
    """The ENTRY-FRAME CC push pair for one candidate key, or None when out of contact (s168).

    On the roll-dispatch frame the engine resolves the Link<->Tetra Co pair off Link's WALK-END
    exec Co centre (the 1-frame pose lag) at the walk-end positions, and the halves land on the
    post-roll-step Link and on Tetra -- `cc_push_pair`, proven 0-ULP forward on 5 engine-measured
    plans (`tests/test_entry_recoil.py`). The pair is a function of the CANDIDATE alone -- the aim
    never enters it (validated across cells) -- so it computes once per key: ``k[4:6]`` is the exec
    centre `fan_exact.collect` banked, ``k[-2:]`` the walk-end Tetra. The s167rung06 lesson: the
    uncorrected `roll_entry` scored 9.4M candidates ~5-8 u off their true entries everywhere the
    strip lives, minting 4 fictional genuine and an untrustworthy zero."""
    lh, th_ = cc_push_pair((k[4], k[5]), (k[-2], k[-1]))
    if lh == (0.0, 0.0) and th_ == (0.0, 0.0):
        return None
    return lh, th_


def entry_corrected(walk_xz, facing, rec):
    """`entry_search.roll_entry` plus the candidate's entry-frame recoil half. ``rec`` None (out of
    contact) reduces to the plain roll entry byte-identically."""
    e = ES.roll_entry(walk_xz, facing, ES.ROLL_NSPEED)
    if rec is None:
        return e
    return fadds(e[0], rec[0][0]), fadds(e[1], rec[0][1])


def tetra_corrected(k, rec):
    """The candidate's Tetra at the razor's first frame: the walk-end point plus her entry-frame
    push half. ``rec`` None reduces to the walk-end point byte-identically."""
    if rec is None:
        return k[-2], k[-1]
    return fadds(k[-2], rec[1][0]), fadds(k[-1], rec[1][1])


def hold_row(seed):
    """The walk's template row: the herd's last delivered row with the buttons, the trigger and the
    C-stick Y released.

    ONE definition, used by the fan (`entry_fan.base_core`'s hold), the camera trail, the confirmation
    and the composite -- if they disagree by one byte they are four different plans. L is released
    because the plan presses it deliberately (`plan_rows`) and a lock still live at the A-press routes
    the roll's exit to CUT_A, the vertical slash, instead of the in-line cut
    (`clip_roll.clip_stream`)."""
    return dict(seed['log'][-1], buttons=0, triggerL=0, substickY=0)


def plan_rows(hold, plan):
    """A plan's raw walk INPUT ROWS -- the encoding `entry_search.confirm_entry` and
    `cross_engine.agree` are handed instead of their own triples.

    ``plan = (n0, sx, sy, l, j, sx, sy, l, j, ...)``: ``n0`` frames of the arrival's own held stick,
    then each segment's stick held ``j`` frames with L down or up."""
    out = [dict(hold) for _ in range(int(plan[0]))]
    for i in range(1, len(plan), 4):
        sx, sy, l, j = plan[i:i + 4]
        for _ in range(int(j)):
            out.append(dict(hold, stickX=int(sx), stickY=int(sy),
                            buttons=(PAD_L if int(l) else 0),
                            triggerL=(TRIG_L if int(l) else 0)))
    return out


def plan_from_rows(rows):
    """`plan_rows` INVERTED: the plan tuple for a run of recorded input rows, run-length-encoded.

    What turns a stretch of a real delivered movie into a candidate this driver can price -- the
    console's own conversion off a herd cut short of it, say (session 154's rediscovery split: the
    console's log rows 71..81 ARE the answer at ``walk=11``, and this is how they are read back as a
    plan rather than authored as one). ``n0`` is always 0: a recorded run carries its own sticks from
    its first frame, and the base hold is the herd's, not the plan's.

    Round-tripping it is the containment question itself -- ``plan_rows(hold, plan_from_rows(rows)) ==
    rows`` says the recorded segment is expressible in this driver's own encoding, and a caller that
    cares should check it rather than assume (a row differing in a field the plan cannot carry, a
    C-stick move mid-walk, would fail that comparison and not this function)."""
    plan = [0]
    for r in rows:
        seg = (int(r['stickX']), int(r['stickY']), 1 if int(r.get('buttons', 0)) & PAD_L else 0)
        if len(plan) > 1 and tuple(plan[-4:-1]) == seg:
            plan[-1] += 1
        else:
            plan += [seg[0], seg[1], seg[2], 1]
    return tuple(plan)


def from_triples(plan):
    """A pre-s150 plan ``(n0, sx, sy, j, ...)`` in the L-capable encoding, L up on every segment. What
    lets the banked console plan be fed through this driver's own pipeline unchanged."""
    out = [int(plan[0])]
    for i in range(1, len(plan), 3):
        sx, sy, j = plan[i:i + 3]
        out += [int(sx), int(sy), 0, int(j)]
    return tuple(out)


def composite_log(seed, plan, aim, thrust, tail=XE.TAIL):
    """The whole delivery log for a plan: the herd, the walk, the A-press, the roll out to the UP+B
    thrust, then ``tail`` neutral frames.

    `cross_engine.composite_log`'s own index arithmetic, kept verbatim because getting it wrong reads
    exactly like a physics divergence (its session-86 trap): the roll dispatches at ``entry_i`` and the
    stream is delay-1, so ``roll[b_step]`` fires the cut on ``entry_i + b_step + 1`` and
    ``b_step = thrust + 2``. The only difference is the WALK, which comes from `plan_rows` so an L press
    inside it survives."""
    hold = hold_row(seed)
    extra = plan_rows(hold, plan)
    extra.append(dict(hold, stickX=int(aim[0]), stickY=int(aim[1]), buttons=0x100))
    log = list(seed['log']) + extra
    a_i = len(log) - 1
    entry_i = a_i + 1
    b_log = entry_i + int(thrust) + 2
    neu = dict(hold, stickX=128, stickY=128, buttons=0)
    upb = dict(hold, stickX=128, stickY=254, buttons=0x200)   # 254: authored == delivered
    for i in range(a_i + 1, b_log + 1 + int(tail)):
        log.append(dict(upb) if i == b_log else dict(neu))
    return log, dict(n_console=len(seed['log']), a_i=a_i, entry_i=entry_i, b_log=b_log)


def at_cap(speedF):
    """Would a roll dispatched from this walk speed carry the cut's momentum?

    ``roll_nspeed(speedF) == 26`` -- NOT ``speedF == 17.0``, which is what every fan before this used.
    The conversion lands speedF at **+17.609**, so an equality on the cap would have thrown away the
    only state that reaches the cap at all (measured s148). And sub-cap is not a cheaper locus but a
    dead one: at nspeed 5 the cut delivers 28.2 u against a ~49.46 u seam minimum, so 26 is a
    THRESHOLD (Dereck, s149) and this is a membership test."""
    return ES.roll_nspeed(float(speedF)) == ES.ROLL_NSPEED


def _rows_for(sticks, ls, cs):
    return [(sx, sy, PAD_L if l else 0, TRIG_L if l else 0, cs)
            for (sx, sy), l in zip(sticks, ls)]


def _step_batch(cores, sticks, l, csangle, nthreads):
    """One frame on a CLONE of each of ``cores``, each with its own delivered stick.

    The heterogeneous-fleet counterpart of `_fan`: `CourtyardFleet` takes a per-core schedule row, so a
    batch of unrelated states advances in the same `prange` as a batch of siblings. This is what makes
    the endpoint MEASUREMENT batched -- a prefix is carried after its last delivered byte, and the
    endpoint a roll dispatches from is one step further on (`_fan`)."""
    from tww_sim.core.anim import _anmc as N
    out = [c.clone(c.pe.clone_state()) for c in cores]
    if not out:
        return out
    fleet = N.CourtyardFleet(out, 1)
    fleet.set_schedule([[(sx, sy, PAD_L if l else 0, TRIG_L if l else 0, int(csangle))]
                        for (sx, sy) in sticks])
    fleet.run_par(1, nthreads)
    return out


def _atom_junction(base, flips, rotate_side, rotate_off, csangle, cs_trail, n0, nthreads):
    """**The escape atom's own recipe (`away_walk`'s module docstring, steps 2-4), per candidate,
    natively** -- the fan's counterpart of `away_walk.escape_atom`, which cannot be a `_families`
    member because its rotate and slam frames each need a DIFFERENT stick, derived from the
    candidate's OWN flip, not a stick held constant like every other family.

    ``flips`` is a list of WORLD BEARINGS (BAM), `away_walk.flip_arc`'s own output -- NOT a stick-byte
    alphabet (session 151's own correction: a byte alphabet mixes in whatever magnitude each draw
    happens to have, but `escape_atom` always drives the L-press at FULL deflection,
    ``stick_for_bearing(flip, cs, msd=1.0)`` -- module docstring step 2, "full stick toward Tetra". A
    partial-deflection draw is not the same input `escape_atom` was gated on, and comparing the two
    directly is what caught this: `tests/test_overnight_driver.py`'s bit-exactness gate). Candidate
    ``i``'s own flip bearing derives ``rot = flip +- rotate_off`` and ``slam = flip + 0x8000``
    (`escape_atom`'s own formulas), each re-driven through `stick_for_bearing` at full deflection too --
    STICK DECODING is frozen at ``cs0`` (the junction's own starting value) for all four frames, matching
    `escape_atom`'s ``_clone_for_atom`` convention (its own documented ``cs_bill`` cost, not a new one).

    **The frames' own INJECTED csangle is not frozen at ``cs0`` past the L-press (session 153).**
    `LandCamera` fires a real 1-frame followCamera blip on the L rising edge that resets the yaw target,
    so the release/rotate/slam frames read a CORRECTED trail (`cs_trail.from_l(n0)`) instead -- the
    stick-decoding reference stays ``cs0`` (that is what `escape_atom` itself derives its bearings
    against; freezing it is faithful, not a shortcut), but what actually reaches the physics as csangle
    is the real post-blip value, not a re-use of the pre-junction one.

    Steps: `_fan` for the L-press + release (its existing per-candidate-single-stick shape already
    fits those two, given full-deflection sticks precomputed from ``flips``, and now self-corrects for
    the blip -- see `_fan`'s own docstring), then `_step_batch` twice more -- rotate, then slam -- with a
    freshly-derived per-candidate stick each time, each reading its own corrected-trail frame. A
    candidate that leaves the follow bar during rotate/slam is dropped, same as `_fan`'s own
    ``alive_only``.

    ``turnaround_first`` is NOT a parameter here (yet): every real backslide measured so far (session
    151, off the locked console fixture) already faces away and fires without it, and a terminal that
    does not can still clear the cone through the EXISTING `fan_exact` PRE segment before reaching this
    junction. Widening this to sweep `away_walk`'s own ``turnaround_first`` is open, scoped work, not a
    silent gap: a herd whose backslide faces TOWARD Tetra and whose PRE sweep cannot clear the cone
    either is not yet reachable by this family.

    Returns a list of ``dict(i, core, flip, rot, slam)`` -- ``i`` indexes ``flips``, ``core`` is the
    post-slam state, ``flip``/``rot``/``slam`` the three stick byte pairs a caller needs to rebuild the
    plan tuple's own segments (``flip`` already the full-deflection L-press/release stick, not the
    bearing itself)."""
    cs0 = csangle if cs_trail is None else int(cs_trail[n0])
    sticks = [stick_for_bearing(int(f) & 0xFFFF, cs0, msd=1.0) for f in flips]
    junc = _fan(base, sticks, [1, 0], csangle, cs_trail, n0, nthreads)
    if not junc:
        return []
    trail = cs_trail if cs_trail is None else cs_trail.from_l(n0)
    rot_cs = cs0 if trail is None else int(trail[n0 + 2])
    slam_cs = cs0 if trail is None else int(trail[n0 + 3])
    off = int(rotate_off) if int(rotate_side) >= 0 else -int(rotate_off)
    cand = []
    for i, c in junc:
        flip = int(flips[i]) & 0xFFFF
        rot = stick_for_bearing((flip + off) & 0xFFFF, cs0, msd=1.0)
        slam = stick_for_bearing((flip + 0x8000) & 0xFFFF, cs0, msd=1.0)
        cand.append(dict(i=i, core=c, flip=sticks[i], rot=rot, slam=slam))
    rot_cores = _step_batch([r['core'] for r in cand], [r['rot'] for r in cand], 0, rot_cs, nthreads)
    for r, c in zip(cand, rot_cores):
        r['core'] = c
    slam_cores = _step_batch([r['core'] for r in cand], [r['slam'] for r in cand], 0, slam_cs, nthreads)
    for r, c in zip(cand, slam_cores):
        r['core'] = c
    return [r for r in cand
            if math.hypot(r['core'].pos_x - r['core']._tetra_x,
                         r['core'].pos_z - r['core']._tetra_z) <= ES.FOLLOW_BAR]


def _atom_candidates(base, walk, n0, csangle, cs_trail, s1_stride, alpha, flips, chunk,
                     nthreads, collect, out, st, *, junction_cap=None, deadline=None, beat=None):
    """**The escape-atom conversion, off ``n0`` base frames, then the ordinary family sweep for
    whatever walk is left** -- `_atom_junction` composed into `fan_exact` the same way the PRE segment
    already is: a junction, then `_families` again from each survivor.

    ``flips`` (bearings, `away_walk.flip_arc`'s output) plays the PRE alphabet's role: the junction's
    job, like the PRE's, is only to pick a DIRECTION to convert through, so it is deliberately a small,
    dedicated sweep -- the continuation after it is where the search still needs `alpha`'s resolution.

    The continuation's own `_fan` reads through the JUNCTION's corrected trail (``cs_trail.from_l(n0)``),
    never the plain one straight from the caller (session 153): the junction already pressed L once
    (release, rotate, slam all after it), so a continuation family choosing L_AXIS's l=1 branch presses
    it a SECOND time on a camera that has already been through one blip and settle -- composing onto
    that real history, not a fresh L-free one, is what a held-L continuation actually experiences."""
    remaining = walk - n0 - ATOM_FRAMES
    if remaining < 1:
        return
    junction_trail = cs_trail if cs_trail is None else cs_trail.from_l(n0)
    for ro in ATOM_ROTATE_OFFS:
        for side in ATOM_ROTATE_SIDES:
            if deadline is not None and time.time() >= deadline:
                st['deadline_cut'] = True
                return
            junc = _atom_junction(base, flips, side, ro, csangle, cs_trail, n0, nthreads)
            st['atom_junctions'] = st.get('atom_junctions', 0) + len(junc)
            st['atom_junctions_dead'] = (st.get('atom_junctions_dead', 0)
                                         + len(flips) - len(junc))
            for r in junc:
                if junction_cap is not None and st['junctions'] >= junction_cap:
                    st['junction_cap_hit'] = True
                    return
                if beat is not None and st['junctions'] % 64 == 0:
                    beat(junctions=st['junctions'], at_cap=len(out))
                st['junctions'] += 1
                for fam in _families(remaining, 0, s1_stride):
                    for c0 in range(0, len(alpha), chunk):
                        part = alpha[c0:c0 + chunk]
                        st['fleets'] += 1
                        cores = _fan(r['core'], part, fam['lsched'], csangle, junction_trail,
                                     n0 + ATOM_FRAMES, nthreads)
                        collect(cores, lambda i, _p=part, _fl=r['flip'], _rt=r['rot'], _sl=r['slam'],
                                _n0=n0, _f=fam:
                                (_n0, _fl[0], _fl[1], 1, 1, _fl[0], _fl[1], 0, 1,
                                 _rt[0], _rt[1], 0, 1, _sl[0], _sl[1], 0, 1)
                                + tuple(_f['label'](_p[i][0], _p[i][1]))[1:])


def _fan(base, sticks, lsched, csangle, cs_trail, cs_from, nthreads, *, alive_only=True):
    """Step one core per stick through ``lsched`` and return the endpoints at the LAST frame.

    ``lsched`` is the L bit per stepped frame, so the L RELEASE happens inside one fleet instead of
    needing a junction -- which is what makes the conversion family affordable: the cost of a fan here
    is its CORE CLONES, not its frames (measured s150: 2.6 M clones was 31 s where the stepping was
    ~5 M frames at ~1 M/s). One fleet, ``len(lsched)`` frames, one clone per stick.

    ``len(lsched)`` must be the plan's delivered frames PLUS ONE: at ``input_delay = 1`` the endpoint
    after j+1 steps is the one a plan of j delivered frames rolls from, and whatever is delivered on that
    last step has not acted (`entry_fan._fan_chunk`'s own note, gated in `tests/test_entry_search.py`).
    So the byte on the extra frame is inert and the A-press replaces it in the real log.

    Returns ``[(i, core)]`` for the cores still inside the follow bar -- past it she is turning and the
    plow model's measured constant is gone, so the branch is dead from that frame on.

    ``cs_trail``, when it presses L anywhere in ``lsched``, reads through the CORRECTED trail from
    that frame on (`entry_camera.CamTrail.from_l`) instead of the L-free one -- the followCamera blip
    a real L rising edge fires (session 153), which every L-pressing caller shares (`_atom_junction`'s
    L-conversion, `_families`' L_AXIS uniform hold) and none of them modelled before this."""
    from tww_sim.core.anim import _anmc as N
    cores = [base.clone(base.pe.clone_state()) for _ in sticks]
    fleet = N.CourtyardFleet(cores, 1)
    alive = [True] * len(cores)
    trail = cs_trail
    if cs_trail is not None:
        l_at = next((cs_from + j for j, l in enumerate(lsched) if l), None)
        if l_at is not None:
            trail = cs_trail.from_l(l_at)
    for j, l in enumerate(lsched):
        cs = csangle if trail is None else int(trail[cs_from + j])
        fleet.set_schedule([[(sx, sy, PAD_L if l else 0, TRIG_L if l else 0, cs)]
                            for (sx, sy) in sticks])
        fleet.run_par(1, nthreads)
        if not alive_only:
            continue
        for i, c in enumerate(cores):
            if alive[i] and math.hypot(c.pos_x - c._tetra_x,
                                       c.pos_z - c._tetra_z) > ES.FOLLOW_BAR:
                alive[i] = False
    return [(i, c) for i, c in enumerate(cores) if alive[i]]


#: The per-item CLONE budget and the flip-alphabet strides `fan_exact` walks to meet it. 8 M leaves is
#: ~400 s of one worker at the measured 74 k core-frames/s, which is what keeps a deep walk affordable.
LEAF_BUDGET = 8_000_000
ALPHA_STRIDES = (1, 2, 3, 4, 6, 8, 16)

#: `_steered_tail`'s prefix pool held one live `LandCore` clone per prefix, uncapped (session 150's
#: MemoryError). Bounds it like `tail_beam` bounds the between-frame beam: nearest her, kept.
PREFIX_CAP = 20000

#: The atom junction's own knob grid -- `escape_atom.probe`'s own small sweep; `turnaround_first` is
#: NOT yet swept, see `_atom_junction`'s docstring for why that is a scoped gap, not an oversight.
ATOM_ROTATE_OFFS = AW.ROTATE_OFFS
ATOM_ROTATE_SIDES = (1, -1)

#: The flip's own bearing sweep -- `away_walk.flip_arc`'s default step; the herd's down-bearing is
#: always a member (what fired cleanly off the real console backslide, session 151).
ATOM_FLIP_STEP = 0x400

#: Frames the recipe itself fixes: L-press, release (the negation), rotate, backwards slam
#: (`away_walk`'s module docstring, steps 2-4). Never a search variable.
ATOM_FRAMES = 4


def _fleet_estimate(walk, two_segment, pre_stride, pre_frames, pre_l, atom=True, n_flips=0):
    """Fleets `fan_exact` will build for this shape -- the clone budget's own arithmetic, so the
    alphabet can be sized BEFORE the first one is cloned."""
    n = sum(len(_families(walk, n0, 32)) for n0 in range(walk))
    if two_segment:
        pre = len(EF.stick_alphabet(pre_stride))
        pre_frames = pre_frames_for(walk, pre_frames)
        for n0 in range(walk):
            j = walk - n0
            for jp in [p for p in pre_frames if p < j]:
                n += len(pre_l) * (1 + pre * len(_families(walk - n0 - jp, 0, 32)))
    if atom:
        combos = len(ATOM_ROTATE_OFFS) * len(ATOM_ROTATE_SIDES)
        for n0 in range(walk):
            remaining = walk - n0 - ATOM_FRAMES
            if remaining >= 1:
                n += combos * n_flips * len(_families(remaining, 0, 32))
    return n


def alpha_for(fleets_est, budget, alpha_stride=None):
    """**THE HOLD ALPHABET'S STRIDE, and whether the budget was allowed to choose it.**

    Pulled out of `fan_exact` so the trade it makes is testable without cloning 4.6e8 cores. Two modes,
    and the difference is the whole containment question:

      * ``alpha_stride is None`` -- the AUTOSCALER: coarsen until the item fits ``budget``. Affordable,
        and it is what let a run report coverage it did not have, because the console's hold letter
        exists at stride 1 and nowhere else (`containment_knobs`).
      * ``alpha_stride`` given -- PINNED. Containment is a property of the alphabet and may not be
        traded for the budget, so an item that does not fit says ``over_budget`` instead of quietly
        dropping the letters that matter.

    Returns ``(stride, over_budget)``."""
    if alpha_stride is None:
        s = next((s for s in ALPHA_STRIDES if fleets_est * len(EF.stick_alphabet(s)) <= budget),
                 ALPHA_STRIDES[-1])
    else:
        s = int(alpha_stride)
    return s, bool(fleets_est * len(EF.stick_alphabet(s)) > budget)


def _families(walk, n0, s1_stride):
    """The L SCHEDULE a ``walk``-frame plan can carry, off ``n0`` base frames -- the search's own
    structure, and every one of them is one fleet.

    **uniform** -- one stick, L up or down for the whole walk. The ordinary walk-up. The other known
    way a herd's untarget backslide reaches the roll cap -- `away_walk.escape_atom`'s L-conversion,
    rotate, backwards-slam recipe -- is NOT a member of this family: it needs a DIFFERENT stick per
    frame (derived per candidate, not held), which is `_atom_junction` + `_atom_candidates`, run
    alongside this in `fan_exact` (session 151; supersedes the s150 ``lswitch`` shape, which held one
    stick through the release and never rotated or slammed -- see the module docstring's headline).

    ``label`` turns each into a plan tuple, so a hit's log is rebuildable from the plan alone."""
    j = walk - n0
    return [dict(kind='uniform', lsched=[l] * (j + 1),
                label=lambda sx, sy, _l=l, _j=j: (n0, sx, sy, _l, _j))
            for l in L_AXIS]


#: The PRE segment: the stick that turns Tetra out of the front cone before the L frame -- see `fan_exact`
#: for why a plan without one tops out at speedF 12.000, and why stride 32 buys the depth that matters.
#: The s155-s159 values, kept NAMED because the s160 diagnosis is a measurement about them: they exclude
#: the console's own plan -- knowledge/model/fan-containment-gap.md.
LEGACY_PRE_STRIDE = 32
LEGACY_PRE_FRAMES = (1,)
PRE_L = (0,)

#: ``pre_frames=PRE_FRAMES_ALL`` -> every ``jp`` a walk of this length admits (`pre_frames_for`). A tuple
#: cannot say that, because the set depends on the walk.
PRE_FRAMES_ALL = 'all'

#: The pre alphabet that contains the console's own first letter ``(208, 110)`` -- present at stride 1 and
#: 2 and in no coarser grid (`containment_knobs`, pinned in `tests/test_overnight_driver.py`).
CONTAINED_PRE_STRIDE = 2

#: The hold alphabet the console's own second letter ``(169, 192)`` needs. PINNED, because coarsening the
#: hold to pay for a finer pre breaks containment the other way (`alpha_for`).
CONTAINED_ALPHA_STRIDE = 1

#: **THE SHIPPED KNOBS ARE THE CONTAINING ONES** (s161): every reader of these -- `fan_exact`, `worker`,
#: `launch`, `containment_knobs`, `verify_console` -- runs at the set that holds the console's plan.
PRE_STRIDE = CONTAINED_PRE_STRIDE
PRE_FRAMES = PRE_FRAMES_ALL


def pre_frames_for(walk, pre_frames):
    """The pre-segment splits enumerated for a walk of ``walk`` frames.

    ``PRE_FRAMES_ALL`` -> ``1 .. walk - 1``, which is every split a two-segment plan of this length can
    have; a tuple is passed through and filtered by `fan_exact` per ``n0`` as before."""
    if pre_frames == PRE_FRAMES_ALL:
        return tuple(range(1, max(int(walk), 1)))
    return tuple(int(p) for p in pre_frames)


def fan_exact(seed, env, walk, csangle, cs_trail, hold, *, s1_stride=32, nthreads=0, chunk=EF.CHUNK,
              two_segment=True, atom=True, junction_cap=None, pre_stride=PRE_STRIDE,
              pre_frames=PRE_FRAMES, pre_l=PRE_L, deadline=None, beat=None, leaf_budget=None,
              tail_frames=(), tail_beam=400, prefix_cap=PREFIX_CAP, contained=True,
              alpha_stride=CONTAINED_ALPHA_STRIDE, target=None, target_tol=None, target_prune=False):
    """Every distinct ``(endpoint, lean, speedF, exec Co centre, Tetra)`` Link can stand on AT THE
    ROLL CAP after EXACTLY ``walk`` delivered frames, as ``(dict of key -> plan, stats)``. The key is
    ``(x, z, m351C, speedF, ccx, ccz, tx, tz)`` -- the exec centre joined it in s168 because the
    entry-frame CC recoil (`entry_recoil`) is a function of it, so two plans at one endpoint with
    different poses are different candidates.

    Frame-exact because the objective is frame-minimal: a unit is searched walk length by walk length,
    ascending, so its first hit is its best. Every base offset ``n0``, every L schedule (`_families`),
    the full DECODED stick alphabet (`entry_fan.stick_alphabet`: the byte grid collapsed onto what the
    physics reads -- 11405 draws instead of 65536 pairs, the same endpoints), and then the
    stick-SWITCHING family off coarse junctions, which is the one that has to be budgeted.

    The fan runs UNCAPPED and `at_cap` filters here, so the key carries speedF and the sub-cap count is
    REPORTED rather than silently pruned.

    THE ALPHABET IS SIZED TO A LEAF BUDGET, not fixed. A fan's cost is its core CLONES (measured s150:
    the stepping is a fraction of it), and the fleet count grows as ``|pre| x walk``, so a fixed
    full-resolution alphabet makes a 7-frame walk cost fifteen times a 3-frame one -- and the deep walks
    are the ones that can reach contact at all (it closes ~4 u a frame from -17 u at walk 3). So the FLIP
    alphabet is coarsened until the item fits `LEAF_BUDGET`, and the stride it settled on is logged with
    the item (``alpha_stride``, ``alphabet``). Never the PRE: its job is only to rotate him.

    **``contained=True`` IS THE KNOB SET THAT HOLDS THE ONE PLAN KNOWN TO WORK** (s161): every split
    (`PRE_FRAMES_ALL`), the stride-2 pre alphabet, and the hold PINNED at stride 1 so the autoscaler
    cannot pay for the finer pre by coarsening the hold -- which would break containment the other way,
    since the console's two letters need opposite ends of the alphabet (`containment_knobs`). It is
    measured at 40274 fleets against the default's 353 at walk 4, so it is not a default: it is what
    ``target`` makes affordable.

    **``target`` AIMS THE ENUMERATION** (s161, `aimed_fan`): an ``(x, z)`` walk endpoint -- or a
    sequence of them, since the razor's target is a strip and not a point -- that the plan has to reach.
    `entry_aim.aim` puts an entry on the strip and `entry_aim.walk_end_for` inverts it to the endpoint.

    It does TWO things, and only one of them is a prune:

      * ``target_prune=True`` drops junctions `aimed_fan.reachable` says cannot reach the target in the
        frames they have left, BEFORE their |alpha| fleets are cloned. Admissible, and measured at only
        **1.4x** on the console item -- the reach disc is nearly the whole reachable set, so this does
        not pay for containment's 114x and is off by default.
      * ORDERING, always, and it is lossless: `aimed_fan.rank` puts the junctions whose at-cap leaves
        land ON the target first. That is what a deadline reads, so ``covered`` becomes the part of the
        space that could have hit rather than an arbitrary prefix.

    ``target_tol`` widens the prune (default `aimed_fan.REACH_TOL`). Logged as ``target_pruned`` /
    ``target_kept``, never silent."""
    from harness.tetrapush.reposition import HerdLine
    from harness.tetrapush import aimed_fan as AF
    out = {}
    hl = HerdLine.from_env(env)
    flips = AW.flip_arc(hl, step=ATOM_FLIP_STEP) if atom else []
    if contained:
        pre_stride = CONTAINED_PRE_STRIDE if pre_stride == LEGACY_PRE_STRIDE else pre_stride
        pre_frames = PRE_FRAMES_ALL if pre_frames == LEGACY_PRE_FRAMES else pre_frames
    # ``alpha_stride='auto'`` is the OPT-OUT: it hands the hold alphabet back to the leaf budget, which
    # is affordable and not contained -- `verify_console(alpha_stride=...)` will say so.
    alpha_stride = None if alpha_stride == 'auto' else alpha_stride
    pre_frames = pre_frames_for(walk, pre_frames)
    fleets_est = _fleet_estimate(walk, two_segment, pre_stride, pre_frames, pre_l, atom=atom,
                                 n_flips=len(flips))
    budget = LEAF_BUDGET if leaf_budget is None else int(leaf_budget)
    a_stride, over = alpha_for(fleets_est, budget, alpha_stride)
    alpha = EF.stick_alphabet(a_stride)
    st = dict(raw=0, sub_cap=0, off_cap_only=0, junctions=0, junctions_dead=0, fleets=0,
              families=0, alphabet=len(alpha), alpha_stride=a_stride, fleets_est=fleets_est,
              leaves_est=fleets_est * len(alpha), atom_junctions=0, atom_junctions_dead=0,
              pre_stride=int(pre_stride), pre_frames=list(pre_frames), contained=bool(contained),
              alpha_pinned=alpha_stride is not None, over_budget=over)
    if target is not None:
        # a point or a whole curve -- the strip is not a point (`aimed_fan.aim_curve`)
        pts = [target] if AF._is_point(target) else list(target)
        st.update(target=[[float(p[0]), float(p[1])] for p in pts], target_pruned=0, target_kept=0)

    def collect(cores, label):
        for i, c in cores:
            st['raw'] += 1
            if not EF._is_rollable(c):
                continue
            if not at_cap(c.speedF):
                st['sub_cap'] += 1
                continue
            # the walk-end exec centre joins the key: `entry_recoil` is a function of it
            # (knowledge/mechanics/entry-frame-recoil.md; init_frame=False = the validated convention)
            cc = c.co_center_exec(init_frame=False)
            out[(c.pos_x, c.pos_z, int(c.m351C) & 0xFFFF, c.speedF,
                 cc[0], cc[1], c._tetra_x, c._tetra_z)] = label(i)

    for n0 in range(0, walk):
        base, _run = EF.base_core(n0, seed=seed, env=env, hold=hold)
        for fam in _families(walk, n0, s1_stride):
            st['families'] += 1
            for c0 in range(0, len(alpha), chunk):
                part = alpha[c0:c0 + chunk]
                st['fleets'] += 1
                cores = _fan(base, part, fam['lsched'], csangle, cs_trail, n0, nthreads)
                collect(cores, lambda i, _p=part, _f=fam: _f['label'](_p[i][0], _p[i][1]))
        if atom:
            # the escape-atom conversion (L-conversion, rotate, backwards slam), then the ordinary
            # family sweep for whatever walk is left -- see `_atom_candidates`.
            _atom_candidates(base, walk, n0, csangle, cs_trail, s1_stride, alpha, flips, chunk,
                             nthreads, collect, out, st, junction_cap=junction_cap, deadline=deadline,
                             beat=beat)
            if st.get('deadline_cut'):
                return out, st
        if not two_segment:
            continue
        # the PRE segment, then the whole family set again off each junction. One fleet per junction, so
        # this is where the clone budget goes -- hence `junction_cap`, logged and never silent.
        pre = EF.stick_alphabet(pre_stride)
        j = walk - n0
        for jp in [p for p in pre_frames if p < j]:
            for lp in pre_l:
                jcs = _fan(base, pre, [lp] * jp, csangle, cs_trail, n0, nthreads)
                st['junctions_dead'] += len(pre) - len(jcs)
                if target is not None:
                    # STEPPED frames, not delivered -- the hold below runs `_families`' j+1 schedule.
                    r = walk - n0 - jp + 1
                    if target_prune:
                        # the subtree prune: |alpha| clones per junction, so this is where it pays
                        keep_jcs = [(i1, jc) for i1, jc in jcs
                                    if AF.reachable(jc, target, r, tol=target_tol)]
                        st['target_pruned'] += len(jcs) - len(keep_jcs)
                        jcs = keep_jcs
                    # and then ORDER what is left, which is lossless and is what a deadline reads
                    jcs = AF.rank(jcs, target, r)
                    st['target_kept'] += len(jcs)
                for i1, jc in jcs:
                    if junction_cap is not None and st['junctions'] >= junction_cap:
                        st['junction_cap_hit'] = True
                        break
                    if beat is not None and st['junctions'] % 64 == 0:
                        beat(junctions=st['junctions'], at_cap=len(out), alpha=len(alpha))
                    if deadline is not None and time.time() >= deadline:
                        # a deep walk's fan is minutes long, so the clock is checked at the junction
                        # rather than only before the item: an overnight run must stop ON its deadline
                        st['deadline_cut'] = True
                        st['covered'] = st['junctions']
                        return out, st
                    st['junctions'] += 1
                    for fam in _families(walk - n0 - jp, 0, s1_stride):
                        for c0 in range(0, len(alpha), chunk):
                            part = alpha[c0:c0 + chunk]
                            st['fleets'] += 1
                            cores = _fan(jc, part, fam['lsched'], csangle, cs_trail,
                                         n0 + jp, nthreads)
                            collect(cores, lambda i, _p=part, _s=pre[i1], _jp=jp, _lp=lp,
                                    _n0=n0, _f=fam:
                                    (_n0, _s[0], _s[1], _lp, _jp)
                                    + tuple(_f['label'](_p[i][0], _p[i][1]))[1:])
    if tail_frames:
        _steered_tail(out, st, seed, env, walk, csangle, cs_trail, hold, alpha, chunk, nthreads,
                      s1_stride, pre_stride, pre_frames, pre_l, tail_frames, tail_beam, deadline,
                      beat=beat, prefix_cap=prefix_cap, flips=flips)
    return out, st


def _trail_for(cs_trail, plan):
    """The trail a PREFIX's own continuation reads through: the L rising edges the prefix has already
    delivered, composed onto the item's trail (`entry_camera.CamTrail.from_l`).

    Read off the plan tuple itself (`l_press_frames`), so it cannot disagree with the schedule that built
    it. `_fan` already corrects for edges inside its OWN schedule; nothing corrected for an edge a
    PREVIOUS segment delivered, which is every steered frame after an atom junction and every one after a
    `_families` L_AXIS hold."""
    if cs_trail is None:
        return None
    t = cs_trail
    for f in l_press_frames(plan):
        t = t.from_l(f)
    return t


def _steered_tail(out, st, seed, env, walk, csangle, cs_trail, hold, alpha, chunk, nthreads,
                  s1_stride, pre_stride, pre_frames, pre_l, tail_frames, tail_beam, deadline,
                  beat=None, prefix_cap=PREFIX_CAP, flips=()):
    """**PER-FRAME STEERING AFTER THE CONVERSION** -- the one coverage gap the family set leaves, and the
    draw multiplier where contact is already made.

    Every family holds ONE stick from the L frame on, because that is the recipe that reaches the cap.
    So a plan cannot convert and THEN steer, which is exactly what s149's stage-B beam did to close the
    contact deficit -- and where contact is already deep (rung 3 at walk 4: overlap +60.7 u, the razor
    bracketed) the binding constraint is no longer distance but DRAWS: 112 in-contact scorings expressing
    one best |resid| of 1.55e-01 against a ~1e-4 acceptance.

    **``flips`` steers off the ATOM JUNCTION too (session 155), which is what the headline above always
    claimed and the code did not do.** The prefixes were built from `_families`/PRE only, so "steering
    after the conversion" could only steer after a UNIFORM walk -- and the conversion that reaches the cap
    off a real backslide is `_atom_junction`'s (L-press, release, rotate, backwards slam). The console's
    own 11 frames are that atom EXACTLY, followed by a THREE-segment continuation ((241,59) x3, (208,110)
    x2, (169,192) x2), where `_families` offers ONE held stick: so its own input was not a member of the
    enumerated set at ``walk=11`` at any camera (session 154's second, independent containment gap). An
    atom junction, a uniform continuation, then ``tail_frames=(4,)`` is the shape that contains it, and it
    is this branch. ``remaining == 0`` (steer straight off the slam) is admitted too -- one prefix per
    junction rather than per alphabet draw, so it is nearly free.

    Each prefix carries the TRAIL its own steered frames read through (`_trail_for`, off the prefix plan's
    own L edges), because a prefix that pressed L has already fired the followCamera blip and the frames
    after it read the FROZEN chase, never the L-free reference. That is true of every atom prefix by
    construction and of every `_families` L_AXIS hold, and neither corrected for it before this: `_fan`
    only ever corrected the edges inside its own schedule (session 153's fix, session 154's aim half --
    the same bug in two places, and a trail derived from the plan is the shape that cannot repeat it).

    ``pfx`` is a pool of LIVE CLONES, not numbers, so "affordable in fleets" and "affordable in memory"
    are two different budgets and only the first one is `LEAF_BUDGET`. Fan the ordinary families at
    ``walk - k``, keep the at-cap prefixes UNDER `PREFIX_CAP`, and re-fan the last ``k`` frames over the
    full alphabet from each; k=2 beams between the two frames on distance to her, the contact gradient's
    own driver.

    **SIZE `prefix_cap` AND ``alpha`` DELIBERATELY: the atom branch changed the cost class.** Off a
    backslide the ordinary families reach the cap almost never, so the pool used to be nearly empty and
    the default cap never bound; every atom junction converts, so the pool is now
    ``flips x 8 knob combos x families x |alpha|`` before the cap, and the first steered depth costs
    ``|pfx| x |alpha|`` clones (at the default 20000 x 11405 that is 228 M -- minutes, not seconds). The
    cap is the knob, ``prefix_cap_hit`` says when it bound, and the beam bounds every depth after the
    first.

    ``at_cap`` is read on the PREFIX core here, one delivered byte before the endpoint: the conversion
    holds speedF at ~17.6 once it has fired, so it is a filter on the same population and not a
    different test. The pool is ranked on the prefix's OWN tracked Tetra, never the seed's -- she moves
    36.7 u across the console's own conversion, so a prefix that plowed her is nearer than the seed point
    says (`score`'s ``with_tetra`` rule, which this ranking silently broke). Logged as ``tail_prefixes``
    (what survived the cap and got steered), ``tail_atom_prefixes`` (what the atom branch GENERATED, so
    the two together say how hard the cap bit), ``tail_leaves`` and ``prefix_cap_hit``."""
    st['tail_prefixes'] = st.get('tail_prefixes', 0)
    st['tail_atom_prefixes'] = st.get('tail_atom_prefixes', 0)
    st['tail_leaves'] = st.get('tail_leaves', 0)
    st['prefix_cap_hit'] = st.get('prefix_cap_hit', False)

    def feet(c):
        return math.hypot(c.pos_x - c._tetra_x, c.pos_z - c._tetra_z)

    def keep(pfx):
        """Rank-and-truncate NOW, before the pool grows further -- a prefix far from contact cannot
        become the razor's winner after k more frames."""
        if len(pfx) > prefix_cap:
            pfx.sort(key=lambda t: t[2])
            del pfx[prefix_cap:]
            st['prefix_cap_hit'] = True

    for k in sorted(x for x in tail_frames if 1 <= x < walk):
        w0 = walk - k
        pfx = []
        for n0 in range(0, w0):
            base, _run = EF.base_core(n0, seed=seed, env=env, hold=hold)
            shapes = [(None, 0, 0, base)]
            for jp in [p for p in pre_frames if p < w0 - n0]:
                for lp in pre_l:
                    for i1, jc in _fan(base, EF.stick_alphabet(pre_stride), [lp] * jp,
                                       csangle, cs_trail, n0, nthreads):
                        shapes.append((EF.stick_alphabet(pre_stride)[i1], lp, jp, jc))
            for (ps, lp, jp, node) in shapes:
                for fam in _families(w0 - n0 - jp, 0, s1_stride):
                    for c0 in range(0, len(alpha), chunk):
                        part = alpha[c0:c0 + chunk]
                        # ONE frame short of the family's own schedule: these are PREFIXES, and the
                        # endpoint is what the steered frames will produce
                        for i, c in _fan(node, part, fam['lsched'][:-1], csangle, cs_trail,
                                         n0 + jp, nthreads):
                            if not at_cap(c.speedF):
                                continue
                            head = ((n0,) if ps is None else (n0, ps[0], ps[1], lp, jp))
                            pfx.append((head + tuple(fam['label'](part[i][0], part[i][1]))[1:],
                                        c, feet(c)))
                    keep(pfx)
                    if beat is not None:
                        beat(tail_k=k, tail_n0=n0, tail_pfx=len(pfx))
                if deadline is not None and time.time() >= deadline:
                    st['deadline_cut'] = True
                    return
            # THE ATOM JUNCTION AS A PREFIX -- see the docstring: the conversion a real backslide
            # actually reaches the cap through, steered afterwards instead of held
            remaining = w0 - n0 - ATOM_FRAMES
            if not flips or remaining < 0:
                continue
            jtrail = cs_trail if cs_trail is None else cs_trail.from_l(n0)
            for ro in ATOM_ROTATE_OFFS:
                for side in ATOM_ROTATE_SIDES:
                    junc = _atom_junction(base, flips, side, ro, csangle, cs_trail, n0, nthreads)
                    st['atom_junctions'] = st.get('atom_junctions', 0) + len(junc)
                    st['atom_junctions_dead'] = (st.get('atom_junctions_dead', 0)
                                                 + len(flips) - len(junc))
                    for r in junc:
                        head = (n0, r['flip'][0], r['flip'][1], 1, 1, r['flip'][0], r['flip'][1], 0, 1,
                                r['rot'][0], r['rot'][1], 0, 1, r['slam'][0], r['slam'][1], 0, 1)
                        if not remaining:
                            if at_cap(r['core'].speedF):
                                pfx.append((head, r['core'], feet(r['core'])))
                                st['tail_atom_prefixes'] += 1
                            continue
                        for fam in _families(remaining, 0, s1_stride):
                            for c0 in range(0, len(alpha), chunk):
                                part = alpha[c0:c0 + chunk]
                                st['fleets'] += 1
                                for i, c in _fan(r['core'], part, fam['lsched'][:-1], csangle,
                                                 jtrail, n0 + ATOM_FRAMES, nthreads):
                                    if not at_cap(c.speedF):
                                        continue
                                    pfx.append((head + tuple(fam['label'](part[i][0],
                                                                          part[i][1]))[1:],
                                                c, feet(c)))
                                    st['tail_atom_prefixes'] += 1
                            keep(pfx)
                    if beat is not None:
                        beat(tail_k=k, tail_n0=n0, tail_pfx=len(pfx),
                             tail_atom=st['tail_atom_prefixes'])
                    if deadline is not None and time.time() >= deadline:
                        st['deadline_cut'] = True
                        return
        pfx.sort(key=lambda t: t[2])
        pfx = [(p, c, _trail_for(cs_trail, p)) for p, c, _d in pfx[:prefix_cap]]
        st['tail_prefixes'] += len(pfx)
        for depth in range(k):
            nxt = []
            last = depth == k - 1
            for pi, (plan, c, tr) in enumerate(pfx):
                for c0 in range(0, len(alpha), chunk):
                    part = alpha[c0:c0 + chunk]
                    st['fleets'] += 1
                    st['tail_leaves'] += len(part)
                    sched = [0, 0] if last else [0]
                    for i, cc in _fan(c, part, sched, csangle, tr,
                                      plan_frames(plan) + depth, nthreads):
                        p2 = tuple(plan) + (part[i][0], part[i][1], 0, 1)
                        if last:
                            st['raw'] += 1
                            if EF._is_rollable(cc) and at_cap(cc.speedF):
                                cen = cc.co_center_exec(init_frame=False)
                                out[(cc.pos_x, cc.pos_z, int(cc.m351C) & 0xFFFF, cc.speedF,
                                     cen[0], cen[1], cc._tetra_x, cc._tetra_z)] = p2
                            else:
                                st['sub_cap'] += 1
                        elif at_cap(cc.speedF):
                            nxt.append((p2, cc, feet(cc), tr))
                if beat is not None and pi % 32 == 0:
                    beat(tail_k=k, tail_depth=depth, tail_prefix=pi, tail_of=len(pfx))
                if deadline is not None and time.time() >= deadline:
                    st['deadline_cut'] = True
                    return
            if not last:
                nxt.sort(key=lambda t: t[2])
                st['tail_beam_kept'] = min(len(nxt), int(tail_beam))
                st['tail_beam_seen'] = len(nxt)
                pfx = [(p, c, tr) for p, c, _d, tr in nxt[:int(tail_beam)]]


# --------------------------------------------------------------------------- the razor

#: `terminal.CO_R_SUM`, imported lazily: overlap is ``CO_R_SUM - |co_centre - tetra|`` on the cut frame,
#: and it is the CONTACT gradient the razor's own residual does not carry -- see `score`.
CO_R_SUM = None

#: Where a clip can be: the console's own is at overlap +1.2259, a GRAZING touch, and 96% of a blind
#: fan's scorings cannot clip at all -- knowledge/strategy/clip-overlap-band.md has the distribution.
CLIP_TARGET = 1.2259
CLIP_BAND = (0.0, 3.0)

#: A hypot off the baked schedule CANNOT gate it -- 39.7 u out on the known clip, because she is plowed
#: 47 u during the roll (measured before shipping one; same page). The sweep is the only verdict.
BAND_IS_NOT_PREFILTERABLE = True


def score(cands, quals, *, pool=None, batch=200000, near_probe=1e-3, near_cap=256, cam=None):
    """Score a candidate dict against every configuration, at each candidate's OWN Tetra.

    Grouped by ``(facing, thrust, lean, nspeed)`` -- the four things that pick the baked roll schedule
    -- and swept in one `ShoveCtx.sweep_par` call per group, because `CtxPool` re-schedules ONE ctx in
    place and a caller must finish one configuration before asking for the next (its own contract, and
    an interleaved caller silently gets another configuration's answer).

    Returns ``(hits, stats)``. ``hits`` are the GENUINE ones -- ground truth off the sweep, never a band
    -- with everything `confirm_entry` and `cross_engine.agree` need to re-derive them. The stats carry
    the CONTACT population and the residual SIGN SPLIT, because those are what say where a barren item
    stood: outside contact the razor's residual is a dead constant, so "0 genuine, 0 near" alone cannot
    distinguish an item that was 20 u from touching her from one that bracketed the razor and missed.

    ``best_overlap`` / ``best_resid_in_contact`` are scalars for a quick read, but every value this
    function ever singles out -- the best-overlap row, the best-in-contact-residual row, and every
    ``near`` row (capped at ``near_cap``, ``near_capped`` says if any were dropped) -- is recorded in
    FULL, the same shape as a genuine ``hit``, in ``best_overlap_row`` / ``best_resid_row`` / ``near_rows``
    (Dereck, s152: a near-miss the search finds and then throws away, keeping only the scalar, is exactly
    what forces an expensive re-run just to look at it -- this is the fix, not another recompute).

    ``cam`` (session 154) is a callable ``plan -> csangle``: the camera THAT PLAN'S OWN A-press frame
    decodes against (`aim_camera`). Without it every candidate is priced against ``quals``, one camera
    for the whole item -- which is wrong for every plan that presses L, because the followCamera blip
    moves the aim frame's csangle by up to 81 BAM (five sine cells, measured off the console's own
    conversion) and the aim BYTE recorded beside a facing then reaches a different facing, so
    `confirm_entry` refuses the hit. That is what refused the walk=11 rediscovery hit and what put
    s152's facing deltas in three discrete buckets.

    The fix costs nothing, because A CELL IS ONE RAZOR DRAW AT ANY CAMERA: every term a facing reaches
    goes through ``jmaTable[angle >> 4]``, so two facings in one cell bake a bit-identical schedule and a
    bit-identical 26 u entry step (`entry_search.aim_cell`, gated 0-ULP by
    `test_the_aim_alphabet_resolves_to_the_sine_table_cell`). So the sweep runs per CELL over exactly
    today's lean groups and batches -- one ctx per (cell, lean, thrust), the cell's own representative
    facing -- and only the (facing, aim) pair RECORDED is resolved per candidate, at its own camera. What
    the camera changes is the BYTE, not the draw. Cells the union of cameras reaches but this item's own
    does not are swept too; a cell no candidate can aim at ITS camera is skipped for that candidate and
    counted in ``unaimable``, never silently scored."""
    global CO_R_SUM
    if CO_R_SUM is None:
        from harness.tetrapush import terminal as TM
        CO_R_SUM = TM.CO_R_SUM
    pool = ES.CtxPool() if pool is None else pool
    items = list(cands.items())
    hits, n_eval, n_near = [], 0, 0
    n_band, n_unaimable, n_priced = 0, 0, 0
    n_contact, n_neg, n_pos = 0, 0, 0
    best_ovl, best_resid = -1e30, None      # 'best' = NEAREST `CLIP_TARGET`, never the max
    best_ovl_row, best_resid_row = None, None
    near_rows, near_capped = [], False
    by_roll, cams = {}, {}
    for k, plan in items:
        cs = None if cam is None else int(cam(plan)) & 0xFFFF
        if cs is not None and cs not in cams:
            cams[cs] = aim_cell_map(cs)
        # the entry-frame CC push pair ONCE per candidate: aim-independent (`entry_recoil`)
        by_roll.setdefault(ES.lean_at_roll(k[2]), []).append((k, plan, cs, entry_recoil(k)))

    # the DRAWS, cell-major then thrust as `configurations` orders them (see the docstring)
    thrusts = sorted({int(q['thrust']) for q in quals})
    if cam is None:
        draws = [(q['cell'], q['facing'], q['aim'], q['thrust']) for q in quals]
    else:
        reps = {}
        for cs in sorted(cams):
            for cell, (f, b) in cams[cs].items():
                reps.setdefault(cell, (f, b))
        draws = [(cell, reps[cell][0], reps[cell][1], t) for cell in sorted(reps) for t in thrusts]

    def _why(o):
        """**WHY a row is not genuine, in the acceptance's own three terms** (session 155).

        `_shovec`'s acceptance is ``(not blocked) and in_front(old) and crossed(new)``, and it reports
        only the AND -- so ``genuine = 0`` beside a ``|resid|`` of 2e-5 (measured this session at walk 9)
        reads as a mystery. It is not: every near-razor row across walks 7-9 turned out to be refused at
        the FIRST test, the swept lunge path hitting the wall, while the one row that ever delivered
        (s154's accepted 101) has it clear. ``resid`` cannot see that -- it is the cut RAY's offset from
        the seam vertex, and a ray can aim through a wall.

        Computed off the row's own old/new via the Python reference `geometry_tetra` (the native block
        test is `crr_pos_walls` transcribed), only for the rows this function SINGLES OUT (every genuine
        hit, the two bests, the capped near set), so it never touches the hot path."""
        from harness.rollstab import geometry_tetra as GT
        po, pn = GT.p32(o[1], o[2]), GT.p32(o[3], o[4])
        _p, info = GT.crr_pos_walls(po, pn, GT.TRIS)
        return dict(blocked=bool(info['line_hit'] or info['wall_hit']),
                    line_hit=bool(info['line_hit']), wall_hit=bool(info['wall_hit']),
                    in_front=bool(GT.in_front(po)),
                    crossed=bool(o[8] < 0.0 or o[9] < 0.0))

    def _row(k, plan, e, o, fac, thrust, lean, aim, cell, resid_val, ovl, cs, rec):
        # ``pred``/``why`` as before; ``entry``/``tetra`` are the recoil-corrected values the razor
        # scored, ``tetra_walk`` the fan's walk-end point, ``recoil`` Link's half (None = no contact)
        tc = tetra_corrected(k, rec)
        return dict(entry=[e[0], e[1]], walk=[k[0], k[1]], m351C_walk=k[2],
                   m351C=lean, facing=fac, aim=list(aim), thrust=thrust,
                   b_step=thrust + 2, resid=resid_val, nspeed=ES.ROLL_NSPEED,
                   push=[o[5], o[6]], plan=list(plan), cell=cell, csangle=cs,
                   tetra=[tc[0], tc[1]], tetra_walk=[k[-2], k[-1]], co_center=[k[4], k[5]],
                   recoil=(None if rec is None else [rec[0][0], rec[0][1]]),
                   overlap=ovl, pred=[o[8], o[9]], why=_why(o),
                   walkable=bool(XE.TA.is_walkable(k[0], k[1]) and XE.TA.is_walkable(e[0], e[1])))

    for cell, fac_rep, aim_rep, thrust in draws:
        for lean, group in by_roll.items():
            ctx, sch, resid = pool.get(fac_rep, lean, thrust, nspeed=ES.ROLL_NSPEED)
            for c0 in range(0, len(group), batch):
                part = group[c0:c0 + batch]
                # the razor sweeps the RECOIL-CORRECTED entry and tetra (out of contact rec is
                # None and both reduce byte-identically -- knowledge/mechanics/entry-frame-recoil.md)
                ents = [entry_corrected((k[0], k[1]), fac_rep, rec)
                        for k, _p, _c, rec in part]
                rows = ctx.sweep_par([tetra_corrected(k, rec) + (e[0], e[1])
                                      for (k, _p, _c, rec), e in zip(part, ents)], 0, extra=True)
                n_eval += len(rows)
                for (k, plan, cs, rec), e, o in zip(part, ents, rows):
                    fac, aim = (fac_rep, aim_rep) if cs is None else cams[cs].get(cell, (None, None))
                    if fac is None:
                        n_unaimable += 1          # this cell is not aimable at THIS plan's camera
                        continue
                    n_priced += 1
                    ovl = CO_R_SUM - math.hypot(o[10] - o[12], o[11] - o[13])
                    r = resid(o)
                    if CLIP_BAND[0] <= ovl <= CLIP_BAND[1]:
                        n_band += 1              # the only scorings that could have been a clip
                    if abs(ovl - CLIP_TARGET) < abs(best_ovl - CLIP_TARGET):
                        best_ovl = ovl
                        best_ovl_row = _row(k, plan, e, o, fac, thrust, lean, aim, cell, r, ovl, cs, rec)
                    if ovl >= 0.0:
                        n_contact += 1
                        n_neg += r < 0.0
                        n_pos += r > 0.0
                        if best_resid is None or abs(r) < abs(best_resid):
                            best_resid = r
                            best_resid_row = _row(k, plan, e, o, fac, thrust, lean, aim, cell,
                                                  r, ovl, cs, rec)
                    if not o[0]:
                        if abs(r) < near_probe:
                            n_near += 1
                            if len(near_rows) < near_cap:
                                near_rows.append(_row(k, plan, e, o, fac, thrust, lean, aim,
                                                      cell, r, ovl, cs, rec))
                            else:
                                near_capped = True
                        continue
                    hits.append(_row(k, plan, e, o, fac, thrust, lean, aim, cell, r, ovl, cs, rec))
    return hits, dict(candidates=len(items), evaluations=n_priced, swept=n_eval, genuine=len(hits),
                      near=n_near, configurations=len(draws), n_contact=n_contact, resid_neg=n_neg,
                      resid_pos=n_pos, bracketed=bool(n_neg and n_pos),
                      cameras=len(cams), cells=len(draws) // max(1, len(thrusts)),
                      unaimable=n_unaimable,
                      best_overlap=(None if best_ovl <= -1e29 else best_ovl),
                      best_overlap_row=best_ovl_row,
                      best_resid_in_contact=best_resid, best_resid_row=best_resid_row,
                      band=list(CLIP_BAND), band_draws=n_band,
                      band_share=(n_band / n_priced if n_priced else 0.0),
                      near_rows=near_rows, near_capped=near_capped)


# --------------------------------------------------------------------------- acceptance

def accept(hit, seed, unit, env, walk, walls=None):
    """**THE ACCEPTANCE TEST.** A genuine sweep row is a PREDICTION; this is what makes it a plan.

    Three stages, cheapest first, each one able to refuse:

      1. `entry_search.confirm_entry` -- replay the herd, the walk plan and a REAL A-press on the wired
         courtyard engine and read the roll entry back. The fan never presses A; it predicts the entry
         from the walk endpoint, and about one aim in eight brakes on the entry frame instead.
      2. `cross_engine.agree` -- the WALLED composite, frame for frame against the razor's own trace
         through the cut, at this candidate's own Tetra. ``deliverable`` is the razor genuine AND the
         handover AND a bit-identical cut AND 0 ULP between the engines.
      3. `objective.score_plan` / `verdict` -- the objective's own four rules, with the plan's TOTAL.

    Returns the full record either way; ``ok`` is stage 2's ``deliverable``. Nothing counts without it."""
    out = dict(unit=unit['unit'], herd=unit['herd'], walk=walk, thrust=hit['thrust'],
               total=total_frames(unit['herd'], walk, hit['thrust']), hit=hit)
    hold = hold_row(seed)
    rows_in = plan_rows(hold, hit['plan'])
    log, ix = composite_log(seed, hit['plan'], hit['aim'], hit['thrust'])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        conf = ES.confirm_entry(hit, seed=seed, env=env, rows=rows_in)
        out['confirm'] = dict(ok=conf['ok'], all_ok=bool(conf['all_ok']),
                              measured=dict((k, v) for k, v in conf['measured'].items()
                                            if k != 'procs'))
        if not conf['all_ok']:
            out.update(ok=False, stage='confirm')
            return out
        ag = XE.agree(hit, seed=seed, env=env, tetra=tuple(hit['tetra']), log=log, ix=ix)
        out['agree'] = ag
        out['blocked'] = bool(XE.blocked(ag))
        if not ag['deliverable']:
            out.update(ok=False, stage='cross_engine')
            return out
        out['log'] = log
        out['index'] = ix
        out['cut_i'] = ag['cut_i']
        # the plan's own frame count, read off the delivery log rather than asserted
        out['total_log'] = int(ag['cut_i'])
        rows = _score_rows(env, log[:ix['a_i'] + 1])
        sc = O.score_plan(env, rows, walls=walls, total=out['total'])
        out['score'] = dict((k, v) for k, v in sc.items() if k not in ('terminal',))
        out['verdict'] = bool(O.verdict(sc))
        out.update(ok=True, stage='deliverable')
    return out


def _score_rows(env, log):
    """The per-frame rows `objective.score_plan` reads, from a raw log: the wired reference run."""
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for d in log:
            rows.append(run.step(d))
    return rows


# --------------------------------------------------------------------------- the unit loop

#: One prepared herd per (process, unit): the two replays, the seed and the camera trail. A herd owns up
#: to 14 independently-claimed items, so without this a worker re-replays it for every one of them.
_PREPARED = {}


def prepared(unit, env, walls, top, *, cache=_PREPARED):
    """`prepare` plus the camera trail, memoised per unit inside one process."""
    key = (unit['unit'], unit['herd'])
    got = cache.get(key)
    if got is not None and got[0]['ok'] and len(got[2]) >= top + TRAIL_PAD:
        return got
    prep = prepare(unit, env, walls)
    if not prep['ok']:
        cache[key] = (prep, None, ())
        return cache[key]
    hold = hold_row(prep['seed'])
    trail = EC.CamTrail(int(hold.get('substickX', 128)), top + TRAIL_PAD, prep['seed'], env)
    cache[key] = (prep, hold, trail)
    return cache[key]


def run_item(item, d, env, *, worker='w0', deadline=None, s1_stride=32, nthreads=0,
             dflt_incumbent=None, on_event=None, two_segment=True, atom=True, pre_stride=PRE_STRIDE,
             leaf_budget=None, tail_frames=(), tail_beam=400, prefix_cap=PREFIX_CAP):
    """One ``(herd, walk length)`` item: prepare the herd, fan every plan of exactly that length, score
    it against every aimable configuration, and push what is genuine through the acceptance stack.

    Everything it produces is written before it returns, so killing a worker loses at most one item."""
    t0 = time.time()
    inc0 = O.TOTAL_INCUMBENT if dflt_incumbent is None else int(dflt_incumbent)
    ev = on_event or (lambda **kw: None)
    walls = O.courtyard_walls()
    walk = item['walk']
    prep, hold, trail = prepared(item, env, walls, walk)
    if not prep['ok']:
        rec = dict(item=item['item'], unit=item['unit'], herd=item['herd'], walk=walk,
                   floor=item['floor'], worker=worker, seconds=time.time() - t0, dropped=True,
                   reason=prep['reason'])
        ev(event='herd_refused', item=item['item'], reason=prep['reason'],
           first_divergence=prep['first_divergence'], n_refused=prep['n_refused'])
        IO.append(os.path.join(d, 'manifest.jsonl'), rec)
        return rec
    seed = prep['seed']
    inc, _rec = IO.incumbent(d, inc0)
    thrusts = [t for t in item['thrusts'] if max_walk(item['herd'], t, inc) >= walk]
    if not thrusts:
        rec = dict(item=item['item'], unit=item['unit'], herd=item['herd'], walk=walk,
                   floor=item['floor'], worker=worker, seconds=time.time() - t0, dropped=True,
                   reason='branch-and-bound: no thrust at walk %d beats incumbent %d' % (walk, inc))
        IO.append(os.path.join(d, 'manifest.jsonl'), rec)
        return rec
    IO.beat(d, item['item'], worker, walk=walk, incumbent=inc, herd=item['herd'],
            unit_of=item['unit'])
    # the camera an L-FREE plan's aim frame decodes against; a plan that presses L reads its own
    # (`score(cam=...)` below), and this stays the item's reported reference
    csa = EC.aim_camera(trail, walk)
    quals = configurations(csa, thrusts)
    tf = time.time()
    cands, fst = fan_exact(seed, env, walk, csa, trail, hold, s1_stride=s1_stride,
                           nthreads=nthreads, two_segment=two_segment, atom=atom,
                           pre_stride=pre_stride, deadline=deadline, leaf_budget=leaf_budget,
                           tail_frames=tail_frames, tail_beam=tail_beam, prefix_cap=prefix_cap,
                           beat=lambda **kw: IO.beat(d, item['item'], worker, walk=walk,
                                                     incumbent=inc, herd=item['herd'],
                                                     unit_of=item['unit'], **kw))
    t_fan = time.time() - tf
    ts = time.time()
    hits, st = score(cands, quals, cam=lambda p: aim_camera(p, walk, trail))
    t_score = time.time() - ts
    row = dict(item=item['item'], unit=item['unit'], herd=item['herd'], walk=walk, worker=worker,
               thrusts=thrusts, incumbent=inc, csangle=csa, fan_seconds=t_fan,
               score_seconds=t_score, floor=item['floor'],
               totals={t: total_frames(item['herd'], walk, t) for t in thrusts},
               two_segment=bool(two_segment), atom=bool(atom), s1_stride=s1_stride,
               pre_stride=pre_stride, atom_rotate_offs=list(ATOM_ROTATE_OFFS),
               leaf_budget=leaf_budget, prefix_cap=prefix_cap, fan=fst, **st)
    ev(event='scored', item=item['item'], candidates=st['candidates'], genuine=st['genuine'],
       near=st['near'], fan_seconds=round(t_fan, 1), score_seconds=round(t_score, 1),
       at_cap=len(cands), raw=fst['raw'], n_contact=st['n_contact'],
       band_draws=st['band_draws'], band_share=round(st['band_share'], 8),
       best_overlap=st['best_overlap'], bracketed=st['bracketed'],
       best_resid_in_contact=st['best_resid_in_contact'])
    n_ok, plans = 0, []
    ranked = sorted([h for h in hits if h['walkable']],
                    key=lambda h: (h['thrust'], abs(h['resid'])))
    for hit in ranked[:MAX_ACCEPT]:
        ev(event='genuine', item=item['item'], thrust=hit['thrust'],
           total=total_frames(item['herd'], walk, hit['thrust']), resid=hit['resid'],
           cell=hit['cell'], plan=list(hit['plan']))
        try:
            res = accept(hit, seed, item, env, walk, walls=walls)
        except Exception as exc:                        # an unported branch must not end the run
            ev(event='exception', item=item['item'], cls=type(exc).__name__,
               msg=str(exc)[:400], where='accept')
            row['exceptions'] = row.get('exceptions', 0) + 1
            continue
        if not res['ok']:
            ev(event='refused', item=item['item'], stage=res['stage'], thrust=hit['thrust'],
               blocked=res.get('blocked'))
            continue
        n_ok += 1
        res.update(unit=item['unit'], item=item['item'], worker=worker, t=time.time())
        name = IO.save_plan(d, res)
        took = IO.offer(d, dict(total=res['total'], unit=item['unit'], item=item['item'],
                                walk=walk, thrust=hit['thrust'], plan=list(hit['plan']),
                                aim=hit['aim'], facing=hit['facing'], resid=hit['resid'],
                                verdict=res['verdict'], file=name, t=time.time()))
        plans.append(dict(total=res['total'], thrust=hit['thrust'], file=name,
                          incumbent_now=bool(took)))
        ev(event='plan', item=item['item'], thrust=hit['thrust'], total=res['total'],
           became_incumbent=bool(took), file=name, verdict=res['verdict'], cut_i=res['cut_i'])
    row['confirmed'] = n_ok
    row['deliverable'] = n_ok
    row['n_ranked'] = len(ranked)
    row['accept_capped'] = bool(len(ranked) > MAX_ACCEPT)
    IO.append(os.path.join(d, 'progress.jsonl'), row)
    rec = dict(item=item['item'], unit=item['unit'], herd=item['herd'], walk=walk,
               floor=item['floor'], worker=worker, seconds=time.time() - t0, dropped=False,
               candidates=st['candidates'], genuine=st['genuine'], n_plans=len(plans),
               plans=plans, deadline_cut=bool(fst.get('deadline_cut')))
    IO.append(os.path.join(d, 'manifest.jsonl'), rec)
    return rec


# --------------------------------------------------------------------------- the containment gate

def console_candidate():
    """The console 101 expressed as this search's OWN candidate -- its unit, its walk length, its plan
    tuple, its aim, its thrust, all read off the LOCKED fixture.

    This is what `verify_console` feeds back through the pipeline. Nothing here is authored: the plan
    tuple and the aim are the fixture's own ``hit`` block, which is what `cross_engine.composite_log`
    reconstructed the delivered movie from."""
    d = json.load(open(CONSOLE_CLIP))
    h = d['hit']
    return dict(unit=console_herd(), plan=tuple(h['plan']), aim=list(h['aim']),
                thrust=int(h['thrust']), facing=int(h['facing']), m351C=int(h['m351C']),
                entry=list(h['entry']), walk=int(h['frames']), nspeed=float(h['nspeed']),
                resid=float(h['resid']), cut_i=int(d['plan']['cut_i']),
                n_console=int(d['plan']['n_console']))


def containment_knobs(cc=None, strides=(1, 2, 4, 8, 16, 32, 64), *, pre_stride=None, pre_frames=None,
                      alpha_stride=None, contained=False):
    """**WHAT THE FAN'S ENUMERATION WOULD HAVE TO BE TO CONTAIN THE CONSOLE'S OWN PLAN**, and what that
    costs (session 160) -- **AT THE KNOBS A RUN IS ABOUT TO USE** (session 161).

    The knob arguments default to the module's own, which is the question s160 asked ("does the SHIPPED
    default contain it": no). Pass ``contained=True``, or the three knobs, to ask it of the containing
    set -- that is what `verify_console` does, so a run cannot report containment against a
    configuration it will not run at.

    A search is not trusted until it rediscovers a known answer (`[[search-must-rediscover-known-
    answer]]`), and `verify_console`'s alphabet check tested `entry_fan.stick_alphabet(1)` while
    `fan_exact` draws its PRE segment from `stick_alphabet(PRE_STRIDE)`. Measured at the default knobs:

      * the console's plan is ``(0, 208, 110, 0, 2, 169, 192, 0, 2)`` -- a **2 + 2** split, and
        ``PRE_FRAMES = (1,)`` cannot express it at any alphabet;
      * its pre letter ``(208, 110)`` is in the stride-1 and stride-2 class sets and **in none coarser**,
        so the 57-class stride-32 pre alphabet excludes it;
      * its hold letter ``(169, 192)`` is in the stride-1 set ONLY -- which is the trap in "just raise the
        pre resolution": `fan_exact` sizes ``alpha`` to `LEAF_BUDGET`, so a 118x bigger pre makes the
        autoscaler coarsen the HOLD and break containment the other way. Both segments have to be paid.

    Returns ``dict(splits, split_ok, pre_ok, hold_ok, pre_stride_needed, hold_stride_needed,
    pre_classes, fleets_default, fleets_contained, factor)``. The fleet numbers are
    `_fleet_estimate`'s own, so the cost of containment is a measured multiple and not an adjective."""
    cc = console_candidate() if cc is None else cc
    if contained:
        pre_stride = CONTAINED_PRE_STRIDE if pre_stride is None else pre_stride
        pre_frames = PRE_FRAMES_ALL if pre_frames is None else pre_frames
        alpha_stride = CONTAINED_ALPHA_STRIDE if alpha_stride is None else alpha_stride
    pre_stride = PRE_STRIDE if pre_stride is None else int(pre_stride)
    alpha_stride = 1 if alpha_stride is None else int(alpha_stride)
    plan = from_triples(cc['plan'])
    segs = [(int(plan[i]), int(plan[i + 1]), int(plan[i + 2]), int(plan[i + 3]))
            for i in range(1, len(plan), 4)]
    walk = int(cc['walk'])
    pre_frames = PRE_FRAMES if pre_frames is None else pre_frames
    pf = pre_frames_for(walk, pre_frames)
    sets = {s: {EF._decoded(*p) for p in EF.stick_alphabet(s)}
            for s in sorted(set(strides) | {pre_stride, alpha_stride})}
    pre, hold = segs[0], segs[-1]
    need = {}
    for tag, seg in (('pre', pre), ('hold', hold)):
        k = EF._decoded(seg[0], seg[1])
        ok = [s for s in sorted(sets) if k in sets[s]]
        need[tag] = max(ok) if ok else None
    jp = pre[3]                                     # the pre segment's own delivered frames
    n0 = int(plan[0])
    a_pre = tuple(sorted(set(pf) | {jp}))
    # LEGACY price, minimum containing price, and what the run costs today
    d = _fleet_estimate(walk, True, LEGACY_PRE_STRIDE, LEGACY_PRE_FRAMES, PRE_L, atom=False)
    c = _fleet_estimate(walk, True, need['pre'] or 1, a_pre, PRE_L, atom=False)
    shipped = _fleet_estimate(walk, True, PRE_STRIDE, PRE_FRAMES, PRE_L, atom=False)
    return dict(splits=[(s[0], s[1], s[3]) for s in segs], n0=n0,
                split_ok=bool(len(segs) == 1 or jp in pf),
                pre_ok=bool(EF._decoded(pre[0], pre[1]) in sets[pre_stride]),
                hold_ok=bool(EF._decoded(hold[0], hold[1]) in sets[alpha_stride]),
                pre_stride_needed=need['pre'], hold_stride_needed=need['hold'],
                pre_classes=len(sets[pre_stride]), pre_frames_needed=a_pre,
                pre_stride_used=pre_stride, pre_frames_used=list(pf), alpha_stride_used=alpha_stride,
                fleets_default=d, fleets_contained=c, fleets_shipped=shipped,
                factor=(c / d if d else None))


def verify_console(env=None, incumbent=None, *, contained=False, pre_stride=None, pre_frames=None,
                   alpha_stride=None):
    """**IS THE BANKED 101 INSIDE THIS SEARCH'S SPACE?** Measured, phase by phase, never asserted.

    `[[search-space-contains-human]]`: a search whose range does not intrinsically contain the known-good
    reference input is broken. Session 149 found out the hard way that this was not gated one level down.
    So this checks the range of every axis the driver actually enumerates:

      * the console's HERD is a unit, and it is not dropped at an incumbent that leaves room for it;
      * its WALK LENGTH is inside the unit's own budget at its thrust;
      * both of its walk letters are members of the fan's alphabet -- as CLASSES, since the alphabet is
        the byte grid collapsed onto what the physics reads, and a class is one draw;
      * its AIM is in the aim alphabet at the camera the fan runs, and its facing is a cell this
        driver's `configurations` enumerates;
      * its THRUST is in the driver's thrust set;
      * and end to end, its own candidate passes `accept` -- confirm, walled composite, `verdict` -- at
        a total equal to the fixture's own cut frame.

    ``incumbent`` defaults to the console total + 1: the run's own bound is 101 and a plan may not beat
    itself, so containment is the question of whether the search WOULD find it with one frame of room."""
    env = env or SD.load_env()
    cc = console_candidate()
    total = total_frames(cc['unit']['herd'], cc['walk'], cc['thrust'])
    inc = int(total + 1) if incumbent is None else int(incumbent)
    keep, drop = units(incumbent=inc)
    out = dict(total=total, cut_i=cc['cut_i'], incumbent_used=inc, checks=[])

    def chk(name, ok, detail):
        out['checks'].append(dict(name=name, ok=bool(ok), detail=detail))
        return bool(ok)

    chk('total == the fixture cut frame', total == cc['cut_i'],
        'driver total %d, locked cut frame %d' % (total, cc['cut_i']))
    unit = next((u for u in keep if u['unit'] == 'console'), None)
    chk('the console herd is a live unit', unit is not None,
        'floor %s, dropped %s' % (unit['floor'] if unit else None,
                                  [x for x in drop if x['unit'] == 'console']))
    if unit is None:
        out['ok'] = False
        return out
    chk('its thrust is in the search set', cc['thrust'] in unit['thrusts'],
        'thrust %d, unit admits %s' % (cc['thrust'], unit['thrusts']))
    chk('its walk length is inside the budget', unit['walks'].get(cc['thrust'], 0) >= cc['walk'],
        'walk %d, budget %s at thrust %d' % (cc['walk'], unit['walks'].get(cc['thrust']),
                                            cc['thrust']))
    alpha = {EF._decoded(*p) for p in EF.stick_alphabet(1)}
    plan = from_triples(cc['plan'])
    letters = [tuple(plan[i:i + 2]) for i in range(1, len(plan), 4)]
    missing = [p for p in letters if EF._decoded(*p) not in alpha]
    chk('its walk letters are in the fan alphabet', not missing,
        'letters %s, missing %s of %d classes' % (letters, missing, len(alpha)))
    # **AND IN THE ALPHABET THE RUN ACTUALLY DRAWS THEM FROM** (s160): the check above is the stride-1
    # grid, and the pre segment is not -- knowledge/model/fan-containment-gap.md. Asked at the knobs
    # passed in, so a run reports containment for the configuration it will actually enumerate (s161).
    kn = containment_knobs(cc, pre_stride=pre_stride, pre_frames=pre_frames,
                           alpha_stride=alpha_stride, contained=contained)
    out['knobs'] = dict((k, kn[k]) for k in ('pre_stride_used', 'pre_frames_used',
                                             'alpha_stride_used', 'fleets_default',
                                             'fleets_contained', 'factor'))
    chk('its SPLIT SHAPE is enumerated at the run\'s PRE_FRAMES', kn['split_ok'],
        'plan splits %s, driver enumerates n0 + jp in %s + a uniform hold'
        % (kn['splits'], tuple(kn['pre_frames_used'])))
    chk('its pre letter is in the alphabet the run DRAWS the pre segment from', kn['pre_ok'],
        'pre stride %d = %d classes; the letter needs stride <= %s'
        % (kn['pre_stride_used'], kn['pre_classes'], kn['pre_stride_needed']))
    chk('its HOLD letter is in the alphabet the run holds at', kn['hold_ok'],
        'hold stride %d; the letter needs stride <= %s -- a leaf budget that coarsens the hold to '
        'pay for the pre breaks containment the other way'
        % (kn['alpha_stride_used'], kn['hold_stride_needed']))
    chk('its walk length round-trips the L-capable encoding', plan_frames(plan) == cc['walk'],
        'plan %s -> %d frames, fixture says %d' % (list(plan), plan_frames(plan), cc['walk']))
    prep = prepare(cc['unit'], env)
    chk('its herd is wall-inert and rule-4 clean', prep['ok'], prep['reason'] or 'clean')
    hold = hold_row(prep['seed'])
    trail = EC.CamTrail(int(hold.get('substickX', 128)), cc['walk'] + TRAIL_PAD, prep['seed'], env)
    csa = aim_camera(plan, cc['walk'], trail)
    quals = configurations(csa, [cc['thrust']])
    cells = {q['cell'] for q in quals}
    chk('its facing cell is enumerated at the aim camera', ES.aim_cell(cc['facing']) in cells,
        'cell %d at csangle %d; driver enumerates %d cells %s'
        % (ES.aim_cell(cc['facing']), csa, len(cells), sorted(cells)[:6]))
    aims = {tuple(b) for (_f, b, _s) in ES.aim_cells(csa)}
    sibs = {tuple(s) for (_f, _b, sib) in ES.aim_cells(csa) for s in sib}
    chk('its aim bytes are in the aim alphabet', tuple(cc['aim']) in (aims | sibs),
        'aim %s; %d cell aims, %d siblings' % (cc['aim'], len(aims), len(sibs)))
    # and the PAIR, not just the membership (s154): the byte -> facing map moves with the camera, so a
    # byte can be in the alphabet while reaching a facing five cells from the one it is recorded beside
    reach = dict((tuple(b), f) for f, b in ES.aim_alphabet(csa))
    chk('its aim byte REACHES its own facing at the aim camera',
        reach.get(tuple(cc['aim'])) == cc['facing'],
        'aim %s at csangle %d reaches %s, fixture facing %d'
        % (cc['aim'], csa, reach.get(tuple(cc['aim'])), cc['facing']))
    hit = dict(entry=cc['entry'], walk=None, m351C_walk=None, m351C=cc['m351C'],
               facing=cc['facing'], aim=cc['aim'], thrust=cc['thrust'], b_step=cc['thrust'] + 2,
               resid=cc['resid'], nspeed=cc['nspeed'], plan=list(plan),
               tetra=list(prep['seed']['tetra']), cell=ES.aim_cell(cc['facing']), walkable=True)
    # two passes: the first MEASURES the walk endpoint (the search reads it off the fan key, which this
    # replay does not have), the second is then the same strict all-flags confirmation the search runs
    conf = ES.confirm_entry(hit, seed=prep['seed'], env=env, rows=plan_rows(hold, plan))
    hit['walk'] = list(conf['measured']['walk'])
    hit['m351C_walk'] = int(conf['measured']['m351C'])
    conf = ES.confirm_entry(hit, seed=prep['seed'], env=env, rows=plan_rows(hold, plan))
    chk('the driver re-derives its own roll entry from a real A-press', conf['all_ok'],
        'confirm %s' % conf['ok'])
    res = accept(hit, prep['seed'], cc['unit'], env, cc['walk'])
    out['accept'] = dict((k, v) for k, v in res.items() if k not in ('log', 'hit'))
    chk('its own candidate is DELIVERABLE through this driver', res['ok'],
        'stage %s; agree %s' % (res.get('stage'), res.get('agree')))
    chk('the delivered cut frame is the locked one', res.get('total_log') == cc['cut_i'],
        'driver read %s, locked %d' % (res.get('total_log'), cc['cut_i']))
    out['ok'] = all(c['ok'] for c in out['checks'])
    return out


# --------------------------------------------------------------------------- workers and the run

def _env_for_worker():
    """One OpenMP thread per worker. The fan's `prange` fleet and `ShoveCtx.sweep_par` are both
    internally parallel, so N workers x M threads oversubscribes N*M ways and every one of them slows
    down; the units are independent, so the parallelism belongs at the unit."""
    e = dict(os.environ)
    e['OMP_NUM_THREADS'] = '1'
    e['PYTHONUNBUFFERED'] = '1'
    return e


def worker(d, worker_id, *, deadline=None, resume=True, steal_after=None, walk_cap=None,
           s1_stride=32, two_segment=True, atom=True, order=None, pre_stride=PRE_STRIDE,
           leaf_budget=None, only=None, tail_frames=(), tail_beam=400, prefix_cap=PREFIX_CAP):
    """Pull items from the claim queue until the deadline. Nothing in this function is state: every
    item's outcome is on disk before the next one starts, so killing it loses at most one item.

    The queue is walked in the config's order, which is ascending TOTAL (`items`), and the claim is an
    ``O_EXCL`` file -- so N workers together consume the globally frame-minimal order without a server
    and without duplicating work."""
    cfg = IO.read_json(os.path.join(d, 'config.json'), {})
    inc0 = int(cfg.get('incumbent0', O.TOTAL_INCUMBENT))
    ilist, _drop = items(incumbent=inc0, trunc=int(cfg.get('trunc', 0) or 0))
    if walk_cap is not None:
        ilist = [x for x in ilist if x['walk'] <= int(walk_cap)]
    if order:
        ilist = [x for x in ilist if x['item'] in set(order)]
    if only:
        # a FOCUSED pass: the herds (or items) a first pass showed reaching contact, re-run at a bigger
        # leaf budget -- clip-lottery-draws.md's "widen where the draws are", as one command
        want = set(only)
        ilist = [x for x in ilist if x['item'] in want or x['unit'] in want]
    env = SD.load_env()
    evp = os.path.join(d, 'events-%s.jsonl' % worker_id)

    def ev(**kw):
        kw.setdefault('t', time.time())
        kw.setdefault('worker', worker_id)
        IO.append(evp, kw)

    ev(event='worker_start', pid=os.getpid(), deadline=deadline, n_items=len(ilist))
    done = IO.completed(d) if resume else set()
    for it in ilist:
        if deadline is not None and time.time() >= deadline:
            ev(event='worker_deadline')
            break
        if it['item'] in done:
            continue
        inc, _r = IO.incumbent(d, inc0)
        if it['floor'] >= inc:
            ev(event='bound_skip', item=it['item'], floor=it['floor'], incumbent=inc)
            IO.append(os.path.join(d, 'manifest.jsonl'),
                      dict(item=it['item'], unit=it['unit'], herd=it['herd'], walk=it['walk'],
                           floor=it['floor'], worker=worker_id, seconds=0.0, dropped=True,
                           reason='branch-and-bound: floor %d >= incumbent %d'
                                  % (it['floor'], inc)))
            continue
        if not IO.claim(d, it['item'], worker_id, steal_after=steal_after):
            continue
        ev(event='item_start', item=it['item'], herd=it['herd'], walk=it['walk'],
           floor=it['floor'], incumbent=inc)
        try:
            rec = run_item(it, d, env, worker=worker_id, deadline=deadline,
                           s1_stride=s1_stride, nthreads=1, dflt_incumbent=inc0, on_event=ev,
                           two_segment=two_segment, atom=atom, pre_stride=pre_stride,
                           leaf_budget=leaf_budget, tail_frames=tail_frames,
                           tail_beam=tail_beam, prefix_cap=prefix_cap)
            ev(event='item_done', item=it['item'], seconds=round(rec['seconds'], 1),
               n_plans=rec.get('n_plans', 0), dropped=rec.get('dropped'))
        except Exception as exc:
            ev(event='exception', item=it['item'], cls=type(exc).__name__, msg=str(exc)[:600],
               where='run_item', tb=traceback.format_exc()[-1500:])
            IO.append(os.path.join(d, 'manifest.jsonl'),
                      dict(item=it['item'], unit=it['unit'], herd=it['herd'], walk=it['walk'],
                           floor=it['floor'], worker=worker_id, seconds=0.0, dropped=True,
                           failed=True, reason='%s: %s' % (type(exc).__name__, str(exc)[:200])))
    ev(event='worker_end')


def launch(run_id=None, workers=11, hours=7.0, resume=False, trunc=0, walk_cap=None, s1_stride=32,
           two_segment=True, atom=True, wait=True, only=None, leaf_budget=None,
           pre_stride=PRE_STRIDE, tail_frames=(), tail_beam=400, prefix_cap=PREFIX_CAP):
    """Write the run's configuration, spawn the workers, wait. The parent holds no search state."""
    run_id = run_id or time.strftime('s150-%Y%m%d-%H%M%S')
    d = IO.ensure(IO.run_dir(REPO, run_id))
    keep, drop = items(trunc=trunc)
    if walk_cap is not None:
        keep = [x for x in keep if x['walk'] <= int(walk_cap)]
    if only:
        want = set(only)
        keep = [x for x in keep if x['item'] in want or x['unit'] in want]
    t0 = time.time()
    deadline = t0 + float(hours) * 3600.0
    cfg = IO.read_json(os.path.join(d, 'config.json'), {}) if resume else {}
    if not cfg:
        cfg = dict(run_id=run_id, t0=t0, deadline=deadline, workers=int(workers),
                   hours=float(hours), incumbent0=O.TOTAL_INCUMBENT, trunc=int(trunc),
                   walk_cap=walk_cap, s1_stride=int(s1_stride), two_segment=bool(two_segment),
                   atom=bool(atom), walk_floor=WALK_FLOOR, thrusts=list(ES.THRUSTS),
                   pre_stride=PRE_STRIDE, pre_frames=PRE_FRAMES, max_accept=MAX_ACCEPT,
                   atom_rotate_offs=list(ATOM_ROTATE_OFFS), only=(sorted(only) if only else None),
                   leaf_budget=(int(leaf_budget) if leaf_budget else LEAF_BUDGET),
                   pre_stride_run=int(pre_stride), tail_frames=list(tail_frames),
                   tail_beam=int(tail_beam), prefix_cap=int(prefix_cap),
                   items=[dict((k, v) for k, v in x.items() if k != 'log') for x in keep],
                   units=sorted({x['unit'] for x in keep}), dropped=drop, cpu=os.cpu_count(),
                   note='items are ordered by the TOTAL they could produce, so the run is globally '
                        'best-first; floors are admissible and drops are proofs, not heuristics')
        IO.write_atomic(os.path.join(d, 'config.json'), cfg)
    else:
        # a resume starts with no workers running, so a claim without a manifest line is abandoned;
        # releasing it is what makes an interrupted item re-run instead of being silently skipped
        done = IO.completed(d)
        stale = [k for k in IO.claims(d) if k not in done]
        for k in stale:
            os.remove(os.path.join(d, 'claims', '%s.claim' % k))
        cfg.update(deadline=deadline, resumed_at=t0, workers=int(workers),
                   released_on_resume=stale)
        IO.write_atomic(os.path.join(d, 'config.json'), cfg)
        print('  resumed: %d items complete, %d abandoned claims released %s'
              % (len(done), len(stale), stale[:6]))
    print('run %s -> %s' % (run_id, d))
    print('  %d items over %d herds (%d herds dropped before any work), %d workers,'
          ' deadline in %.2f h'
          % (len(keep), len(set(x['unit'] for x in keep)), len(drop), workers, hours))
    print('  first items: %s' % [(x['item'], x['floor']) for x in keep[:6]])
    procs = []
    for k in range(int(workers)):
        cmd = [sys.executable, '-u', '-m', 'harness.tetrapush.overnight', 'worker',
               'id=%s' % run_id, 'wid=w%02d' % k, 'deadline=%r' % deadline,
               'resume=%d' % (1 if resume else 1), 's1=%d' % s1_stride,
               'two=%d' % (1 if two_segment else 0), 'atom=%d' % (1 if atom else 0)]
        if walk_cap is not None:
            cmd.append('walk=%d' % walk_cap)
        if leaf_budget:
            cmd.append('leaf=%d' % int(leaf_budget))
        if pre_stride != PRE_STRIDE:
            cmd.append('pre=%d' % int(pre_stride))
        if only:
            cmd.append('only=%s' % ','.join(sorted(only)))
        if tail_frames:
            cmd.append('tail=%s' % ','.join(str(x) for x in tail_frames))
            cmd.append('tbeam=%d' % int(tail_beam))
            cmd.append('pcap=%d' % int(prefix_cap))
        lp = os.path.join(d, 'worker-w%02d.log' % k)
        procs.append(subprocess.Popen(cmd, cwd=REPO, env=_env_for_worker(),
                                      stdout=open(lp, 'a'), stderr=subprocess.STDOUT))
    print('  spawned pids %s' % [p.pid for p in procs])
    if not wait:
        return d, procs
    for p in procs:
        p.wait()
    print('all workers finished after %.2f h' % ((time.time() - t0) / 3600.0))
    return d, procs


# --------------------------------------------------------------------------- CLI

def _fmt_dt(s):
    if s is None:
        return '-'
    s = float(s)
    sign = '-' if s < 0 else ''
    s = abs(s)
    return '%s%d:%02d:%02d' % (sign, int(s // 3600), int(s % 3600 // 60), int(s % 60))


def report(d, full=False):
    """The mid-run answer to "what has been searched, how long is left, what is the best so far"."""
    s = IO.summarise(d)
    cfg = s['config']
    print('RUN %s   %s' % (cfg.get('run_id', '?'), d))
    print('  elapsed %s   remaining %s   deadline %s'
          % (_fmt_dt(s['elapsed']), _fmt_dt(s['remaining']),
             time.strftime('%H:%M:%S', time.localtime(s['deadline'])) if s['deadline'] else '-'))
    print('  items: %d total, %d done, %d in flight, %d left   (%d herds dropped before any work)'
          % (s['n_units'], s['n_done'], s['n_inflight'], s['n_left'], len(cfg.get('dropped', []))))
    print('  mean %s / item -> ETA %s at %d workers'
          % (_fmt_dt(s['per_unit']), _fmt_dt(s['eta']), cfg.get('workers', 0)))
    t = s['totals']
    print('  coverage: %d candidates, %d razor evaluations, %d GENUINE, %d near, %d deliverable'
          % (t['candidates'], t['evaluations'], t['genuine'], t['near'], t['deliverable']))
    print('  BAND DRAWS -- overlap in %s, the only scorings that could clip: %d = %.4f%% of them'
          % (str(CLIP_BAND), t['band_draws'],
             100.0 * t['band_draws'] / max(1, t['evaluations'])))
    ovl = [r for r in s['progress'] if r.get('best_overlap') is not None]
    if ovl:
        b = min(ovl, key=lambda r: abs(r['best_overlap'] - CLIP_TARGET))
        nc = sum(r.get('n_contact', 0) or 0 for r in s['progress'])
        br = [r['item'] for r in s['progress'] if r.get('bracketed')]
        rc = [r for r in s['progress'] if r.get('best_resid_in_contact') is not None]
        print('  contact: %d scorings IN contact; overlap nearest the clip band %+0.3f u at %s'
              '   (the console clip is %+0.4f)'
              % (nc, b['best_overlap'], b['item'], CLIP_TARGET))
        if rc:
            k = min(rc, key=lambda r: abs(r['best_resid_in_contact']))
            print('           best |resid| in contact %.4e at %s; razor BRACKETED at %s'
                  % (abs(k['best_resid_in_contact']), k['item'], br[:6] if br else 'nowhere yet'))
    print('            %s in the fan, %s in the razor'
          % (_fmt_dt(t['fan_seconds']), _fmt_dt(t['score_seconds'])))
    if s['exceptions']:
        print('  exceptions (counted, never fatal): %s' % s['exceptions'])
    inc = s['incumbent']
    print('  INCUMBENT: %s'
          % ('total %d frames  (%s, walk %d, thrust %d, resid %+.3e, verdict %s)  %s'
             % (inc['total'], inc['unit'], inc['walk'], inc['thrust'], inc['resid'],
                inc['verdict'], inc['file'])
             if inc else 'nothing has beaten the banked console %d' % cfg.get('incumbent0', 101)))
    if s['inflight']:
        print('  in flight:')
        for u, c in sorted(s['inflight'].items()):
            print('    %-12s %-4s walk %-3s incumbent %-4s  quiet %s'
                  % (u, c.get('worker'), c.get('walk'), c.get('incumbent'),
                     _fmt_dt(time.time() - float(c.get('beat', 0) or 0))))
    bad = [m for m in s['manifest'] if m.get('dropped')]
    if bad:
        print('  items dropped DURING the run: %d (bound skips + refused herds)' % len(bad))
        for m in bad[:12 if not full else len(bad)]:
            print('    %-14s %s' % (m.get('item', m.get('unit')), m.get('reason', '')[:96]))
    if full:
        print('  per-unit walk coverage:')
        for r in s['progress']:
            print('    %-14s cands %8d evals %10d genuine %4d near %5d contact %6d'
                  ' ovl %+8.2f fan %6.1fs razor %6.1fs'
                  % (r.get('item', r.get('unit')), r.get('candidates', 0),
                     r.get('evaluations', 0), r.get('genuine', 0), r.get('near', 0),
                     r.get('n_contact', 0) or 0,
                     (r.get('best_overlap') if r.get('best_overlap') is not None else float('nan')),
                     r.get('fan_seconds', 0), r.get('score_seconds', 0)))
    return s


def main(argv=None):
    warnings.simplefilter('ignore')
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'status'
    opt = dict(a.split('=', 1) for a in argv if '=' in a)

    def _i(k, dflt):
        return int(opt.get(k, dflt))

    if cmd == 'units':
        keep, drop = units(incumbent=_i('incumbent', O.TOTAL_INCUMBENT), trunc=_i('trunc', 0))
        print('%d units, ordered by admissible floor; %d dropped' % (len(keep), len(drop)))
        for u in keep:
            print('  %-12s herd %3d  floor %3d  thrusts %s  walk budget %s'
                  % (u['unit'], u['herd'], u['floor'], u['thrusts'],
                     {t: u['walks'][t] for t in u['thrusts']}))
        for x in drop:
            print('  DROPPED %-12s %s' % (x['unit'], x['reason']))
        return 0
    if cmd == 'items':
        keep, drop = items(incumbent=_i('incumbent', O.TOTAL_INCUMBENT), trunc=_i('trunc', 0))
        n = _i('head', 40)
        print('%d items over %d herds, ordered by the TOTAL each could produce; %d herds dropped'
              % (len(keep), len(set(x['unit'] for x in keep)), len(drop)))
        for x in keep[:n]:
            print('  %-14s herd %3d  walk %2d  -> total %3d  thrusts %s'
                  % (x['item'], x['herd'], x['walk'], x['floor'], x['thrusts']))
        if len(keep) > n:
            print('  ... %d more, up to total %d' % (len(keep) - n, keep[-1]['floor']))
        return 0
    if cmd == 'verify-console':
        r = verify_console(incumbent=(int(opt['incumbent']) if 'incumbent' in opt else None))
        print('CONTAINMENT of the banked console %d (bound used %d)'
              % (r['total'], r['incumbent_used']))
        for c in r['checks']:
            print('  [%s] %-52s %s' % ('ok' if c['ok'] else 'FAIL', c['name'], c['detail'][:110]))
        print('%s' % ('CONTAINED: the search space holds the best known plan'
                      if r['ok'] else 'NOT CONTAINED -- the search is broken until this passes'))
        return 0 if r['ok'] else 1
    if cmd == 'item':
        want = argv[0] if argv and '=' not in argv[0] else opt.get('item')
        # ONE bound for BOTH halves (s162): it filtered the item LIST only, so `item console-w04
        # incumbent=102` then ran at 101, where `max_walk` drops the console's own thrust.
        inc = _i('incumbent', O.TOTAL_INCUMBENT)
        keep, _d = items(incumbent=inc)
        sel = [x for x in keep if x['item'] == want or x['unit'] == want]
        if 'walk' in opt:
            sel = [x for x in sel if x['walk'] <= _i('walk', 99)]
        d = IO.ensure(IO.run_dir(REPO, opt.get('id', 'probe')))
        if not os.path.exists(os.path.join(d, 'config.json')):
            IO.write_atomic(os.path.join(d, 'config.json'),
                            dict(run_id='probe', t0=time.time(), workers=1,
                                 incumbent0=inc, items=[], dropped=[]))
        secs = float(opt.get('seconds', 0) or 0)
        dl = (time.time() + secs) if secs else None
        env = SD.load_env()
        for it in sel:
            rec = run_item(it, d, env, worker='probe', deadline=dl, s1_stride=_i('s1', 32),
                           dflt_incumbent=inc,
                           nthreads=_i('threads', 0), two_segment=bool(_i('two', 1)),
                           atom=bool(_i('atom', 1)), pre_stride=_i('pre', PRE_STRIDE),
                           leaf_budget=(int(opt['leaf']) if 'leaf' in opt else None),
                           tail_frames=(tuple(int(x) for x in opt['tail'].split(','))
                                        if 'tail' in opt else ()),
                           tail_beam=_i('tbeam', 400), prefix_cap=_i('pcap', PREFIX_CAP),
                           on_event=lambda **kw: print('  [%s] %s'
                                                       % (kw.get('event'),
                                                          {k: v for k, v in kw.items()
                                                           if k not in ('event', 't', 'worker')}),
                                                       flush=True))
            print(json.dumps(dict((k, v) for k, v in rec.items() if k != 'plans'), default=float),
                  flush=True)
        return 0
    if cmd == 'worker':
        d = IO.run_dir(REPO, opt['id'])
        worker(d, opt.get('wid', 'w0'),
               deadline=(float(opt['deadline']) if 'deadline' in opt else None),
               resume=bool(_i('resume', 1)), walk_cap=(_i('walk', 0) or None),
               s1_stride=_i('s1', 32), two_segment=bool(_i('two', 1)),
               atom=bool(_i('atom', 1)), pre_stride=_i('pre', PRE_STRIDE),
               leaf_budget=(int(opt['leaf']) if 'leaf' in opt else None),
               only=(opt['only'].split(',') if 'only' in opt else None),
               tail_frames=(tuple(int(x) for x in opt['tail'].split(',')) if 'tail' in opt else ()),
               tail_beam=_i('tbeam', 400), prefix_cap=_i('pcap', PREFIX_CAP),
               steal_after=(float(opt['steal']) if 'steal' in opt else None))
        return 0
    if cmd == 'run':
        launch(run_id=opt.get('id'), workers=_i('workers', 11), hours=float(opt.get('hours', 7)),
               resume=bool(_i('resume', 0)), trunc=_i('trunc', 0),
               walk_cap=(_i('walk', 0) or None), s1_stride=_i('s1', 32),
               two_segment=bool(_i('two', 1)), atom=bool(_i('atom', 1)),
               pre_stride=_i('pre', PRE_STRIDE),
               leaf_budget=(int(opt['leaf']) if 'leaf' in opt else None),
               only=(opt['only'].split(',') if 'only' in opt else None),
               tail_frames=(tuple(int(x) for x in opt['tail'].split(',')) if 'tail' in opt else ()),
               tail_beam=_i('tbeam', 400), prefix_cap=_i('pcap', PREFIX_CAP))
        return 0
    if cmd == 'status':
        rid = opt.get('id')
        if rid is None:
            root = os.path.join(REPO, '_generated', 'overnight')
            ids = sorted(os.listdir(root)) if os.path.isdir(root) else []
            if not ids:
                print('no runs under %s' % root)
                return 1
            rid = ids[-1]
        report(IO.run_dir(REPO, rid), full=bool(_i('full', 0)))
        return 0
    raise SystemExit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
