#!/usr/bin/env python3
"""plot_convergence.py - convergence table and log-log plot for Task 7.2.

Reads <dir>/runs.txt (summary lines of the heat program, case V) and writes
<dir>/convergence_table.md and <dir>/convergence.png.
p_obs = log2(E(h) / E(h/2)) for consecutive grids.
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse(line):
    return dict(kv.split("=", 1) for kv in line.split() if "=" in kv)


def main():
    d = sys.argv[1]
    rows = [parse(l) for l in open(os.path.join(d, "runs.txt")) if l.startswith("decomp=")]
    rows.sort(key=lambda r: int(r["N"]))
    N = [int(r["N"]) for r in rows]
    h = [1.0 / n for n in N]
    einf = [float(r["err_inf"]) for r in rows]
    el2 = [float(r["err_l2"]) for r in rows]
    steps = [int(r["steps"]) for r in rows]

    md = ["| N | h | steps | r | e_inf | e_2,h | p_obs (e_inf) | p_obs (e_2,h) |",
          "|---|---|---|---|---|---|---|---|"]
    for k in range(len(N)):
        if k == 0:
            pi, p2 = "--", "--"
        else:
            pi = f"{math.log2(einf[k-1] / einf[k]):.3f}"
            p2 = f"{math.log2(el2[k-1] / el2[k]):.3f}"
        md.append(f"| {N[k]} | 1/{N[k]} | {steps[k]} | {float(rows[k]['r']):g} | "
                  f"{einf[k]:.4e} | {el2[k]:.4e} | {pi} | {p2} |")
    open(os.path.join(d, "convergence_table.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))

    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    ax.loglog(h, el2, "o-", label=r"$\|e\|_{2,h}$")
    ax.loglog(h, einf, "s-", label=r"$\|e\|_\infty$")
    ref = [el2[0] * (hh / h[0]) ** 2 for hh in h]
    ax.loglog(h, ref, "k--", lw=1, label=r"slope 2 ($\propto h^2$)")
    ax.set_xlabel("grid spacing h")
    ax.set_ylabel("error at T = 0.05")
    ax.set_title(f"Convergence study, test V, r = {float(rows[0]['r']):g}")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(d, "convergence.png"), dpi=150)
    print(f"written {d}/convergence_table.md and convergence.png")


if __name__ == "__main__":
    main()
