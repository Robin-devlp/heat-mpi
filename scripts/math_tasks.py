#!/usr/bin/env python3
"""math_tasks.py - the computations of the background-notes Tasks 3.2(c), 3.5, 4.1 and 6.7.

Writes tables (tables.md) and plots (PNG) to results/math_tasks/.
Usage:  python scripts/math_tasks.py [output folder]
"""
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, "results", "math_tasks")
os.makedirs(OUT, exist_ok=True)
lines = []
w = lines.append


def d2(f, x, h):
    """Three-point second difference (Task 3.2)."""
    return (f(x - h) - 2.0 * f(x) + f(x + h)) / (h * h)


# ---------------------------------------------------------------- Task 3.2(c)
w("## Task 3.2(c): D2 f(1; h) for f = sin, exact f''(1) = -sin(1)\n")
w("| h | D2f(1;h) | E(h) | R = E(2h)/E(h) | p_obs |")
w("|---|---|---|---|---|")
prev = None
for h in (0.1, 0.05, 0.025, 0.0125):
    d = d2(math.sin, 1.0, h)
    e = abs(d + math.sin(1.0))
    if prev is None:
        w(f"| {h} | {d:.10f} | {e:.8e} | - | - |")
    else:
        r = prev / e
        w(f"| {h} | {d:.10f} | {e:.8e} | {r:.4f} | {math.log2(r):.4f} |")
    prev = e
w("")

# ---------------------------------------------------------------- Task 3.5
w("## Task 3.5: where round-off takes over (h = 1e-1 ... 1e-10)\n")
w("| h | D2f(1;h) | E(h) |")
w("|---|---|---|")
hs = [10.0 ** (-k) for k in range(1, 11)]
errs = []
for h in hs:
    d = d2(math.sin, 1.0, h)
    e = abs(d + math.sin(1.0))
    errs.append(e)
    w(f"| {h:.0e} | {d:.12e} | {e:.12e} |")
k = int(np.argmin(errs))
w(f"\nSmallest error at h = {hs[k]:.0e}: E = {errs[k]:.12e}. "
  f"Theory: h ~ eps^(1/4) = {np.finfo(float).eps ** 0.25:.6e}.\n")

fig, ax = plt.subplots(figsize=(6.5, 4.3))
ax.loglog(hs, errs, "o-", label="measured error E(h)")
ax.loglog(hs, [math.sin(1.0) * h * h / 12 for h in hs], "--", label="truncation error sin(1) h^2 / 12")
ax.loglog([hs[k]], [errs[k]], "o", ms=12, mfc="none", label=f"minimum at h = {hs[k]:.0e}")
ax.invert_xaxis()
ax.set_xlabel("h")
ax.set_ylabel("|D2 f(1;h) - f''(1)|")
ax.set_title("Task 3.5: truncation error vs. round-off error")
ax.grid(alpha=0.3, which="both")
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, "task3_5_roundoff.png"), dpi=150)
plt.close(fig)

# ---------------------------------------------------------------- Task 4.1
LAM = 50.0
EXACT = math.exp(-LAM)


def euler(nt, method):
    dt = 1.0 / nt
    g = 1.0 - LAM * dt if method == "FE" else 1.0 / (1.0 + LAM * dt)
    u = 1.0
    traj = [u]
    for _ in range(nt):
        u = g * u
        traj.append(u)
    return g, np.array(traj)


w("## Task 4.1: u' = -50 u, u(0) = 1 on [0, 1]; exact u(1) = e^-50 = "
  f"{EXACT:.12e}\n")
w("### Stability (values at t = 1)\n")
w("| Nt | dt | g_FE | u_FE(1) | g_BE | u_BE(1) |")
w("|---|---|---|---|---|---|")
for nt in (20, 24, 25, 26, 30, 50, 100):
    gf, tf = euler(nt, "FE")
    gb, tb = euler(nt, "BE")
    w(f"| {nt} | {1/nt:.8f} | {gf:+.6f} | {tf[-1]:+.3e} | {gb:.6f} | {tb[-1]:.3e} |")
w("\nForward Euler: |g| <= 1 needs dt <= 2/50 = 0.04. Backward Euler: 0 < g < 1 for every dt.\n")

