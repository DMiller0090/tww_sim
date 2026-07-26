"""Locate Tetra (daNpc_Zl1_c, actor id 429) live: her REL code base + runtime instance pointer.

REL actors have no static address, so we walk the DMC list to get the loaded REL's .text base
(the find-rel-actor-live recipe / DOLPHIN_CONTROL "Breakpointing a REL actor"), compute the runtime
_execute address, breakpoint it, step one frame so the game traps it, and read r3 = the `this`
instance. The REL base moves per scene load, so recompute every session; the instance pointer is then
stable across loadstate of the SAME slot within one Dolphin session.

Self-contained: dolphin_mem (../../tools) only. Needs a running Dolphin with the Hyrule courtyard
scene loaded (Tetra present). Reads live process RAM -- no mem1.raw dump.

    from harness.tetrapush.find_tetra import find_tetra_instance
    tetra = find_tetra_instance(D)          # D = dolphin_mem module (attached)

CLI:  python -m harness.tetrapush.find_tetra
"""
import struct
import sys
import os

# >>> repo bootstrap: locate tww_sim/ + ../tools (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path:
    sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')  # locate tools/
if _tb not in sys.path:
    sys.path.append(_tb)

# JP GZLJ01 anchors (framework.map / DOLPHIN_CONTROL).
CC_INIT = 0x80022430          # cCc_Init__Fv
ZL1_ID = 429                  # d_a_npc_zl1 actor id
ZL1_EXECUTE_OFF = 0x69D8      # _execute__11daNpc_Zl1_cFv (d_a_npc_zl1.map)
ZL1_TYPE_OFF = 0x84F          # daNpc_Zl1_c field_0x84F == 5 for the following variant


def _reader(D):
    h, mem1 = D.attach()

    def ru32(a):
        return struct.unpack('>I', D.read_bytes(h, mem1, a, 4))[0]

    def ru16(a):
        return struct.unpack('>H', D.read_bytes(h, mem1, a, 2))[0]

    def rs16(a):
        return struct.unpack('>h', D.read_bytes(h, mem1, a, 2))[0]

    return h, mem1, ru32, ru16, rs16


def zl1_execute_addr(D):
    """Runtime address of daNpc_Zl1_c::_execute via the DMC walk (0 if Zl1 not loaded)."""
    _h, _m, ru32, ru16, rs16 = _reader(D)
    dmc_list = (ru16(CC_INIT + 0x7A) << 16) + rs16(CC_INIT + 0x7E)
    dmc_ptr = ru32(dmc_list + ZL1_ID * 4)
    if not dmc_ptr:
        return 0
    rel_base = ru32(dmc_ptr + 0x10)
    if not rel_base:
        return 0                                  # REL not loaded (Tetra not in this scene)
    sec_tbl = ru32(rel_base + 0x10)
    text = ru32(sec_tbl + 8) & ~1                 # first non-null section = .text
    return text + ZL1_EXECUTE_OFF


def tetra_scan(D, xz_lo=(-2300.0, -1400.0), xz_hi=(-1000.0, 500.0), floor_y=0.16327, y_tol=0.05,
               lo=0x80A00000, hi=0x80F00000, verbose=True):
    """Locate Tetra WITHOUT a breakpoint, by scanning the actor heap. Returns the `this` pointer or None.

    `find_tetra_instance` needs its `_execute` breakpoint to TRAP, which cannot happen on a HALTED movie
    (a movie paused at its last frame, or one being single-stepped -- the advance halts on the pause
    boundary instead, reported as "breakpoint at 0x... did not trap"). That silently yields no reads at
    all, so any endpoint read off a finished DTM playback must come through here (session 54).

    The struct is identifiable from RAM alone: fopAc pos (+0x1F8 x, +0x1FC y, +0x200 z) on the courtyard
    floor (Y = 0.16327) plus the Zl1 following-variant tag `field_0x84F == 5`. Reads MEM1 in ONE block
    and filters in Python, so it is fast and perturbs nothing."""
    h, mem1 = D.attach()
    blob = D.read_bytes(h, mem1, lo, hi - lo)
    hits = []
    for off in range(0, len(blob) - 0x900, 4):
        y = struct.unpack_from('>f', blob, off + 0x1FC)[0]
        if not (abs(y - floor_y) <= y_tol):
            continue
        if blob[off + ZL1_TYPE_OFF] != 5:
            continue
        x = struct.unpack_from('>f', blob, off + 0x1F8)[0]
        z = struct.unpack_from('>f', blob, off + 0x200)[0]
        if xz_lo[0] <= x <= xz_hi[0] and xz_lo[1] <= z <= xz_hi[1]:
            hits.append((lo + off, x, y, z))
    if verbose:
        for a, x, y, z in hits:
            print("  tetra_scan hit 0x%08x pos(%.4f, %.4f, %.4f)" % (a, x, y, z))
    return hits[0][0] if hits else None


def find_tetra_instance(D, reload_slot=None, verbose=True):
    """Return Tetra's runtime `this` pointer by trapping _execute.

    Sets a code breakpoint on the computed _execute, advances one frame so the running game hits it,
    reads r3, clears the breakpoint. If `reload_slot` is given, reloads that savestate slot afterward
    so the one consumed frame is undone (pass the slot you captured from, e.g. 2).
    """
    import json
    exe = zl1_execute_addr(D)
    if not exe:
        raise RuntimeError("Zl1 (Tetra) REL not loaded -- is the courtyard scene up?")
    if verbose:
        print("Zl1 _execute runtime = 0x%08x" % exe)

    def _reg(name):
        return json.loads(D.control_pipe_quiet("readreg", {"reg": name})).get("value")

    D.control_pipe_quiet("setbp", {"addr": exe})
    D.control_pipe_quiet("advance", {"frames": 1})       # movie steps; the game traps _execute
    pc, r3 = _reg("pc"), _reg("r3")
    D.control_pipe_quiet("clearbp")
    if reload_slot is not None:
        D.control_pipe_quiet("pause")
        D.control_pipe_quiet("savestate", {"action": "load", "slot": int(reload_slot)})
    if pc != exe:
        raise RuntimeError("breakpoint at 0x%08x did not trap (pc=0x%08x)" % (exe, pc or 0))
    if not r3:
        raise RuntimeError("trapped _execute but r3 read failed")
    if verbose:
        print("Tetra instance (r3) = 0x%08x" % r3)
    return r3


if __name__ == '__main__':
    import dolphin_mem as D
    kw = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
    slot = int(kw['reload']) if 'reload' in kw else None
    print("Tetra @ 0x%08x" % find_tetra_instance(D, reload_slot=slot))
