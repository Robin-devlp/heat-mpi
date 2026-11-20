#!/usr/bin/env python3
"""analyze_perf.py - Part 4 analysis: measurements, performance model, plots and tables.

Inputs (defaults are the files of this project):
  results/perf/run_20261119/perf.csv              strong + weak scaling runs (run_perf.sh)
  results/perf/baseline_*/baseline.csv            serial baseline of every VM (run_baseline.sh)
  results/raw/pingpong/20261118-192223/pingpong_table.csv   t_s, t_w of every link (fit_pingpong.py)
Output: <run>/analysis/  (PNG plots + summary.md)

Performance model (background notes, Task 8.2), time per step = compute + communication:
  compute = max over ranks of  (local interior nodes) * t_node(host, local size)
            t_node from the serial baseline of that VM, interpolated in the local grid size
  comm    = sum over the exchange phases of the slowest message in that phase,
            message cost  t_s + m * t_w  of the link it uses (same VM or the VM pair, ping-pong)
            strips: 2 phases (send up, send down), m = 8 (N+1) bytes
            blocks: 4 phases (up, down, right, left), rows m = 8 nlx, columns m = 8 nly
  "shared uplink" variant: when k processes of one VM send over the network in the same phase,
            they share that VM's internet connection, so each message gets t_w * k.
Usage:  python scripts/analyze_perf.py [run_dir] [pingpong_dir]
"""
import csv
import glob
import math
import os
import sys
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, "results/perf/run_20261119")
PP = sys.argv[2] if len(sys.argv) > 2 else os.path.join(PROJ, "results/raw/pingpong/20261118-192223")
OUT = os.path.join(RUN, "analysis")
os.makedirs(OUT, exist_ok=True)

HOSTS = [("heat-robin", 4), ("heat-elio", 2), ("heat-michel", 4)]   # hostfile order and slots
SHORT = {"heat-robin": "robin", "heat-elio": "elio", "heat-michel": "michel"}
STEPS = 200
COLORS = {"strips": "#1f77b4", "blocks": "#d62728"}
MARK = {"node": "o", "slot": "s"}


# ----------------------------------------------------------------------------- inputs
def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


perf = [r for r in read_csv(os.path.join(RUN, "perf.csv")) if r["status"] == "ok"]
for r in perf:
    for k in ("N", "P", "steps", "rep"):
        r[k] = int(r[k])
    for k in ("t_total", "t_comp", "t_comm"):
        r[k] = float(r[k])

base_rows = []
for p in glob.glob(os.path.join(PROJ, "results/perf/baseline_*/baseline.csv")):
    base_rows += read_csv(p)
base = defaultdict(list)                       # (host, N) -> [seconds per node]
for r in base_rows:
    base[(r["host"], int(r["N"]))].append(float(r["t_per_node"]))
BASE_N = sorted({n for _, n in base})


def t_node(host, nodes):
    """Serial time per node on `host` for a grid of `nodes` interior nodes (log-log interpolation
    of the baseline medians; constant beyond the measured range)."""
    xs = np.log([(n - 1) ** 2 for n in BASE_N])
    ys = np.log([np.median(base[(host, n)]) for n in BASE_N])
    return float(np.exp(np.interp(math.log(max(nodes, 1)), xs, ys)))


link = {}
for r in read_csv(os.path.join(PP, "pingpong_table.csv")):
    ts, tw = float(r["t_s_us"]) * 1e-6, float(r["t_w_s_per_byte"])
    name = r["case"]
    if name.startswith("same_"):
        h = name[5:]
        link[(h, h)] = (ts, tw)
    else:
        a, b = name[6:].split("__")
        link[(a, b)] = link[(b, a)] = (ts, tw)


# ----------------------------------------------------------------------------- placement
def placement(P, mapping):
    """Host of every rank, as Open MPI places them with our hostfile."""
    if mapping == "slot":
        hosts = [h for h, s in HOSTS for _ in range(s)]
        return hosts[:P]
    left = {h: s for h, s in HOSTS}
    out = []
    while len(out) < P:
        for h, _ in HOSTS:
            if left[h] > 0 and len(out) < P:
                out.append(h)
                left[h] -= 1
    return out


def split(n, parts):
    base_, extra = divmod(n, parts)
    return [base_ + (1 if k < extra else 0) for k in range(parts)]


