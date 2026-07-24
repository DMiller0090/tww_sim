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
"""Native-fleet BFS for the Courtyard on-line reposition (session 38).

The pre-performance blocker (`[[courtyard-tetra-push]]`, `[[tetrapush-frame-minimal]]`): the
frame-minimal cycle (turnaround -> proc-7 +18 flip -> talk-safe +26 roll aimed ALONG the herd
line -> release L 1 frame early for the -25.727 EBS glide) is a self-stabilising PURSUIT only when
Link is ON the herd line DIRECTLY behind Tetra. The hand-composed `reposition.frame_min_reroll`
leaves Link ~15 u laterally off-line, so the straight roll crosses her path and OVERSHOOTS. Session
37 made the whole coupled step native (`LandCore.step_courtyard`, 1.06M steps/s on the OpenMP fleet),
so a genuine state-space search over the reposition is now affordable.

This module is that search. It runs a beam BFS whose frontier is a set of native `FreeRun` nodes
(each wrapping a `LandCore`); a generation is expanded by fanning every (node, candidate-input)
child through `CourtyardFleet.run_par` ONE frame in parallel, syncing the public C fields back, then
pruning off-line/past-Tetra (`reposition.HerdLine.on_line_ok`), talk-unsafe (`search.a_press_is_talk`),
and out-of-regime (the follow guard) nodes, deduping by a quantized state tag, and keeping the
top-`beam` by frame-minimal score (down-herd achieved minus a per-frame cost). Roll count is NOT
capped (more rolls = optimal, Dereck s35): a roll is just what the alphabet produces when an A-press
fires talk-safe.

Fidelity: the frontier step is `LandCore.step_courtyard(native_push=1)`, gated 0-ULP vs the Python
`from_f0.FreeRun` over the DTM window (`test_freerun_native`), and the fleet is bit-identical
parallel-vs-sequential (`test_courtyard_fleet_native`). This module adds its own gate
(`test_native_search`) that a degenerate 1-wide frontier replaying the recorded stream reproduces the
FreeRun rollout 0-ULP, so the search reads state exactly. Any winning plan is bit-confirmed on a
FRESH Python-stepped `FreeRun` (`bit_confirm`).

CLI: ``python -m harness.tetrapush.native_search {selfcheck|search} [k=v ...]``.
"""
import math

from harness.tetrapush import seeds
from harness.tetrapush import search as S
from harness.tetrapush import primitives as P
from harness.tetrapush.reposition import HerdLine, ESS_DOWN
from harness.tetrapush.from_f0 import FreeRun, FOLLOW_ENGAGE_DIST
from tww_sim.core.anim import _anmc as N
from tww_sim.land.land import FRONT_ROLL
from tww_sim.land.plan_land._primitives import stick_for_bearing


# =============================================================================== fleet frame-step

def _sync(run, csangle):
    """Sync a native `FreeRun`'s Python-side view (`run.link` scalars, `run.tx/tz`, the pend pair,
    the FOLLOW guard) from its `LandCore` after a fleet step -- the exact block `from_f0._step_native`
    runs, so `search.a_press_is_talk` / `reposition.on_line_ok` read the same values as in Python
    mode."""
    c = run._core
    l = run.link
    l.pos_x = c.pos_x
    l.pos_z = c.pos_z
    l.facing = c.facing
    l.travel = c.travel
    l.speedF = c.speedF
    l.nspeed = c.nspeed
    l.state = c.state
    run.tx = c._tetra_x
    run.tz = c._tetra_z
    run.pend_link = (c._pend_link_x, c._pend_link_z)
    run.pend_tetra = (c._pend_tetra_x, c._pend_tetra_z)
    run.csangle = int(csangle) & 0xFFFF
    if not run._follow_warned:
        dist = math.sqrt((l.pos_x - run.tx) ** 2 + (l.pos_y - run.ty) ** 2
                         + (l.pos_z - run.tz) ** 2)
        if dist > FOLLOW_ENGAGE_DIST:
            run._follow_warned = True


def _row(d, cs):
    """One CourtyardFleet schedule frame from a delivered-input dict + csangle."""
    return (int(d['stickX']), int(d['stickY']), int(d.get('buttons', 0)),
            int(d.get('triggerL', 0)), int(cs) & 0xFFFF)


