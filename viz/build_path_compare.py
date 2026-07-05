"""A/B path player comparing two saved seq files (traced from the cold anchor, mrate 0.5).

Usage: python viz/build_path_compare.py A=<seqA> B=<seqB> [labelA=..] [labelB=..] [out=name] [title=..]
Defaults to the 50k no-pump vs +pump comparison.
"""
import json, os, re, sys
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)

from tww_sim.swim import actions as A
from viz.build_path_viz import TEMPLATE
from viz.build_path_ab import build   # trace+classify wrapper (ColdStart mrate 0.5)

_GEN = os.path.join(_rb, '_generated')


def resolve(p):
    return p if os.path.isabs(p) else os.path.join(_GEN, p)


def main():
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    fa = resolve(o.get('A', 'swim50k_seq.txt'))
    fb = resolve(o.get('B', 'swim50k_pump_seq.txt'))
    acts_a = A.expand(open(fa).read())
    acts_b = A.expand(open(fb).read())
    la = o.get('labelA', f'No pumps — {len(acts_a)} fr')
    lb = o.get('labelB', f'+Pumps (dips) — {len(acts_b)} fr')
    traces = [build(acts_a, la, '#5aa9e6'), build(acts_b, lb, '#2fc6a4')]

    dk = o.get('title', '50,000')
    delta = len(acts_b) - len(acts_a)
    sign = f"{delta:+d}" if delta else "±0"
    html = TEMPLATE.replace('__DATA__', json.dumps(traces, separators=(',', ':')))
    html = (html
            .replace('Superswim 200k — pumps vs reboosts (path player)',
                     'Superswim — no pumps vs +pumps (path player)')
            .replace('Superswim → 200,000 units · pumps vs. reboosts',
                     f'Superswim → {dk} units · no pumps vs. +pumps')
            .replace('to 200,000 units', f'to {dk} units'))
    html = re.sub(r'<div class="sub">.*?</div>',
                  '<div class="sub">Top-down replay. Same cold start & target; the '
                  '<b style="color:var(--ess)">+pump</b> plan inserts mid-cruise '
                  '<b style="color:var(--pump)">ESS-pump dips</b> the '
                  f'<b>no-pump</b> plan can\'t → <b>{len(acts_b)} fr</b> vs '
                  f'<b>{len(acts_a)} fr</b> <span class="g">({sign})</span>.</div>',
                  html, count=1, flags=re.S)

    out = os.path.join(_GEN, o.get('out', 'superswim_path_50k_pump_ab') + '.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('wrote', out, len(html), 'bytes; frames', [len(acts_a), len(acts_b)],
          'dips', [t2['pumps'] and len(t2['pumps']) for t2 in traces])


if __name__ == '__main__':
    main()
