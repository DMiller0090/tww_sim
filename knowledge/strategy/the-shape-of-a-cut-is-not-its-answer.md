# The shape of a cut is not its answer: a beam that fires 100% of the time lands the same 105.00

**Answers:** Half my beam is endpoints that can never end a plan - is fixing the keep that admits them
worth a session? My screen is a keep SHARE; should it be a REQUIREMENT? How do I tell a calibration
that transfers from one that was measured on a different quantity? What does an A/B owe me when both
lanes tie?
**Status:** MEASURED (session 122) on the flooded-Hyrule Tetra corner. Pre-flight
`_notes/s122_shape_preflight.py` at the 33 R2 cells behind the 165-survivor population (41 s + 62 s);
inertness `_notes/s122_inert_check.py` against the pre-edit function out of git; the A/B
`_notes/s122_recut_c3.py` (require lane 3160 s, log `_notes/s122b_require.log`, dumps
`_generated/s106/s122_c3_require_{beam,landing}.json`) against the banked session-119 pair lane
(3936 s); read by `_notes/s122_read_shape.py`.
**Source:** [`harness/tetrapush/full_herd.py`](../../harness/tetrapush/full_herd.py)
(`lok_probe_key`, `as_requirement`, `roll_candidates`' ``tcs_probe``/``tcs_require``,
`extend_cycle`'s ``lok_require``),
[`harness/tetrapush/away_walk.py`](../../harness/tetrapush/away_walk.py) (`lok_clear`),
[`harness/tetrapush/beam_io.py`](../../harness/tetrapush/beam_io.py) (`split_last_roll`).

---

Session 121 closed the last clause-level axis (`dips` decides no endpoint,
[the-dip-budget-is-not-the-lever.md](the-dip-budget-is-not-the-lever.md)) and left one lever standing:
**53 of the census's 99 cycle-3 endpoints are ones where ``l_ok`` refuses every variant**, and the
cut's camera keep is a SHARE, so it cannot stop admitting them. This page is what happened when the
same predicate was made a REQUIREMENT instead.

## The share was spending half the beam on endpoints that can never fire

Re-run R2 whole at the cells behind the banked beam - the pre-roll endpoint recovered exactly by
`beam_io.split_last_roll`, the same grid, grading and orders `roll_candidates` uses:

| over the 165-survivor population's 33 R2 cells | share (shipped) | requirement |
|---|---|---|
| camera targets kept | 99 | 63 |
| of those, states that **can fire** | **45** | **63** |
| targets kept that the other shape never keeps | - | **25** |
| R2 cells emptied | - | 8 of 33 |
| **junction nodes lost** | - | **0** |

The last row is the one that matters and it is why the s73 objection does not apply here: every one of
the 8 emptied cells sits at a pre-roll node that keeps live cells on another aim or L window. A
requirement on this predicate does not prune endpoints, it re-spends a slot.

**Check the emulation before you trust the measurement.** The first version of this pre-flight ranked
terminal rolls by the frame bound alone and disagreed with the banked keep - `junction_quality` is
still COMPUTED on the last cycle (only `require_quality` is off) and a scored target sorts
`(-inbox, lat)`, ahead of every unscored one. Fixed, the emulation reproduces the banked keep at
**33 of 33** cells; that agreement is what makes the table above a fact about the cut and not about
the script.

## Re-cut whole, the requirement does everything it promised except pay

The s119 pair lane verbatim, one knob different ([the A/B](#the-ab-and-what-it-cost)):

| | share (control) | requirement |
|---|---|---|
| nodes / probed / **that FIRE** | 64 / 47 / **27** | 63 / 50 / **50** |
| terminals clearing `l_ok` | 33 of 64 | **63 of 63** |
| in-band records / joint / deliverers | 2 / 1 / 1 | **6** / 1 / **4** |
| endpoints the other lane never reached | 35 | **34** |
| disagreements at the 23 shared endpoints | - | **0** |
| best `plan_bound` | 93.95 | 93.95 |
| **best DELIVERED** | **105.00** | **105.00** - the same endpoint |
| wall clock | 3936 s | **3160 s** |

Every structural promise landed: the beam went from 57% firing to **100%** firing, in-band records
tripled and spread across the whole along range (877.9 x2, 886.8, 934.3, 936.6, 947.4 against the
share's 877.9 and 934.3), three deliverers appeared that the share never saw, and it cost 20% less
wall clock. The three new deliverers are **106.66 / 115.82 / 117.85** - all worse - and the winner is
the same endpoint at the same figure the capped slice and the uncapped census both returned.

## The rule: a differently-shaped cut of an exhausted set is still that set

**105.00 has now been returned by three cuts that do not share a population:** the capped slice (58%
of the survivors), the uncapped census (all 165, [what it settled][census]), and a requirement-shaped
cut that reaches 34 endpoints neither of the others contained. That is much stronger evidence than any
one of them - and it is evidence about the ENDPOINT SET, not about the cut. When a search's answer
survives a change of population, stop re-shaping the search.

Two transferable rules:

- **A calibration is scoped to the quantity it was measured on.** "A camera term as a filter throws
  away 96% of firing states" was measured on the SNAP BILL, a sufficient-but-incomplete condition, and
  was applied for five sessions to the ``l_ok`` cone, which has no false positives at all
  ([the retired argument][retired]). Before inheriting a number, check what it was a number ABOUT.
- **Shape changes the population, not necessarily the answer.** An A/B that ties still buys something:
  here it converted "105.00 is what our cut finds" into "105.00 is what this endpoint set contains",
  and it retired a lever that had been on the list since session 116.

The shape ships as a share by default (``lok_require`` off) because the lanes tie and default-off
leaves every banked beam's provenance intact. **A new cut should prefer the requirement:** same
answer, all-firing beam, 20% cheaper.

[census]: the-dip-budget-is-not-the-lever.md
[retired]: ../history/the-cone-keep-was-a-share-because-a-filter-throws-away-firing-states.md

## The A/B, and what it cost

- **Prove the knob was in force, with a prediction made before the run.** A shape A/B where the knob
  silently did not fire looks exactly like a tie. The prediction was "every terminal of the require
  lane clears, where 45 of 99 do at the share"; measured **63 of 63**.
- **Prove the control is still the control.** The edit that added ``tcs_require`` also moved the
  candidate dict ahead of `junction_quality`, and "it is the same dict" is a claim about a model.
  Loading the PRE-EDIT function straight out of git and running both on 6 real pre-roll nodes returns
  **0-ULP identical keeps** - so the banked 3936 s lane did not need re-running.
- **Prove the lanes agree where they overlap.** 23 endpoints are reached by both, keyed on the dumped
  input ``log`` (a node index is a rank and geometry is not an identity either); **0 disagree** on
  every field.

## Traps

- **`nohup … &` from a tool call does not reliably detach here, and `pgrep -f` cannot see the
  process.** Concluding "the run died silently" from `pgrep` was wrong - it had been running the whole
  time - and relaunching over the same redirect target left **NUL padding** in the log (two writers,
  one file) and would have raced two processes onto one JSON dump. The NUL block is the tell; check
  `Get-CimInstance Win32_Process` before believing a job is gone.
- **Do not edit a source file while a run is in flight.** Gates here assert on source TEXT via
  `inspect.getsource` (session 121 lost a run to it), and a mid-run docstring edit also muddies which
  file produced a banked dump. Batch the doc edits after the dump lands.