def batch_step(items, nthreads=0):
    """Step a batch of ``(run, input_dict, csangle)`` one frame each, all in ONE
    `CourtyardFleet.run_par`, then sync every run. ``run`` must be a native `FreeRun` (its `_core`
    is borrowed by the fleet). Bit-identical to stepping each run's `.step` individually (the fleet
    gate); this is the search's parallel expansion primitive."""
    if not items:
        return
    cores = [it[0]._core for it in items]
    fleet = N.CourtyardFleet(cores, native_push=1)
    fleet.set_schedule([[_row(d, cs)] for (_, d, cs) in items])
    fleet.run_par(1, nthreads)
    for (run, d, cs) in items:
        _sync(run, cs)


# =============================================================================== nodes

class Node:
    """A search node: a native `FreeRun` at some state + a back-pointer chain recording the
    (input, csangle) that produced it, so `reconstruct` can rebuild the full input sequence from
    the root for the bit-confirm."""
    __slots__ = ('run', 'parent', 'action', 'depth', 'nroll', 'released')

    def __init__(self, run, parent, action, depth, nroll, released=False):
        self.run = run
        self.parent = parent
        self.action = action           # (input_dict, csangle) or None at the root
        self.depth = depth
        self.nroll = nroll             # rolls completed so far (diagnostic; NOT a cap)
        self.released = released        # in-roll: has the mid-roll lock-L been dropped yet


def reconstruct(node):
    """Walk parents to the root, returning the ordered list of ``(input_dict, csangle)`` that drives
    a fresh run from the root state to ``node`` (the root's own action is excluded)."""
    seq = []
    n = node
    while n is not None and n.action is not None:
        seq.append(n.action)
        n = n.parent
    seq.reverse()
    return seq


# =============================================================================== the root (cyc1)

def seed_root(env):
    """Build the native frontier ROOT: a native `FreeRun` at the state-2 f0 seed, pre-seeded with the
    delay-1 controller buffer (the recorded f0 input, so the first stepped frame acts on it -- the
    from-f0 convention). The BFS discovers the WHOLE push (cyc1 + every reposition + roll) inside the
    stripped sim: the recorded human's inputs are NOT a valid pursuit template here (the stripped
    feet-aim facing diverges from the full camera+eye sim mid-roll, s34), so the search must find its
    own on-line chain. Returns ``(root_node, prologue)`` with ``prologue`` empty (a plan is just
    ``reconstruct(goal)`` from state 2)."""
    run = seeds.make_freerun_native(env)
    run.pre_seed_input(seeds.dtm_input_at(env)(0))
    return Node(run, None, None, 0, 0), []


# =============================================================================== action alphabet

def _turnaround_csangles(step=1024):
    """Coarse BAM-circle sweep of the turnaround snap-window csangle (`reposition.turnaround`): a
    precise csangle makes the facing chase cross travel in one frame; the search keeps the survivor."""
    return list(range(0, 65536, step))


