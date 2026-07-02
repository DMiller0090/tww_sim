"""Canonical planner-benchmark cases + known-best table.

A "case" is a fully-specified, reproducible planner invocation: a planner function
name plus the COMPLETE kwargs it is called with. Because the planner is deterministic
(no RNG), the param dict is a reproduction recipe -- re-running it on the same code
yields the identical plan (see record.reproduce). Every field the planner reads must
live in `params` so the record is self-contained.

Tiers (which cases run, by intent -- NOT a difference in what's recorded):
  smoke  fast pump-mode cases; run after any planner change. Small dests still exercise
         the pump path (frontier saturation, and dips where present) at low runtime.
  full   the real destinations in pump mode -- the mode that produces the SHIPPED
         optimal plan. Slow (200k pump ~8 min); run before shipping / when chasing
         frames or search speed. `known_best` is asserted here.

`known_best` (frames) seeds the regression gate. Values below are from the 2026-07-02
handoff table (seed = cold anchor, mrate 0.5). The FIRST full run records measured
actuals; if an actual disagrees with the table it is a signal (code drift or a config
mismatch), surfaced by the runner -- NOT silently reconciled. None = no baseline yet
(recorded anyway; the dataset wants the data regardless).

Cold anchor (the real cold-start savestate seed):
  ColdStartSwimState v=0 anim=0.06392288208007812 air=900 mrate=0.5
"""

# --- Cold-start anchor: one canonical definition, referenced by every cold case. ---
COLD_ANIM = 0.06392288208007812
COLD_MRATE = 0.5
COLD_AIR = 900

# Shared planner knobs held constant across the benchmark so cross-case / cross-run
# comparisons are apples-to-apples. Overridable per case via the params merge below.
_COMMON = dict(
    v=0.0, anim=COLD_ANIM, air=COLD_AIR, cold_start=True, cold_mrate=COLD_MRATE,
    rank='astar', cap=4000, speed_gate=0.98, speed_gate_end=0.90,
    verbose=False,
)

# max_frontier is the runtime<->optimality lever: smoke=1000 fast (converges for 50k); full=8000
# = the shipped optimum (hardest cases land 1 frame short at 1000). See README for the tradeoff.
_TIER_FRONTIER = {'smoke': 1000, 'full': 8000}


def _case(name, tier, dest, allow_pump, known_best, xfail_live=False, note=None,
          **overrides):
    """xfail_live: this plan is KNOWN to desync live (DTM verification fails) -- an expected
    failure tracked until the underlying sim/pump issue is fixed. verify_dtm flags an xfail_live
    case that starts PASSING (the signal it's resolved -> clear the flag). `note` documents why."""
    params = dict(_COMMON, dest=dest, allow_pump=allow_pump,
                  max_frontier=_TIER_FRONTIER[tier])
    if allow_pump:
        params['pump_chg'] = False        # CLEAN ESS pump (bit-exact v+anim); see plan.py
    params.update(overrides)
    return {
        'name': name,
        'tier': tier,
        'planner': 'plan_min_frames',
        'params': params,
        'known_best': known_best,
        'xfail_live': xfail_live,
        'note': note,
    }


# Ordered fastest-first so a smoke run surfaces failures early.
CASES = [
    # --- smoke: fast, pump-mode, exercises the pump/saturation path ---
    _case('cold_pump_20k',  'smoke',  20000, True,  177),   # DTM-verified 2026-07-02
    _case('cold_pump_30k',  'smoke',  30000, True,  218),   # DTM-verified 2026-07-02
    _case('cold_pump_50k',  'smoke',  50000, True,  280),
    # no-pump companions: cheap, exercise the shared cruise-DP core (NOT the shipped
    # optimum -- 50k no-pump is 282, not 280 -- so recorded, but not the quality gate).
    _case('cold_nopump_50k', 'smoke', 50000, False, 282),

    # --- full: the real destinations; pump = the shipped optimal mode ---
    _case('cold_nopump_100k', 'full', 100000, False, 401),
    _case('cold_pump_100k',   'full', 100000, True,  397),   # DTM-verified 2026-07-02 (untested @ handoff)
    _case('cold_nopump_200k', 'full', 200000, False, 561),
    _case('cold_pump_200k',   'full', 200000, True,  555),
    # long-haul: also probes the 900-frame air budget (a cold swim can only last ~900 frames).
    _case('cold_nopump_300k', 'full', 300000, False, 711),   # DTM-verified 2026-07-02
    # KNOWN LIVE DESYNC (xfail): sim says 705 but Dolphin reaches only ~282852 (pump plan not
    # live-faithful at 300k). See README + memory superswim-pump-300k-desync. 705 is not a truth.
    _case('cold_pump_300k',   'full', 300000, True,  None, xfail_live=True,
          note='live reaches ~282852 not 300000 (sim v=804 vs live 524); pump plan not live-faithful'),
    _case('cold_nopump_400k', 'full', 400000, False, 819),   # DTM-verified 2026-07-02 (pending air-delta fix)
    _case('cold_pump_400k',   'full', 400000, True,  814),   # DTM-verified 2026-07-02
    # 400k is the ceiling for THIS anchor (Link hits the map edge before the ~900-frame air budget);
    # a differently-placed savestate could test 700k+. Extend here when such an anchor exists.
]

CASES_BY_NAME = {c['name']: c for c in CASES}
TIERS = ('smoke', 'full')


def cases_for(tiers):
    """Cases whose tier is in `tiers` (a set/tuple of tier names)."""
    return [c for c in CASES if c['tier'] in tiers]
