#!/usr/bin/env python3
"""plot_heatmaps.py - one figure per case: the field at each time T, same colour scale.

Usage: plot_heatmaps.py <dir> <N> "<T1 T2 ...>"
Reads <dir>/case{1,2}_T{T}.bin and writes <dir>/heatmaps_case{1,2}.png.
Also prints sanity checks: maximum principle (0 <= u <= 1) and the symmetries of each case.
"""
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TITLES = {1: "Case 1: all four edges at u = 1",
          2: "Case 2: top and bottom at u = 1, left and right at u = 0"}


def load(path, N):
    u = np.fromfile(path, dtype="<f8")
    if u.size != (N + 1) ** 2:
        sys.exit(f"{path}: {u.size} values, expected {(N + 1) ** 2}")
    return u.reshape(N + 1, N + 1)  # u[j, i], row j = y_j


def main():
    d, N, tlist = sys.argv[1], int(sys.argv[2]), sys.argv[3].split()
    for c in (1, 2):
        fig, axes = plt.subplots(1, len(tlist), figsize=(3.3 * len(tlist), 3.6), constrained_layout=True)
        for ax, T in zip(axes, tlist):
            u = load(f"{d}/case{c}_T{T}.bin", N)
            # sanity checks on the interior
            inner = u[1:-1, 1:-1]
            sym_lr = np.max(np.abs(u - u[:, ::-1]))   # mirror x -> 1-x
            sym_tb = np.max(np.abs(u - u[::-1, :]))   # mirror y -> 1-y
            sym_diag = np.max(np.abs(u - u.T)) if c == 1 else float("nan")
            print(f"case={c} T={T}: interior min={inner.min():.6f} max={inner.max():.6f} "
                  f"in[0,1]={bool(inner.min() >= 0 and inner.max() <= 1)} "
                  f"sym_x={sym_lr:.1e} sym_y={sym_tb:.1e}" +
                  (f" sym_diag={sym_diag:.1e}" if c == 1 else ""))
            im = ax.imshow(u, origin="lower", extent=[0, 1, 0, 1], cmap="inferno", vmin=0.0, vmax=1.0)
            ax.set_title(f"t = {T}", fontsize=10)
            ax.set_xlabel("x")
            ax.set_ylabel("y")
        fig.colorbar(im, ax=axes, label="u", shrink=0.9)
        fig.suptitle(f"{TITLES[c]}  (N = {N}, r = 0.25)", fontsize=11)
        out = f"{d}/heatmaps_case{c}.png"
        fig.savefig(out, dpi=150)
        print(f"-> {out}")


if __name__ == "__main__":
    main()
