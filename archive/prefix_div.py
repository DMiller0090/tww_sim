"""Binary-search the FIRST frame where live anim diverges from the sim, race-free.

Each probe loadstates the slate, sets the cold start, replays seq[:k] in ONE advanceseq
(race-free, unlike per-frame advancewith), and reads the live state at frame k. ~log2(N)
probes find the first divergence instead of a fragile dense per-frame loop.

Usage: python prefix_div.py seq=plan200k_seq.txt [slot=10] [tol=0.02]
"""
import sys
import os, sys  # >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)
import dolphin_mem as D
from superswim import sim as S
from superswim import actions as A
from harness import live as L


def live_at(seq, slot):
    D.control_pipe_quiet("savestate", {"action": "load", "slot": slot})
    h, m = D.attach()
    D.control_pipe_quiet("advancewith", {"stickX": 128, "stickY": 128,
                                         "substickY": 0, "frames": 1})
    h, m = D.attach()
    L.wnamed(h, m, "air", 900); L.wnamed(h, m, "potential_speed", 0.0)
    v0 = D.read_named(h, m, "potential_speed"); an0 = D.read_named(h, m, "anim_frame")
    a0 = D.read_named(h, m, "air"); s0 = D.read_named(h, m, "link_state")
    if seq:
        D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq})
    return (D.read_named(h, m, "potential_speed"), D.read_named(h, m, "anim_frame"),
            D.read_named(h, m, "air"), D.read_named(h, m, "link_state"),
            (v0, an0, a0, s0))


def sim_at(acts, seed, k):
    v0, an0, a0, s0 = seed
    sim = S.SwimState(v=v0, anim=an0, air=a0); sim.state = s0; sim._entry_tax = False
    for a in acts[:k]:
        sim.step(a)
    return sim.v, sim.anim, sim.air, sim.state


def main():
    opts = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    slot = int(opts.get('slot', '10')); tol = float(opts.get('tol', '0.02'))
    acts = A.expand(open(opts.get('seq', 'plan200k_seq.txt')).read())
    seq = A.acts_to_seq(acts)
    N = len(acts)

    def diverged(k):
        vl, anl, airl, stl, seed = live_at(seq[:k], slot)
        vs, ans, airs, sts = sim_at(acts, seed, k)
        cyc = 26.0 if stl == 54 else 23.0
        dan = A.animdiff(anl, ans, cyc)
        return (abs(vl - vs) > tol or dan > tol or stl != sts or airl != airs,
                vl, vs, anl, ans, dan, airl, airs, stl, sts)

    full = diverged(N)
    if not full[0]:
        print(f"no divergence over all {N} frames (tol {tol})"); return
    lo, hi = 1, N                       # invariant: lo passes-ish, hi diverges
    while lo < hi:
        mid = (lo + hi) // 2
        if diverged(mid)[0]:
            hi = mid
        else:
            lo = mid + 1
    d = diverged(lo)
    print(f"FIRST divergence at frame {lo}/{N} (act={acts[lo-1]}):")
    print(f"  v   live {d[1]:.4f}  sim {d[2]:.4f}  dv {d[1]-d[2]:+.4f}")
    print(f"  an  live {d[3]:.4f}  sim {d[4]:.4f}  dan {d[5]:.4f}")
    print(f"  air live {d[6]}  sim {d[7]}   state live {d[8]} sim {d[9]}")
    pre = diverged(lo - 1) if lo > 1 else None
    if pre:
        print(f"  (frame {lo-1} OK: an live {pre[3]:.4f} sim {pre[4]:.4f} dan {pre[5]:.4f}, "
              f"act={acts[lo-2]})")


if __name__ == "__main__":
    main()
