"""Predicted ESS efficiency over the next N frames — float-accurate recreation of the
legacy SuperSwimPredictionTool `PredictAnimationFrames` graph (Form1.cs).

The old C# tool plotted, for each of the next 150 frames, the ratio of Link's
drag-affected (true) speed to his potential speed as the swim animation cycles,
assuming constant acceleration. It used the tool's own approximate drag formulas.

This recreates the same graph with our validated sim primitives (`sim.incr` for the
animation cycle, `sim.true_disp` for the head-bob + air drag) — see
knowledge/mechanics/animation.md. Efficiency = true_disp(v, anim, air) / v * 100,
so it runs ~100% at anim 0/23 (|cos|=1) down to ~60% at anim 11.5 (|cos|=0).

Usage:
  # from an explicit state
  python viz/predict_ess_efficiency.py --v -1630 --anim 3.5 --air 790 [--accel 0] [--cap 18]
  # live: open a window that continuously redraws as you move through the game
  # (like the C# tool's timer-driven Dolphin hook)
  python viz/predict_ess_efficiency.py --live [--interval 0.05]
Offline writes a PNG (default _generated/ess_efficiency.png); --show opens a window.
"""
import argparse
import os, sys  # >>> repo bootstrap: locate tww_sim/ package + ../tools/ (dolphin_mem)
_rb = os.path.dirname(os.path.abspath(__file__))
while _rb != os.path.dirname(_rb) and not os.path.exists(os.path.join(_rb, 'pyproject.toml')):
    _rb = os.path.dirname(_rb)
if _rb not in sys.path: sys.path.insert(0, _rb)
_tb = os.path.join(os.path.dirname(_rb), 'tools')
if _tb not in sys.path: sys.path.append(_tb)

from tww_sim.swim import sim as S

SWIM_MAX = 18.0  # potential-speed cap for normal swimming (|v|); matches tool speedCap


def efficiency_curve(v, anim, air, steps=150, accel=0.0, cap=SWIM_MAX):
    """Project ESS efficiency forward `steps` frames.

    v, anim, air: current potential speed (signed), animation frame (0..23), air meter.
    accel: per-frame change in the SIGNED speed (constant-acceleration assumption, as in
           the C# tool's `linkAccel`). Holding ESS bleeds speed toward 0, so accel is a
           deceleration; the animation cycle slows over the projected window. 0 = steady.
    cap: signed upper clamp (matches the C# `newSpeed > speedCap` guard; never triggers
         while superswimming, where speed is large-negative).
    Returns list of (frame, efficiency_percent). The animation advances via the exact
    validated `incr` cycle, air decrements 1/frame, and efficiency = |true_disp| / |v|
    * 100 using the head-bob + air drag (true_disp) — the float-accurate replacement for
    the C# `total_drag_coef`.
    """
    pos = anim
    out = []
    for i in range(steps):
        newv = v + accel * i           # signed projection (C#: currentSpeed + linkAccel*i)
        if newv > cap:                 # C#: if (newSpeed > speedCap) newSpeed = speedCap
            newv = cap
        cur_air = max(air - i, 0)
        pos = S.nfmod(pos + S.incr(newv, cur_air), 23.0)
        disp = S.true_disp(newv, pos, cur_air)
        eff = abs(disp) / abs(newv) * 100.0 if newv else 0.0
        out.append((i, eff))
    return out


def _live_reader():
    """Attach to Dolphin once and return a reader() -> (v, anim, air, link_state)."""
    import dolphin_mem as dm
    h, mem1 = dm.attach()

    def reader():
        rd = lambda nm: dm.read_named(h, mem1, nm)
        return (float(rd("potential_speed")), float(rd("anim_frame")),
                int(round(float(rd("air")))), int(round(float(rd("link_state")))))
    return reader


