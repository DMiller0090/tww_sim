# How long the entry lean survives a roll (and why it is not a lever on a late cut)

**Answers:** Is the entry lean `m351C` a knob on what happens late in a roll? Why does sweeping the lean
move my cut-frame result by nothing? Which roll frames does the lean actually shape? Should a search
carry the lean as an axis at every cut step?
**Status:** measured and gated (session 101) in
[`tests/test_razor_depth.py`](../../tests/test_razor_depth.py)
(`test_the_entry_lean_is_spent_before_the_cut_fires`): the delivered lean's draw runs −388 → −1 over 15
roll frames, and with the razor re-solved per lean the cut-frame depth moves 0.0003 u over ±3000 s16.
**Source:** `harness/tetrapush/entry_search.py` (`lean_at_roll`), `tww_sim/land/state.py`
(`SLANT_DECAY` = 0.35, `_set_move_slant_angle`). Constants:
[reference/constants.md](../reference/constants.md).

---

The MOVE turn lean `m351C` is what tilts Link's body, and through the body it tilts the Co-cylinder
centre ([link-co-centre.md](link-co-centre.md)). A roll is not a MOVE, so `_set_move_slant_angle` takes
its **decay branch** every roll frame:

    m351C ← m351C − int(f32(m351C · 0.35))          `entry_search.lean_at_roll`

which is a 35%-per-frame geometric decay with an integer truncation under it. The pose reads
`m351C >> 1`, so from the delivered clip's entry lean of 64761 (−775 signed) the draw goes

| roll frame | 0 | 1 | 2 | 4 | 6 | 8 | 11 | **15** | 16 |
|---|---|---|---|---|---|---|---|---|---|
| draw | −388 | −252 | −164 | −70 | −30 | −13 | −4 | **−1** | 0 |

**So the entry lean is spent within about ten frames, whatever it was.** A ±3000 s16 entry lean - four
times the delivered one - is down to −2 by frame 15 as well: the decay is geometric, so a bigger lean
buys two or three more frames, not a different regime.

## The consequence for a search

A cut that dispatches at `cut_step` 15 or 17 ([roll-cut-thrust-floor.md](roll-cut-thrust-floor.md)) is
posed from a body with **no lean left**, so the lean cannot move anything the cut frame reads - the Co
centre, the push it generates, or the endpoint. Measured at the arrive-exactly configuration with the
razor re-solved at each value, ±3000 s16 of entry lean moves the cut-frame depth by **0.0003 u** against
a floor of 0.115.

That is not the same as "the lean does not matter". It shapes the **early** roll frames, where the Co
centre is displaced by tenths of a unit and the push on a nearby actor is real - which is why
`entry_lean`'s band census is a live axis for the acceptance band, and why the two-lean Co model was
needed to make the clip roll bit-exact in the first place. The rule is about WHERE in the roll:

> **The lean is an early-roll lever. Past ~10 roll frames it has decayed out, and a sweep of it at a
> late cut frame is measuring nothing.**

And "the depth at a solved configuration" is not "the set of configurations that solve". Re-scanning
the Courtyard terminal family at a non-zero entry lean keeps the depth and still moves the family, on
the early frames that decide where the plow leaves her. Quote the 0.0003 u for a depth and re-scan for
a family: [../strategy/dispatchable-is-not-clipping.md](../strategy/dispatchable-is-not-clipping.md).

**Which lean to re-scan AT is the roll's own, and it is not the walk's.** The A press acts a frame
late, so the roll's first frame is still a MOVE and its turn WRITES `m351C` before any decay begins -
the schedule seed is the value after the ENTRY frame, which `lean_at_roll` names and one simulated
roll reads: [../strategy/the-lean-is-the-rolls-own-dispatch.md](../strategy/the-lean-is-the-rolls-own-dispatch.md).

## The methodology trap this hides behind

Sweeping the lean **at a frozen entry** reads a spurious sensitivity - 0.03 u at the same configuration
where the true figure is 0.0003. Changing the lean moves the razor, so a frozen entry is compared
off-curve, and what the sweep reports is the residual's own gradient wearing the lean's name. Re-solve
the entry onto the razor at every lean value, then compare.

## See also

- [link-co-centre.md](link-co-centre.md) - the two lean terms and which frame each reads.
- [roll.md](roll.md) - the roll's constant momentum and facing snap.
- [roll-cut-thrust-floor.md](roll-cut-thrust-floor.md) - which frame the cut can dispatch on.
- [../strategy/clip-razor-depth.md](../strategy/clip-razor-depth.md) - the search this ruled a lever out
  of.
