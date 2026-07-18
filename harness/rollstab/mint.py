"""Mint anchors for the roll-stab sandbox.

Translated anchors: load a base anchor with the emulator PAUSED FIRST (zero frames run, so the
idle anim state is preserved bit-for-bit -- letting the game run even ~2.5s between load and
pause advances the idle/fidget state and desyncs the anchor from its seed json; that bug cost the
idle4..idle11 chain), write link_x/z += delta, save as the new anchor, and copy the seed json
with the new position.

The seed json also carries the REST_* fields rest.rest_state seeds the from-rest-exact sim
with, all read from RAM at the paused anchor:
  * the WAIT(4) blend frame ctrls (d/w frame + rate, player +0x2F64/+0x2F78/+0x2F60/+0x2F74),
  * the posMoveFromFootPos smoothing state (m359C/m35B4, +0x34C4/+0x34DC),
  * the STORED delayed foot poses t2 (mFootData[i] 018/00C: rtoe +0x3CF8, ltoe +0x3E10, rheel
    +0x3CEC, lheel +0x3E04 on JP) and t1 (the same fields after ONE paused frame-advance -- the
    advanced frame's execute stores the pose the anchor's matrices held). These carry the BASE
    anchor's position rounding noise, which a translated anchor's re-posed stream cannot.

    python -m harness.rollstab.mint base=<anchor> name=<anchor> dx=0.0 dz=0.05
"""
import os, sys, json, time, struct
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path:
    sys.path.append(_tb)

import dolphin_mem as D
from harness import dolphin_env as ENV
from harness.rollstab.geometry import ANCHOR_DIR
from tww_sim.core.fp import f32 as _f

_FOOT_OFF = dict(rtoe=0x3CF8, ltoe=0x3E10, rheel=0x3CEC, lheel=0x3E04)  # JP mFootData 018/00C


def _player(h, m):
    return struct.unpack('>I', D.read_bytes(h, m, 0x803AD860, 4))[0]


def _f32_at(h, m, addr):
    return struct.unpack('>f', D.read_bytes(h, m, addr, 4))[0]


def _foot_tuple(h, m, Pp):
    out = []
    for key in ('rtoe', 'ltoe', 'rheel', 'lheel'):
        out += list(struct.unpack('>3f', D.read_bytes(h, m, Pp + _FOOT_OFF[key], 12)))
    return out


def _load_paused(path):
    D.control_pipe_quiet('pause')
    time.sleep(0.5)
    D.control_pipe_quiet('savestate', {'action': 'load', 'path': path.replace('\\', '/')})
    time.sleep(1.5)


def capture_rest(src):
    """Read the rest_* seed fields from an anchor savestate (leaves the anchor re-loaded)."""
    _load_paused(src)
    h, m = D.attach()
    Pp = _player(h, m)
    rest = dict(rest_d_frame=_f32_at(h, m, Pp + 0x2F64),
                rest_w_frame=_f32_at(h, m, Pp + 0x2F78),
                rest_d_rate=_f32_at(h, m, Pp + 0x2F60),
                rest_w_rate=_f32_at(h, m, Pp + 0x2F74),
                rest_m359C=_f32_at(h, m, Pp + 0x34C4),
                rest_m35B4=_f32_at(h, m, Pp + 0x34DC),
                rest_t2=_foot_tuple(h, m, Pp))
    # ONE paused frame-advance stores the anchor's held pose into mFootData (t1). rest_noops =
    # advances-until-d-changes = the anchor's DTM-alignment / savestate capture phase (see #30).
    d0 = rest['rest_d_frame']
    noops = 0
    for _ in range(3):
        D.control_pipe_quiet('advance', {'frames': 1})
        time.sleep(0.3)
        noops += 1
        if _f32_at(h, m, Pp + 0x2F64) != d0:
            break
    rest['rest_noops'] = noops
    rest['rest_t1'] = _foot_tuple(h, m, Pp)
    _load_paused(src)          # restore: the advance must never leak into the minted anchor
    return rest


def capture_full_seed(h, m):
    """Read the COMPLETE seed json (base state + rest_* fields) from the currently loaded paused
    anchor. Unlike `mint` (translate + inherit the base seed), this reads EVERY field from RAM, so
    it can mint an anchor whose equip/idle/facing differs from any existing base (e.g. a SHEATHED
    roll anchor -- session 36). Assumes the desired paused state is already live + saved to `dst`."""
    Pp = _player(h, m)
    seed = dict(link_x=D.read_named(h, m, 'link_x'), link_z=D.read_named(h, m, 'link_z'),
                link_y=_f32_at(h, m, Pp + 0x124),
                facing=D.read_named(h, m, 'facing') & 0xFFFF,
                shape_angle_y=D.read_named(h, m, 'shape_angle_y') & 0xFFFF,
                travel_angle=D.read_named(h, m, 'travel_angle') & 0xFFFF,
                csangle=D.read_named(h, m, 'csangle') & 0xFFFF,
                link_state=D.read_named(h, m, 'link_state'),
                anim_frame=_f32_at(h, m, Pp + 0x2F64),
                mEquipItem=struct.unpack('>H', D.read_bytes(h, m, Pp + 0x3488, 2))[0])
    seed['sword_drawn'] = (seed['mEquipItem'] == 0x103)
    seed['equip_item'] = seed['mEquipItem']
    return seed


