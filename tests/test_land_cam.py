"""The land-camera (dCamera_c) port vs the live courtyard oracle -- 0-ULP, chained.

Oracle: fixtures/courtyard_cam_oracle.json (single-stepped from slot 2; run A of the
session-17 A/B probe re-captured with the full dCamera_c block + statuses + attention).
The camera is seeded ONCE from the f0 block and stepped through all 120 frames with no
reseeding: every committed csangle, the whole view-cache globe (R / elevation / yaw), the
center chase, and the manual-work springs must match the live capture exactly. The window
covers: settled manual camera, active C-stick orbit, 4 followCamera blip frames (L rising
edges), two lockon windows (blend in/out), and the post-release settle.

dup=True frames are single-step double-reads (the game frame did not run) and are skipped.
"""
import json
import os
import struct

import pytest

from tww_sim.core.camera.land_cam import LandCamera, SGlobe, TYPE_JUMP

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "courtyard_cam_oracle.json")


def _f(b, o):
    return struct.unpack(">f", b[o:o + 4])[0]


def _s(b, o):
    return struct.unpack(">h", b[o:o + 2])[0]


def _i(b, o):
    return struct.unpack(">i", b[o:o + 4])[0]


def _u(b, o):
    return struct.unpack(">I", b[o:o + 4])[0]


def _v3(b, o):
    return tuple(struct.unpack(">3f", b[o:o + 12]))


def seed_from_block(cam, b):
    """Seed a LandCamera from a raw dCamera_c block (the f0 oracle state)."""
    cam.dir = SGlobe(_f(b, 0x08), _s(b, 0x0C), _s(b, 0x0E), formal=False)
    cam.center = _v3(b, 0x10)
    cam.eye = _v3(b, 0x1C)
    cam.fovy = _f(b, 0x38)
    cam.angleY = struct.unpack(">H", b[0x6C:0x6E])[0]
    cam.vc_dir = SGlobe(_f(b, 0x3C), _s(b, 0x40), _s(b, 0x42), formal=False)
    cam.vc_center = _v3(b, 0x44)
    cam.vc_eye = _v3(b, 0x50)
    cam.vc_fovy = _f(b, 0x60)
    cam.cur_mode = _i(b, 0x13C)
    cam.m144 = _i(b, 0x144)
    cam.m100, cam.m101, cam.m102 = b[0x100], b[0x101], b[0x102]
    cam.m108 = _u(b, 0x108)
    cam.m110 = b[0x110]
    cam.m11C = _u(b, 0x11C)
    cam.flags = _u(b, 0x50C)
    cam.m184 = _i(b, 0x184)
    cam.mx, cam.my, cam.mval = _f(b, 0x154), _f(b, 0x158), _f(b, 0x15C)
    cam.cx, cam.cy, cam.cval = _f(b, 0x16C), _f(b, 0x170), _f(b, 0x174)
    cam.trigL = _f(b, 0x190)
    cam.m19A, cam.m19B = b[0x19A], b[0x19B]
    cam.w_delta = _v3(b, 0x37C)
    cam.w_target = _v3(b, 0x388)
    cam.w_m394 = _f(b, 0x394)
    cam.w_m398 = _f(b, 0x398)
    cam.w_m3A0 = b[0x3A0]
    cam.w_m3A4 = _f(b, 0x3A4)
    cam.w_glob = SGlobe(_f(b, 0x3A8), _s(b, 0x3AC), _s(b, 0x3AE), formal=False)
    cam.w_m3B0 = _f(b, 0x3B0)
    cam.w_m3B4 = _f(b, 0x3B4)
    cam.cur_style = TYPE_JUMP[cam.cur_mode]
    return cam


@pytest.fixture(scope="module")
def oracle():
    with open(FIX) as fh:
        return json.load(fh)


def test_land_cam_chained_bit_exact(oracle):
    cam = LandCamera()
    seed_from_block(cam, bytes.fromhex(oracle["seed_cam_raw"]))
    checked = 0
    for fr in oracle["frames"]:
        if fr["dup"]:
            continue
        link = dict(pos=tuple(fr["link"]["pos"]), facing=fr["link"]["facing"],
                    attn_pos=tuple(fr["link"]["attn"]))
        truth = fr["lockstate"] in (1, 2)
        attn = dict(truth=truth, lockon=truth,
                    target_attn=tuple(fr["tattn"]) if truth else None)
        cs = cam.step(fr["pad"], link, attn,
                      status0=fr["status0"], status1=fr["status1"])
        e = fr["expect"]
        f = fr["f"]
        assert cs == e["csangle"], "f%d csangle %d != %d" % (f, cs, e["csangle"])
        assert cam.cur_mode == e["mode"], "f%d mode" % f
        assert cam.vc_dir.r == e["vc_r"], "f%d vc.r" % f
        assert cam.vc_dir.az == e["vc_az"], "f%d vc.az" % f
        assert cam.vc_dir.inc == e["vc_inc"], "f%d vc.inc" % f
        assert list(cam.vc_center) == e["vc_center"], "f%d vc_center" % f
        assert list(cam.vc_eye) == e["vc_eye"], "f%d vc_eye" % f
        assert list(cam.center) == e["center"], "f%d center" % f
        assert list(cam.eye) == e["eye"], "f%d eye" % f
        if e["mode"] == 12:     # manual-work fields are unioned; only valid on manual frames
            assert [cam.w_glob.r, cam.w_glob.az, cam.w_glob.inc] == e["glob"], "f%d glob" % f
            assert cam.w_m398 == e["m398"], "f%d m398" % f
            assert cam.w_m3B0 == e["m3B0"], "f%d m3B0" % f
            assert cam.w_m3B4 == e["m3B4"], "f%d m3B4" % f
        checked += 1
    assert checked >= 118      # 120 frames minus the known dup(s)


def test_land_cam_lock_windows_covered(oracle):
    """The gate exercises both untarget-cycle lockon windows and all four follow blips."""
    lock_frames = [fr["f"] for fr in oracle["frames"] if fr["lockstate"] in (1, 2)]
    blip_frames = [fr["f"] for fr in oracle["frames"] if fr["expect"]["mode"] == 0]
    assert len(lock_frames) >= 20
    assert len(blip_frames) == 4
