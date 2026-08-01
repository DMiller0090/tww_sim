"""THE SEPARATE ENTRY SEARCH (Dereck, session 60): Link's roll position + angle for the clip, with
the herd ALREADY DONE and Tetra frozen where the console left her.

This is the dual of `_generated/tetra_placements.tsv`. That list sweeps TETRA at a fixed roll entry
(`harness/rollstab/turnaround.search`, the slot-7 setup the list's header names). Here the herd has
happened, so Tetra is a MEASURED CONSTANT -- `fixtures/courtyard_plan_s73_console.json` reads her
bit-frozen at the same point on console frames 76/77/78 -- and the free variable is the ENTRY. Same
razor, swept the other way round.

THE FORK IT SETTLES (open since session 45). Two routes were on the table: (A) walk Link to the
tabulated `seeds.ENTRY_ROLL_POS` that the coord list is valid for, or (B) re-solve the clip at the
herd's natural endpoint. **(A) is falsified by measurement, not by argument** -- see `tabulated_
verdict()`. The console's Tetra misses coord 274 by 0.4321 u, and that miss is 0.4313 u PERPENDICULAR
to the coord thread, so standing exactly on the tabulated entry does not clip her: the cut ray passes
`resid` +0.3139 u from the seam vertex against an acceptance window ~1.2e-4 u wide. Reaching that
entry to f32 precision was never the hard part; it would not have paid.

THE COORDINATE THE RAZOR LIVES ON. `genuine_clip` needs the cut SEGMENT old->new to thread the gap at
the corner vertex S, so the smooth residual is that segment's signed offset from S:

    pred  = old + roll_step + push + cut_lunge      (the pre-CrrPos endpoint, decomp posMove order)
    resid = cross(pred - old, S - old) / |pred - old|

`genuine` is f32 dust inside a hair of resid == 0. Measured off the 288 tabulated coords at their own
entry: the 279 that still read genuine sit in resid [-3e-6, +1.1e-4] -- about ONE f32 ULP at this
distance from the origin, which is why the tsv is dust and not a region.

WHAT ACTUALLY MOVES IT. `old` is the same wall-braced point almost everywhere (the roll runs into the
corner and CrrPos pins it), so the entry matters ONLY through the CUT-FRAME PUSH -- whether Tetra is
still shoving Link on the frame the cut fires. push 0 gives resid -0.3294 (the bare roll-stab, 0.33 u
short of threading); the tabulated entry's push (-1.115,-0.258) gives +0.3139; genuine wants
~(-0.551,-0.127). From Link's own console endpoint the push is exactly ZERO -- Tetra is out of Co
range by the cut frame -- which is why no knob moves the residual THERE.

WHAT THE SEARCH MUST CARRY (all measured, `_notes/s79_*`):
- **entry precision ~1.0e-4 u** (window / |grad resid| = 1.2e-4 / 1.18), i.e. about one f32 ULP;
- **m351C**, the body lean, is NOT free: 0 and 1 clip, **64 already does not** (resid 1.1e-2), and the
  replayed herd hands Link m351C -191 and a walk that settles near -160. A ctx is only valid for the
  m351C it was built at;
- **link_y does not matter** (the acceptance runs on the geometry's own `LINK_Y`);
- the **roll facing** is a second knob worth ~0.0075 u of locus shift per BAM, so each realizable
  A-press aim has its own locus -- a family of near-parallel curves, not one target.

THE TARGET SET, for a pinned Tetra at the tabulated facing and m351C 0: **1735 genuine entries**, one
thin curve ~104 u long (thickness 0.9 u), every one walkable. **856 of them lie inside the 230 u
follow bar** and are the USABLE target -- past the bar Tetra leaves stt 3 and walks, so an entry out
there is not an entry. `fixtures/courtyard_entry_locus_s79.json` carries them with that flag.

REACHABILITY, measured: continuing the console-confirmed log with its own last stick held walks Link
to **3.06 u** from the usable locus by frame 85, and four other steady sticks pass within 3.8-13.1 u
by frame 82-86, all still at the speedF 17 cap the roll wants. So the target is inside Link's
reachable set and the open work is LANDING on it -- a density problem, not an accuracy one.

HOW TO SIZE THAT DENSITY (session 79's first pass ran and returned 0, by the expected margin). The
figure of merit is ``P(a near-zero candidate is genuine) ~ window / local resid spacing``, and the
spacing must be measured AT ONE FACING over the candidates that actually reach near zero -- taking it
over "the N closest by |resid|" gives a clustered, far-too-good answer (that mistake produced a 0.55
estimate for a population whose real P was 0.11). A stride-2 fan x 8 holds from two base nodes gives
3699 candidates, of which only **4** reach |resid| < 5e-3 at spacing 1.0e-3 -> an expected 0.4 hits.
And **rank the SIGNED distance to the window, not |resid|** (`window_gap`): the window is asymmetric
because its sign is which side of the gap the ray passes, so |resid| scores a blocked-side near-miss
just as highly (the pass's own best candidate was -5.45e-5 -- inside the window's width, on the wrong
side of it).

WHAT SESSION 80 CHANGED, and why the lottery got ~80x better PER CANDIDATE without a bigger fan.
The fidelity gate the s79 handoff left open -- is a real A-press roll the roll the sweep scores? --
turned out to be the thing that was wrong, in three places, all now measured:

  1. **THE ENTRY WAS THE WRONG POINT.** `ShoveCtx`'s ``link_x0`` is Link's position at the END of the
     roll-entry frame; the reseed's step 0 IS the roll's second frame. s79 fed the WALK endpoint, one
     full 26 u roll step short, so every candidate was scored at a place Link never rolls from. See
     `roll_entry` -- and note the consequence: the aim MOVES the entry, so an aim is not just its own
     locus, it is its own candidate.
  2. **THE AIM ALPHABET IS 81 WIDE, NOT 6.** s79 read it off `reachable_stick_fan(msd_min=1.0)`, the
     saturated octagon boundary. Nothing needs that magnitude: the roll takes its speed from the walk
     cap and `_roll_init` snaps facing to the latched target whatever the deflection. Measured, every
     aim in the window fires the roll and lands on the facing it commands. See `aim_alphabet`.
  3. **THE THRUST STEP IS A THIRD DRAW.** 13/14/15 all dispatch a CUT (cut_step 15/16/17) and read
     wildly different residuals at one entry (+2.78 / -0.09 / +0.27), so each bakes an independent
     locus. See `THRUSTS`.

That is ~40x more independent loci, and it is affordable only because `fast_schedule` replaced the
22 ms simulated ctx build with a 0.19 ms analytic one -- the ctx build, not the alphabet, was the
budget. Two things the gate CLEARED rather than found: a real roll arms ``_roll_m3570`` where the
reseed forces it off, and it does contact the wall mid-roll, but the bonk cone never lines up before
the B edge fires (0 of 246 entry x facing rolls differ), so `ShoveCtx` having no crash branch is
exact here; and the reseed's 9 baked tables are bit-identical to a real A-press roll out of a walk.

    python -m harness.tetrapush.entry_search verdict   # the fork measurement (A is dead)
    python -m harness.tetrapush.entry_search window    # the acceptance window off the 288 coords
    python -m harness.tetrapush.entry_search locus     # map the genuine entries (slow; writes json)
    python -m harness.tetrapush.entry_search reach     # replay the log, walk on, distance to locus
    python -m harness.tetrapush.entry_search search    # the fan + the 81 x 3 loci (slow)
"""
import json
import math
import os
import sys
import time
import warnings

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.core import mathlib as ML
from tww_sim.core.fp import f32, fadds, fmuls
from tww_sim.core.anim import body_cyl
from tww_sim.core.cc_push import push_shares, WEIGHT_LINK, WEIGHT_TETRA_V5
from tww_sim.core.npc_zl1 import STT_IDLE
from tww_sim.land.land import LandState, FRONT_ROLL, CUT_F
from tww_sim.land.state import s16_signed
from tww_sim.land.walls import WALL_H, WALL_R, GRAVITY
from harness.rollstab import fast_shove as FS
from harness.rollstab import turnaround as TA
from harness.rollstab import geometry_tetra as GT
from harness.rollstab.cc_stepper import LINK_CO_R, LINK_CO_H, TETRA_CO_R, TETRA_CO_H
from harness.tetrapush import seeds as SD
from harness.tetrapush import two_roll as TR