def dims_create(P):
    """MPI_Dims_create(P, 2): the most square factorisation, dims[0] >= dims[1]."""
    best = (P, 1)
    for a in range(1, int(math.isqrt(P)) + 1):
        if P % a == 0:
            best = (P // a, a)
    return best


# ----------------------------------------------------------------------------- model
def model(decomp, mapping, N, P, params=None, shared=False):
    """Predicted time per step (compute, comm) in seconds."""
    lk = params or link
    hosts = placement(P, mapping)
    msgs_per_phase = []                 # list of phases, each a list of (src_host, dst_host, bytes)
    if decomp == "strips":
        rows = split(N - 1, P)
        local = [rows[k] * (N - 1) for k in range(P)]
        m = 8 * (N + 1)
        up = [(hosts[k], hosts[k + 1], m) for k in range(P - 1)]
        down = [(hosts[k + 1], hosts[k], m) for k in range(P - 1)]
        msgs_per_phase = [up, down]
    else:
        Py, Px = dims_create(P)
        ny, nx = split(N - 1, Py), split(N - 1, Px)
        rank = lambda cy, cx: cy * Px + cx
        local = [ny[k // Px] * nx[k % Px] for k in range(P)]
        up, down, right, left = [], [], [], []
        for cy in range(Py):
            for cx in range(Px):
                r = rank(cy, cx)
                if cy + 1 < Py:
                    up.append((hosts[r], hosts[rank(cy + 1, cx)], 8 * nx[cx]))
                    down.append((hosts[rank(cy + 1, cx)], hosts[r], 8 * nx[cx]))
                if cx + 1 < Px:
                    right.append((hosts[r], hosts[rank(cy, cx + 1)], 8 * ny[cy]))
                    left.append((hosts[rank(cy, cx + 1)], hosts[r], 8 * ny[cy]))
        msgs_per_phase = [up, down, right, left]
    comp = max(local[k] * t_node(hosts[k], local[k]) for k in range(P))
    comm = 0.0
    for phase in msgs_per_phase:
        if not phase:
            continue
        # how many network messages leave each VM in this phase (shared uplink)
        out_count = defaultdict(int)
        for s, d, _ in phase:
            if s != d:
                out_count[s] += 1
        worst = 0.0
        for s, d, m in phase:
            ts, tw = lk[(s, d)]
            k = out_count[s] if (shared and s != d) else 1
            worst = max(worst, ts + m * tw * k)
        comm += worst
    return comp, comm


# ----------------------------------------------------------------------------- measurements
def stats(exp, decomp, mapping, N, P, key="t_total"):
    v = [r[key] / STEPS for r in perf if r["exp"] == exp and r["decomp"] == decomp and
         r["map"] == mapping and r["N"] == N and r["P"] == P]
    if not v:
        return None
    return float(np.median(v)), float(min(v)), float(max(v)), len(v)


def strong(decomp, mapping, N, P, key="t_total"):
    m = "node" if P == 1 else mapping          # P = 1 was run once (with --map-by node)
    return stats("strong", decomp, m, N, P, key)


def T1(N):
    """Reference one-process time per step for the speed-ups: median of ALL one-process runs at N
    (strips and blocks, every repetition). On one process both versions do identical work (checked
    separately: serial, strips and blocks give the same compute time), so one common reference is
    used for every version, as in the usual definition S(P) = T_serial / T_P."""
    v = [r["t_total"] / STEPS for r in perf if r["exp"] == "strong" and r["N"] == N and r["P"] == 1]
    return float(np.median(v))


PMAX = 10
PS = list(range(1, PMAX + 1))
STRONG_N = sorted({r["N"] for r in perf if r["exp"] == "strong"})
lines = []                                    # summary.md
w = lines.append

w("# Part 4 - performance analysis\n")
w(f"Source: `{os.path.relpath(RUN, PROJ)}/perf.csv` ({len(perf)} successful runs, {STEPS} steps each, "
  f"Case 1, r = 0.25); ping-pong: `{os.path.relpath(PP, PROJ)}`. All times are **per step**, "
  "median of 3 repetitions (spread = min..max).\n")

# ----------------------------------------------------------------------------- 1 baseline
w("## 1. Single-node baseline (serial, 500 steps, 3 repetitions)\n")
w("| N | " + " | ".join(SHORT[h] + " ns/node" for h, _ in HOSTS) + " | " +
  " | ".join(SHORT[h] + " ms/step" for h, _ in HOSTS) + " |")
w("|---" * (1 + 2 * len(HOSTS)) + "|")
for n in BASE_N:
    ns = [np.median(base[(h, n)]) * 1e9 for h, _ in HOSTS]
    ms = [np.median(base[(h, n)]) * (n - 1) ** 2 * 1e3 for h, _ in HOSTS]
    w(f"| {n} | " + " | ".join(f"{x:.2f}" for x in ns) + " | " + " | ".join(f"{x:.1f}" for x in ms) + " |")
w("")
fig, ax = plt.subplots(figsize=(6.5, 4.2))
for h, _ in HOSTS:
    y = [np.median(base[(h, n)]) * 1e9 for n in BASE_N]
    lo = [min(base[(h, n)]) * 1e9 for n in BASE_N]
    hi = [max(base[(h, n)]) * 1e9 for n in BASE_N]
    ax.errorbar(BASE_N, y, yerr=[np.subtract(y, lo), np.subtract(hi, y)], marker="o", capsize=3, label=SHORT[h])
ax.set_xscale("log", base=2)
ax.set_xlabel("N")
ax.set_ylabel("serial time per grid node per step [ns]")
ax.set_title("Single-node baseline (compute rate of each VM)")
ax.grid(alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, "baseline.png"), dpi=150)
plt.close(fig)

# ----------------------------------------------------------------------------- 2 strong scaling
w("## 2. Strong scaling\n")
for N in STRONG_N:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, mapping in zip(axes, ("node", "slot")):
        for d in ("strips", "blocks"):
            st = [strong(d, mapping, N, P) for P in PS]
            y = np.array([s[0] for s in st])
            lo = y - np.array([s[1] for s in st])
            hi = np.array([s[2] for s in st]) - y
            ax.errorbar(PS, y, yerr=[lo, hi], fmt=MARK[mapping], color=COLORS[d], capsize=3,
                        label=f"{d} measured")
            mod = [sum(model(d, mapping, N, P)) for P in PS]
            mods = [sum(model(d, mapping, N, P, shared=True)) for P in PS]
            ax.plot(PS, mod, "-", color=COLORS[d], lw=1.2, label=f"{d} model")
            ax.plot(PS, mods, "--", color=COLORS[d], lw=1.2, label=f"{d} model, shared uplink")
        ax.set_yscale("log")
        ax.set_xlabel("P (processes)")
        ax.set_title(f"N = {N}, --map-by {mapping}")
        ax.grid(alpha=0.3, which="both")
    axes[0].set_ylabel("time per step [s]")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"strong_time_N{N}.png"), dpi=150)
    plt.close(fig)

