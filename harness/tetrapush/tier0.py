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
"""TIER 0 -- the geometric shove planner (ms-per-candidate, the cheap monotone predictor).

A push CYCLE (re-target -> roll -> untarget tier -> backslide, 26 frames) is modeled as a RIGID
per-frame template (`primitives.cycle_template` off the validated FreeRun window) steered by ONE
knob: the roll AIM (the world angle the roll's locked facing snaps to). Per frame the template
supplies Link's foot term + exec-centre offset; the REAL fp plow laws (`_cc_settled_center` +
`full_depth_push`, the gated full-depth pair) then run the coupling arithmetic -- so the only
approximation is Link's own body kinematics on the ~10 non-roll frames whose facing chases the
Tetra bearing (frozen into the template at the recorded geometry). Everything position-coupled
(depth, ejection directions, the chase-and-plow oscillation) is exact arithmetic.

The canonical cycle is STITCHED: cycle 2's 3-frame re-target + its rigid roll body, closed with
cycle 1's untarget tier + backslide (cycle 2's own tail is outside the gated window). Re-target
frames still travel along the PREVIOUS cycle's motion direction (the +18 flip only swings travel
at the roll), so their template rows are expressed in the OLD aim frame; roll+ rows in the NEW.

Plan shape searched: ``[aim_1 .. aim_N]`` (one aim per cycle) + the end-game constraints:
  * Tetra lands near a genuine `tetra_placements.tsv` coord (the target set);
  * Link can WALK-IN to the entry start (`seeds.ENTRY_LINK_START`) without re-touching Tetra
    (clearance > CONTACT_CLEAR along the straight walk path) and without ever exceeding the
    FOLLOW_ENGAGE_DIST plow-regime bound (Tetra must stay stt-3).

CLI: ``python -m harness.tetrapush.tier0 validate`` (tier-0 vs FreeRun on the recorded aims),
``... sweep [cycles=N] [grid=K]`` (the exhaustive aim sweep -> ranked candidates + a reachable-
landings TSV under _generated/), ``... map`` (the one-shot reachable-landings heatmap data).
"""
import math
import os

from tww_sim.core.npc_zl1 import FOLLOW_ENGAGE_DIST

from harness.tetrapush import seeds
from harness.tetrapush.from_f0 import full_depth_push, _cc_settled_center
from harness.tetrapush import primitives as P

# Link's mCyl centre leads his feet by up to ~28 u through the roll pose; feet-to-feet clearance
# above 80 + 28 guarantees no Co contact on the final walk-in. (R_link 30 + R_tetra 50 = 80.)
CONTACT_CLEAR = 110.0


# ---------------------------------------------------------------------- template construction