CONSOLE_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_plan_s73_console.json')
LOCUS_FIXTURE = os.path.join(_rb, 'fixtures', 'courtyard_entry_locus_s79.json')

#: The entry the 288-coord list is valid for (the tsv header; LIVE-measured, NOT the sim walk, which
#: lands 2.6 u away -- `turnaround.entry_from_walk` is not bit-exact from rest).
TAB_ENTRY = (SD.ENTRY_ROLL_POS[0], SD.ENTRY_ROLL_POS[1])
TAB_FACING = SD.ENTRY_ROLL_FACING

#: The escape atom's neutral C-stick freezes the camera here (console-confirmed), so this is the
#: csangle every roll facing is measured against.
CSANGLE = 34325
#: The roll's constant momentum out of the speedF-17 walk cap: clamp(17*1.5 + 0.5, 5, 26) == 26.
ROLL_NSPEED = 26.0
#: Facings worth aiming at: the seam gap's angular window, widened enough to hold the whole alphabet.
AIM_WINDOW = (40400, 41300)
#: Thrust steps that still dispatch a CUT out of this roll schedule -- each bakes its own locus.
THRUSTS = (13, 14, 15)
#: Tetra leaves stt 3 and walks past this, so a walk frame beyond it has not got her pinned any more.
FOLLOW_BAR = 230.0

_CHAIN_CACHE = {}
_CTX_CACHE = {}
_CTX_CACHE_MAX = 8
_M37 = None


def _cut_root_translate():
    """The CUT_F joint-0 root translate at the cut's entry frame ctrl -- a constant."""
    global _M37
    if _M37 is None:
        lk = LandState(pos_x=0.0, pos_z=0.0, pos_y=TA.GROUND_Y, facing=0, travel=0,
                       state=FRONT_ROLL, nspeed=ROLL_NSPEED, speedF=ROLL_NSPEED, use_anim=True,
                       native=False, sword_drawn=True)
        _M37 = lk._cut_m3700_at(CUT_F, lk.CUT_START)
    return _M37


def console_seed(path=CONSOLE_FIXTURE):
    """The LOCKED console read this search seeds from -- a MEASURED state, not a simulated one.
    Returns Tetra's frozen point, Link's endpoint, and the delivered log."""
    d = json.load(open(path))
    by_n = {s['n']: s for s in d['samples']}
    scored = by_n[d['plan']['scored_frames']]
    last = by_n[max(by_n)]
    return dict(tetra=(scored['tetra']['x'], scored['tetra']['z']),
                link=(last['link']['x'], last['link']['z']),
                link_facing=last['link']['facing'], link_speedF=last['link']['speedF'],
                n_scored=scored['n'], n_last=last['n'], log=d['log'],
                placement_idx=d['plan']['placement_idx'],
                placement_dist=d['plan']['placement_dist'])


def resid_fn(sch):
    """The smooth razor coordinate for a baked schedule: the cut ray's signed offset from the seam
    vertex S. Takes one `ShoveCtx.sweep_par` row (genuine, old_x, old_z, new_x, new_z, push_x,
    push_z, ...) and returns u."""
    cs = sch['cut_step']
    mx, mz = sch['dx'][cs] + sch['cutx'][cs], sch['dz'][cs] + sch['cutz'][cs]

    def resid(o):
        dx, dz = mx + o[5], mz + o[6]
        return (dx * (GT.S[1] - o[2]) - dz * (GT.S[0] - o[1])) / math.hypot(dx, dz)
    return resid