# speed-up and efficiency
fig, axes = plt.subplots(2, len(STRONG_N), figsize=(5 * len(STRONG_N), 8))
for c, N in enumerate(STRONG_N):
    for d in ("strips", "blocks"):
        for mapping in ("node", "slot"):
            S = [T1(N) / strong(d, mapping, N, P)[0] for P in PS]
            E = [s / P for s, P in zip(S, PS)]
            ls = "-" if mapping == "node" else ":"
            axes[0, c].plot(PS, S, ls, marker=MARK[mapping], color=COLORS[d], label=f"{d}, map-by {mapping}")
            axes[1, c].plot(PS, E, ls, marker=MARK[mapping], color=COLORS[d], label=f"{d}, map-by {mapping}")
    axes[0, c].plot(PS, PS, "k--", lw=0.8, label="ideal")
    axes[0, c].set_yscale("log")
    axes[0, c].set_title(f"N = {N}")
    axes[0, c].set_ylabel("speed-up S(P) = T1 / TP")
    axes[1, c].set_ylabel("efficiency E(P) = S(P) / P")
    axes[1, c].set_yscale("log")
    for r_ in (0, 1):
        axes[r_, c].set_xlabel("P")
        axes[r_, c].grid(alpha=0.3, which="both")
axes[0, 0].legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "strong_speedup_efficiency.png"), dpi=150)
plt.close(fig)