def reposition_actions(run, hl, *, csangle, turn_step=1024, msd=1.0):
    """The per-frame candidate inputs for a grounded (reposition) frame. Sound, compact alphabet
    keyed on geometry -- NOT the raw 255x255 stick space:

      * GLIDE   -- slight held stick down-herd, no buttons: continue the -25.7 EBS backslide.
      * TURN    -- ESS-down with each candidate csangle (the 1-frame-180 snap lever, `reposition.
                   turnaround`); the search keeps whichever snaps Link on-line.
      * FLIP    -- L held + stick toward Tetra (down-herd): the proc-7 DIR_BACKWARD +18 flip that
                   arms a fast (+26) roll. Only when Tetra is OUT of the front cone (else L hard-
                   locks to proc-9).
      * ROLL    -- A + stick along the herd line: the +26 pursuit roll. Emitted ONLY when talk-safe
                   (`a_press_is_talk` False at the delivery state) -- a roll-A in Tetra's cone TALKS.

    `csangle` is the currently-held camera yaw (injected); GLIDE/FLIP/ROLL hold it, TURN sweeps it.
    Returns a list of ``(input_dict, csangle, kind)``."""
    down = hl.bearing_bam()                                  # aim ALONG the herd line (down-herd)
    away = (down + 0x8000) & 0xFFFF
    out = []

    # GLIDE: keep the EBS alive (a slight held stick down-herd; a truly-neutral stick brakes to 0).
    gx, gy = stick_for_bearing(down, csangle, msd=0.35)
    out.append((dict(stickX=gx, stickY=gy, buttons=0, triggerL=0, substickX=128, substickY=128),
                csangle, 'glide'))

    # TURN: ESS-down at each candidate csangle (the instant-180 snap; keep only ones that flip).
    for cs in _turnaround_csangles(turn_step):
        out.append((dict(stickX=ESS_DOWN[0], stickY=ESS_DOWN[1], buttons=0, triggerL=0,
                         substickX=128, substickY=128), cs, 'turn'))

    # FLIP: L + stick toward Tetra (arms the +26 roll). Facing-away frames only make this useful,
    # but it is always sound to emit -- if Tetra is in cone it just locks (pruned later if it stalls).
    fx, fy = stick_for_bearing(down, csangle, msd=msd)
    out.append((dict(stickX=fx, stickY=fy, buttons=0x40, triggerL=255, substickX=128, substickY=128),
                csangle, 'flip'))

    # ROLL: A + stick along the herd line. Talk-safe only.
    rx, ry = stick_for_bearing(down, csangle, msd=msd)
    d_roll = dict(stickX=rx, stickY=ry, buttons=0x100, triggerL=0, substickX=128, substickY=128)
    if not S.a_press_is_talk(run, d_roll):
        out.append((d_roll, csangle, 'roll'))

    # Also allow a lateral nudge either side to correct the ~15 u off-line drift (steer the EBS
    # onto the line): stick offset +-0x2000 from down-herd.
    for rel, tag in ((0x2000, 'lat+'), (-0x2000, 'lat-')):
        lx, ly = stick_for_bearing((down + rel) & 0xFFFF, csangle, msd=msd)
        out.append((dict(stickX=lx, stickY=ly, buttons=0, triggerL=0, substickX=128, substickY=128),
                    csangle, tag))
    return out, away


def roll_actions(run, hl, *, csangle, release, msd=1.0):
    """During a FRONT_ROLL the alphabet collapses: the facing is locked, so the only decision is
    when to RELEASE the mid-roll lock-L (steer #2/#3 -- release 1 frame early to retain -25.727).
    ``release`` = the current release policy for this node (a bool that, once True, stays True). We
    branch it exactly ONCE (hold-vs-release) per node; after release there is a single action, so a
    roll adds a LINEAR (not exponential) branch. Stick is pinned along the herd line."""
    down = hl.bearing_bam()
    sx, sy = stick_for_bearing(down, csangle, msd=msd)
    rf = getattr(run._core, 'roll_frame', 0.0)
    acts = []
    if not release:
        # hold L this frame (keep the lock)
        acts.append((dict(stickX=sx, stickY=sy, buttons=0x40, triggerL=255,
                          substickX=128, substickY=128), csangle, 'roll_hold'))
        # OR release now (drop L) -- the branch point
        if rf > 1.0:
            acts.append((dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                              substickX=128, substickY=128), csangle, 'roll_release'))
    else:
        acts.append((dict(stickX=sx, stickY=sy, buttons=0, triggerL=0,
                          substickX=128, substickY=128), csangle, 'roll_release'))
    return acts


# =============================================================================== the beam BFS

