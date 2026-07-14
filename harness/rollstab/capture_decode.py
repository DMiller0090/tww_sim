"""capture_decode.py -- JITTER-IMMUNE live capture of the stick DECODE + two-angle state.

WHY THIS EXISTS (session 40, 2026-07-14): `run_dtm`'s log playback fast-polls and its per-frame read
lands +-1 frame off, so a per-frame read of a fast-changing value (a 1-frame fine's decoded target/msd,
the facing) can silently return the NEIGHBORING frame's value. That poll jitter has now misled the
roll-stab diagnosis in sessions 36, 37, 39 AND the session-40 intermediate (the "MOVE-turn shape
overshoot" of dead-end #31 was a jittered read of the aim frame). This tool removes the jitter two ways:
  1. **game_frame tagging** (like `capture_walkentry.py`): every row is tagged with the deterministic
     emulator frame (`game_frame = emu - F0`, F0 = the savestate's stored frame), so alignment is exact
     and a misaligned poll is DETECTABLE, not silent.
  2. **hold-to-measure** (`hold_decode`): a stick held CONSTANT for N frames decodes to the same value
     every frame, so any poll within the hold reads the true value regardless of jitter.

Use it for ANY per-frame live decode / facing / two-angle measurement in the roll-stab pipeline; do NOT
read those off a raw `run_dtm` log without game_frame tags.

JP RAM offsets (player = deref 0x803AD860; these are the JP GZLJ offsets = US class offset - 0xD8 for
the player-specific 0x34xx/0x35xx fields; the fopAc base fields use run_dtm's proven reads):
  target  m34E8        @ P+0x3410 (s16)   -- setStickData want-angle = m34DC + csangle
  m34DC                @ P+0x3404 (s16)   -- stick want-angle pre-csangle
  mStickDistance       @ P+0x34D8 (f32)   -- the decoded stick magnitude (msd)
  proc                 @ P+0x3100 (s32)   -- run_dtm reads this
  speedF               @ P+0x17C  (f32)   -- run_dtm reads this
  shape_angle.y/travel -- via run_dtm's named reads ('shape_angle_y' / 'travel_angle')

KEY FINDING this tool established (dead-end #32): the closed-form `main_stick_decode` is BIT-EXACT live
for a HELD stick (incl. the (0.889,1.0) band), but a 1-FRAME TRANSIENT band stick decodes live to ~the
prior/aim value (input-layer smoothing near the magnitude cap) -- the sim decodes it raw. Modelling that
transient behaviour to f32 is the open frontier for the sheathed roll-stab clip; use `hold` (settled
truth) and a transient sweep (build on `capture`) to characterize it.

    python -m harness.rollstab.capture_decode ship [hit=0]        # play a solver hit's stream, diff vs sim
    python -m harness.rollstab.capture_decode hold                # jitter-immune held-stick decode test

Live-only (Dolphin). Relaunches Dolphin like rest.py / capture_walkentry.py.
"""
import json
import os
import struct
import subprocess
import sys

# >>> repo bootstrap
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path:
    sys.path.append(_tb)

LINK_PTR = 0x803AD860
OFF = dict(target=0x3410, m34dc=0x3404, mStickDistance=0x34D8)   # JP player-ptr offsets


def _emu_frame():
    out = subprocess.run([sys.executable, os.path.join(_tb, 'dolphin_mem.py'), 'status'],
                         capture_output=True, text=True).stdout.strip()
    try:
        return json.loads(out).get('frame')
    except Exception:
        return None


def _read_f0(sav):
    """Load the savestate PAUSED and read its stored emulator frame (the deterministic F0)."""
    import dolphin_mem as D
    D.control_pipe_quiet('clearinput')
    D.control_pipe_quiet('pause')
    D.control_pipe_quiet('savestate', {'action': 'load', 'path': sav.replace('\\', '/')})
    return _emu_frame()


