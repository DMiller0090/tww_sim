import json, math
import os, sys  # >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)

from tww_sim.swim import sim as S
from tww_sim.swim import actions as A


def runs(acts):
    out, i = [], 0
    while i < len(acts):
        j = i
        while j < len(acts) and acts[j] == acts[i]:
            j += 1
        out.append((acts[i], i, j - i))
        i = j
    return out


def trace(acts):
    seed = S.SwimState(v=0.0, anim=0.06392288208007812, air=900)
    seed.state = 54; seed._entry_tax = False
    st = seed.clone(); vs = []
    for a in acts:
        st.step(a); vs.append(round(abs(st.v), 1))
    return vs


def classify(acts):
    rr = runs(acts)
    build_end = 0
    for (a, s, l) in rr:
        if a == 'chg' and l >= 10:
            build_end = s + l
    dash_start = len(acts)
    if rr and rr[-1][0] == 'neu':
        dash_start = rr[-1][1]
    phase = []
    for f, a in enumerate(acts):
        if f < build_end:
            phase.append('build')
        elif f >= dash_start:
            phase.append('dash')
        elif a == 'chg':
            phase.append('reboost')
        elif a == 'neu':
            phase.append('pump')
        else:
            phase.append('ess')
    reboosts = [(s, l) for (a, s, l) in rr if a == 'chg' and build_end <= s < dash_start]
    pumps = [(s, l) for (a, s, l) in rr if a == 'neu' and s < dash_start]
    return {
        'acts': acts, 'phase': phase, 'v': trace(acts),
        'build_end': build_end, 'dash_start': dash_start,
        'reboosts': reboosts, 'pumps': pumps, 'frames': len(acts),
        'n_reboost': len(reboosts), 'n_pump': len(pumps),
    }


def main():
    plans = {}
    for key, fn, label, net in [
        ('nopump', 'ab_nopump_seq.txt', 'No-pump baseline', 200583),
        ('pump', 'ab_synced_seq.txt', 'Pump plan (live-synced)', 200128),
    ]:
        acts = A.expand(open(fn).read())
        d = classify(acts)
        d['label'] = label
        d['live_net'] = net
        plans[key] = d
    with open('viz_data.json', 'w') as f:
        json.dump(plans, f)
    for k, d in plans.items():
        print(f"{k}: {d['frames']}f  build_end={d['build_end']} dash_start={d['dash_start']} "
              f"reboosts={d['n_reboost']} pumps={d['n_pump']}")


if __name__ == '__main__':
    main()