def build_at(entry=TAB_ENTRY, facing=TAB_FACING, m351c=0, thrust=TA.THRUST):
    """(ctx, sch, resid) for one (facing, m351C, thrust). The ctx is valid for ANY entry POSITION --
    the baked schedule is position-independent (gated: `test_schedule_is_entry_position_invariant`),
    and `sweep_par` takes link_x0/link_z0 per sample -- but NOT for another facing or m351C."""
    ctx, sch = TA.build_ctx_at(entry, facing, m351c, TA.GROUND_Y, thrust)
    return ctx, sch, resid_fn(sch)


# ------------------------------------------------------------- the roll entry, as the game makes it

def lean_at_roll(m351c):
    """m351C after the roll-ENTRY frame. The entry frame is not MOVE, so `_set_move_slant_angle`
    takes its decay branch once; the reseed must be handed THIS value, not the walk's own (the
    pre-entry value mismatches `chx/chz`)."""
    sv = int(f32(s16_signed(int(m351c) & 0xFFFF) * LandState.SLANT_DECAY))
    return 0 if sv == 0 else ((int(m351c) & 0xFFFF) - sv) & 0xFFFF


def roll_entry(walk_pos, facing):
    """Link's ROLL ENTRY from a walk endpoint: the entry frame moves him one full roll step before
    the schedule's step 0 (which IS the roll's second frame). `_roll_init` takes nspeed from the walk
    cap -- clamp(17*1.5 + 0.5) == 26 exactly -- and snaps travel to the commanded facing, so the step
    is `fadds(p, fmuls(26, sin/cos(facing)))`, bit-exact (gated `test_the_roll_entry_is_the_walk_
    endpoint_plus_one_roll_step`).

    This is the correction that matters most to a search: the aim MOVES the entry 26 u, so each aim
    contributes its own entry as well as its own locus.

    ASSUMES THE ENTRY FRAME DOES NOT BRAKE, which is not always true. `_roll_init` reads the speedF
    that same frame computed, and MOVE runs first: when the aim swings far enough from travel the walk
    decelerates before the roll dispatches and nspeed lands under 26 (measured 18.99, off a speedF
    that had dropped to 12.32). About one candidate-aim pair in eight is affected here, and a few
    plans do not roll at all. So a swept hit is a PREDICTION until `confirm_entry` reproduces it with
    a real A-press -- which is exactly what that function is for."""
    facing = int(facing) & 0xFFFF
    return (fadds(walk_pos[0], fmuls(ROLL_NSPEED, ML.cM_ssin_s16(facing))),
            fadds(walk_pos[1], fmuls(ROLL_NSPEED, ML.cM_scos_s16(facing))))


def fast_schedule(facing, m351c, thrust=TA.THRUST, entry=TAB_ENTRY, link_y=TA.GROUND_Y):
    """`turnaround.extract_schedule_at` WITHOUT the simulation -- 0-ULP identical, ~110x cheaper
    (gated `test_the_analytic_schedule_is_the_simulated_one`).

    A ctx build was 22 ms and all of it was a 17-frame Python coupled roll run to read back numbers
    that never depended on the world; that cost, not the size of the aim alphabet, is what bounds the
    search. The schedule is a pure function of (facing, m351C, thrust): speedF is the constant 26.0
    and travel == facing on every frame including the cut entry, `roll_frame` is the f32 accumulation
    of ROLL_RATE, `_draw_lean` is m351C >> 1 with m351C decaying 35% per frame, the Co chain is a
    direct `roll_co_chain_consts` on those three, the cut lunge is the constant joint-0 root translate
    at CUT_START rotated by the facing, and the cut lands `thrust + 2`."""
    facing = int(facing) & 0xFFFF
    cut_step = int(thrust) + 2
    dxv = fmuls(ROLL_NSPEED, ML.cM_ssin_s16(facing))
    dzv = fmuls(ROLL_NSPEED, ML.cM_scos_s16(facing))
    m37 = _cut_root_translate()
    s_, c_ = ML.cM_ssin_s16(facing), ML.cM_scos_s16(facing)
    cx = f32(f32(m37[2] * s_) + f32(m37[0] * c_))
    cz = f32(f32(m37[2] * c_) - f32(m37[0] * s_))
    dx, dz, cutx, cutz, chx, chz = [], [], [], [], [], []
    rf, lean, nroot = 0.0, int(m351c) & 0xFFFF, None
    for k in range(cut_step + 1):
        rf = f32(rf + LandState.ROLL_RATE)
        draw = s16_signed(lean) >> 1
        lean = lean_at_roll(lean)
        dx.append(dxv)
        dz.append(dzv)
        cutx.append(cx if k == cut_step else 0.0)
        cutz.append(cz if k == cut_step else 0.0)
        row = _CHAIN_CACHE.get((facing, rf, draw))
        if row is None:
            rc, nc = body_cyl.roll_co_chain_consts(facing, rf, shape_z=draw)
            row = ([c[0] for c in rc] + [c[0] for c in nc],
                   [c[1] for c in rc] + [c[1] for c in nc], len(rc))
            _CHAIN_CACHE[(facing, rf, draw)] = row
        chx.append(row[0])
        chz.append(row[1])
        nroot = row[2]
    return dict(dx=dx, dz=dz, cutx=cutx, cutz=cutz, is_pose=[1] * (cut_step + 1), chx=chx, chz=chz,
                nroot=nroot, cut_step=cut_step, link_x0=entry[0], link_z0=entry[1], link_y=link_y,
                tet_seed=(TA.FAR[0], f32(TA.GROUND_Y), f32(FS.FAR_TETRA_Z), facing, 0.0, STT_IDLE))