class RepositionSearch:
    """Beam BFS over the reposition, frontier = native `FreeRun` nodes, expanded a frame at a time
    through `CourtyardFleet.run_par`. Frame-minimal objective: maximise Tetra's down-herd distance
    per total frame while staying a behind-Tetra pursuit (never overtake) and in the stt-3 plow
    regime; roll count is uncapped. See the module docstring."""

    def __init__(self, env, *, beam=200, lat_w=0.15, max_lead=4.0,
                 max_lateral=220.0, turn_step=1024, nthreads=0,
                 goal_along=None, gens=60, verbose=True):
        self.env = env
        self.hl = HerdLine.from_env(env)
        self.beam = beam
        self.lat_w = lat_w
        self.max_lead = max_lead
        self.max_lateral = max_lateral
        self.turn_step = turn_step
        self.nthreads = nthreads
        self.gens = gens
        self.verbose = verbose
        self.placements, _ = seeds.load_placements()
        cx = sum(p['x'] for p in self.placements) / len(self.placements)
        cz = sum(p['z'] for p in self.placements) / len(self.placements)
        self.goal_along = goal_along if goal_along is not None \
            else self.hl.along(cx, cz)                       # cluster centroid down-herd (~967 u)
        self.best = None                                     # (score, along, node)

    # ---- per-node geometry ------------------------------------------------
    def _geo(self, run):
        lx, lz = run.link.pos_x, run.link.pos_z
        tx, tz = run.tx, run.tz
        along = self.hl.along(tx, tz)
        lead = self.hl.lead(lx, lz, tx, tz)
        lat = self.hl.lateral(lx, lz) - self.hl.lateral(tx, tz)
        dist = math.hypot(lx - tx, lz - tz)
        return along, lead, lat, dist

    def _score(self, run, depth):
        """Beam rank within a generation (all nodes share depth in synchronous BFS, so frame-cost is
        constant and omitted here): make down-herd PROGRESS while staying near the line. The
        frame-minimal comparison is applied to COMPLETE waypoints in `_waypoint`, not the frontier."""
        along, lead, lat, dist = self._geo(run)
        return along - self.lat_w * abs(lat)

    def _waypoint(self, run, depth):
        """Is this an on-line pursuit waypoint (behind Tetra, on the line, in-regime), and its
        frame-minimal rate (down-herd per frame from state 2)? The reported 'best' is the deepest-herd
        such waypoint -- a real, re-rollable pursuit state, not a lateral-drift artifact."""
        along, lead, lat, dist = self._geo(run)
        ok = (-110.0 <= lead <= -5.0) and abs(lat) <= 22.0 and not run._follow_warned
        return ok, (along / depth if depth else 0.0)

    def _alive(self, run):
        """Hard prune: dropped the plow regime, or Link OVERTOOK Tetra (herd freezes), or wandered
        far off the line. Everything else is scored, not cut, so the search can explore off-line
        reposition states and correct them."""
        if run._follow_warned:
            return False
        along, lead, lat, dist = self._geo(run)
        if lead > self.max_lead:
            return False
        if abs(lat) > self.max_lateral:
            return False
        return True

    def _tag(self, run, released):
        l = run.link
        return (round(l.pos_x * 4), round(l.pos_z * 4), round(run.tx * 4), round(run.tz * 4),
                int(l.facing) >> 9, int(l.state), round(l.speedF * 8), bool(released))

    # ---- one generation ---------------------------------------------------
    def _children_actions(self, node):
        run = node.run
        if run.link.state == FRONT_ROLL:
            acts = roll_actions(run, self.hl, csangle=run.csangle, release=node.released)
            return [(a[0], a[1], a[2]) for a in acts]
        acts, _away = reposition_actions(run, self.hl, csangle=run.csangle,
                                         turn_step=self.turn_step)
        return acts

    def expand(self, frontier):
        # 1) build every (clone, input, csangle) child and remember its provenance
        items = []
        meta = []
        for node in frontier:
            for (d, cs, kind) in self._children_actions(node):
                child_run = node.run.clone()
                items.append((child_run, d, cs))
                meta.append((node, d, cs, kind))
        # 2) step the whole generation in parallel, one frame
        batch_step(items, self.nthreads)
        # 3) prune + dedup + score
        best_by_tag = {}
        for (child_run, d, cs), (parent, dd, css, kind) in zip(items, meta):
            if not self._alive(child_run):
                continue
            in_roll = child_run.link.state == FRONT_ROLL
            if kind == 'roll_release':
                released = True
            elif kind == 'roll_hold':
                released = parent.released
            else:
                released = False
            nroll = parent.nroll + (1 if (kind == 'roll' and in_roll) else 0)
            child = Node(child_run, parent, (d, cs), parent.depth + 1, nroll, released)
            sc = self._score(child_run, child.depth)
            tag = self._tag(child_run, released)
            cur = best_by_tag.get(tag)
            if cur is None or sc > cur[0]:
                best_by_tag[tag] = (sc, child)
            along = self.hl.along(child_run.tx, child_run.tz)
            wp_ok, rate = self._waypoint(child_run, child.depth)
            # best = deepest-herd ON-LINE waypoint (a real pursuit state), tie-break by rate
            if wp_ok and (self.best is None or along > self.best[1]):
                self.best = (sc, along, child, rate)
        # 4) keep the top-beam by score
        ranked = sorted(best_by_tag.values(), key=lambda t: -t[0])
        return [t[1] for t in ranked[:self.beam]]

    # ---- driver -----------------------------------------------------------
    def run(self, root):
        frontier = [root]
        for g in range(self.gens):
            frontier = self.expand(frontier)
            if not frontier:
                if self.verbose:
                    print("  gen %2d: frontier EMPTY (all pruned)" % g)
                break
            if self.verbose:
                b_along = self.best[1] if self.best else float('nan')
                b_rate = self.best[3] if self.best else float('nan')
                top = frontier[0]
                ta, tl, tlat, td = self._geo(top.run)
                print("  gen %2d: |F|=%d  best_online_along=%.1f (%.2f u/f)  top[along=%.1f "
                      "lead=%+.1f lat=%+.1f dist=%.1f depth=%d nroll=%d proc=%d]"
                      % (g, len(frontier), b_along, b_rate, ta, tl, tlat, td, top.depth,
                         top.nroll, top.run.link.state))
            if self.best is not None and self.best[1] >= self.goal_along:
                if self.verbose:
                    print("  GOAL along %.1f >= %.1f reached" % (self.best[1], self.goal_along))
                break
        return self.best


