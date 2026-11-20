#!/usr/bin/env python3
"""plot_field.py - heat map of a field file written by heat --out.

Usage: plot_field.py <file.bin> <N> [output.png] [title]
The file holds (N+1)x(N+1) little-endian doubles, row-major, row j = line y = y_j.
"""
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    path, N = sys.argv[1], int(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else path.rsplit(".", 1)[0] + ".png"
    title = sys.argv[4] if len(sys.argv) > 4 else path
    u = np.fromfile(path, dtype="<f8")
    if u.size != (N + 1) ** 2:
        sys.exit(f"{path}: {u.size} values, expected {(N + 1) ** 2} for N={N}")
    u = u.reshape(N + 1, N + 1)
    fig, ax = plt.subplots(figsize=(5.5, 4.6))
    im = ax.imshow(u, origin="lower", extent=[0, 1, 0, 1], cmap="inferno", vmin=0.0, vmax=max(1.0, u.max()))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(title, fontsize=10)
    fig.colorbar(im, ax=ax, label="u")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"min={u.min():.6g} max={u.max():.6g} -> {out}")


if __name__ == "__main__":
    main()