def build_fast(facing=TAB_FACING, m351c=0, thrust=TA.THRUST, entry=TAB_ENTRY, margin=140.0,
               cache=False):
    """(ctx, sch, resid) off `fast_schedule` -- the search's ctx factory.

    ``cache`` keeps the LAST few builds, which is what a Newton solve wants: `zero_the_resid` asks
    for the SAME (facing, m351C, thrust) once per iteration, and a ShoveCtx copies the whole
    collision mesh, so the cache is deliberately tiny (`_CTX_CACHE_MAX`) rather than unbounded."""
    from tww_sim.core._shovec import ShoveCtx
    key = (int(facing) & 0xFFFF, int(m351c) & 0xFFFF, int(thrust), entry, margin)
    if cache and key in _CTX_CACHE:
        return _CTX_CACHE[key]
    sch = fast_schedule(facing, m351c, thrust, entry)
    sh = push_shares(WEIGHT_LINK, WEIGHT_TETRA_V5)
    ctx = ShoveCtx(TA.WALLS, GT.TRIS, GT.wA.pla, GT.wB.pla, GT.LINK_Y,
                   ML._SIN_TABLE, ML._COS_TABLE, ML._ATN_TABLE,
                   sch['dx'], sch['dz'], sch['cutx'], sch['cutz'], sch['is_pose'],
                   sch['chx'], sch['chz'], sch['nroot'], sch['cut_step'],
                   sch['link_x0'], sch['link_z0'], sch['link_y'],
                   WALL_H, WALL_R, GRAVITY,
                   sch['tet_seed'], FS.TET_WH, FS.TET_R, TA.GROUND_Y,
                   LINK_CO_R, LINK_CO_H, TETRA_CO_R, TETRA_CO_H,
                   sh[1], sh[0], margin=margin)
    out = (ctx, sch, resid_fn(sch))
    if cache:
        if len(_CTX_CACHE) >= _CTX_CACHE_MAX:
            _CTX_CACHE.clear()
        _CTX_CACHE[key] = out
    return out


def aim_alphabet(csangle=CSANGLE, lo=AIM_WINDOW[0], hi=AIM_WINDOW[1], msd_min=0.0):
    """The roll facings this camera can actually deliver, as [(facing, (sx, sy))].

    s79 read this as SIX wide, off `two_roll.reachable_stick_fan(msd_min=1.0)` -- the saturated
    octagon-boundary bytes. That floor is not a physical one: `_set_stick_data` latches the target
    from ANY non-dead-centre stick and `_roll_init` snaps facing to it unconditionally, while the
    roll's speed comes from the walk cap and not from the stick. Measured, every aim in the window
    fires the roll and lands on the facing it commands, so the alphabet is the whole decoded-angle
    grid -- 81 in the seam window, not 6 (gated `test_the_aim_alphabet_is_the_whole_decoded_grid`)."""
    out = []
    for ang, byts in TR.reachable_stick_fan(msd_min=msd_min):
        f = (ang + 0x8000 + int(csangle)) & 0xFFFF
        if lo <= f <= hi:
            out.append((f, byts))
    return sorted(out)


def zero_the_resid(tetra, facing, thrust, lean, start, iters=40, tol=1e-6):
    """Newton the entry along the residual gradient to `resid ~ 0`. Returns (entry, resid, grad).

    A grad that stays ~0 is the diagnostic that this configuration has NO LEVERAGE -- the pushed
    actor is out of Co range on the cut frame, so nothing about the entry moves the razor there."""
    p, g = tuple(start), None
    for _ in range(iters):
        g = entry_gradient(tetra, p, facing=facing, m351c=lean, thrust=thrust)
        if abs(g['resid']) < tol or g['grad'] == 0.0:
            break
        s = g['resid'] / (g['grad'] ** 2)
        p = (p[0] - s * g['gx'], p[1] - s * g['gz'])
    return p, g['resid'], g['grad']


def configuration_band(tetra, facing, thrust, lean, ref_entry, half=0.006, n=1201):
    """THE ACCEPTANCE BAND AT ONE (facing, thrust, lean) -- measured, not inherited.

    The window in `fixtures/courtyard_entry_locus_s79.json` was read off the 288 tabulated coords at
    ONE configuration (facing 40835, thrust 14). It is a UNION, not the target: a single configuration's
    own band is 8e-6 to 5e-5 wide and sits offset from it (all of them positive, ~+2e-5 to +1.2e-4).
    Ranking every configuration against the union overstates the target by 2-10x, which is most of why
    a pass can report a thousand "near-zero" candidates and zero clips.

    Some configurations have no band at all -- either no leverage (grad ~ 0) or simply nothing genuine
    anywhere along the residual zero. Both are worth knowing before spending candidates on them."""
    p, r, grad = zero_the_resid(tetra, facing, thrust, lean, ref_entry)
    if grad < 1e-3 or abs(r) > 1e-3:
        return dict(productive=False, reason='no leverage' if grad < 1e-3 else 'resid will not zero',
                    grad=grad, resid=r, entry=list(p), lo=None, hi=None, width=0.0, n_genuine=0)
    ctx, sch, resid = build_fast(facing, lean, thrust)
    g = entry_gradient(tetra, p, facing=facing, m351c=lean, thrust=thrust)
    ux, uz = g['gx'] / g['grad'], g['gz'] / g['grad']     # sweep ACROSS the locus, not along it
    pts = [(p[0] + (2.0 * i / (n - 1) - 1.0) * half * ux,
            p[1] + (2.0 * i / (n - 1) - 1.0) * half * uz) for i in range(n)]
    ok = [resid(o) for o in ctx.sweep_par([(tetra[0], tetra[1], q[0], q[1]) for q in pts], 0) if o[0]]
    if not ok:
        return dict(productive=False, reason='no genuine on the residual zero', grad=grad,
                    resid=r, entry=list(p), lo=None, hi=None, width=0.0, n_genuine=0)
    return dict(productive=True, reason='', grad=grad, resid=r, entry=list(p),
                lo=min(ok), hi=max(ok), width=max(ok) - min(ok), n_genuine=len(ok))


