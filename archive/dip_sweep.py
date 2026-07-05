"""Characterize the neutral->ESS (pump) re-entry timing vs neutral-hold length N.

Builds a clean cold-start ESS cruise, then does ONE neutral dip of length N
followed by ESS, and prints a per-frame side-by-side of LIVE vs SIM
(link_state, anim, v) across the dip window -- so we can SEE how many WAIT (54)
frames live spends vs the sim, as a function of N. This pins the modeling rule:
bug#2 = sim re-enters ESS one frame early for SHORT dips (neu,1) but pump_seq
(neu,8) passes, so the extra wait must vanish as the hold lengthens.

Usage: python dip_sweep.py [build=chg,60;ess,24] [A=6] [B=10] [Ns=1,2,3,4,5,8] [slot=10]
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


def live_window(seq, lo, hi, slot):
    """Probe live (state, anim, v) for frames lo..hi by replaying seq[:k] per k."""
    rows = {}
    for k in range(lo, hi + 1):
        D.control_pipe_quiet("savestate", {"action": "load", "slot": slot}); h, m = D.attach()
        D.control_pipe_quiet("advancewith", {"stickX": 128, "stickY": 128,
                                             "substickY": 0, "frames": 1}); h, m = D.attach()
        L.wnamed(h, m, "air", 900); L.wnamed(h, m, "potential_speed", 0.0)
        if k > 0:
            D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq[:k]})
        rows[k] = (D.read_named(h, m, "link_state"), D.read_named(h, m, "anim_frame"),
                   D.read_named(h, m, "potential_speed"))
    return rows


def sim_seq(acts, seed):
    v0, an0, a0, s0 = seed
    sim = S.SwimState(v=v0, anim=an0, air=a0); sim.state = s0; sim._entry_tax = False
    out = []
    for a in acts:
        sim.step(a)
        out.append((sim.state, sim.anim, sim.v))
    return out


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    slot = int(o.get('slot', '10'))
    build = o.get('build', 'chg,60;ess,24')
    A = int(o.get('A', '6')); B = int(o.get('B', '10'))
    Ns = [int(x) for x in o.get('Ns', '1,2,3,4,5,8').split(',')]

    # seed (cold start after loadstate + 1 neutral frame + write air/v)
    D.control_pipe_quiet("savestate", {"action": "load", "slot": slot}); h, m = D.attach()
    D.control_pipe_quiet("advancewith", {"stickX": 128, "stickY": 128,
                                         "substickY": 0, "frames": 1}); h, m = D.attach()
    L.wnamed(h, m, "air", 900); L.wnamed(h, m, "potential_speed", 0.0)
    seed = (D.read_named(h, m, "potential_speed"), D.read_named(h, m, "anim_frame"),
            D.read_named(h, m, "air"), D.read_named(h, m, "link_state"))

    for N in Ns:
        spec = f"{build};ess,{A};neu,{N};ess,{B}"
        acts = A.expand(spec)
        seq = A.acts_to_seq(acts)
        nbuild = len(A.expand(build))
        dip0 = nbuild + A            # 1-based frame index of first neu
        lo = dip0 - 1; hi = dip0 + N + 4
        live = live_window(seq, lo, hi, slot)
        sim = sim_seq(acts, seed)    # sim[k-1] is frame k
        print(f"\n=== N={N}  dip starts at frame {dip0} (after {nbuild} build + {A} ess) ===")
        print("  f  act   | live st  anim       v        | sim st  anim       v       | dST dV")
        for k in range(lo, hi + 1):
            a = acts[k - 1] if 0 < k <= len(acts) else '?'
            lst, lan, lv = live[k]
            sst, san, sv = sim[k - 1]
            dst = '' if lst == sst else f"st!{lst}/{sst}"
            print(f"  {k:<3}{a:5} | {lst:>4} {lan:9.3f} {lv:9.2f}  | "
                  f"{sst:>4} {san:9.3f} {sv:9.2f} | {dst} {lv-sv:+.2f}")


if __name__ == "__main__":
    main()
