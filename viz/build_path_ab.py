"""A/B path player for an arbitrary destination: optimizer (mixed build) vs best traditional
(pure charge -> ESS -> neutral dash). Reuses the build_path_viz template.

Usage: python viz/build_path_ab.py [dest=50000]
"""
import json, math, os, re, sys
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.swim import plan as P
from tww_sim.swim import actions as A
from tww_sim.swim import optimize as O
from tww_sim.swim.coldstart import ColdStartSwimState
from viz.build_path_viz import classify, TEMPLATE

A0 = 0.06392288208007812


def seed():
    s = ColdStartSwimState(v=0.0, anim=A0, air=900, mrate=0.5)
    s.state = 54; s._entry_tax = False
    return s


def trace(acts):
    st = seed()
    rows = []
    for a in acts:
        d, _ = st.step(a)
        rows.append({"a": a, "prog": round(-st.x, 1), "z": round(st.z, 1),
                     "v": round(abs(st.v), 1), "anim": round(st.anim, 2), "air": st.air,
                     "step": round(abs(d), 1),
                     "eff": round(0.6 + 0.4 * abs(math.cos(math.pi * st.anim / 23.0)), 4)})
    return rows, -st.x


def build(acts, label, color):
    rows, net = trace(acts)
    phase, build_end, dash_start, reboosts, pumps = classify(acts)
    return {"label": label, "color": color, "frames": len(acts), "live_net": round(net),
            "rows": rows, "phase": phase, "build_end": build_end,
            "dash_start": dash_start, "reboosts": reboosts, "pumps": pumps}


def best_traditional(dest):
    """Sweep charge length; each gets an optimal ESS+neutral-dash suffix. Return the min-frame seq."""
    best = None
    for N in range(90, 301, 5):
        s = seed()
        for _ in range(N):
            s.step('chg')
        cr = P.plan_min_frames(dest, s.v, s.anim, s.air, seed_state=s, actions=('ess', 'neu'),
                               allow_pump=False, verbose=False)
        if cr['frames'] is None:
            continue
        total = N + cr['frames']
        if best is None or total < best[0]:
            best = (total, ['chg'] * N + list(cr['actions']), N)
    return best[1], best[2]


def main():
    dest = float(dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t).get('dest', '50000'))
    dk = f"{int(dest/1000)}k"

    opt = P.plan_min_frames(dest, 0.0, A0, 900, actions=('ess', 'chg', 'neu'),
                            cold_start=True, cold_mrate=0.5, verbose=False)['actions']
    trad, N = best_traditional(dest)
    delta = len(opt) - len(trad)

    traces = [build(opt, f'Optimizer (mixed build) — {len(opt)} fr', '#2fc6a4'),
              build(trad, f'Traditional charge→ESS→dash — {len(trad)} fr', '#5aa9e6')]

    html = TEMPLATE.replace('__DATA__', json.dumps(traces, separators=(',', ':')))
    html = (html
            .replace('Superswim 200k — pumps vs reboosts (path player)',
                     f'Superswim {dk} — optimizer vs traditional (path player)')
            .replace('Superswim → 200,000 units · pumps vs. reboosts',
                     f'Superswim → {int(dest):,} units · optimizer vs. traditional')
            .replace('to 200,000 units', f'to {int(dest):,} units'))
    sign = f"{delta:+d}" if delta else "±0"
    html = re.sub(r'<div class="sub">.*?</div>',
                  '<div class="sub">Top-down replay, real westward distance. Both build to the same '
                  'cruise speed. The <b style="color:var(--ess)">optimizer</b> cashes forward progress '
                  'with ESS during the build (+ <b style="color:var(--reboost)">reboost</b> '
                  'maintenance); the <b>traditional</b> swim charges straight through → '
                  f'<b>{len(opt)} fr</b> vs <b>{len(trad)} fr</b> <span class="g">({sign})</span>.</div>',
                  html, count=1, flags=re.S)

    out = os.path.join(_rb, '_generated', f'superswim_path_{dk}_ab.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('wrote', out, len(html), 'bytes; frames', [t['frames'] for t in traces],
          'trad charge', N, 'reboosts', [len(t['reboosts']) for t in traces],
          'pumps', [len(t['pumps']) for t in traces])


if __name__ == '__main__':
    main()