def qualify(tetra, ref_entry, facings=None, thrusts=THRUSTS, lean=0, csangle=CSANGLE,
            progress=False):
    """Which (facing, thrust) admit a genuine entry locus at all, and where each one's band sits.
    Spending candidates on the rest buys nothing -- it is the cheapest 4x in the search."""
    aims = aim_alphabet(csangle) if facings is None else [(f, None) for f in facings]
    out = []
    for i, (fac, byts) in enumerate(aims):
        for thrust in thrusts:
            b = configuration_band(tetra, fac, thrust, lean, ref_entry)
            b.update(facing=fac, thrust=thrust, aim=list(byts) if byts else None, lean=lean)
            out.append(b)
        if progress and (i + 1) % 20 == 0:
            print("  qualified %d/%d aims: %d productive"
                  % (i + 1, len(aims), sum(1 for b in out if b['productive'])))
    return out


def window_gap(resid, window):
    """The rank the search sorts on: SIGNED distance to the acceptance window, 0 inside it.

    Ranking |resid| is wrong because the window is asymmetric -- its sign is which side of the gap
    the cut ray passes -- so |resid| scores a blocked-side near-miss as highly as a live one. s79's
    best candidate was -5.45e-5, inside the window's WIDTH and on the wrong side of it."""
    if resid < window['lo']:
        return window['lo'] - resid
    if resid > window['hi']:
        return resid - window['hi']
    return 0.0


def evaluate(ctx, resid, tetra, entries):
    """Score a list of entry (x, z) against a pinned Tetra -> [(entry, genuine, resid, push)]."""
    rows = ctx.sweep_par([(tetra[0], tetra[1], e[0], e[1]) for e in entries], 0)
    return [(e, bool(o[0]), resid(o), (o[5], o[6])) for e, o in zip(entries, rows)]


# ------------------------------------------------------------------------------------- the search
# The lottery is countable: candidates reached x INDEPENDENT loci drawn against. See the KB page.

def walk_fan(seed=None, env=None, base_frames=(3, 4), stride=2, jmax=8, progress=False):
    """The reachable set: distinct ``(walk endpoint, m351C)`` Link can stand on with the walk cap
    still under him, continuing the console-confirmed log.

    The atom is "hold stick S for j frames" -- a single fanned frame is INERT, because `INPUT_DELAY`
    2 buffers it and the fan collapses to one child. Two prunes, both hard: speedF must be exactly
    17.0 (the roll takes its whole nspeed from the walk cap) and Link must stay inside the 230 u
    follow bar on EVERY frame, since one frame outside starts Tetra turning and she is only a
    measured constant while she is idle."""
    seed = seed or console_seed()
    env = env or SD.load_env()
    hold = dict(seed['log'][-1], buttons=0)
    tx, tz = seed['tetra']
    out = {}
    for n0 in base_frames:
        base, _ = continue_walk([hold] * n0, env=env)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            for sx in range(0, 256, stride):
                for sy in range(0, 256, stride):
                    c = base.clone()
                    inp = dict(hold, stickX=sx, stickY=sy)
                    for j in range(jmax + 1):
                        c.step(inp)
                        lk = c.link
                        if math.hypot(lk.pos_x - tx, lk.pos_z - tz) > FOLLOW_BAR:
                            break                      # she is moving from here on: branch is dead
                        # `INPUT_DELAY`: the endpoint after j+1 steps is the one a plan of j
                        # DELIVERED frames rolls from (measured; gated in test_entry_search)
                        if j >= 1 and lk.speedF == 17.0:
                            out[(lk.pos_x, lk.pos_z, lk.m351C & 0xFFFF)] = (n0, sx, sy, j)
            if progress:
                print("  fan from n0=%d: %d distinct (endpoint, lean)" % (n0, len(out)))
    return out


def search(candidates=None, facings=None, thrusts=THRUSTS, seed=None, window=None, keep=60,
           csangle=CSANGLE, progress=False, **fan_kw):
    """Score every (walk endpoint x aim x thrust) and return the genuine ones.

    Each aim contributes TWICE: it moves the entry 26 u (`roll_entry`) and it bakes its own locus.
    Ranking is `window_gap`, the signed distance to the acceptance window -- never |resid|."""
    seed = seed or console_seed()
    if candidates is None:
        candidates = walk_fan(seed=seed, progress=progress, **fan_kw)
    tx, tz = seed['tetra']
    if facings is None:
        # spend candidates only where a locus exists, and score each configuration against ITS OWN
        # band -- the fixture window is a union over configurations and overstates the target 2-10x
        ref = min((h for h in load_locus()['hits'] if h['follow_ok']),
                  key=lambda h: math.hypot(h['entry'][0] - seed['link'][0],
                                           h['entry'][1] - seed['link'][1]))['entry']
        quals = [q for q in qualify(seed['tetra'], tuple(ref), thrusts=thrusts, csangle=csangle,
                                    progress=progress) if q['productive']]
    else:
        quals = [dict(facing=f, thrust=t, aim=None, lo=None, hi=None)
                 for f in facings for t in thrusts]
    fallback = window or load_locus()['window']
    if progress:
        print("  %d productive (facing, thrust) configurations" % len(quals))

    by_lean = {}
    for k, plan in candidates.items():
        by_lean.setdefault(lean_at_roll(k[2]), []).append((k, plan))
    hits, near, t0 = [], [], time.time()
    for fi, q in enumerate(quals):
        fac, byts, thrust = q['facing'], q['aim'], q['thrust']
        window = q if q.get('lo') is not None else fallback
        for lean, group in by_lean.items():
            ctx, sch, resid = build_fast(fac, lean, thrust)
            ents = [roll_entry((k[0], k[1]), fac) for k, _ in group]
            rows = ctx.sweep_par([(tx, tz, e[0], e[1]) for e in ents], 0)
            for (k, plan), e, o in zip(group, ents, rows):
                r = resid(o)
                g = window_gap(r, window)
                if o[0]:
                    # no wall collision in the courtyard sim: a point behind a seam wall is unreachable
                    hits.append(dict(entry=[e[0], e[1]], walk=[k[0], k[1]], m351C_walk=k[2],
                                     m351C=lean, facing=fac, aim=list(byts) if byts else None,
                                     thrust=thrust, b_step=thrust + 2, resid=r, gap=g,
                                     push=[o[5], o[6]], plan=list(plan),
                                     walkable=bool(TA.is_walkable(k[0], k[1])
                                                   and TA.is_walkable(e[0], e[1]))))
                elif g < 5e-3:
                    near.append(g)
        if progress and (fi + 1) % 10 == 0:
            print("  %d/%d configurations: %d genuine, %d within gap 5e-3  [%.0fs]"
                  % (fi + 1, len(quals), len(hits), len(near), time.time() - t0))
    walkable = [h for h in hits if h['walkable']]
    walkable.sort(key=lambda h: (h['plan'][0] + h['plan'][3], abs(h['resid'])))
    near.sort()
    return dict(hits=walkable, n_hits_raw=len(hits), n_candidates=len(candidates),
                n_leans=len(by_lean), n_configurations=len(quals), n_thrusts=len(thrusts),
                n_near=len(near), near=near[:keep], seconds=time.time() - t0,
                configurations=[dict(facing=q['facing'], thrust=q['thrust'], lo=q.get('lo'),
                                     hi=q.get('hi')) for q in quals])


