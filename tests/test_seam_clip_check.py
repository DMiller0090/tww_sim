"""Regression guard for the out-of-the-box seam-clip scanner
(:mod:`harness.collision.seam_clip_check`). Offline (no Dolphin): the GanonL synthetic seam, the
live-confirmed Hyrule (-1727,-990) f32 clip, and a flat seam that must be rejected."""
import json
import os
import struct

from harness.collision.seam_clip_check import clip_check, ROLL_STAB_MAX

_G = os.path.join(os.path.dirname(__file__), "golden")


def _fh(s):
    return struct.unpack(">f", struct.pack(">I", int(s, 16)))[0]


def _load(name):
    """Return (tris, link_y, S) from a hex golden (4 seam tris + stored planes)."""
    from tww_sim.core.collision import Tri, Plane
    g = json.load(open(os.path.join(_G, name)))
    tris = [Tri([_fh(x) for x in t["v"][0]], [_fh(x) for x in t["v"][1]], [_fh(x) for x in t["v"][2]],
                plane=Plane(*[_fh(x) for x in t["n"]], _fh(t["D"]))) for t in g["tris"]]
    if "seam_v_hex" in g:                       # hyrule golden: seam vertex as hex xyz
        sv = [_fh(x) for x in g["seam_v_hex"]]
        return tris, sv[1], (sv[0], sv[2])
    return tris, g["link_y"], tuple(g["seam_xz"])   # flat golden: plain floats


def test_scanner_finds_ganonl_clip():
    """GanonL grand-staircase seam — reachable by a bare roll-stab (disp < 49.22)."""
    from harness.collision.seam_model import SEAM_TRIS, LINK_Y
    S = (-847.632, -37336.613)
    r = clip_check(SEAM_TRIS, [], S, SEAM_TRIS[1], SEAM_TRIS[2],
                   require_standable=False, override_link_y=LINK_Y)
    assert r["clips"], r
    assert r["reachable_rollstab"] and not r["needs_push"]
    assert r["disp"] <= ROLL_STAB_MAX
    assert r["floor"] < r["disp"] < r["floor"] + 5.0    # near-minimal, not the old ~60 over-estimate


def test_scanner_finds_hyrule_1727_needs_push():
    """Live-confirmed Hyrule (-1727,-990) f32 clip: found, and correctly classified needs-push
    (disp ~49.96 > the 49.22 roll-stab ceiling). Guards against the ULP-scaled false-negative."""
    tris, link_y, S = _load("hyrule_seam_1727_ram.json")
    r = clip_check(tris, [], S, tris[1], tris[2], require_standable=False, override_link_y=link_y)
    assert r["clips"], r
    assert r["needs_push"] and not r["reachable_rollstab"]
    assert 49.0 < r["disp"] < 51.0, r["disp"]


def test_scanner_rejects_flat_seam():
    """A flat (coplanar) seam must be screened out — no LineCheck miss, unclippable."""
    tris, link_y, S = _load("flat_seam_ram.json")
    r = clip_check(tris, [], S, tris[1], tris[2], require_standable=False, override_link_y=link_y)
    assert not r["clips"], r


def test_scanner_requires_standable_floor():
    """With require_standable and no ground mesh, a clippable seam is dropped (no valid old)."""
    from harness.collision.seam_model import SEAM_TRIS
    S = (-847.632, -37336.613)
    r = clip_check(SEAM_TRIS, [], S, SEAM_TRIS[1], SEAM_TRIS[2], require_standable=True)
    assert not r["clips"]
    assert "standable floor" in r["reason"]
