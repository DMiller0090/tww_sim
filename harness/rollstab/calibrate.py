"""Live prefix calibration: pin the sim to a live anchor run, bit-exact from row K0 on.

The characterized-from-rest sim cannot model every idle-anim walk entry (the anchor may rest in
WAIT(4)/sword-out `waits`, a fidget, ...), so the plan starts with a FIXED constant-stick prefix
that absorbs the entry transient, and ONE live DTM run measures the truth. `apply_calibration`
then overwrites, at row K0:
  * pos_x/pos_z            (the live f32 position; live f_k == sim row k, both input pipelines
                            carry the 2-frame delay),
  * fc0/fc1 anim phases    (the under-body walk controllers),
  * m359C / m35B4          (the posMoveFromFootPos recursive-smoothing state),
  * the toe stream t1/t2   (re-posed at the seeded phase; without this the pre-seed poses linger
                            2 frames and the 0.3/0.7 recursion carries the raw-f312 error ~20
                            frames -- the last term found in session 8).
After this the sim is BIT-EXACT vs live through cruise, mid-walk arcs, partial-magnitude dips,
and the roll (verified 0-diff per frame; see the package README).

    python -m harness.rollstab.calibrate anchor=kaze_r11_rollstab_idle5@twwgz
        -> writes _generated/rollstab_calib.json (+ prints the per-frame verify)
"""
import os, sys, json, struct
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path:
    sys.path.append(_tb)

from tww_sim.land.land import LandState
from tww_sim.land.plan_land import stick_for_bearing
from harness.rollstab import geometry as G

CALIB_PATH = os.path.join(_rb, '_generated', 'rollstab_calib.json')
NPREF = 10                     # straight prefix frames (the entry transient fully inside)
K0 = 7                         # calibration row consumers seed from (at cap, before any knob)
NCRUISE = 18


def sticks_of(anchor):
    seed = G.load_seed(anchor)
    cs = seed['csangle'] & 0xFFFF
    f0 = seed['shape_angle_y'] & 0xFFFF
    straight = stick_for_bearing(f0, cs, 1.0)
    aim = stick_for_bearing(G.F, cs, 1.0)
    return seed, straight, aim


def base_state(anchor):
    """Sim seed for the anchor. foot_native=False: the calibration overwrites the walk anim
    phase, only settable on the pure-Python foot path (the fused core carries its own state)."""
    seed, straight, aim = sticks_of(anchor)
    s = LandState(pos_x=seed['link_x'], pos_z=seed['link_z'],
                  facing=seed['shape_angle_y'] & 0xFFFF, travel=seed['travel_angle'] & 0xFFFF,
                  csangle=seed['csangle'] & 0xFFFF, state=seed['link_state'], nspeed=0.0,
                  speedF=0.0, idle_frame=seed['anim_frame'], use_anim=True, native=False,
                  foot_native=False, sword_drawn=True, idle_anim='waits')
    s._foot.st.m34C3 = 2
    s._foot._pending_morf = LandState.MOVE_REENTRY_MORF
    s.step(128, 128)           # the DTM seed frame (build_dtm_from_sticks seed=1)
    return s


def apply_calibration(s, calib, k):
    """Overwrite pos + the under-body anim phase + smoothing state + toe stream at live row k."""
    lf = calib['frames'][k]
    s.pos_x = lf['pos_x']
    s.pos_z = lf['pos_z']
    assert (s.facing & 0xFFFF) == (lf['facing'] & 0xFFFF), (s.facing, lf['facing'])
    if lf.get('d_frame') is not None and s._foot is not None:
        st = s._foot.st
        st.fc0.frame = lf['d_frame']
        st.fc1.frame = lf['w_frame']
        if lf.get('m359C') is not None:
            s._foot.prev_f312 = lf['m359C']
        if lf.get('m35B4') is not None:
            s._foot.m35B4 = lf['m35B4']
        f_cur = lf['d_frame']
        f_prev = f_cur - st.fc0.rate
        if f_prev < 0.0:
            f_prev += st.fc0.end
        mv0, mv1 = st.move0, (st.move1 if st.move1 else st.move0)
        s._foot.t2 = s._foot.ff.step_feet(mv0, mv1, f_prev, f_prev, st.ratio, -1.0)
        s._foot.t1 = s._foot.ff.step_feet(mv0, mv1, f_cur, f_cur, st.ratio, -1.0)
    return s