def mint_current(name):
    """Mint the anchor from whatever Link is doing RIGHT NOW (the live, paused state) -- full-seed
    capture, no base inheritance. Set Link up live first (load + press A to sheathe, settle the
    idle, etc.), then call this. Saves the savestate, captures the complete seed json (incl. the
    rest_* fields via capture_rest), and leaves the anchor re-loaded."""
    dst = os.path.join(ANCHOR_DIR, name + '.sav')
    D.control_pipe_quiet('pause')
    time.sleep(0.4)
    D.control_pipe_quiet('savestate', {'action': 'save', 'path': dst.replace('\\', '/')})
    time.sleep(0.8)
    rest = capture_rest(dst)          # loads dst, reads rest_*, t1-advance, reloads dst (paused)
    h, m = D.attach()
    seed = capture_full_seed(h, m)
    seed.update(rest)
    json.dump(seed, open(os.path.join(ANCHOR_DIR, name + '.seed.json'), 'w'), indent=1)
    print('minted %s' % dst)
    print('  pos=(%.6f,%.6f,%.6f) facing=%d csangle=%d state=%d equip=0x%X anim=%.5f' % (
          seed['link_x'], seed['link_y'], seed['link_z'], seed['shape_angle_y'], seed['csangle'],
          seed['link_state'], seed['mEquipItem'], seed['anim_frame']))
    print('  rest d=%.6f w=%.6f d_rate=%.4f w_rate=%.4f m359C=%.6g' % (
          rest['rest_d_frame'], rest['rest_w_frame'], rest['rest_d_rate'], rest['rest_w_rate'],
          rest['rest_m359C']))
    return seed


def mint(base, name, dx, dz):
    ENV.ensure_running()
    src = os.path.join(ANCHOR_DIR, base + '.sav')
    rest = capture_rest(src)
    h, m = D.attach()
    x0 = D.read_named(h, m, 'link_x')
    z0 = D.read_named(h, m, 'link_z')
    nx, nz = _f(x0 + dx), _f(z0 + dz)
    D.cmd_writename('link_x', repr(nx))
    D.cmd_writename('link_z', repr(nz))
    print('pos (%.10f,%.10f) -> (%.10f,%.10f)' % (x0, z0, nx, nz))
    dst = os.path.join(ANCHOR_DIR, name + '.sav')
    D.control_pipe_quiet('savestate', {'action': 'save', 'path': dst.replace('\\', '/')})
    # seed json travels with the anchor
    seed_src = os.path.join(ANCHOR_DIR, base + '.seed.json')
    seed = json.load(open(seed_src))
    seed['link_x'], seed['link_z'] = float(nx), float(nz)
    seed.update(rest)
    json.dump(seed, open(os.path.join(ANCHOR_DIR, name + '.seed.json'), 'w'), indent=1)
    print('captured %s (rest d=%.10f w=%.10f m359C=%.10g)' % (
          dst, rest['rest_d_frame'], rest['rest_w_frame'], rest['rest_m359C']))


def _sdiff(a, b):
    d = (int(a) - int(b)) & 0xFFFF
    return d - 65536 if d > 32768 else d