for N in STRONG_N:
    w(f"### N = {N}\n")
    w("| P | strips node | blocks node | strips slot | blocks slot | S strips node | S blocks node | "
      "S strips slot | S blocks slot |")
    w("|---|---|---|---|---|---|---|---|---|")
    for P in PS:
        cells, sp = [], []
        for mapping in ("node", "slot"):
            for d in ("strips", "blocks"):
                s = strong(d, mapping, N, P)
                cells.append(f"{s[0]*1e3:.1f} ({s[1]*1e3:.1f}..{s[2]*1e3:.1f})")
                sp.append(f"{T1(N)/s[0]:.3f}")
        w(f"| {P} | " + " | ".join(cells) + " | " + " | ".join(sp) + " |")
    w(f"\n(times in ms per step: median (min..max). S = T1 / TP with one common reference "
      f"T1 = {T1(N)*1e3:.2f} ms = median of all six one-process runs at this N, strips and blocks.)\n")

# ----------------------------------------------------------------------------- 3 model vs measurement
w("## 3. Model vs measurement (time per step, map-by node)\n")
w("| N | decomp | P | measured | model | model shared uplink | measured / model | measured / shared |")
w("|---|---|---|---|---|---|---|---|")
ratio_plain, ratio_shared = [], []
for N in STRONG_N:
    for d in ("strips", "blocks"):
        for P in (2, 3, 4, 6, 8, 10):
            meas = strong(d, "node", N, P)[0]
            mp = sum(model(d, "node", N, P))
            ms = sum(model(d, "node", N, P, shared=True))
            ratio_plain.append(meas / mp)
            ratio_shared.append(meas / ms)
            w(f"| {N} | {d} | {P} | {meas*1e3:.1f} ms | {mp*1e3:.1f} ms | {ms*1e3:.1f} ms | "
              f"{meas/mp:.2f} | {meas/ms:.2f} |")
gm = lambda v: float(np.exp(np.mean(np.log(v))))
w(f"\nGeometric mean of measured/model: plain model **{gm(ratio_plain):.2f}** "
  f"(range {min(ratio_plain):.2f}..{max(ratio_plain):.2f}); shared-uplink model **{gm(ratio_shared):.2f}** "
  f"(range {min(ratio_shared):.2f}..{max(ratio_shared):.2f}).\n")

# ----------------------------------------------------------------------------- 4 strips vs blocks (Part 3 question)
w("## 4. Strips or blocks? Prediction (Task 8.2 model) vs measurement, map-by node\n")
w("| N | P | model strips | model blocks | predicted faster | measured strips | measured blocks | measured faster |")
w("|---|---|---|---|---|---|---|---|")
for N in (512, 2048, 8192):
    for P in (4, 8):
        ms_, mb_ = sum(model("strips", "node", N, P)), sum(model("blocks", "node", N, P))
        es, eb = strong("strips", "node", N, P)[0], strong("blocks", "node", N, P)[0]
        w(f"| {N} | {P} | {ms_*1e3:.1f} ms | {mb_*1e3:.1f} ms | {'strips' if ms_ < mb_ else 'blocks'} | "
          f"{es*1e3:.1f} ms | {eb*1e3:.1f} ms | {'strips' if es < eb else 'blocks'} |")
w("")

# ----------------------------------------------------------------------------- 5 communication share
w("## 5. Communication share t_comm / t_total (median), map-by node\n")
w("| N | decomp | " + " | ".join(f"P={P}" for P in PS[1:]) + " |")
w("|---|---|" + "---|" * (len(PS) - 1))
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
for ax, mapping in zip(axes, ("node", "slot")):
    for N, ls in zip(STRONG_N, ("-", "--", ":")):
        for d in ("strips", "blocks"):
            sh = []
            for P in PS[1:]:
                v = [r["t_comm"] / r["t_total"] for r in perf if r["exp"] == "strong" and r["decomp"] == d
                     and r["map"] == mapping and r["N"] == N and r["P"] == P]
                sh.append(float(np.median(v)))
            ax.plot(PS[1:], sh, ls, marker="o", ms=3, color=COLORS[d], label=f"{d} N={N}")
            if mapping == "node":
                w(f"| {N} | {d} | " + " | ".join(f"{100*s:.0f}%" for s in sh) + " |")
    ax.set_title(f"--map-by {mapping}")
    ax.set_xlabel("P")
    ax.grid(alpha=0.3)
axes[0].set_ylabel("communication share of the run time")
axes[1].legend(fontsize=7, ncol=2)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "comm_share.png"), dpi=150)
plt.close(fig)
w("")