def calibrated_state(anchor, calib=None, k0=K0):
    """The bit-exact-vs-live warm state at row k0 (clone this for solver runs)."""
    if calib is None:
        calib = json.load(open(CALIB_PATH))
        assert calib['anchor'] == anchor, (calib['anchor'], anchor)
    s = base_state(anchor)
    _, straight, aim = sticks_of(anchor)
    stream = [straight] * NPREF + [aim] * (k0 - NPREF + 1)
    for (sx, sy) in stream:
        s.step(sx, sy)
    return apply_calibration(s, calib, k0)


def main(anchor):
    from harness.dtm.run_dtm import run_dtm, land_ready
    import harness.dtm.run_dtm as R
    import dolphin_mem as D
    _orig = R._read_frame

    def rich(h, m):
        d = _orig(h, m)
        Pp = struct.unpack('>I', D.read_bytes(h, m, 0x803AD860, 4))[0]
        for kk, off in (('d_frame', 0x2F64), ('w_frame', 0x2F78), ('d_rate', 0x2F60),
                        ('m3598', 0x34C0), ('m359C', 0x34C4), ('m35B4', 0x34DC)):
            d[kk] = struct.unpack('>f', D.read_bytes(h, m, Pp + off, 4))[0]
        return d
    R._read_frame = rich

    _, straight, aim = sticks_of(anchor)
    stream = [straight] * NPREF + [aim] * NCRUISE
    sticks = [dict(stickX=sx, stickY=sy, substickX=128, substickY=128, buttons=0)
              for (sx, sy) in stream] + [dict(stickX=128, stickY=128, substickX=128,
                                              substickY=128, buttons=0)] * 20
    end = run_dtm(sticks, anchor=anchor, ready=land_ready, relaunch_dolphin=True,
                  log_frames=len(stream) + 2, verbose=True)
    frames = end['log']
    calib = dict(anchor=anchor, NPREF=NPREF, K0=K0,
                 frames=[dict(pos_x=f['pos_x'], pos_z=f['pos_z'],
                              facing=f['facing'] & 0xFFFF, proc=f['proc'],
                              d_frame=f.get('d_frame'), w_frame=f.get('w_frame'),
                              d_rate=f.get('d_rate'), m3598=f.get('m3598'),
                              m359C=f.get('m359C'), m35B4=f.get('m35B4')) for f in frames])
    os.makedirs(os.path.dirname(CALIB_PATH), exist_ok=True)
    json.dump(calib, open(CALIB_PATH, 'w'))
    print('wrote %s (%d frames)' % (CALIB_PATH, len(frames)), flush=True)

    s = calibrated_state(anchor, calib)
    nbad = 0
    for k in range(K0 + 1, len(stream)):
        sx, sy = stream[k]
        s.step(sx, sy)
        lf = frames[k] if k < len(frames) else None
        if lf is None:
            break
        ok = (s.pos_x == lf['pos_x'] and s.pos_z == lf['pos_z']
              and (s.facing & 0xFFFF) == (lf['facing'] & 0xFFFF))
        nbad += 0 if ok else 1
        print('  k=%-2d sim(%.9f,%.9f) live(%.9f,%.9f)%s' % (
              k, s.pos_x, s.pos_z, lf['pos_x'], lf['pos_z'], '' if ok else '  <-- DIFF'),
              flush=True)
    print('\n%s' % ('CALIBRATED BIT-EXACT' if nbad == 0 else 'STILL DIVERGED (%d)' % nbad))
    return 0 if nbad == 0 else 1


if __name__ == '__main__':
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    sys.exit(main(o.get('anchor', 'kaze_r11_rollstab_idle2@twwgz')))
