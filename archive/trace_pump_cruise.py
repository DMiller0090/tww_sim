import math, sys
import os, sys  # >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)

from superswim import sim as S
from superswim import actions as A

f = sys.argv[1] if len(sys.argv) > 1 else 'ab_synced_seq.txt'
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 264
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 340
acts = A.expand(open(f).read())

# composition
from collections import Counter
seed = S.SwimState(v=0.0, anim=0.06392288208007812, air=900); seed.state = 54; seed._entry_tax = False
st = seed.clone(); prev = st.x
print(f"{f}: {len(acts)} frames, counts={dict(Counter(acts))}")
print(f"{'f':>4} {'act':>4} {'st':>3} {'v':>9} {'anim':>6} {'air':>4} {'eff':>5} {'step':>8} {'ratio':>6}")
for i, a in enumerate(acts):
    d, tag = st.step(a)
    step = abs(st.x - prev); prev = st.x
    eff = 0.6 + 0.4 * abs(math.cos(math.pi * st.anim / 23.0))
    ratio = step / max(abs(st.v), 1e-6)
    if lo <= i <= hi:
        mark = "  <== NEU dip" if a == 'neu' else ""
        print(f"{i:>4} {a:>4} {st.state:>3} {st.v:9.2f} {st.anim:6.2f} {st.air:>4} "
              f"{eff:5.3f} {step:8.1f} {ratio:6.3f}{mark}")