# ----------------------------------------------------------------------------- 6 weak scaling
w("## 6. Weak scaling (about 1024 x 1024 interior nodes per process, map-by node)\n")
w("| P | N | strips measured | strips model | blocks measured | blocks model |")
w("|---|---|---|---|---|---|")
fig, ax = plt.subplots(figsize=(6.5, 4.2))
for d in ("strips", "blocks"):
    xs, ys, lo, hi, mo = [], [], [], [], []
    for P in PS:
        rows = [r for r in perf if r["exp"] == "weak" and r["decomp"] == d and r["P"] == P]
        N = rows[0]["N"]
        s = stats("weak", d, "node", N, P)
        xs.append(P); ys.append(s[0]); lo.append(s[0] - s[1]); hi.append(s[2] - s[0])
        mo.append(sum(model(d, "node", N, P)))
    ax.errorbar(xs, ys, yerr=[lo, hi], fmt="o", color=COLORS[d], capsize=3, label=f"{d} measured")
    ax.plot(xs, mo, "-", color=COLORS[d], lw=1.2, label=f"{d} model")
for P in PS:
    N = [r for r in perf if r["exp"] == "weak" and r["P"] == P][0]["N"]
    s_, b_ = stats("weak", "strips", "node", N, P)[0], stats("weak", "blocks", "node", N, P)[0]
    w(f"| {P} | {N} | {s_*1e3:.1f} ms | {sum(model('strips','node',N,P))*1e3:.1f} ms | "
      f"{b_*1e3:.1f} ms | {sum(model('blocks','node',N,P))*1e3:.1f} ms |")
ax.set_yscale("log")
ax.set_xlabel("P (N grows so that every process keeps about 1024 x 1024 nodes)")
ax.set_ylabel("time per step [s]")
ax.set_title("Weak scaling (ideal: constant)")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "weak_scaling.png"), dpi=150)
plt.close(fig)
w("")

# ----------------------------------------------------------------------------- 7 crossover and a real cluster
w("## 7. When does spreading over the VMs pay off? (model, map-by node, P = 10 vs P = 1)\n")


def crossover(decomp, params):
    for k in range(9, 18 * 4):
        N = int(2 ** (k / 4))
        t1 = sum(model(decomp, "node", N, 1, params))
        t10 = sum(model(decomp, "node", N, 10, params))
        if t10 < t1:
            return N
    return None


fast = {k: (1e-6, 1 / 10e9) if k[0] != k[1] else v for k, v in link.items()}   # t_s = 1 us, 10 GB/s
fast_ts = {k: (1e-6, v[1]) if k[0] != k[1] else v for k, v in link.items()}    # t_s = 1 us, our bandwidth
w("| network | strips: P=10 faster than P=1 from N = | blocks: from N = |")
w("|---|---|---|")
for name, prm in (("our tailnet (ping-pong)", link), ("t_s = 1 us, our bandwidth", fast_ts),
                  ("real cluster: t_s = 1 us, 10 GB/s", fast)):
    w(f"| {name} | {crossover('strips', prm) or '> 2^18'} | {crossover('blocks', prm) or '> 2^18'} |")
w("\nMeasured: at N = 8192 (the largest grid run) P = 10 is still slower than P = 1 for both versions.\n")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
NN = [int(2 ** (k / 2)) for k in range(16, 37)]
for ax, (name, prm) in zip(axes, (("our tailnet", link), ("real cluster (t_s = 1 us, 10 GB/s)", fast))):
    for d in ("strips", "blocks"):
        for P, ls in ((3, ":"), (10, "-")):
            S = [sum(model(d, "node", N, 1, prm)) / sum(model(d, "node", N, P, prm)) for N in NN]
            ax.plot(NN, S, ls, color=COLORS[d], label=f"{d} P={P}")
    if prm is link:
        for d in ("strips", "blocks"):
            for P in (3, 10):
                S = [T1(N) / strong(d, "node", N, P)[0] for N in STRONG_N]
                ax.plot(STRONG_N, S, MARK["node"], color=COLORS[d], mfc="none" if P == 3 else COLORS[d])
    ax.axhline(1, color="k", lw=0.8)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("N")
    ax.set_title(f"Model speed-up, {name}")
    ax.grid(alpha=0.3, which="both")
axes[0].set_ylabel("speed-up vs 1 process (markers: measured)")
axes[0].legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "model_speedup_vs_N.png"), dpi=150)
plt.close(fig)

with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\n-> {OUT}")