def build_template(env, records=None):
    """The canonical push-cycle template. Returns ``(rows, exit_rel)``: per-frame dicts with
    ``phase`` ('old' = expressed in the entry-motion frame, 'new' = the cycle aim's frame),
    ``foot_local``, ``facing_rel``, ``o_local``, ``proc``, ``speedF``; ``exit_rel`` = the
    cycle-exit motion direction relative to the aim. The re-target BACKSLIDE-continuation rows
    are 'old'; the +18 FLIP row and everything after are 'new' (the flip's travel has chased
    to the new target -- storing it rel-entry freezes the recorded old-new angle, the
    session-22 first-cut contact-loss bug)."""
    recs = records if records is not None else P.window_records(env)
    spans = P.find_cycles(recs)
    assert len(spans) >= 2, "expected both recorded cycles in the window"
    by_f = {r['f']: r for r in recs}
    (s1, r1, e1), (s2, r2, e2) = spans[0], spans[1]
    aim1 = by_f[r1]['facing']
    aim2 = by_f[r2]['facing']

    # re-target rows are expressed rel the ENTRY MOTION direction, not the old aim (see the
    # class of bug in the docstring: rel-old-aim double-counts the backslide chase offset)
    prev = by_f[s2 - 1]
    entry_dir = _dir_bam(prev['foot_world'])

    rows = []
    # cycle 2's re-target (f s2..r2-1): backslide-continuation rows in the ENTRY-MOTION frame;
    # the +18 flip row (speedF > 0) in the NEW aim frame.
    for f in range(s2, r2):
        r = by_f[f]
        flip = r['speedF'] > 0.0
        base = aim2 if flip else entry_dir
        rows.append(dict(
            phase='new' if flip else 'old', proc=r['proc'], speedF=r['speedF'],
            facing_rel=P._s16(r['facing'] - base),
            foot_local=P.to_local(r['foot_world'][0], r['foot_world'][1], base),
            o_local=r['o_local']))
    # cycle 2's roll body (f r2..e2): the NEW aim (aim2) frame.
    for f in range(r2, e2 + 1):
        r = by_f[f]
        rows.append(dict(
            phase='new', proc=r['proc'], speedF=r['speedF'],
            facing_rel=P._s16(r['facing'] - aim2),
            foot_local=P.to_local(r['foot_world'][0], r['foot_world'][1], aim2),
            o_local=r['o_local']))
    # close with cycle 1's tail (the roll's last frame + the proc-9 tier + the MOVE backslide),
    # frames e2-r2+r1+1 .. up to the frame before cycle 2's re-target span begins (s2 - 1).
    tail_from = r1 + (e2 - r2) + 1
    for f in range(tail_from, s2):
        r = by_f[f]
        rows.append(dict(
            phase='new', proc=r['proc'], speedF=r['speedF'],
            facing_rel=P._s16(r['facing'] - aim1),
            foot_local=P.to_local(r['foot_world'][0], r['foot_world'][1], aim1),
            o_local=r['o_local']))
    # the cycle-exit motion direction, relative to the cycle aim: what the NEXT cycle's
    # re-target rows continue along (step_cycle threads it through T0State.motion_dir).
    exit_rel = P._s16(_dir_bam(P.to_world(rows[-1]['foot_local'][0],
                                          rows[-1]['foot_local'][1], 0)))
    return rows, exit_rel


def _dir_bam(v):
    """World direction of an (x, z) vector as a BAM angle (0 = +z, 0x4000 = +x)."""
    return int(math.atan2(v[0], v[1]) / (2.0 * math.pi) * 65536.0) & 0xFFFF


def build_first_template(env, records=None):
    """The FIRST cycle's template: every plan starts at state 2, so its entry (the recorded f1
    backslide-continuation + f2 flip) is fixed data -- f1 is stored as a WORLD row ('world'
    phase, applied unrotated), the flip + roll + tail rotate with the aim knob. Rows f1..(cycle
    2's re-target start - 1)."""
    recs = records if records is not None else P.window_records(env)
    spans = P.find_cycles(recs)
    by_f = {r['f']: r for r in recs}
    (s1, r1, e1), (s2, _, _) = spans[0], spans[1]
    aim1 = by_f[r1]['facing']
    rows = []
    for f in range(max(s1, 1), s2):
        r = by_f[f]
        flipped = f >= r1 - 1 or r['speedF'] > 0.0     # the flip row and everything after
        phase = 'new' if flipped else 'world'
        base = aim1 if flipped else 0
        rows.append(dict(
            phase=phase, proc=r['proc'], speedF=r['speedF'],
            facing_rel=P._s16(r['facing'] - base) if flipped else r['facing'],
            foot_local=P.to_local(r['foot_world'][0], r['foot_world'][1], base) if flipped
            else tuple(r['foot_world']),
            o_local=r['o_local']))
    exit_rel = P._s16(_dir_bam(P.to_world(rows[-1]['foot_local'][0],
                                          rows[-1]['foot_local'][1], 0)))
    return rows, exit_rel


# ---------------------------------------------------------------------- the tier-0 stepper

class T0State:
    """The tier-0 planning state: Link feet, Tetra feet, the pending push pair (the FreeRun
    end-of-frame convention), and the previous cycle's aim (the re-target frames still travel
    along it)."""
    __slots__ = ('lx', 'lz', 'tx', 'tz', 'pend_link', 'pend_tetra', 'motion_dir', 'frames',
                 'max_dist', 'contact')

    def __init__(self, lx, lz, tx, tz, pend_link, pend_tetra, motion_dir, frames=0,
                 max_dist=0.0, contact=0):
        self.lx, self.lz, self.tx, self.tz = lx, lz, tx, tz
        self.pend_link, self.pend_tetra = pend_link, pend_tetra
        self.motion_dir = motion_dir       # the current physical travel direction (BAM)
        self.frames = frames
        self.max_dist = max_dist
        self.contact = contact

    def clone(self):
        return T0State(self.lx, self.lz, self.tx, self.tz, self.pend_link, self.pend_tetra,
                       self.motion_dir, self.frames, self.max_dist, self.contact)

    def dist(self):
        return math.hypot(self.lx - self.tx, self.lz - self.tz)


