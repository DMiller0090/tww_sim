# >>> repo bootstrap
import os
import sys
_d = os.path.dirname(os.path.abspath(__file__))
while _d and not os.path.exists(os.path.join(_d, 'pyproject.toml')):
    _p = os.path.dirname(_d)
    if _p == _d:
        break
    _d = _p
if _d not in sys.path:
    sys.path.insert(0, _d)
# <<< repo bootstrap
"""onestep_divergence -- the human-readable per-frame ONE-STEP live/offline divergence table.

The 0-ULP hunt's diagnostic (session 24). Reset the sim to the EXACT captured state[k-1] each frame,
feed the EXACT fixture Co centre for the outgoing push, step ONCE, and report the per-axis
sim-vs-live position divergence in ULP and absolute u. Because the recoil is fed exact, the pos
divergence IS the coupled step's own error (Link's foot term + the applied recoil law).

The live pos is true console ground truth: breakpoint-captured, and `setcol.pos == cyl.pos` to 0 ULP
over f1..12 (session 14), so a nonzero ULP here is a real sim-vs-console diff, NOT single-step noise.

This is the diagnostic behind `tests/test_from_f0.py::test_onestep_pos_bit_exact_from_exact_state`
(the strict 0-ULP gate, currently xfail). Run: `python -m harness.tetrapush.onestep_divergence`.
"""
import json
import math
import struct

from harness.tetrapush import seeds
from harness.tetrapush.from_f0 import FreeRun, full_depth_push
from tww_sim.core.fp import f32


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _ulp(a, b):
    return abs(_bits(a) - _bits(b))


def rows(env):
    """Yield per-frame dicts: f, proc, x/z ULP + abs-u divergence, and the setcol cross-check."""
    cyl = env['cyl']
    dtm = env['dtm']
    seed = env['seed']
    eyes = env.get('eyes')
    setcol_pos = {r['f']: r['pos'] for r in env.get('setcol', [])}
    input_at = lambda k: dtm[k]['inp']

    run = FreeRun(cyl[0], seed_nspeed=seed['link']['nspeed'], computed_pose=True,
                  seed_old_pose=seed.get('old_pose'))
    run.pre_seed_input(input_at(0))
    link = run.link
    for k in range(1, min(44, len(cyl))):
        prev = cyl[k - 1]
        link.pos_x = f32(prev['link']['pos'][0]); link.pos_z = f32(prev['link']['pos'][2])
        run.tx = f32(prev['tetra']['pos'][0]); run.tz = f32(prev['tetra']['pos'][2])
        run.pend_link, run.pend_tetra = full_depth_push(prev['link']['cyl'], (run.tx, run.tz))
        eye = eyes[k - 1] if (eyes is not None and k - 1 < len(eyes)) else None
        row = run.step(input_at(k), csangle=cyl[k - 1]['csangle'], eye=eye,
                       center=cyl[k]['link']['cyl'])
        lv = cyl[k]['link']
        ex = _ulp(row['sim_link'][0], lv['pos'][0])
        ez = _ulp(row['sim_link'][1], lv['pos'][2])
        sc = ''
        if k in setcol_pos:
            d = _ulp(lv['pos'][0], setcol_pos[k][0]) + _ulp(lv['pos'][2], setcol_pos[k][2])
            sc = 'exact' if d == 0 else 'setcol!=cyl(%d)' % d
        yield dict(f=k, proc=cyl[k]['proc'], x_ulp=ex, z_ulp=ez,
                   x_u=abs(f32(row['sim_link'][0]) - f32(lv['pos'][0])),
                   z_u=abs(f32(row['sim_link'][1]) - f32(lv['pos'][2])), setcol=sc)


def load_env():
    root = _d
    def _j(name):
        p = os.path.join(root, 'fixtures', name)
        return json.load(open(p)) if os.path.exists(p) else None
    cyl = _j('courtyard_push_cyl.json')
    dtm = _j('courtyard_push_dtm.json')
    seed = _j('courtyard_push_seed.json')
    eye = _j('courtyard_push_eyepos.json')
    setcol = _j('courtyard_push_setcol.json')
    if not (cyl and dtm and seed):
        raise SystemExit("Courtyard capture fixtures not present (need a live slot-2 capture)")
    return dict(cyl=cyl['frames'], dtm=dtm['frames'], seed=seed,
                eyes=[r['eye'] for r in eye['frames']] if eye else None,
                setcol=setcol['frames'] if setcol else [])


def main():
    env = load_env()
    print("frame proc |  x ULP   x abs-u  |  z ULP   z abs-u  | live pos")
    print("-" * 72)
    worst = 0.0
    n_div = 0
    for r in rows(env):
        tot = math.hypot(r['x_u'], r['z_u'])
        worst = max(worst, tot)
        if r['x_ulp'] or r['z_ulp']:
            n_div += 1
        flag = '  <== roll-entry' if r['f'] in (3, 4, 5) else ''
        print("f%-3d  %-3d | %5d  %9.2e | %5d  %9.2e | %s%s" % (
            r['f'], r['proc'], r['x_ulp'], r['x_u'], r['z_ulp'], r['z_u'], r['setcol'], flag))
    print("-" * 72)
    print("divergent frames: %d/43   worst one-step position divergence: %.3e u" % (n_div, worst))


if __name__ == '__main__':
    main()