def confirm_entry(hit, seed=None, env=None):
    """Close the loop the fan leaves open: it never presses A, it PREDICTS the entry from the walk
    endpoint. Replay the console log, the hit's own plan, then a REAL A-press with its aim bytes on
    the courtyard engine, and read the roll entry back.

    Returns the measured entry beside the predicted one plus the bit-equality flags. Anything False
    means the hit is scored at a point Link does not roll from -- the s79 failure, one level down."""
    seed = seed or console_seed()
    n0, sx, sy, j = hit['plan']
    hold = dict(seed['log'][-1], buttons=0)
    extra = [hold] * n0 + [dict(hold, stickX=sx, stickY=sy)] * j
    extra.append(dict(hold, stickX=hit['aim'][0], stickY=hit['aim'][1], buttons=0x100))
    extra += [dict(hold, stickX=128, stickY=128)] * 3          # INPUT_DELAY 2, then the entry frame
    run, rows = continue_walk(extra, env=env)
    walk = next((r for r in rows if r['proc'] == FRONT_ROLL), None)
    k = rows.index(walk) if walk else None
    prev = rows[k - 1] if k else None
    got = dict(entry=(walk['x'], walk['z']) if walk else None,
               facing=walk['facing'] if walk else None,
               m351C=walk['m351C'] if walk else None,
               walk=(prev['x'], prev['z']) if prev else None,
               speedF=prev['speedF'] if prev else None,
               procs=[r['proc'] for r in rows[-5:]])
    ok = dict(rolled=walk is not None,
              walk_matches=bool(prev) and [prev['x'], prev['z']] == hit['walk'],
              capped=bool(prev) and prev['speedF'] == 17.0,
              facing=bool(walk) and walk['facing'] == hit['facing'],
              lean=bool(walk) and walk['m351C'] == hit['m351C'],
              entry=bool(walk) and [walk['x'], walk['z']] == hit['entry'])
    return dict(measured=got, predicted=dict(entry=hit['entry'], facing=hit['facing'],
                                             m351C=hit['m351C'], walk=hit['walk']),
                ok=ok, all_ok=all(ok.values()))


def acceptance_window(placements=None):
    """The genuine `resid` band, MEASURED off the tabulated coords at their own entry rather than
    assumed. Returns dict(lo, hi, width, n_genuine, n_total, miss_lo, miss_hi)."""
    rows = placements if placements is not None else SD.load_placements()[0]
    ctx, sch, resid = build_at()
    scored = ctx.sweep_par([(r['x'], r['z'], TAB_ENTRY[0], TAB_ENTRY[1]) for r in rows], 0)
    ok = [resid(o) for o in scored if o[0]]
    no = [resid(o) for o in scored if not o[0]]
    return dict(lo=min(ok), hi=max(ok), width=max(ok) - min(ok), n_genuine=len(ok),
                n_total=len(rows), miss_lo=(min(no) if no else None),
                miss_hi=(max(no) if no else None),
                miss_idx=[r['idx'] for r, o in zip(rows, scored) if not o[0]])


def tabulated_verdict(seed=None, placements=None):
    """**THE FORK MEASUREMENT.** Stand Link exactly on the tabulated entry the coord list is valid
    for and fire the clip at the console's own Tetra. Returns the residual, the genuine flag, and the
    perpendicular half of her miss on the nearest coord -- the three numbers that kill route (A)."""
    seed = seed or console_seed()
    rows = placements if placements is not None else SD.load_placements()[0]
    ctx, sch, resid = build_at()
    o = ctx.sweep_par([(seed['tetra'][0], seed['tetra'][1], TAB_ENTRY[0], TAB_ENTRY[1])], 0)[0]
    idx = seed['placement_idx']
    c = next(r for r in rows if r['idx'] == idx)
    # split her miss into along-thread and perpendicular, using the local thread direction
    nxt = next(r for r in rows if r['idx'] == idx + 1)
    ux, uz = nxt['x'] - c['x'], nxt['z'] - c['z']
    n = math.hypot(ux, uz)
    ux, uz = ux / n, uz / n
    dx, dz = seed['tetra'][0] - c['x'], seed['tetra'][1] - c['z']
    along = dx * ux + dz * uz
    perp = math.hypot(dx - along * ux, dz - along * uz)
    return dict(genuine=bool(o[0]), resid=resid(o), push=(o[5], o[6]), old=(o[1], o[2]),
                coord_idx=idx, miss=math.hypot(dx, dz), miss_along=along, miss_perp=perp)