def seed_state(env):
    """The tier-0 state at f0 (state 2): both actors' seed feet, the seed-frame pending push
    (from the captured f0 Co centre -- static initial-condition data, as in FreeRun), and the
    incoming motion direction (state 2's backslide travel + 0x8000 == the physical direction,
    which the first re-target frames continue along)."""
    e = env['cyl'][0]
    pend_link, pend_tetra = full_depth_push(e['link']['cyl'],
                                            (e['tetra']['pos'][0], e['tetra']['pos'][2]))
    dir0 = (e['link']['travel'] + 0x8000) & 0xFFFF   # backslide: motion = travel flipped
    return T0State(e['link']['pos'][0], e['link']['pos'][2],
                   e['tetra']['pos'][0], e['tetra']['pos'][2],
                   pend_link, pend_tetra, dir0)


def step_cycle(st, new_aim, template, trace=None, skip=0):
    """Advance one push cycle at roll aim ``new_aim`` (BAM). ``template`` is the
    (rows, exit_rel) pair from `build_template`. Re-target ('old') rows continue along
    ``st.motion_dir``; roll+ ('new') rows run in the aim frame; the exit motion direction is
    threaded into the state for the next cycle. ``skip`` drops the first n re-target rows (the
    state-2 first cycle enters mid-re-target: skip=1). Pure float arithmetic + the exact fp plow
    laws; mirrors the FreeRun frame order (pend applied, then this frame's settled centre
    produces the next pend). Mutates and returns ``st``."""
    tpl, exit_rel = template
    old_dir = st.motion_dir
    for row in tpl[skip:]:
        if row['phase'] == 'world':                    # recorded state-2 entry row, unrotated
            fx, fz = row['foot_local']
            facing = row['facing_rel'] & 0xFFFF        # stores the absolute facing
        else:
            base = old_dir if row['phase'] == 'old' else new_aim
            fx, fz = P.to_world(row['foot_local'][0], row['foot_local'][1], base)
            facing = (base + row['facing_rel']) & 0xFFFF
        st.lx += fx + st.pend_link[0]
        st.lz += fz + st.pend_link[1]
        st.tx += st.pend_tetra[0]
        st.tz += st.pend_tetra[1]
        ox, oz = P.to_world(row['o_local'][0], row['o_local'][1], facing)
        settled = _cc_settled_center((st.lx + ox, st.lz + oz), (st.tx, st.tz))
        st.pend_link, st.pend_tetra = full_depth_push(settled, (st.tx, st.tz))
        st.frames += 1
        d = st.dist()
        if d > st.max_dist:
            st.max_dist = d
        if st.pend_tetra != (0.0, 0.0):
            st.contact += 1
        if trace is not None:
            trace.append((st.lx, st.lz, st.tx, st.tz, d))
    st.motion_dir = (new_aim + exit_rel) & 0xFFFF
    return st


# ---------------------------------------------------------------------- constraints + scoring

def walk_in_ok(st, clear=CONTACT_CLEAR):
    """Can Link disengage to the entry start without re-touching Tetra (straight-path clearance)
    and while keeping her in the stt-3 plow regime (never past FOLLOW_ENGAGE_DIST)? Returns
    (ok, why)."""
    ex, ez = seeds.ENTRY_LINK_START
    # distance from Tetra to the segment link_end -> entry_start
    ax, az = st.lx, st.lz
    bx, bz = ex, ez
    px, pz = st.tx, st.tz
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
    cx, cz = ax + t * dx, az + t * dz
    seg_clear = math.hypot(px - cx, pz - cz)
    if seg_clear < clear:
        return False, "walk-in path passes %.1f u from Tetra (< %.0f)" % (seg_clear, clear)
    d_end = math.hypot(px - bx, pz - bz)
    if d_end > FOLLOW_ENGAGE_DIST:
        return False, "entry start is %.1f u from Tetra (> follow bound %d)" % (
            d_end, FOLLOW_ENGAGE_DIST)
    d_roll = math.hypot(px - seeds.ENTRY_ROLL_POS[0], pz - seeds.ENTRY_ROLL_POS[1])
    if d_roll > FOLLOW_ENGAGE_DIST:
        return False, "entry roll pos is %.1f u from Tetra (> follow bound)" % d_roll
    return True, "clear %.1f u, entry dist %.1f u" % (seg_clear, d_end)


