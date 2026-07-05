"""Watch the MOVE0 frame-controller (rate/end/frame) + state/stick across a window.

Race-free: one advanceseq prefix per probed frame from the slate. For each frame k
in [lo,hi] it replays seq[:k] then reads the live state, so we can see exactly what
the SWIMING/SWIMWAIT controller phase is doing at the wait=1 vs wait=2 boundary.

Usage: python probe_fc.py [seq=test_pumptrans_seq.txt] [lo=393] [hi=400] [slot=10]
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
from superswim import actions as A
from harness import live as L


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    slot = int(o.get('slot', '10'))
    seqfile = o.get('seq', 'test_pumptrans_seq.txt')
    lo, hi = int(o.get('lo', '393')), int(o.get('hi', '400'))
    acts = A.expand(open(seqfile).read())
    seq = A.acts_to_seq(acts)

    def at(k):
        D.control_pipe_quiet("savestate", {"action": "load", "slot": slot}); h, m = D.attach()
        D.control_pipe_quiet("advancewith", {"stickX": 128, "stickY": 128,
                                             "substickY": 0, "frames": 1}); h, m = D.attach()
        L.wnamed(h, m, "air", 900); L.wnamed(h, m, "potential_speed", 0.0)
        if k > 0:
            D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq[:k]})
        rd = lambda n: D.read_named(h, m, n)
        return (rd("link_state"), rd("air"), rd("anim_frame"), rd("fc_rate"),
                rd("fc_end"), rd("msd"), rd("stick_distance"), rd("potential_speed"))

    print(f"# {seqfile}  frames {lo}..{hi}")
    print("  f   act    st  air   anim      fc_rate  fc_end  msd     sdCopy   v")
    for k in range(lo, hi + 1):
        st, air, anim, rate, end, msd, sd, v = at(k)
        a = acts[k - 1] if 0 < k <= len(acts) else '?'
        print(f"  {k:<4}{a:5} {st:>4} {air:>4} {anim:9.4f} {rate:8.4f} {end:>5}  "
              f"{msd:.4f}  {sd:.4f}  {v:.2f}")


if __name__ == "__main__":
    main()