def genuine_entries(tetra, *, facing=TAB_FACING, m351c=0, centre=None, half=130.0,
                    coarse=0.5, fine=0.002, tol=0.05, thrust=TA.THRUST, progress=False):
    """Map the genuine ENTRY set for a pinned Tetra: coarse-sweep the smooth residual, keep the
    cells within `tol` of zero, then refine those to the f32 dust. Blind fine sweeping does not work
    -- the window is ~1 ULP wide, so a 0.25 u grid over a 120 u box finds 1 hit in 231k."""
    ctx, sch, resid = build_at(TAB_ENTRY, facing, m351c, thrust)
    if centre is None:
        centre = TAB_ENTRY
    n = int(half / coarse)
    keys = [(centre[0] + i * coarse, centre[1] + j * coarse)
            for i in range(-n, n + 1) for j in range(-n, n + 1)]
    seeds_ = [k for k, o in zip(keys, ctx.sweep_par(
        [(tetra[0], tetra[1], k[0], k[1]) for k in keys], 0)) if abs(resid(o)) < tol]
    if progress:
        print("  coarse %d -> %d seed cells" % (len(keys), len(seeds_)))
    m = int(coarse / fine) // 2
    hits = []
    for c, k in enumerate(seeds_):
        pts = [(tetra[0], tetra[1], k[0] + i * fine, k[1] + j * fine)
               for i in range(-m, m + 1) for j in range(-m, m + 1)]
        for p, o in zip(pts, ctx.sweep_par(pts, 0)):
            if o[0]:
                hits.append(dict(entry=[p[2], p[3]], resid=resid(o), push=[o[5], o[6]]))
        if progress and (c + 1) % 50 == 0:
            print("  refined %d/%d cells, %d genuine" % (c + 1, len(seeds_), len(hits)))
    return hits


def locus_metrics(hits, seed=None):
    """Shape of a `genuine_entries` result: principal axis, extent, thickness, and the reachability
    numbers (distance from Link's console endpoint, distance to Tetra vs the 230 u follow bar)."""
    seed = seed or console_seed()
    pts = [tuple(h['entry']) for h in hits]
    xs, zs = [p[0] for p in pts], [p[1] for p in pts]
    mx, mz = sum(xs) / len(xs), sum(zs) / len(zs)
    sxx = sum((x - mx) ** 2 for x in xs)
    szz = sum((z - mz) ** 2 for z in zs)
    sxz = sum((x - mx) * (z - mz) for x, z in zip(xs, zs))
    th = 0.5 * math.atan2(2 * sxz, sxx - szz)
    ux, uz = math.cos(th), math.sin(th)
    ts = sorted((p[0] - mx) * ux + (p[1] - mz) * uz for p in pts)
    ps = [abs((p[0] - mx) * -uz + (p[1] - mz) * ux) for p in pts]
    dl = sorted(math.hypot(p[0] - seed['link'][0], p[1] - seed['link'][1]) for p in pts)
    dt = sorted(math.hypot(p[0] - seed['tetra'][0], p[1] - seed['tetra'][1]) for p in pts)
    return dict(n=len(pts), axis=(ux, uz),
                axis_bam=math.degrees(math.atan2(ux, uz)) % 360 / 360 * 65536,
                extent=ts[-1] - ts[0], thickness=max(ps), centroid=(mx, mz),
                d_link=(dl[0], dl[-1]), d_tetra=(dt[0], dt[-1]),
                walkable=sum(1 for p in pts if TA.is_walkable(p[0], p[1])),
                follow_ok=sum(1 for d in dt if d <= 230.0))


def entry_gradient(tetra, entry, *, facing=TAB_FACING, m351c=0, d=0.01, thrust=TA.THRUST):
    """|d resid / d entry| at a point, and the entry precision it implies for a given window.

    Builds the ANALYTIC ctx (0-ULP identical to the simulated one -- `test_the_analytic_schedule_is_
    the_simulated_one`) and caches it: this runs once per Newton iteration inside `zero_the_resid`,
    and at the simulated 22 ms build a single `configuration_band` cost ~0.9 s, which is what made
    qualifying 243 configurations a 269 s job."""
    ctx, sch, resid = build_fast(facing, m351c, thrust, TAB_ENTRY, cache=True)
    q = ctx.sweep_par([(tetra[0], tetra[1], entry[0], entry[1]),
                       (tetra[0], tetra[1], entry[0] + d, entry[1]),
                       (tetra[0], tetra[1], entry[0], entry[1] + d)], 0)
    r0 = resid(q[0])
    gx, gz = (resid(q[1]) - r0) / d, (resid(q[2]) - r0) / d
    return dict(resid=r0, gx=gx, gz=gz, grad=math.hypot(gx, gz))


def continue_walk(extra, *, log=None, env=None):
    """Replay the console-confirmed delivered log on a fresh `FreeRun`, then keep stepping `extra`
    (a list of raw input dicts). Returns (run, rows) with one row per EXTRA frame -- the reachability
    probe, seeded from the measured endpoint the handoff asks for."""
    seed = console_seed()
    env = env or SD.load_env()
    run = SD.make_freerun(env)
    run.pre_seed_input(SD.dtm_input_at(env)(0))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for inp in (log if log is not None else seed['log']):
            run.step(inp)
        n0 = len(seed['log'])
        for k, inp in enumerate(extra):
            run.step(inp)
            lk = run.link
            rows.append(dict(n=n0 + k + 1, x=lk.pos_x, z=lk.pos_z, facing=lk.facing & 0xFFFF,
                             proc=lk.state & 0xFF, speedF=lk.speedF,
                             m351C=getattr(lk, 'm351C', 0) & 0xFFFF,
                             csangle=getattr(lk, 'csangle', 0) & 0xFFFF))
    return run, rows


def load_locus(path=LOCUS_FIXTURE):
    return json.load(open(path))


# --------------------------------------------------------------------------- CLI

