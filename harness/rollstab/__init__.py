"""Roll-stab seam-clip solver harness (kaze r11 sandbox; see README.md in this package).

Live-calibrated, bit-exact-vs-live planning of the roll-stab (FRONT_ROLL -> B-edge CUT_F) seam
clip: `calibrate` pins the sim to a live anchor run, `solver` searches the input knobs against
the f32 "dust" acceptance (exact per-candidate geometry), `finisher` iterates the anchor position
onto a razor sliver, `deliver` ships the plan as a clean DTM and confirms per-frame live.
"""
