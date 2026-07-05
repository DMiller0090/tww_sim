"""Instruction-level trace of the wait->move gate via the mStickDistance watchpoint.

Requires bp_stick.py enabled (arms a read+write log-only watchpoint on
mStickDistance) and Debugging UI on. Replays a seq via advanceseq, then reads the
MI-channel watchpoint log and reconstructs, per frame:
  - polled stick  = the setStickData WRITE value (PC 0x8011ca44) -> what the game polled
  - gate read     = procSwimWait read (PC 0x8013abd0) / procSwimMove read (0x8013af34)
Frames are delimited by the once-per-frame setStickData write; numbered backward
from the total frame count. Prints a window [lo,hi].

Usage: python gate_trace.py [seq=test_pumptrans_seq.txt] [lo=393] [hi=400] [slot=10]
"""
import sys, struct, json
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

WR_SETSTICK = 0x8011ca44   # setStickData writes mStickDistance
RD_WAIT = 0x8013abd0       # procSwimWait gate read (if >0.05 -> procSwimMove_init)
RD_MOVE = 0x8013af34       # procSwimMove read
WR_CPAD = 0x8000774c       # SI poll writes cpad mMainStickValue (the delivered input)
CPAD_ADDR = "80398310"     # cpad mMainStickValue address (distinguishes from player addr)


def hexf(h):
    return struct.unpack(">f", struct.pack(">I", int(h, 16)))[0]


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    slot = int(o.get('slot', '10'))
    seqfile = o.get('seq', 'test_pumptrans_seq.txt')
    lo, hi = int(o.get('lo', '393')), int(o.get('hi', '400'))
    acts = A.expand(open(seqfile).read())
    seq = A.acts_to_seq(acts)
    N = len(acts)

    D.control_pipe_quiet("savestate", {"action": "load", "slot": slot}); h, m = D.attach()
    D.control_pipe_quiet("advancewith", {"stickX": 128, "stickY": 128, "substickY": 0, "frames": 1})
    h, m = D.attach()
    L.wnamed(h, m, "air", 900); L.wnamed(h, m, "potential_speed", 0.0)
    D.control_pipe_quiet("advanceseq", {"port": 0, "seq": seq})

    resp = D.control_pipe_full("log", {"channel": "MI", "count": 1024})
    lines = json.loads(resp).get("lines", [])

    # parse MBP lines -> (pc, rw, value, at_addr)
    parsed = []
    for ln in lines:
        if "MBP " not in ln:
            continue
        try:
            tail = ln.split("MBP ", 1)[1]
            pc = int(tail.split()[0], 16)
            rw = "W" if "Write" in ln else "R"
            after = tail.split("Write32 " if rw == "W" else "Read32 ", 1)[1].split()
            valhex = after[0]
            at = after[2]  # "<val> at <addr> ( --- )"
            parsed.append((pc, rw, hexf(valhex), at))
        except Exception:
            continue

    # delimit frames by setStickData writes; number backward from N
    wr_idx = [i for i, p in enumerate(parsed) if p[0] == WR_SETSTICK and p[1] == "W"]
    nframes = len(wr_idx)
    print(f"# {seqfile}: {N} acts; MI log has {len(parsed)} accesses, {nframes} frame-writes")
    print(f"# (only the last {nframes} frames survive the 1024-line ring buffer)")
    print(f"# cpad=SI-delivered (WR 0x8000774c), latched=setStickData write, gate=procWait read")
    print("  f    act   cpad(SI)   latched   gate(8013abd0)   move(8013af34)")
    for fi, start in enumerate(wr_idx):
        frame = N - (nframes - 1 - fi)     # last write == frame N
        if not (lo <= frame <= hi):
            continue
        end = wr_idx[fi + 1] if fi + 1 < len(wr_idx) else len(parsed)
        block = parsed[start:end]
        latched = block[0][2]
        cpads = [v for (pc, rw, v, at) in block if pc == WR_CPAD]
        waits = [v for (pc, rw, v, at) in block if pc == RD_WAIT]
        moves = [v for (pc, rw, v, at) in block if pc == RD_MOVE]
        a = acts[frame - 1] if 0 < frame <= N else '?'
        cq = ",".join(f"{v:.4f}" for v in cpads) or "-"
        wq = ",".join(f"{v:.4f}" for v in waits) or "-"
        mq = ",".join(f"{v:.4f}" for v in moves) or "-"
        print(f"  {frame:<4} {a:5} {cq:10} {latched:8.4f}  {wq:15} {mq}")


if __name__ == "__main__":
    main()