# =============================================================================== bit-confirm

def bit_confirm(env, prologue, seq):
    """Bit-confirm a plan (``prologue`` from state 2 + reposition ``seq``, each a list of
    ``(input_dict, csangle)``) on a FRESH run pair: the native `FreeRun` and a Python-stepped
    stripped `FreeRun` (`native_step=False`, csangle injected) must land Tetra AND Link at
    _bit_-identical positions every frame. Returns ``(ok, nframes, final_tetra, final_link)``."""
    import struct

    def bits(x):
        return struct.pack('<d', float(x)).hex()

    def build(native):
        seed = env['seed']
        row = env['cyl'][0]
        return FreeRun(row, seed_nspeed=seed['link']['nspeed'],
                       seed_old_pose=seed.get('old_pose'), computed_pose=True,
                       seed_push=seeds.seed_push_f0(env), native_step=native)
    full = prologue + seq
    nat = build(True)
    pyr = build(False)
    nat.pre_seed_input(full[0][0])
    pyr.pre_seed_input(full[0][0])
    ok = True
    for k in range(1, len(full)):
        d, cs = full[k]
        nat.step(d, csangle=cs)
        pyr.step(d, csangle=cs)
        for a, b in ((nat.link.pos_x, pyr.link.pos_x), (nat.link.pos_z, pyr.link.pos_z),
                     (nat.tx, pyr.tx), (nat.tz, pyr.tz),
                     (float(nat.link.facing), float(pyr.link.facing)),
                     (nat.link.speedF, pyr.link.speedF)):
            if bits(a) != bits(b):
                ok = False
    return ok, len(full) - 1, (nat.tx, nat.tz), (nat.link.pos_x, nat.link.pos_z)


# =============================================================================== CLI

def _centroid(env):
    pl, _ = seeds.load_placements()
    return (sum(p['x'] for p in pl) / len(pl), 0.0, sum(p['z'] for p in pl) / len(pl))


