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

f = sys.argv[1] if len(sys.argv) > 1 else 'ab_nopump_seq.txt'
acts = A.expand(open(f).read())
seed = S.SwimState(v=0.0, anim=0.06392288208007812, air=900); seed.state = 54
seed._entry_tax = False
st = seed.clone()
prev_x = st.x
print(f"{'f':>4} {'act':>4} {'v':>9} {'anim':>6} {'air':>4} {'|cos|':>6} {'step':>9} {'incr-23k':>9}")
for i, a in enumerate(acts):
    st.step(a)
    step = abs(st.x - prev_x); prev_x = st.x
    cosv = abs(math.cos(math.pi * st.anim / 23.0))
    incr = abs(st.v) / 36 + 0.6 + (1 - (st.air + 1) / 900)
    k = round(incr / 23.0)
    if 210 <= i <= 495 and a != 'neu':
        flag = "  <-- REBOOST (chg)" if a == 'chg' else ""
        print(f"{i:>4} {a:>4} {st.v:9.2f} {st.anim:6.2f} {st.air:>4} {cosv:6.3f} {step:9.1f} {incr-23*k:+9.3f}{flag}")
