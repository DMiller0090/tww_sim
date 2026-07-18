"""From-rest exact seeding + the one-live-run verification gate.

`rest_state(anchor)` builds a sim that is BIT-EXACT vs live FROM ROW 0 with NO mid-run
calibration -- verified 0-ULP through walk entry, cruise, bearing arcs, partial-magnitude dips,
the turn lean, and the roll (kaze r11, 2026-07-10). It needs the anchor's seed json `rest_*`
fields (mint.py captures them at the paused anchor):
  * rest_d_frame/rest_w_frame + rates  (the WAIT(4) blend's two J3DFrameCtrl phases),
  * rest_m359C / rest_m35B4            (the posMoveFromFootPos smoothing state at rest),
  * rest_t1 / rest_t2                  (the STORED delayed foot poses, mFootData 018/00C --
                                        they carry the pre-mint position's f32 rounding noise,
                                        which re-posing at a translated position cannot).
The model behind it (all decomp-grounded, see the package README):
  * procWait re-inits the WAITS/WALK blend EVERY idle frame (setBlendMoveAnime(-1) -> the f31
    frame round-trip) -- foot_speedf.seed_rest_blend + the rest-blend WAIT branch;
  * the draw poses at the END of the frame -- post-integration pos (setWorldMatrix) -- via the
    deferred-draw mode;
  * the base tilts by the MOVE turn lean shape_angle.z = m351C>>1 (setMoveSlantAngle);
  * a savestate-anchored run_dtm movie has 2 leading alignment rows the game never ran
    (REST_NOOPS).

STICK CALIBRATION (dtm_stick): dtm_make writes 255->254 / 0->1 into every DTM, so plans must be
built FROM the delivered bytes -- sim the calibrated stick, never the raw one.

CLI -- the per-anchor live gate (one clean-DTM run, then the offline row diff):
    python -m harness.rollstab.rest anchor=kaze_r11_rollstab_idle13@twwgz
        -> writes _generated/rollstab_calib.json, then verify_rest must print REST BIT-EXACT
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
NPREF = 10                     # straight prefix frames of the verification stream
NCRUISE = 18
REST_NOOPS = 2      # leading run_dtm rows the game never ran (savestate-anchored DTM alignment):
#                     live d_frame holds the REST value through sim rows [seed, 0] and first advances
#                     at row 1 (verified on idle13: d = 30.8, 30.8, 31.9, 33.0(entry) for rows 0..2).

# dtm_make's getMainStickValue calibration: every authored DTM delivers 255 as 254 and 0 as 1.
# The undelivered raw byte cost a 60-tread stick-angle error on the (73,255) arc (found live).
_DTM_CAL = {255: 254, 0: 1}


def dtm_stick(stk):
    """Map a planned stick to the bytes dtm_make will actually deliver. Plan/sim ONLY these."""
    return (_DTM_CAL.get(stk[0], stk[0]), _DTM_CAL.get(stk[1], stk[1]))


def sticks_of(anchor, seam=None):
    """(seed, straight, aim) for the verification/approach stream. `straight` aims at the anchor
    facing; `aim` aims at the seam's thrust facing F. `seam` (a SeamGeo) generalizes a NOVEL seam --
    default None uses the kaze `geometry.F` (byte-identical). For an anchor minted facing INTO its
    corner, straight ~= aim, so the straight walk alone already verifies the from-rest approach."""
    seed = G.load_seed(anchor)
    cs = seed['csangle'] & 0xFFFF
    f0 = seed['shape_angle_y'] & 0xFFFF
    F = seam.F if seam is not None else G.F
    straight = dtm_stick(stick_for_bearing(f0, cs, 1.0))
    aim = dtm_stick(stick_for_bearing(F, cs, 1.0))
    return seed, straight, aim


def rest_state(anchor, walls=None, model_draw=None, dtm_seed=1, noops=None):
    """The bit-exact-from-REST sim state -- NO live calibration run. Seeds the WAIT(4) rest blend
    (both frame ctrls + rates, the stored rest toe stream, m359C/m35B4) from the anchor's seed
    json rest_* fields and models the 2 alignment no-ops, so ANY input stream from row 0 --
    including start-crawl micro-moves during acceleration -- is simulable offline. Clone this for
    solver runs. foot_native=False: the rest blend/lean/deferred draw live on the Python foot.
    `walls` (Phase W): wall tris for the in-stepper CrrPos response (wallgate.py gates).
    `model_draw` (session 35): the mid-walk sword pull-out (LandState.model_draw). Defaults to
    `not sword_drawn` -- a SHEATHED anchor auto-enables it so a walk-up B edge draws the sword
    (setting `sword_drawn` at the draw-completion frame, satisfying the roll->CUT gate); a
    sword-drawn anchor never draws so it stays OFF (byte-identical). No B edge => no draw => the
    walk is byte-identical either way (session-34 handoff).
    `dtm_seed` (session 43): the make_dtm leading-neutral-poll count the stream will be DELIVERED
    with. The stored `rest_noops` bakes in the pipeline default seed=1; a different seed shifts the
    leading-poll layout, so the sim's leading no-op count = `rest_noops + (1 - dtm_seed)`. MEASURED,
    not guessed (session 43, capture_walkentry seed=0 vs the seed-1 golden, d_frame-aligned): seed=1
    => noops=1 (28/0 bit-exact, byte-identical to before), seed=0 => noops=2 (28/0 bit-exact -- the
    seed-0 delivery fix; FEWER leading neutral polls => the game's rest blend advances one MORE frame
    before the plan takes hold, so the sim needs one MORE leading no-op). `noops` overrides outright."""
    seed, straight, aim = sticks_of(anchor)
    # Sword state picks the walk/dash anim SET (WALKS/DASHS vs base WALK/DASH -- different legs; see
    # KB mechanics/walk-stab.md). From the anchor's captured equip; default True (roll-stab idle anchors).
    sword_drawn = bool(seed.get('sword_drawn', seed.get('equip_item', 0x103) == 0x103))
    if model_draw is None:
        model_draw = not sword_drawn
    s = LandState(pos_x=seed['link_x'], pos_z=seed['link_z'], pos_y=seed.get('link_y', 0.0),
                  facing=seed['shape_angle_y'] & 0xFFFF, travel=seed['travel_angle'] & 0xFFFF,
                  csangle=seed['csangle'] & 0xFFFF, state=seed['link_state'], nspeed=0.0,
                  speedF=0.0, idle_frame=seed['anim_frame'], use_anim=True, native=False,
                  foot_native=False, sword_drawn=sword_drawn, idle_anim='waits', walls=walls,
                  model_draw=model_draw)
    # NO _pending_morf arming (the walk-entry frame triggers the oldframe-morf itself; arming it
    # too made the sim morf AGAIN one frame later -- caught by verify_rest row 4).
    # rest_noops = the anchor's savestate capture-phase DTM alignment, derived per-anchor by
    # mint.capture_rest (1 = boundary/canonical, 2 = legacy mid-frame). Default 2 for old seeds (#30).
    # (1 - dtm_seed) shifts it for a non-default make_dtm leading-poll count (session 43 fix,
    # MEASURED live); `noops` overrides outright (measurement path).
    if noops is None:
        noops = max(0, int(seed.get('rest_noops', REST_NOOPS)) + (1 - int(dtm_seed)))
    s._foot.seed_rest_blend(d_frame=seed['rest_d_frame'], w_frame=seed['rest_w_frame'],
                            d_rate=seed['rest_d_rate'], w_rate=seed['rest_w_rate'],
                            m359C=seed['rest_m359C'], m35B4=seed.get('rest_m35B4', 0.0),
                            noops=noops,
                            t1=seed.get('rest_t1'), t2=seed.get('rest_t2'))
    s.step(128, 128)           # the DTM seed frame (build_dtm_from_sticks seed=1; rest no-op 1/2)
    return s


def verify_rest(anchor, calib=None, seam=None, dtm_seed=1):
    """Offline gate: replay the calibration stream FROM REST and diff every row vs the live
    trace -- pos, d/w frames, m359C. Returns nbad (0 == REST BIT-EXACT). `seam`/`dtm_seed` for a
    NOVEL seam (aim at seam.F) / a seed-0 delivery; defaults byte-identical to the kaze path."""
    def bits(x):
        return struct.unpack('<I', struct.pack('<f', float(x)))[0]

    if calib is None:
        calib = json.load(open(CALIB_PATH))
        assert calib['anchor'] == anchor, (calib['anchor'], anchor)
    s = rest_state(anchor, dtm_seed=dtm_seed)
    _, straight, aim = sticks_of(anchor, seam=seam)
    stream = [straight] * NPREF + [aim] * NCRUISE
    nbad = 0
    for k, (sx, sy) in enumerate(stream):
        s.step(sx, sy)
        if k >= len(calib['frames']):
            break
        lf = calib['frames'][k]
        st = s._foot.st
        ok = (bits(s.pos_x) == bits(lf['pos_x']) and bits(s.pos_z) == bits(lf['pos_z'])
              and bits(st.fc0.frame) == bits(lf['d_frame'])
              and bits(st.fc1.frame) == bits(lf['w_frame'])
              and bits(s._foot.prev_f312) == bits(lf['m359C']))
        nbad += 0 if ok else 1
        print('  k=%-2d %s pos(%.7f,%.7f)|(%.7f,%.7f) d %.6f|%.6f w %.6f|%.6f m359C %.8f|%.8f' % (
              k, 'ok  ' if ok else 'DIFF', s.pos_x, s.pos_z, lf['pos_x'], lf['pos_z'],
              st.fc0.frame, lf['d_frame'], st.fc1.frame, lf['w_frame'],
              s._foot.prev_f312, lf['m359C']), flush=True)
    print('\n%s' % ('REST BIT-EXACT' if nbad == 0 else 'REST DIVERGED (%d)' % nbad))
    return nbad


def write_golden(anchor, path, calib=None, seam=None, dtm_seed=1, geo=None):
    """Assemble the tracked REST golden (the `fixtures/seam*_rest_golden.json` schema the per-seam
    gates replay) from a verification calib -- the step every delivery used to hand-author from
    `_generated/rollstab_calib.json` (Phase-A touch-list item 4). Call ONLY after verify_rest
    printed REST BIT-EXACT: the golden is live-captured data and immutable once written."""
    if calib is None:
        calib = json.load(open(CALIB_PATH))
        assert calib['anchor'] == anchor, (calib['anchor'], anchor)
    _, straight, aim = sticks_of(anchor, seam=seam)
    gd = dict(anchor=anchor, seed=int(dtm_seed), geo=geo, straight=list(straight),
              aim=list(aim), NPREF=NPREF, NCRUISE=NCRUISE, frames=calib['frames'])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(gd, open(path, 'w'), indent=1)
    print('rest golden -> %s (%d frames)' % (path, len(calib['frames'])), flush=True)


def main(anchor, seam=None, dtm_seed=1, golden=None, geo=None):
    """The per-anchor LIVE gate: one clean-DTM run of the verification stream, logging the anim
    fields per frame, then the offline from-rest diff. A new anchor must print REST BIT-EXACT
    before its solver hits are trusted. `seam` (a SeamGeo, or built from a `geo=` fixture) aims the
    cruise at a NOVEL seam's F; `dtm_seed` picks the make_dtm leading-poll layout (0 for the seed-0
    delivery a mint_current anchor needs -- noops = rest_noops + (1-dtm_seed)). `golden=` writes the
    tracked REST golden (schema of `fixtures/seam824_rest_golden.json`) on a BIT-EXACT pass --
    `geo` is the fixture path recorded inside it."""
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
        d['csangle'] = D.read_named(h, m, 'csangle') & 0xFFFF
        return d
    R._read_frame = rich

    _, straight, aim = sticks_of(anchor, seam=seam)
    # csy=0 (C-down, free-cam pin) for a NOVEL mint_current anchor whose camera would else drift as Link
    # walks (session 50); csy=128 (neutral) is byte-identical to the legacy proven-anchor goldens.
    csy = 0 if (seam is not None or dtm_seed == 0) else 128
    stream = [straight] * NPREF + [aim] * NCRUISE
    sticks = [dict(stickX=sx, stickY=sy, substickX=128, substickY=csy, buttons=0)
              for (sx, sy) in stream] + [dict(stickX=128, stickY=128, substickX=128,
                                              substickY=csy, buttons=0)] * 20
    end = run_dtm(sticks, anchor=anchor, ready=land_ready, relaunch_dolphin=True,
                  log_frames=len(stream) + 2, verbose=True, seed=dtm_seed)
    frames = end['log']
    calib = dict(anchor=anchor, NPREF=NPREF,
                 frames=[dict(pos_x=f['pos_x'], pos_z=f['pos_z'],
                              facing=f['facing'] & 0xFFFF, proc=f['proc'],
                              d_frame=f.get('d_frame'), w_frame=f.get('w_frame'),
                              d_rate=f.get('d_rate'), m3598=f.get('m3598'),
                              m359C=f.get('m359C'), m35B4=f.get('m35B4'),
                              csangle=f.get('csangle')) for f in frames])
    os.makedirs(os.path.dirname(CALIB_PATH), exist_ok=True)
    json.dump(calib, open(CALIB_PATH, 'w'))
    print('wrote %s (%d frames)' % (CALIB_PATH, len(frames)), flush=True)
    nbad = verify_rest(anchor, calib, seam=seam, dtm_seed=dtm_seed)
    if nbad == 0 and golden:
        write_golden(anchor, golden, calib=calib, seam=seam, dtm_seed=dtm_seed, geo=geo)
    return 0 if nbad == 0 else 1


if __name__ == '__main__':
    o = dict(t.split('=', 1) for t in sys.argv[1:] if '=' in t)
    _seam = None
    if 'geo' in o:                    # NOVEL seam: build a SeamGeo from its geo fixture + anchor csangle
        from harness.rollstab.seamgeo import SeamGeo
        _a = o.get('anchor', 'kaze_r11_rollstab_idle2@twwgz')
        _seam = SeamGeo(json.load(open(o['geo'])), csangle=G.load_seed(_a)['csangle'] & 0xFFFF)
    sys.exit(main(o.get('anchor', 'kaze_r11_rollstab_idle2@twwgz'),
                  seam=_seam, dtm_seed=int(o.get('seed', 1)),
                  golden=o.get('golden'), geo=o.get('geo')))