def _cmd_verdict():
    seed = console_seed()
    v = tabulated_verdict(seed)
    w = acceptance_window()
    print("THE s45 FORK, MEASURED (session 79)\n")
    print("  console Tetra          (%r, %r)  frozen on frames %d..%d"
          % (seed['tetra'][0], seed['tetra'][1], seed['n_scored'], seed['n_last']))
    print("  nearest genuine coord  idx %d, %.4f u away" % (v['coord_idx'], v['miss']))
    print("     of which ALONG the thread %+.4f u, PERPENDICULAR %.4f u" % (v['miss_along'], v['miss_perp']))
    print("  acceptance window      resid [%+.2e, %+.2e]  (%d/%d tabulated coords re-read genuine)"
          % (w['lo'], w['hi'], w['n_genuine'], w['n_total']))
    print("\n  AT THE TABULATED ENTRY (%r, %r) facing %d:" % (TAB_ENTRY + (TAB_FACING,)))
    print("     resid %+.6f u   push (%+.5f, %+.5f)   genuine = %s"
          % (v['resid'], v['push'][0], v['push'][1], v['genuine']))
    print("\n  => route (A) -- walk to the tabulated entry -- is DEAD: standing exactly on it misses")
    print("     the seam by %.0fx the window. Route (B), re-solving the clip at the herd's own"
          % (abs(v['resid']) / w['width']))
    print("     endpoint, is the live one; the ENTRY becomes the razor knob.")


def _cmd_window():
    w = acceptance_window()
    print("acceptance window, measured off the %d tabulated coords at their own entry:" % w['n_total'])
    print("  genuine  n=%d   resid %+.3e .. %+.3e   (width %.2e u)"
          % (w['n_genuine'], w['lo'], w['hi'], w['width']))
    print("  NOT      n=%d   resid %+.3e .. %+.3e   idx %s"
          % (w['n_total'] - w['n_genuine'], w['miss_lo'], w['miss_hi'], w['miss_idx']))
    print("  (the two overlap -- the boundary is f32 dust, which is what makes this a lottery)")


def _cmd_locus(argv):
    half = float(argv[0]) if argv else 130.0
    seed = console_seed()
    hits = genuine_entries(seed['tetra'], half=half, progress=True)
    m = locus_metrics(hits, seed)
    print("\n%d genuine entries" % m['n'])
    print("  axis %.0f BAM   extent %.2f u   thickness %.3f u   centroid (%.3f,%.3f)"
          % (m['axis_bam'], m['extent'], m['thickness'], m['centroid'][0], m['centroid'][1]))
    print("  d(Link console endpoint) %.2f..%.2f u   d(Tetra) %.2f..%.2f u (bar 230)"
          % (m['d_link'] + m['d_tetra']))
    print("  walkable %d/%d   inside the follow bar %d/%d"
          % (m['walkable'], m['n'], m['follow_ok'], m['n']))
    out = os.path.join(_rb, '_generated', 's79', 'entry_locus.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(facing=TAB_FACING, m351c=0, tetra=list(seed['tetra']), hits=hits, metrics=
                   {k: (list(v) if isinstance(v, tuple) else v) for k, v in m.items()}),
              open(out, 'w'))
    print("  wrote %s" % out)


def _cmd_reach(argv):
    n = int(argv[0]) if argv else 10
    seed = console_seed()
    loc = load_locus() if os.path.exists(LOCUS_FIXTURE) else None
    # the USABLE subset only -- an entry outside the follow bar is not an entry
    pts = [tuple(h['entry']) for h in loc['hits'] if h.get('follow_ok', True)] if loc else []

    def dloc(x, z):
        return min(math.hypot(x - p[0], z - p[1]) for p in pts) if pts else float('nan')

    last = dict(seed['log'][-1])
    sticks = [('hold last', (last['stickX'], last['stickY'])), ('N', (128, 255)),
              ('NE', (219, 219)), ('E', (255, 128)), ('SE', (219, 37))]
    print("reachability from the console-measured endpoint (frame %d), %d extra frames:\n"
          % (seed['n_last'], n))
    for name, (sx, sy) in sticks:
        inp = dict(last, stickX=sx, stickY=sy, buttons=0)
        _, rows = continue_walk([inp] * n)
        best = min(rows, key=lambda r: dloc(r['x'], r['z']))
        print("  %-10s closest at frame %d: (%12.5f,%12.5f) d(locus) %7.3f u  m351C %5d csangle %d"
              % (name, best['n'], best['x'], best['z'], dloc(best['x'], best['z']),
                 best['m351C'], best['csangle']))


def _cmd_search(argv):
    stride = int(argv[0]) if argv else 8
    jmax = int(argv[1]) if len(argv) > 1 else 10
    fan = walk_fan(base_frames=tuple(range(7)), stride=stride, jmax=jmax, progress=True)
    print("FAN: %d distinct (endpoint, lean)" % len(fan))
    r = search(candidates=fan, progress=True)
    print("\n%d candidates x %d aims x %d thrusts over %d lean groups, %.0f s"
          % (r['n_candidates'], r['n_aims'], r['n_thrusts'], r['n_leans'], r['seconds']))
    print("  near-zero (gap < 5e-3): %d      GENUINE: %d" % (r['n_near'], len(r['hits'])))
    for h in r['hits'][:20]:
        print("  n0=%d hold (%3d,%3d) x%d  aim %s facing %5d thrust %2d  entry (%r,%r) resid %+.3e"
              % (h['plan'][0], h['plan'][1], h['plan'][2], h['plan'][3], h['aim'], h['facing'],
                 h['thrust'], h['entry'][0], h['entry'][1], h['resid']))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else 'verdict'
    if cmd == 'verdict':
        _cmd_verdict()
    elif cmd == 'window':
        _cmd_window()
    elif cmd == 'locus':
        _cmd_locus(argv)
    elif cmd == 'reach':
        _cmd_reach(argv)
    elif cmd == 'search':
        _cmd_search(argv)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
