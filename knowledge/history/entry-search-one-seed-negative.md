# The productive facing window that was one seed wide (sessions 81-91)

status: historical
Source: superseded by [../strategy/clip-exit-angle.md](../strategy/clip-exit-angle.md) (session 92)

Two claims about the Courtyard entry search were believed for eleven sessions, and both were the same
mistake wearing different clothes: **a negative about a configuration argued from a single station.**
They are recorded here because each one closed an axis that was open, and because the shape recurs.

## Claim 1 (dead): the productive facing window is 32 BAM, two cells wide

Read off a 1 BAM sweep in session 81 and restated through session 91: only facings 40816..40863 admit
a genuine entry, i.e. cells 2551-2553, with 40864 dead. Sessions 83 and 90 both refined it and neither
questioned its shape - session 83 collapsed it onto cells (right, and still current), session 90 found
that the weak form had been hiding cell 2553 inside it and escalated to `locus_scan` (right, and still
current).

What it actually was: every one of those readings started from **one `ref_entry`**, and a
configuration whose residual-zero curve lives elsewhere in the reachable box returns
`no leverage at the seed` having sampled its locus **nowhere**. Seeded off the curve's own crossings,
the window is **two lobes** - cells 2548-2553 and **2560-2573** - with a genuinely dead gap at
2554-2559. The second lobe carries real clips (lunges 49.7-50.3 u, not the refusal shape) at walkable
entries inside the follow bar, and one of its cells has a **wider** acceptance band than the cell the
console clip was delivered on.

Cost: the whole exit-angle axis. When Dereck opened that objective term in session 91, the reachable
answer measured **+9 BAM**; the axis is worth **+336 BAM** in the window and **+144 BAM** at a cell
that is aimable, banded and near. See
[../strategy/clip-exit-angle.md](../strategy/clip-exit-angle.md#the-window-is-a-measured-set-of-cells-and-it-need-not-be-contiguous).

## Claim 2 (dead): Link's CUT POSITION is a steering wheel worth +126 BAM

Session 91's lead, off `_generated/viz/tetra_clip_map.json` (49182 rows, session ~26): the map sweeps
`old` - Link's position at the cut - and at the lunge already delivered it holds 99 clipping positions
spanning +0.69 deg of aim, needing Link to cut from only **0.44 u** away. The handoff called it a lead
rather than a result because the map's `aim` column disagreed with the delivered clip by 40 BAM.

Both halves resolved, and the lead is dead:

- the `aim` column **is** the rounded bearing to the seam vertex, confirmed by computing it at the
  delivered `old` (40882 measured against the map's 40881). It is a per-row constant the map chose as
  its prune, not a range of threading facings - so the join the lead rested on never existed.
- the cut position is **not steerable at all**. `CrrPos` pins it at exactly `WALL_R` from the seam wall
  and the brace has a 30 u basin: a ±30 u entry slide leaves `old` bit-identical, and the 55-candidate
  deliverable population holds 3 distinct cut positions inside 0.035 u.

The map is not wrong about its own geometry - the band at the delivered `old` does contain the
delivered lunge - and its headline number was even roughly the right *size*: the axis really is worth
about that much angle. It is worth it through the **facing cell** with the push rotating to compensate,
not through moving Link. A guide whose mechanism is wrong can still be numerically suggestive, which is
exactly what makes it expensive.

## The general form

Both claims were negatives, and a negative is only as strong as the set it was argued over. Session 90
fixed "one station **across** the locus" by marching **along** it; session 92 fixed "one seed to march
**from**" by seeding off the curve. The lesson that generalizes past this corner is
[../strategy/razor-prices-every-term.md](../strategy/razor-prices-every-term.md) rule 12.

## See also

- [entry-search-s81-camera-lever.md](entry-search-s81-camera-lever.md) - the camera priced at zero
  against claim 1's narrow window; that closure reopens with the window.
- [entry-search-s81-momentum-lever.md](entry-search-s81-momentum-lever.md) - the momentum axis, closed
  by `locus_scan` at the cap. Its negative was argued the same one-seed way and is worth re-measuring.
- [co-centre-two-ports.md](co-centre-two-ports.md) - session 90's seam, the other bug whose shape was
  "two things nobody compared".