def mint_novel(name, rest_x, rest_z, facing, target_csangle, floor_y, base='kaze_r11_rollstab_idle13@twwgz',
               settle_walk=42, settle_idle=20):
    """Mint a fresh anchor for a NOVEL seam with the camera BEHIND Link (session-50 procedure).

    Load `base`, `cmd_teleport` to (rest_x, floor_y, rest_z) facing `facing` (SAME floor Y => no
    sploosh), then get the camera behind Link and mint. The L (recenter) button is NOT wired to live
    input, so the camera is aimed by PANNING the free cam with the C-STICK; and because the free cam
    gets a one-time leash pull as Link speeds up, the camera is PRE-SETTLED by WALKING (C-down held)
    past that pull before minting -- else csangle drifts during the solver's approach and breaks REST
    bit-exactness. All of this is PRE-mint, so none of it lands in the delivered DTM (Dereck's ask).
    After minting, verify with `rest.main(anchor, seam=<SeamGeo>, dtm_seed=0)` -- a mint_current anchor
    needs seed=0 (noops=2) + C-down. Returns the seed dict."""
    from harness.rollstab.rest import dtm_stick
    from tww_sim.land.plan_land import stick_for_bearing
    import time
    ENV.ensure_running()
    src = os.path.join(ANCHOR_DIR, base + '.sav')
    _load_paused(src)
    h, m = D.attach()
    D.cmd_teleport(['x=%r' % rest_x, 'y=%r' % floor_y, 'z=%r' % rest_z, 'facing=%d' % (int(facing) & 0xFFFF), 'frames=2'])
    time.sleep(0.4)

    def cs():
        return D.read_named(h, m, 'csangle') & 0xFFFF
    # pan the free cam toward target_csangle (C-right raises csangle, C-left lowers), 1 frame at a time
    for _ in range(80):
        if abs(_sdiff(target_csangle, cs())) < 800:
            break
        sub = 255 if _sdiff(target_csangle, cs()) > 0 else 0
        D.control_pipe_quiet('advancewith', {'stickX': 128, 'stickY': 128, 'substickX': sub, 'substickY': 128, 'buttons': 0, 'frames': 1})
        time.sleep(0.03)
    # walk-settle toward `facing` (C-down) UNTIL csangle FREEZES -- a fixed frame count
    # under-settles at some seams and the cam creeps through the approach (dead-end ledger #42).
    chunk = 7
    walked, prev_cs = 0, None
    while walked < settle_walk:
        c0 = cs()
        if prev_cs is not None and c0 == prev_cs:
            break
        prev_cs = c0
        sx, sy = dtm_stick(stick_for_bearing(int(facing) & 0xFFFF, c0, 1.0))
        D.control_pipe_quiet('advancewith', {'stickX': sx, 'stickY': sy, 'substickX': 128, 'substickY': 0, 'buttons': 0, 'frames': chunk})
        walked += chunk
        time.sleep(0.1)
    time.sleep(0.2)
    # stop + idle (C-down) to a clean WAITS rest at the frozen camera
    D.control_pipe_quiet('advancewith', {'stickX': 128, 'stickY': 128, 'substickX': 128, 'substickY': 0, 'buttons': 0, 'frames': settle_idle})
    time.sleep(0.3)
    # NOTE do NOT teleport-to-rest after the settle: a teleport resets the cam-Link leash and the
    # next from-rest walk re-pulls the cam, so the settle must END at the rest spot (ledger #42).
    print('pre-mint: csangle=%d (target %d) state=%d' % (cs(), int(target_csangle) & 0xFFFF, D.read_named(h, m, 'link_state')), flush=True)
    return mint_current(name)