w("### Convergence at t = 1 (stable steps)\n")
w("| Nt | dt | E_FE | p_FE | E_BE | p_BE |")
w("|---|---|---|---|---|---|")
pf = pb = None
for nt in (800, 1600, 3200, 6400, 12800, 25600, 51200):
    ef = abs(euler(nt, "FE")[1][-1] - EXACT)
    eb = abs(euler(nt, "BE")[1][-1] - EXACT)
    sf = f"{math.log2(pf / ef):.4f}" if pf else "-"
    sb = f"{math.log2(pb / eb):.4f}" if pb else "-"
    w(f"| {nt} | {1/nt:.6g} | {ef:.6e} | {sf} | {eb:.6e} | {sb} |")
    pf, pb = ef, eb
w("")

fig, ax = plt.subplots(figsize=(6.5, 4.3))
t = np.linspace(0, 1, 400)
ax.semilogy(t, np.exp(-LAM * t), "k-", label="exact e^-50t")
for nt, method, mk in ((40, "FE", "o"), (25, "FE", "s"), (20, "FE", "^"), (20, "BE", "D")):
    _, tr = euler(nt, method)
    ax.semilogy(np.linspace(0, 1, nt + 1), np.abs(tr), mk + "-", ms=3,
                label=f"{method}, dt = {1/nt:g}")
ax.set_xlabel("t")
ax.set_ylabel("|u_n|")
ax.set_title("Task 4.1: forward and backward Euler")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "task4_1_euler.png"), dpi=150)
plt.close(fig)

# ---------------------------------------------------------------- Task 6.7 (seeded mode)
N = 64
x = np.linspace(0.0, 1.0, N + 1)
X, Y = np.meshgrid(x, x)                      # u[j, i], row j = y_j
smooth = np.sin(np.pi * X) * np.sin(np.pi * Y)
mode = np.sin((N - 1) * np.pi * X) * np.sin((N - 1) * np.pi * Y)
STEPS = 240


def run(r, keep=()):
    u = smooth + 1e-6 * mode
    u[0, :] = u[-1, :] = u[:, 0] = u[:, -1] = 0.0
    maxs, snaps = [np.abs(u).max()], {}
    amp = [np.sum(u * mode) / np.sum(mode * mode)]
    for n in range(1, STEPS + 1):
        new = u.copy()
        c = u[1:-1, 1:-1]
        new[1:-1, 1:-1] = c + r * ((u[1:-1, 2:] + u[1:-1, :-2]) + (u[2:, 1:-1] + u[:-2, 1:-1]) - 4.0 * c)
        u = new
        maxs.append(np.abs(u).max())
        if n == 1:
            amp.append(np.sum(u * mode) / np.sum(mode * mode))
        if n in keep:
            snaps[n] = u.copy()
    return np.array(maxs), amp, snaps


SNAP = (120, 160, 200, 240)
m_stable, _, _ = run(0.25)
m_unstable, amp, snaps = run(0.2625, SNAP)
g_theory = 1 - 8 * 0.2625 * math.cos(math.pi / (2 * N)) ** 2
w("## Task 6.7: N = 64, seeded highest-frequency mode, 240 steps\n")
w(f"Amplification of the seeded mode, step 0 -> 1: measured {amp[1] / amp[0]:.8f}, "
  f"theory 1 - 8 r cos^2(pi/(2N)) = {g_theory:.8f}\n")
w("| n | max|u|, r = 0.25 | max|u|, r = 0.2625 |")
w("|---|---|---|")
for n in range(0, STEPS + 1, 40):
    w(f"| {n} | {m_stable[n]:.6e} | {m_unstable[n]:.6e} |")
w("")

fig, ax = plt.subplots(figsize=(6.5, 4.0))
ax.semilogy(m_stable, label="r = 0.25 (at the limit)")
ax.semilogy(m_unstable, label="r = 0.2625 (5% above)")
ax.set_xlabel("time step n")
ax.set_ylabel("max |u|")
ax.set_title("Task 6.7: maximum temperature")
ax.grid(alpha=0.3, which="both")
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, "task6_7_max.png"), dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, len(SNAP), figsize=(3.2 * len(SNAP), 3.2))
for ax, n in zip(axes, SNAP):
    s = snaps[n]
    lim = np.abs(s).max()
    ax.imshow(s, origin="lower", extent=[0, 1, 0, 1], cmap="RdBu_r", vmin=-lim, vmax=lim)
    ax.set_title(f"n = {n}, max|u| = {lim:.3g}", fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])
fig.suptitle("Task 6.7: r = 0.2625, the checkerboard grows")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "task6_7_snapshots.png"), dpi=150)
plt.close(fig)

with open(os.path.join(OUT, "tables.md"), "w", encoding="utf-8") as f:
    f.write("# Background-notes Tasks: computed results\n\n" + "\n".join(lines) + "\n")
print("\n".join(lines))
print(f"-> {OUT}")
