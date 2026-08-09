"""The native-fleet reposition BFS (`harness/tetrapush/native_search`) -- 0-ULP frontier readout +
structural prune/bit-confirm gates (session 38).

The search runs a beam BFS whose frontier is native `FreeRun` nodes, expanded a frame at a time
through `CourtyardFleet.run_par`. The FIDELITY it inherits is `test_freerun_native` /
`test_courtyard_fleet_native` (the native step == the live-0-ULP Python FreeRun, and the fleet is
bit-identical parallel-vs-sequential). What THIS module adds, and what these gates lock, is that the
search READS state exactly:

  * `test_fleet_frontier_bit_exact` -- a 1-wide frontier driven by `batch_step` (re-set a 1-frame
    schedule + `run_par(1)` each generation, then sync the public C fields) reproduces a native
    `FreeRun` rollout of the same recorded stream 0-ULP. This is the precondition for a fleet-backed
    frontier: the parallel one-frame expansion + field sync introduce no drift.
  * `test_batch_step_equals_individual` -- a batch of independently-seeded clones stepped together in
    ONE `batch_step` lands bit-identical to stepping each clone alone (parallel expansion ==
    sequential; the beam's core operation).
  * `test_search_prunes_and_bit_confirms` -- a tiny search runs, its reported best is an on-line
    behind-Tetra pursuit waypoint (the `HerdLine` past-Tetra prune holds), and the reconstructed
    input sequence bit-confirms 0-ULP on a fresh Python-stepped `FreeRun`.

Per `[[zero-ulp-tests-only]]` the position/facing equalities are asserted `_bits`-equal, no tolerance.
"""
import os
import struct
import warnings

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIX = os.path.join(_ROOT, 'fixtures')
_NEED = ('courtyard_push_cyl.json', 'courtyard_push_dtm.json', 'courtyard_push_seed.json',
         'courtyard_cam_oracle.json', 'courtyard_zl1look.json', 'courtyard_m3564.json',
         'courtyard_push_perop.json')


def _bits(x):
    return struct.pack('<d', float(x)).hex()


@pytest.fixture(scope='module')
def env():
    for name in _NEED:
        if not os.path.exists(os.path.join(_FIX, name)):
            pytest.skip("Courtyard capture fixtures not present (need a live slot-2 capture)")
    from harness.tetrapush import seeds
    return seeds.load_env()


def _cs_at(env, k):
    cyl = env['cyl']
    r = cyl[k] if k < len(cyl) else cyl[-1]
    return int(r['csangle']) & 0xFFFF


def test_fleet_frontier_bit_exact(env):
    """A 1-wide fleet-driven frontier == a native FreeRun rollout, 0-ULP over the window."""
    warnings.simplefilter('ignore')
    from harness.tetrapush import seeds
    from harness.tetrapush import native_search as NS
    inp_at = seeds.dtm_input_at(env)

    ref = seeds.make_freerun_native(env)
    ref.pre_seed_input(inp_at(0))
    ref_rows = []
    for k in range(1, 36):
        ref.step(inp_at(k), csangle=_cs_at(env, k))
        ref_rows.append((ref.link.pos_x, ref.link.pos_z, ref.link.facing, ref.link.travel,
                         ref.link.speedF, ref.link.state, ref.tx, ref.tz))

    run = seeds.make_freerun_native(env)
    run.pre_seed_input(inp_at(0))
    node = NS.Node(run, None, None, 0, 0)
    for k in range(1, 36):
        NS.batch_step([(node.run, inp_at(k), _cs_at(env, k))])
        got = (node.run.link.pos_x, node.run.link.pos_z, node.run.link.facing,
               node.run.link.travel, node.run.link.speedF, node.run.link.state,
               node.run.tx, node.run.tz)
        want = ref_rows[k - 1]
        for i in range(len(want)):
            a, b = want[i], got[i]
            if isinstance(a, float):
                assert _bits(a) == _bits(b), "frame %d field %d: %r != %r" % (k, i, a, b)
            else:
                assert a == b, "frame %d field %d: %r != %r" % (k, i, a, b)


def test_batch_step_equals_individual(env):
    """A batch of clones stepped together == each stepped alone (parallel expansion == sequential)."""
    warnings.simplefilter('ignore')
    from harness.tetrapush import seeds
    from harness.tetrapush import native_search as NS
    inp_at = seeds.dtm_input_at(env)

    # advance a base run a few frames, then branch it into distinct clones with distinct inputs
    base = seeds.make_freerun_native(env)
    base.pre_seed_input(inp_at(0))
    for k in range(1, 6):
        base.step(inp_at(k), csangle=_cs_at(env, k))

    # four different candidate inputs (the kind the alphabet emits)
    cands = [dict(stickX=128, stickY=110, buttons=0, triggerL=0, substickX=128, substickY=128),
             dict(stickX=110, stickY=200, buttons=0x40, triggerL=255, substickX=128, substickY=128),
             dict(stickX=200, stickY=110, buttons=0, triggerL=0, substickX=128, substickY=128),
             dict(stickX=128, stickY=128, buttons=0, triggerL=0, substickX=128, substickY=128)]
    cs = _cs_at(env, 6)

    # individual reference
    indiv = []
    for d in cands:
        c = base.clone()
        c.step(d, csangle=cs)
        indiv.append((c.link.pos_x, c.link.pos_z, c.link.facing, c.link.speedF, c.tx, c.tz))

    # batched
    clones = [base.clone() for _ in cands]
    NS.batch_step([(clones[i], cands[i], cs) for i in range(len(cands))])
    for i, c in enumerate(clones):
        got = (c.link.pos_x, c.link.pos_z, c.link.facing, c.link.speedF, c.tx, c.tz)
        for j in range(len(got)):
            assert _bits(indiv[i][j]) == _bits(got[j]), \
                "clone %d field %d: %r != %r" % (i, j, indiv[i][j], got[j])


@pytest.mark.slow
def test_search_prunes_and_bit_confirms(env):
    """A tiny search runs, its best is an on-line behind-Tetra pursuit, and the plan bit-confirms."""
    warnings.simplefilter('ignore')
    from harness.tetrapush import native_search as NS
    root, prologue = NS.seed_root(env)
    assert prologue == []
    # root is state-2 f0: Link behind Tetra (negative lead), in the backslide
    hl = NS.HerdLine.from_env(env)
    lead0 = hl.lead(root.run.link.pos_x, root.run.link.pos_z, root.run.tx, root.run.tz)
    assert lead0 < 0.0

    srch = NS.RepositionSearch(env, beam=24, gens=6, turn_step=16384, verbose=False)
    best = srch.run(root)
    assert best is not None, "no on-line waypoint survived a 6-gen search"
    sc, along, node, rate = best

    # the reported best is an on-line, behind-Tetra pursuit state (the past-Tetra prune held)
    lead = hl.lead(node.run.link.pos_x, node.run.link.pos_z, node.run.tx, node.run.tz)
    lat = hl.lateral(node.run.link.pos_x, node.run.link.pos_z) - hl.lateral(node.run.tx, node.run.tz)
    assert lead <= -5.0 and lead >= -110.0
    assert abs(lat) <= 22.0
    assert along > 0.0

    # the plan (prologue + reconstructed reposition inputs) bit-confirms native == Python-stripped
    seq = NS.reconstruct(node)
    assert len(seq) == node.depth
    ok, nf, ft, fl = NS.bit_confirm(env, prologue, seq)
    assert ok, "bit-confirm mismatch over %d frames" % nf