def mint_online(name, geo_path, d2s=580.0, base='kaze_r11_rollstab_idle13@twwgz',
                perp_tol=2.0, max_iter=3, settle_est=160.0, target_csangle=None):
    """Mint an ON-LINE pan-camera anchor for a novel seam, first-class (session-54 procedure,
    dead-ends #36/#37). The two constraints a novel-seam anchor must satisfy:
      * the camera must be FROZEN (the mint_novel C-stick pan arms the MANUAL cam; anywhere the
        auto-cam tracks Link's walk, an unpanned mint's csangle creeps and the constant-cs rest
        model can never be bit-exact -- #36);
      * the BASELINE ROLL `old` must sit ON the F-through-S line (within the arc reach ~+-9u;
        `mint_novel`'s settle walk drifts off the park bearing AND the resulting misaim's MOVE
        turn to F adds more perp during the approach -- ~12u at the 97m corner's 23-deg misaim --
        so an off-line anchor makes `solve_focused` find 0 hits with Phase-A best score == the
        residual offset -- #37).
    Parks on the seam's aim line at `d2s` (+`settle_est` for the settle walk), pan-mints, then
    measures the PURE-SIM baseline roll `old`'s perp from the minted seed (`solver.run(anchor, [])`
    -- the quantity the arc bracket must center on; the REST perp alone under-measures by the turn
    drift) and RE-PARKS by it with a SECANT gain (session 58: the perp response per unit shift is
    NOT 1:1 everywhere -- ~1.8 at a large settle misaim -- so the 1:1 step can oscillate; the gain
    is estimated from the previous iteration and clamped). NOTE `d2s` must stay ~580 (the solver's
    A_proj derivation and the spF-17 cap distance assume the proven rest envelope) and the seam
    needs park = d2s + settle travel (~1000u+) of clear corridor -- `seam_screen.py` measures it.
    The aim comes from the geo fixture (`aim_deg` if declared, else the interior bisector); the park
    facing = the aim (the anchor need NOT face F exactly -- the arc bracket absorbs the misaim's
    ANGLE, #37 corollary; it is the misaim's perp DRIFT this loop cancels).
    After minting, REST-verify: python -m harness.rollstab.rest anchor=<name> geo=<geo> seed=0."""
    from harness.rollstab.seamgeo import SeamGeo
    from tww_sim.core.mathlib import deg_to_s16
    import math
    geo = json.load(open(geo_path))
    aim_deg = geo.get('aim_deg', geo['bisector_deg'])
    ar = math.radians(float(aim_deg) % 360.0)
    dx, dz = math.sin(ar), math.cos(ar)
    Sx, Sz = geo['S'][0], geo['S'][2]
    facing = deg_to_s16(float(aim_deg) % 360.0)
    if target_csangle is None:
        target_csangle = facing
    park_x = Sx - (d2s + settle_est) * dx
    park_z = Sz - (d2s + settle_est) * dz
    seed = None
    prev_perp, prev_shift = None, None
    for it in range(max_iter):
        seed = mint_novel(name, park_x, park_z, facing, target_csangle, geo['link_y'], base=base)
        seam = SeamGeo(geo, seed['csangle'])
        rest = (seed['link_x'], seed['link_z'])
        # the load-bearing perp = the PURE-SIM baseline roll old's (rest perp + the turn drift)
        import harness.rollstab.solver as _SV
        for _c in (_SV._BASE, _SV._BASE_WALLED):    # the seed on disk just changed: drop the
            for _k in [k for k in _c if k[0] == name]:  # cached rest states for this anchor
                del _c[_k]
        r0 = _SV.run(name, [], dtm_seed=0, seam=seam)
        old = r0.get('old') if (r0 and r0.get('fired')) else None
        perp = seam.perp(old) if old else seam.perp(rest)
        print('mint_online iter %d: old_perp=%.3f (rest_perp=%.3f) old=%s d2S(rest)=%.1f '
              'csangle=%d F=%d facing=%d' % (
              it, perp, seam.perp(rest), old, seam.d2S(rest),
              seed['csangle'], seam.F, seed['shape_angle_y']), flush=True)
        if old is None:
            # unfired baseline = rest outside the ~580u envelope (ledger #42); never accept on
            # the rest-perp fallback -- re-park on the along error and retry
            print('mint_online iter %d: baseline roll did NOT fire (d2S %.1f vs d2s %.1f) -- '
                  're-parking on along error' % (it, seam.d2S(rest), d2s), flush=True)
        elif abs(perp) <= perp_tol:
            print('mint_online: ON-LINE (baseline |old perp| %.3f <= %.1f)' % (abs(perp), perp_tol),
                  flush=True)
            return seed
        # re-park by a SECANT-gain step (clamped; 1:1 on the first iteration) -- the perp response
        # per unit shift is ~1.8 at a large settle misaim, so a 1:1 step oscillates (ledger #42).
        # A rest-perp fallback (old=None) measures a DIFFERENT quantity: drop the secant history.
        if old is None:
            prev_perp = prev_shift = None
        if prev_shift and prev_perp is not None:
            gain = (perp - prev_perp) / prev_shift
            gain = max(0.4, min(2.5, gain))
        else:
            gain = 1.0
        shift = -perp / gain
        prev_perp, prev_shift = perp, shift
        along_err = seam.along(rest) + d2s          # rest sits at along ~ -d2s on the aim line
        park_x += shift * seam.PX - along_err * seam.DIRX
        park_z += shift * seam.PZ - along_err * seam.DIRZ
    print('mint_online: WARNING still off-line after %d iters (perp=%.3f)' % (max_iter, perp), flush=True)
    return seed


if __name__ == '__main__':
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    if 'online' in o:                     # on-line pan mint for a NOVEL seam (session-54 procedure)
        mint_online(o['online'], o['geo'], d2s=float(o.get('d2s', 580.0)),
                    max_iter=int(o.get('max_iter', 3)),
                    base=o.get('base', 'kaze_r11_rollstab_idle13@twwgz'))
    elif 'novel' in o:                    # camera-behind mint for a NOVEL seam (session-50 procedure)
        mint_novel(o['novel'], float(o['x']), float(o['z']), int(o['facing'], 0),
                   int(o['csangle'], 0), float(o['y']), base=o.get('base', 'kaze_r11_rollstab_idle13@twwgz'))
    elif 'current' in o:                  # mint the live paused state as a fresh full-seed anchor
        ENV.ensure_running()
        mint_current(o['current'])
    else:
        mint(o['base'], o['name'], float(o.get('dx', 0.0)), float(o.get('dz', 0.0)))
