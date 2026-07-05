"""Per-frame probe of the swim-transition gate inputs.

Reads, for each frame k in [lo,hi] (race-free advanceseq prefix replay):
  link_state, anim, the TWO candidate mStickDistance fields, and the raw cpad
  mMainStickValue the game polled that frame. Resolves whether bug#2's extra
  wait frame is an input-pipeline effect (cpad delivered neutral) or game logic.

  msd      = deref(0x803AD860)+0x34D8  (dolphin_mem's existing "msd")
  msd_hdr  = deref(0x803AD860)+0x35B0  (d_a_player_main.h:2269 mStickDistance offset)
  mmsv     = 0x80398310 static          (g_mDoCPd_cpadInfo[0].mMainStickValue, +0x08)

Usage: python gate_probe.py [seq=test_pumptrans_seq.txt] [lo=393] [hi=400] [slot=10]
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

D.NAMED_ADDRS["msd_hdr"] = {"base": 0x803AD860, "offsets": [0x35B0], "type": "f32"}
D.NAMED_ADDRS["mmsv"] = {"base": 0x80398310, "offsets": [], "type": "f32"}


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
        return (rd("link_state"), rd("anim_frame"), rd("msd"), rd("msd_hdr"), rd("mmsv"))

    print(f"# {seqfile}  frames {lo}..{hi}")
    print("  f   act    st   anim      msd(34D8) msd_hdr(35B0) mmsv(cpad)")
    for k in range(lo, hi + 1):
        st, anim, msd, msdh, mmsv = at(k)
        a = acts[k - 1] if 0 < k <= len(acts) else '?'
        print(f"  {k:<4}{a:5} {st:>4} {anim:9.4f}  {msd:8.4f}  {msdh:9.4f}    {mmsv:8.4f}")


if __name__ == "__main__":
    main()
