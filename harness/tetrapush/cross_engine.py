"""THE CROSS-ENGINE PRE-FLIGHT: does the composite reproduce the lunge `ShoveCtx` scored genuine?

Two engines decide whether a candidate clips, and they are not the same code. The **search** engine is
`entry_search.build_fast` -- a `ShoveCtx` sweeping a baked roll schedule against the seam, which is
what makes a 39 M-candidate pass affordable. The **composite** is the wired delay-1 `FreeRun` with the
culled courtyard mesh on BOTH actors, stepped frame by frame from the console log; it is the engine
gated against the console on both actors (`tests/test_clip_delivered.py`), so it is the reference.

Session 87 made the two agree for ONE hit and gated that. Session 88 ran the same diff per candidate
and found agreement is a property of the **candidate**, not of the engines: of 19 confirmed hits, two
diverged by 1 ULP of Tetra before the cut and two had the composite refusing the very lunge `ShoveCtx`
called genuine -- 0.15 u where the prediction has 49.86. One of those two was the frame-minimal
survivor, i.e. exactly the candidate the next delivery would have been spent on.

So this is not a diagnostic, it is a filter, and it belongs INSIDE the scoring loop rather than in
front of a delivery: it costs one rollout and no console runs, while a delivery costs a live run and,
when it fails, a session. `entry_score.confirm_hits(cross_engine=True)` runs it on every hit that
confirms. Razor rule 7 (`knowledge/strategy/razor-prices-every-term.md`).

A 1-ULP divergence before the cut can still end in a bit-identical cut frame, so `agree` reports
`worst_ulp` and `cut_ok` separately and `deliverable` demands both. Do not read "the engines agree at
the razor" as "the engines agree".

SESSION 90: THIS FILTER NOW REJECTS NOTHING, and that is a result rather than a reason to delete it.
Session 89 traced every rejection to two implementations of Link's Co centre; session 90 delivered a
blocked candidate to console (49.8582 u against 0.1534 u -- the console cannot land between them) and
it clipped, on `body_cyl`, to the bit. The root cause sat one level under the seam: the two ports were
sampling `rollf` at two different f32 FRAMES, because `FrameCtrl` held `enter_roll`'s Python double
`1.1` where `J3DFrameCtrl::mRate` is f32. Fixed at that boundary, the ports agree bit-for-bit and all
four rejections deliver -- so a filter that starts rejecting again means something has REGRESSED, and
`tests/test_cross_engine.py` asserts the empty class every run. See `tests/test_centre_seam.py`.

Promoted from session 88's `_notes/s88_{clip,agree}.py`; the composite path is unchanged.
"""
import math
import os
import struct
import sys
import warnings

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from harness.rollstab import turnaround as TA
from harness.tetrapush import entry_search as ES
from harness.tetrapush import seeds as SD
from tww_sim.land.land import CUT_A, CUT_F, FRONT_ROLL

#: Neutral frames appended after the UP+B thrust, so a truncate-and-read halt can sit past the cut.
TAIL = 6

#: A lunge shorter than this is the composite refusing to move Link through the seam at all -- the
#: expensive rejection class, since `ShoveCtx` scores those ~49.9 u and genuine.
CLIP_LUNGE_MIN = 45.0


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _ulps(a, b):
    return abs(_bits(a) - _bits(b))


def composite_log(hit, seed, tail=TAIL):
    """The composite input log: the console herd, the hit's own walk plan and A-press, then the roll
    held out to the UP+B thrust.

    `b_step` is the delivered UP+B index into the roll (`entry_search`: thrust + 2). The roll
    dispatches at `entry_i` and the DTM is a delay-1 stream, so roll[k] is plan frame `entry_i` + k
    and roll[b_step] fires the cut on `entry_i` + b_step + 1 -- the session-86 mapping trap, kept
    verbatim because getting it wrong reads as a physics divergence."""
    plan = list(hit['plan'])
    hold = dict(seed['log'][-1], buttons=0)
    extra = [hold] * plan[0]
    for i in range(1, len(plan), 3):
        sx, sy, j = plan[i:i + 3]
        extra += [dict(hold, stickX=sx, stickY=sy)] * j
    extra.append(dict(hold, stickX=hit['aim'][0], stickY=hit['aim'][1], buttons=0x100))  # the A-press
    log = list(seed['log']) + extra
    a_i = len(log) - 1                       # the A-press input frame
    entry_i = a_i + 1                        # the first FRONT_ROLL frame
    b_log = entry_i + hit['thrust'] + 2      # b_step = thrust + 2
    neu = dict(hold, stickX=128, stickY=128, buttons=0)
    upb = dict(hold, stickX=128, stickY=254, buttons=0x200)   # 254, not 255: authored == delivered
    for i in range(a_i + 1, b_log + 1 + tail):
        log.append(dict(upb) if i == b_log else dict(neu))
    return log, dict(n_console=len(seed['log']), a_i=a_i, entry_i=entry_i, b_log=b_log)