def _cmd_selfcheck(env, kw):
    """Prove the fleet-driven frontier reads state exactly: a 1-wide frontier that replays the
    recorded stream reproduces a native FreeRun rollout 0-ULP (this is what `test_native_search`
    gates), plus the human baseline u/frame + the goal-along."""
    import warnings
    import struct
    warnings.simplefilter('ignore')

    def bits(x):
        return struct.pack('<d', float(x)).hex()
    inp_at = seeds.dtm_input_at(env)
    cyl = env['cyl']

    def cs_at(k):
        r = cyl[k] if k < len(cyl) else cyl[-1]
        return int(r['csangle']) & 0xFFFF
    ref = seeds.make_freerun_native(env)
    ref.pre_seed_input(inp_at(0))
    refrows = []
    for k in range(1, 41):
        ref.step(inp_at(k), csangle=cs_at(k))
        refrows.append((ref.link.pos_x, ref.link.pos_z, ref.link.facing, ref.tx, ref.tz))
    run = seeds.make_freerun_native(env)
    run.pre_seed_input(inp_at(0))
    node = Node(run, None, None, 0, 0)
    flrows = []
    for k in range(1, 41):
        batch_step([(node.run, inp_at(k), cs_at(k))])
        flrows.append((node.run.link.pos_x, node.run.link.pos_z, node.run.link.facing,
                       node.run.tx, node.run.tz))
    mism = sum(1 for a, b in zip(refrows, flrows) for i in range(len(a))
               if bits(a[i]) != bits(b[i]))
    print("fleet-frontier vs native FreeRun: %d mismatches over %d frames x 5 fields"
          % (mism, len(refrows)))
    hl = HerdLine.from_env(env)
    rec = S.rollout_recorded(env, upto=44)
    from harness.tetrapush.reposition import rollout_metrics
    m = rollout_metrics(env, rec, hl)
    print("human baseline: %.1f u / %d f = %.2f u/frame (goal along ~%.0f)"
          % (m['herd'], m['frames'], m['per_frame'], hl.along(*_centroid(env)[::2])))


def _cmd_search(env, kw):
    import warnings
    warnings.simplefilter('ignore')
    beam = int(kw.get('beam', 200))
    gens = int(kw.get('gens', 60))
    turn_step = int(kw.get('turn_step', 1024))
    nthreads = int(kw.get('nthreads', 0))
    root, prologue = seed_root(env)
    hl = HerdLine.from_env(env)
    print("root (post-cyc1 untarget): proc=%d speedF=%.3f along=%.1f lead=%+.1f dist=%.1f"
          % (root.run.link.state, root.run.link.speedF, hl.along(root.run.tx, root.run.tz),
             hl.lead(root.run.link.pos_x, root.run.link.pos_z, root.run.tx, root.run.tz),
             math.hypot(root.run.link.pos_x - root.run.tx, root.run.link.pos_z - root.run.tz)))
    srch = RepositionSearch(env, beam=beam, gens=gens, turn_step=turn_step,
                            nthreads=nthreads)
    best = srch.run(root)
    if best is None:
        print("no surviving on-line waypoint (all nodes drifted off-line or overtook Tetra)")
        return
    sc, along, node, rate = best
    seq = reconstruct(node)
    total = len(prologue) + len(seq)
    print("\nBEST: along=%.1f u  depth(reposition)=%d  total_frames_from_state2=%d  nroll=%d"
          % (along, node.depth, total, node.nroll))
    print("  Tetra=(%.2f, %.2f)  Link=(%.2f, %.2f)  proc=%d"
          % (node.run.tx, node.run.tz, node.run.link.pos_x, node.run.link.pos_z,
             node.run.link.state))
    print("  herd/frame from state 2 = %.2f u/f (human 12.67)" % (along / total if total else 0))
    from harness.tetrapush.search import nearest_placement
    p, pd = nearest_placement(srch.placements, node.run.tx, node.run.tz)
    print("  nearest genuine placement idx %d (%.2f, %.2f) dist %.2f u"
          % (p['idx'], p['x'], p['z'], pd))
    ok, nf, ft, fl = bit_confirm(env, prologue, seq)
    print("  BIT-CONFIRM (native vs Python-stripped) over %d frames: %s (Tetra %.4f,%.4f)"
          % (nf, "0-ULP OK" if ok else "MISMATCH", ft[0], ft[1]))


def main(argv):
    env = seeds.load_env()
    cmd = argv[0] if argv else 'selfcheck'
    kw = dict(kv.split('=') for kv in argv[1:] if '=' in kv)
    if cmd == 'selfcheck':
        _cmd_selfcheck(env, kw)
    elif cmd == 'search':
        _cmd_search(env, kw)
    else:
        print("usage: python -m harness.tetrapush.native_search "
              "{selfcheck | search [beam=N gens=N turn_step=N nthreads=N]}")


if __name__ == '__main__':
    main(sys.argv[1:])