def nearest_placement(placements, tx, tz):
    best, bd = None, float('inf')
    for p in placements:
        d = math.hypot(p['x'] - tx, p['z'] - tz)
        if d < bd:
            best, bd = p, d
    return best, bd


def score(st, placements):
    """(nearest-coord distance, feasibility) for a terminal state; the sweep ranks by distance
    among feasible candidates, with infeasibles kept (flagged) for the map."""
    p, d = nearest_placement(placements, st.tx, st.tz)
    ok, why = walk_in_ok(st)
    guard_ok = st.max_dist <= FOLLOW_ENGAGE_DIST
    return dict(coord=p, dist=d, walk_in=ok, walk_why=why, guard_ok=guard_ok)


# ---------------------------------------------------------------------- validate + sweep

def validate(env, per_frame=False):
    """Tier-0 vs the full FreeRun on the recorded window: run the two recorded cycles at their
    own aims (the first with skip=1 -- state 2 enters mid-re-target) and report the Tetra/Link
    error per cycle boundary and at the last gated frame. The tier-0 model's honest error budget
    for ranking."""
    recs = P.window_records(env)
    spans = P.find_cycles(recs)
    by_f = {r['f']: r for r in recs}
    tpl0 = build_first_template(env, records=recs)
    tpl = build_template(env, records=recs)
    aim1 = by_f[spans[0][1]]['facing']
    aim2 = by_f[spans[1][1]]['facing']
    st = seed_state(env)
    tr = []
    step_cycle(st, aim1, tpl0, trace=tr)
    f1 = st.frames
    ref = by_f[f1]
    e1t = math.hypot(st.tx - ref['tetra'][0], st.tz - ref['tetra'][1])
    e1l = math.hypot(st.lx - ref['feet'][0], st.lz - ref['feet'][1])
    step_cycle(st, aim2, tpl, trace=tr)
    last = recs[-1]
    k = last['f'] - 1                        # trace index 0 == f1
    e2t = math.hypot(tr[k][2] - last['tetra'][0], tr[k][3] - last['tetra'][1])
    e2l = math.hypot(tr[k][0] - last['feet'][0], tr[k][1] - last['feet'][1])
    if per_frame:
        for i, (lx, lz, tx, tz, d) in enumerate(tr):
            f = i + 1
            if f in by_f:
                r = by_f[f]
                print("f%2d link err %8.3f  tetra err %8.3f  dist %7.2f (rec %7.2f)" % (
                    f, math.hypot(lx - r['feet'][0], lz - r['feet'][1]),
                    math.hypot(tx - r['tetra'][0], tz - r['tetra'][1]), d,
                    math.hypot(r['feet'][0] - r['tetra'][0], r['feet'][1] - r['tetra'][1])))
    return dict(f_cyc1=f1, tetra_err_cyc1=e1t, link_err_cyc1=e1l,
                f_last=last['f'], tetra_err_last=e2t, link_err_last=e2l)


