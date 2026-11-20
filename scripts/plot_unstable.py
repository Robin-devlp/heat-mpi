#!/usr/bin/env python3
"""plot_unstable.py - figure for Task 6.7 (time step 5% above the stability limit).

Usage: plot_unstable.py <dir> <N>
Plots the fields unstable_s*.bin and stable_s200.bin found in <dir>.
"""
import glob
import os
import re
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import SymLogNorm


def load(path, N):
    return np.fromfile(path, dtype="<f8").reshape(N + 1, N + 1)  # [j, i]


def main():
    d, N = sys.argv[1], int(sys.argv[2])
    files = sorted(glob.glob(os.path.join(d, "unstable_s*.bin")),
                   key=lambda f: int(re.search(r"_s(\d+)", f).group(1)))
    files.append(os.path.join(d, "stable_s200.bin"))

    fig, axes = plt.subplots(1, len(files), figsize=(3.6 * len(files), 3.8))
    for ax, f in zip(axes, files):
        u = load(f, N)
        name = os.path.basename(f)[:-4]
        steps = re.search(r"_s(\d+)", name).group(1)
        r = "0.2625 (unstable)" if name.startswith("unstable") else "0.25 (stable)"
        vmax = max(1.0, np.abs(u).max())
        im = ax.imshow(u, origin="lower", extent=[0, 1, 0, 1], cmap="RdBu_r",
                       norm=SymLogNorm(linthresh=1e-2, vmin=-vmax, vmax=vmax))
        ax.set_title(f"r = {r}\nstep {steps}, max|u| = {np.abs(u).max():.2g}", fontsize=9)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(f"Task 6.7: case 1, N = {N}, time step 5% above the stability limit", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(d, "unstable.png"), dpi=150)

    # zoom on a corner of the last unstable field to show the checkerboard pattern
    u = load(files[-2], N)
    fig2, ax2 = plt.subplots(figsize=(4.5, 4))
    k = 12
    im = ax2.imshow(u[:k, :k], origin="lower", cmap="RdBu_r",
                    norm=SymLogNorm(linthresh=1e-2, vmin=-np.abs(u[:k, :k]).max(), vmax=np.abs(u[:k, :k]).max()))
    ax2.set_title(f"zoom on corner (nodes 0..{k-1}), {os.path.basename(files[-2])[:-4]}", fontsize=9)
    ax2.set_xlabel("i")
    ax2.set_ylabel("j")
    fig2.colorbar(im, ax=ax2)
    fig2.tight_layout()
    fig2.savefig(os.path.join(d, "unstable_zoom.png"), dpi=150)

    for f in files:
        u = load(f, N)
        print(f"{os.path.basename(f)}: min={u.min():.4g} max={u.max():.4g}")
    print(f"written {d}/unstable.png and unstable_zoom.png")


if __name__ == "__main__":
    main()