def plot(curve, out_path, title, show=False):
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = [p[0] for p in curve]
    ys = [p[1] for p in curve]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(xs, ys, color=(74 / 255, 87 / 255, 231 / 255), linewidth=2)
    ax.set_xlim(0, xs[-1] if xs else 1)
    ax.set_ylim(50, 100)
    ax.set_xlabel("Future Frames")
    ax.set_ylabel("ESS Efficiency (%)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=120)
    if show:
        plt.show()
    plt.close(fig)
    return out_path


def _curve_title(v, anim, air, accel):
    return (f"Predicted ESS Efficiency  (v={abs(v):.1f}, anim={anim:.2f}, air={air}"
            + (f", accel={accel:+.3f}/fr" if accel else "") + ")")


def live_loop(reader, steps=150, cap=SWIM_MAX, interval=0.05):
    """Open an interactive window and continuously redraw as Dolphin state changes,
    mirroring the C# tool's timer-driven UpdateSwimGraph. The acceleration is measured
    live from the change in potential speed per game frame (the C# `linkAccel`), using
    `air` as the game-frame clock (air decrements exactly 1/frame while swimming). Runs
    until the window closes."""
    import matplotlib.pyplot as plt
    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 5))
    (line,) = ax.plot(range(steps), [0] * steps,
                      color=(74 / 255, 87 / 255, 231 / 255), linewidth=2)
    ax.set_xlim(0, steps)
    ax.set_ylim(50, 100)
    ax.set_xlabel("Future Frames")
    ax.set_ylabel("ESS Efficiency (%)")
    ax.grid(True, alpha=0.3)
    title = ax.set_title("Predicted ESS Efficiency")
    fig.tight_layout()
    fig.show()

    prev_v = prev_air = None
    accel = 0.0
    while plt.fignum_exists(fig.number):
        try:
            v, anim, air, state = reader()
        except Exception as e:
            title.set_text(f"Dolphin read failed: {e}")
            plt.pause(0.5)
            continue
        if state in (53, 54, 55):
            # measure per-game-frame accel like the C# tool: Δspeed / Δframes, using air
            # as the frame clock (1/frame while swimming). Only update when a frame passed.
            if prev_v is not None and prev_air is not None and air < prev_air:
                accel = (v - prev_v) / (prev_air - air)
            prev_v, prev_air = v, air
            curve = efficiency_curve(v, anim, air, steps=steps, accel=accel, cap=cap)
            line.set_ydata([p[1] for p in curve])
            line.set_color((74 / 255, 87 / 255, 231 / 255))
            title.set_text(_curve_title(v, anim, air, accel))
        else:
            prev_v = prev_air = None           # reset the accel estimator between swims
            line.set_ydata([0] * steps)        # not swimming: hidden, like the C# tool
            line.set_color("none")
            title.set_text(f"Not swimming (link_state={state})")
        fig.canvas.draw_idle()
        plt.pause(interval)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--v", type=float, default=-1630.0, help="potential speed (signed)")
    ap.add_argument("--anim", type=float, default=0.0, help="animation frame 0..23")
    ap.add_argument("--air", type=int, default=900, help="air meter")
    ap.add_argument("--accel", type=float, default=0.0,
                    help="per-frame change in SIGNED speed (constant-accel; live mode "
                         "measures this itself). ESS bleed toward 0 => positive when v<0")
    ap.add_argument("--cap", type=float, default=SWIM_MAX, help="signed upper clamp on speed")
    ap.add_argument("--steps", type=int, default=150, help="frames to project")
    ap.add_argument("--live", action="store_true",
                    help="continuously redraw from live Dolphin state (window stays open)")
    ap.add_argument("--interval", type=float, default=0.05,
                    help="live redraw interval in seconds (default 0.05 = 20 Hz)")
    ap.add_argument("--out", default=os.path.join(_rb, "_generated", "ess_efficiency.png"))
    ap.add_argument("--show", action="store_true", help="open a window instead of only PNG")
    args = ap.parse_args(argv)

    if args.live:
        reader = _live_reader()
        print("live: redrawing from Dolphin (accel measured live) — close the window to stop.")
        live_loop(reader, steps=args.steps, cap=args.cap, interval=args.interval)
        return

    v, anim, air = args.v, args.anim, args.air
    curve = efficiency_curve(v, anim, air, steps=args.steps, accel=args.accel, cap=args.cap)
    path = plot(curve, args.out, _curve_title(v, anim, air, args.accel), show=args.show)
    lo = min(p[1] for p in curve)
    hi = max(p[1] for p in curve)
    print(f"wrote {path}  (efficiency {lo:.1f}%..{hi:.1f}% over {args.steps} frames)")


if __name__ == "__main__":
    main()