def sweep(env, n_cycles=4, grid=48, span_bam=2400, keep=25, verbose=True):
    """The exhaustive tier-0 aim sweep: beam search over per-cycle roll aims on a grid centred
    on the Link->Tetra bearing (the roll must pass THROUGH her to plow; the recorded cycles
    aimed ~+700 BAM off that bearing), span +-``span_bam``, ``grid`` aims per cycle, beam width
    ``keep``. Streams best-so-far; returns the ranked terminal list. Also dumps every terminal
    landing to ``_generated/tetra_push_landings.tsv`` (the reachable-landings map)."""
    placements, _ = seeds.load_placements()
    recs = P.window_records(env)
    tpl0 = build_first_template(env, records=recs)
    tpl = build_template(env, records=recs)
    st0 = seed_state(env)

    def aim_grid(st):
        centre = _dir_bam((st.tx - st.lx, st.tz - st.lz))
        step = max(1, (2 * span_bam) // grid)
        return [(centre - span_bam + i * step) & 0xFFFF for i in range(grid + 1)]
    beam = [([], st0)]
    best = None
    landings = []
    for level in range(n_cycles):
        nxt = []
        for aims, st in beam:
            for a in aim_grid(st):
                s2 = step_cycle(st.clone(), a, tpl0 if level == 0 else tpl)
                sc = score(s2, placements)
                nxt.append((aims + [a], s2, sc))
                landings.append((level + 1, aims + [a], s2.tx, s2.tz, sc))
                if sc['walk_in'] and sc['guard_ok'] and (best is None or sc['dist'] < best[2]['dist']):
                    best = (aims + [a], s2, sc)
                    if verbose:
                        print("best-so-far: %d cycles, aims %s -> tetra (%.3f, %.3f), "
                              "%.3f u from coord #%d [%s]" % (
                                  level + 1, best[0], s2.tx, s2.tz, sc['dist'],
                                  sc['coord']['idx'], sc['walk_why']))
        # prune plow-regime breakers: a state whose max dist passed the follow bound is dead
        # (live Tetra would flip to the unmodeled stt-4 follow and chase Link off her placement).
        nxt = [x for x in nxt if x[2]['guard_ok']]
        nxt.sort(key=lambda x: x[2]['dist'])
        beam = [(a, s) for a, s, _ in nxt[:keep]]
        if not beam:
            if verbose:
                print("level %d: beam empty (every candidate broke the plow regime)" % (level + 1))
            break
    out_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), '_generated')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'tetra_push_landings.tsv')
    with open(out, 'w') as f:
        f.write("# tier-0 reachable Tetra landings (session 22); cols: n_cycles aims tetra_x "
                "tetra_z nearest_coord_idx dist walk_in guard_ok\n")
        for lv, aims, tx, tz, sc in landings:
            f.write("%d\t%s\t%.6f\t%.6f\t%d\t%.4f\t%d\t%d\n" % (
                lv, ",".join(str(a) for a in aims), tx, tz, sc['coord']['idx'], sc['dist'],
                1 if sc['walk_in'] else 0, 1 if sc['guard_ok'] else 0))
    if verbose:
        print("landings map -> %s (%d rows)" % (out, len(landings)))
    ranked = sorted((x for x in
                     ((aims, s, score(s, placements)) for aims, s in beam)),
                    key=lambda x: x[2]['dist'])
    return best, ranked


def main(argv):
    env = seeds.load_env()
    cmd = argv[0] if argv else 'validate'
    if cmd == 'validate':
        v = validate(env)
        print("tier-0 vs FreeRun on the recorded aims:")
        print("  cycle-1 boundary (f%d): tetra err %.3f u, link err %.3f u" % (
            v['f_cyc1'], v['tetra_err_cyc1'], v['link_err_cyc1']))
        print("  last gated frame (f%d): tetra err %.3f u, link err %.3f u" % (
            v['f_last'], v['tetra_err_last'], v['link_err_last']))
    elif cmd == 'sweep':
        kw = dict(kv.split('=') for kv in argv[1:])
        best, ranked = sweep(env, n_cycles=int(kw.get('cycles', 4)),
                             grid=int(kw.get('grid', 48)), keep=int(kw.get('keep', 25)))
        if best is None:
            print("NO feasible candidate found (walk-in + follow guard); see the landings map")
        else:
            aims, st, sc = best
            print("\nBEST: aims %s" % aims)
            print("  tetra (%r, %r) -- %.4f u from coord #%d (%.13f, %.13f)" % (
                st.tx, st.tz, sc['dist'], sc['coord']['idx'],
                sc['coord']['x'], sc['coord']['z']))
            print("  frames %d, contact %d, max dist %.1f, %s" % (
                st.frames, st.contact, st.max_dist, sc['walk_why']))
    else:
        print("usage: python -m harness.tetrapush.tier0 [validate|sweep cycles=4 grid=48]")


if __name__ == '__main__':
    main(sys.argv[1:])