def capture(anchor, stream, tail=6, log_extra=2):
    """Play `stream` (list of (sx, sy, buttons)) from `anchor` via a clean DTM and return rows tagged
    with the deterministic game_frame plus the decode + two-angle state. Jitter-immune by game_frame.
    `stream` is DELIVERED as-is -- calibrate bytes with rest.dtm_stick BEFORE calling if planning."""
    from harness.dtm.run_dtm import run_dtm, land_ready, resolve_anchor
    import harness.dtm.run_dtm as RD
    import dolphin_mem as D

    f0 = _read_f0(resolve_anchor(anchor))
    _orig = RD._read_frame

    def rich(h, m):
        d = _orig(h, m)
        p = struct.unpack('>I', D.read_bytes(h, m, LINK_PTR, 4))[0]
        d['emu'] = _emu_frame()
        d['target'] = struct.unpack('>h', D.read_bytes(h, m, p + OFF['target'], 2))[0] & 0xFFFF
        d['m34dc'] = struct.unpack('>h', D.read_bytes(h, m, p + OFF['m34dc'], 2))[0] & 0xFFFF
        d['msd'] = struct.unpack('>f', D.read_bytes(h, m, p + OFF['mStickDistance'], 4))[0]
        d['shape'] = D.read_named(h, m, 'shape_angle_y') & 0xFFFF
        d['travel'] = D.read_named(h, m, 'travel_angle') & 0xFFFF
        return d
    RD._read_frame = rich
    try:
        sticks = [dict(stickX=sx, stickY=sy, substickX=128, substickY=128, buttons=b)
                  for (sx, sy, b) in stream]
        sticks += [dict(stickX=128, stickY=128, substickX=128, substickY=128, buttons=0)] * tail
        end = run_dtm(sticks, anchor=anchor, ready=land_ready, relaunch_dolphin=True,
                      log_frames=len(stream) + log_extra, verbose=False)
    finally:
        RD._read_frame = _orig
    rows = []
    for r in end['log']:
        gf = (r['emu'] - f0) if (r.get('emu') is not None and f0 is not None) else None
        rows.append(dict(game_frame=gf, proc=r['proc'], pos_x=r['pos_x'], pos_z=r['pos_z'],
                         shape=r['shape'], travel=r['travel'], speedF=r['speedF'],
                         target=r['target'], m34dc=r['m34dc'], msd=round(r['msd'], 6)))
    return dict(anchor=anchor, F0=f0, rows=rows)


def hold_decode(anchor, test_sticks, hold=8):
    """Jitter-immune decode measurement: hold each stick CONSTANT for `hold` frames (walk to cruise
    first) and read live (m34dc, msd). A constant stick decodes the same every frame -> poll jitter
    cannot misalign it. Compares each to the closed-form `main_stick_decode`. This is how session 40
    proved the HELD decode is bit-exact live even in the (0.889,1.0) band (dead-end #32)."""
    from harness.rollstab import rest as C
    from tww_sim.core.mathlib import main_stick_decode
    _, straight, aim = C.sticks_of(anchor)
    stream = [straight + (0,)] * 10 + [aim + (0,)] * 6
    spans = []
    for t in test_sticks:
        spans.append((tuple(t), len(stream), len(stream) + hold))
        stream += [tuple(t) + (0,)] * hold + [aim + (0,)] * 4
    res = capture(anchor, stream)
    rows = res['rows']
    out = []
    for (t, a, b) in spans:
        cf_ang, cf_msd = main_stick_decode(*t)
        cf_m34dc = (cf_ang + 0x8000) & 0xFFFF
        vals = [(rows[k]['m34dc'], round(rows[k]['msd'], 4)) for k in range(a + 3, min(b + 3, len(rows)))]
        match = all(v == (cf_m34dc, round(cf_msd, 4)) for v in vals) if vals else None
        out.append(dict(stick=list(t), cf=(cf_m34dc, round(cf_msd, 4)), live=vals, match=match))
        print('stk %-9s sim(m34dc=%d,msd=%.4f) | live held: %s  %s' % (
            str(t), cf_m34dc, cf_msd, vals, 'MATCH' if match else 'DIFF'))
    return out


def ship(idx=0):
    """Play a solver hit's ship stream jitter-immune and diff vs the from-rest sim, aligned by
    game_frame -- the trustworthy per-frame delivery diff (do NOT use a raw run_dtm log for this)."""
    from harness.rollstab import rest as C
    from harness.rollstab.solver import HITS_PATH
    hit = json.load(open(HITS_PATH))[idx]
    anchor = hit['anchor']
    stream = [tuple(fr) for fr in hit['stream']]
    res = capture(anchor, stream)
    out = os.path.join(_rb, '_generated', 'capture_decode_ship.json')
    json.dump(res, open(out, 'w'), indent=1)
    # sim side
    s = C.rest_state(anchor)
    sim = []
    for (sx, sy, b) in stream:
        s.step(sx, sy, buttons=b)
        sim.append((s.state & 0xFF, s.facing & 0xFFFF, s.travel & 0xFFFF, round(s.speedF, 3),
                    s.target & 0xFFFF, round(s.msd, 4)))
    print('wrote %s (F0=%s)' % (out, res['F0']))
    print(' live rows (game_frame-tagged): idx gf proc shape travel tgt msd speedF -- diff vs sim by hand')
    for i, r in enumerate(res['rows']):
        print(' %2d gf=%3s 0x%02x shape=%d travel=%d tgt=%d msd=%.4f spF=%.2f' % (
            i, r['game_frame'], r['proc'], r['shape'], r['travel'], r['target'], r['msd'], r['speedF']))
    return res


if __name__ == '__main__':
    kw = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    if 'hold' in sys.argv:
        A = kw.get('anchor', 'kaze_r11_rollstab_sheathed@twwgz')
        hold_decode(A, [(96, 192), (98, 191), (98, 196), (77, 249)])
    else:
        ship(int(kw.get('hit', 0)))