def composite_rollout(log, env=None, walls_tetra=True):
    """Step the whole composite on the WIRED walled `FreeRun`; one row per plan frame, both actors.

    `walls_tetra` is the session-87 term -- Tetra's own `mObjAcch.CrrPos` in the courtyard tracking.
    It defaults on because that is the configuration the console gated; False is for diagnosing what
    the missing wall was worth."""
    env = env if env is not None else SD.load_env()
    run = SD.make_freerun(env)
    run.link._walls = TA.WALLS
    run.walls_tetra = TA.WALLS if walls_tetra else None
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i, inp in enumerate(log):
            run.step(inp)
            lk = run.link
            rows.append(dict(i=i, n=i + 1, link_x=lk.pos_x, link_z=lk.pos_z,
                             facing=lk.facing & 0xFFFF, travel=lk.travel & 0xFFFF,
                             proc=lk.state & 0xFF, speedF=lk.speedF, nspeed=lk.nspeed,
                             m351C=lk.m351C & 0xFFFF, csangle=lk.csangle & 0xFFFF,
                             tetra_x=run.tx, tetra_z=run.tz))
    return rows


def agree(hit, seed=None, env=None):
    """One candidate through both engines. Returns the verdict plus every number it rests on.

    ``handover_ok``    the composite rolls from the entry the hit was SCORED at (position, facing,
                       lean and momentum -- a `ShoveCtx` schedule is keyed on all four).
    ``genuine``        the search engine's own verdict for this entry.
    ``worst_ulp``      the largest f32 ULP gap between the two engines over the roll, both actors,
                       through the cut. 0 is agreement; anything else is a candidate whose verdict
                       is decided by a difference neither engine has been gated on.
    ``cut_ok``         the composite's cut frame IS the prediction's `new`, to the bit.
    ``composite_moved`` how far the composite actually moves Link on the cut frame. When this is ~0
                       and ``predicted_lunge`` is ~50, the composite is BLOCKING the lunge -- the
                       rejection class that costs a delivery.
    ``deliverable``    all of the above. Only spend a console run on one of these."""
    seed = seed or ES.console_seed()
    log, ix = composite_log(hit, seed)
    rows = {r['i']: r for r in composite_rollout(log, env=env)}
    entry_i = ix['entry_i']
    ent = rows[entry_i]
    hand = (ent['proc'] == FRONT_ROLL
            and _bits(ent['link_x']) == _bits(hit['entry'][0])
            and _bits(ent['link_z']) == _bits(hit['entry'][1])
            and ent['facing'] == hit['facing'] and ent['m351C'] == hit['m351C']
            and _bits(ent['nspeed']) == _bits(hit['nspeed']))
    ctx, sch, _resid = ES.build_fast(hit['facing'], hit['m351C'], hit['thrust'],
                                     (hit['entry'][0], hit['entry'][1]), nspeed=hit['nspeed'])
    res, tr = ctx.run_trace(seed['tetra'][0], seed['tetra'][1], 0)
    cut_i = next((i for i in sorted(rows) if i > entry_i and rows[i]['proc'] in (CUT_F, CUT_A)), None)
    worst = 0
    for k, row in enumerate(tr):
        i = entry_i + 1 + k                  # ShoveCtx step 0 is the roll's SECOND frame
        if i not in rows or (cut_i is not None and i > cut_i):
            continue
        worst = max(worst, _ulps(row[0], rows[i]['link_x']), _ulps(row[1], rows[i]['link_z']),
                    _ulps(row[2], rows[i]['tetra_x']), _ulps(row[3], rows[i]['tetra_z']))
    cut = rows[cut_i] if cut_i is not None else None
    pre = rows[cut_i - 1] if cut_i is not None else None
    lunge = math.hypot(res['new'][0] - res['old'][0], res['new'][1] - res['old'][1])
    moved = (math.hypot(cut['link_x'] - pre['link_x'], cut['link_z'] - pre['link_z'])
             if cut else None)
    cut_ok = bool(cut and _bits(cut['link_x']) == _bits(res['new'][0])
                  and _bits(cut['link_z']) == _bits(res['new'][1]))
    return dict(entry_i=entry_i, b_log=ix['b_log'], cut_i=cut_i, handover_ok=bool(hand),
                genuine=bool(res['genuine']), worst_ulp=int(worst), cut_ok=cut_ok,
                cut_step=int(sch['cut_step']), predicted_lunge=lunge, composite_moved=moved,
                deliverable=bool(hand and res['genuine'] and cut_ok and worst == 0))


def blocked(res):
    """The expensive rejection: `ShoveCtx` lunges through the seam, the composite does not move.

    Named because it is the one worth diagnosing -- a few f32 ULP of Tetra mid-roll is the scale
    session 86 measured the verdict flipping at, so whichever engine is wrong here is wrong for the
    whole population and not just this candidate."""
    return bool(not res['deliverable'] and res['predicted_lunge'] > CLIP_LUNGE_MIN
                and res['composite_moved'] is not None and res['composite_moved'] < 1.0)
