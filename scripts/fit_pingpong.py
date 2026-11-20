#!/usr/bin/env python3
"""fit_pingpong.py - fit t_msg(m) = t_s + m * t_w to ping-pong results (Part 0 step 6).

Reads every <label>.csv in a results directory written by run_pingpong.sh and
produces, in that directory:
  - pingpong_table.md / pingpong_table.csv : t_s, t_w, bandwidth 1/t_w, link type
  - pingpong_time.png       : one-way time vs message size (log-log) + fitted model
  - pingpong_bandwidth.png  : effective bandwidth vs message size

Fit (as asked by the spec: latency from small messages, bandwidth from large):
  t_s = mean one-way time of the small messages (m <= 64 B)
  t_w = least-squares slope of one-way time vs m over the large messages (m >= 1 MiB)
Usage:  python3 scripts/fit_pingpong.py [results_dir]   (default: the LATEST run)
"""
import csv
import os
import re
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SMALL_MAX = 64
LARGE_MIN = 1 << 20

ROOT = "/home/mpi/heat-mpi"


def load(path):
    rows = []
    with open(path) as f:
        lines = [l for l in f if not l.startswith("#")]
    for r in csv.DictReader(lines):
        rows.append((int(r["bytes"]), float(r["oneway_avg_s"]), int(r["reps"])))
    rows.sort()
    m = np.array([r[0] for r in rows], dtype=float)
    t = np.array([r[1] for r in rows])
    return m, t


def link_type(d, label, ts):
    """Path used by the measurement: direct or relayed (DERP).

    The tailscale ping snapshot is taken just BEFORE the measurement, and Tailscale often
    still answers through the DERP relay at that moment and switches to a direct path a few
    seconds later. So the snapshot alone is not trusted: if every pong went through DERP but
    the measured small-message round trip (2 t_s) is far below the DERP round trip, the
    measurement itself ran on a direct path.
    """
    p = os.path.join(d, f"{label}_tailscale_ping.txt")
    if not os.path.exists(p):
        return "same VM"
    derp, direct = [], []
    for line in open(p):
        m = re.search(r"via (\S+) in ([\d.]+)ms", line)
        if m:
            (derp if m.group(1).startswith("DERP") else direct).append(float(m.group(2)) * 1e-3)
    if direct and derp:
        return "direct (DERP at start)"
    if direct:
        return "direct"
    if derp and 2 * ts < 0.6 * float(np.median(derp)):
        return "direct (measured; snapshot via DERP)"
    return "via DERP (relayed)"


def main():
    if len(sys.argv) > 1:
        d = sys.argv[1]
    else:
        d = open(os.path.join(ROOT, "results/raw/pingpong/LATEST")).read().strip()
    labels = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv") and not f.startswith("pingpong_"))

    results = []
    fig1, ax1 = plt.subplots(figsize=(7.5, 5))
    fig2, ax2 = plt.subplots(figsize=(7.5, 5))
    for label in labels:
        m, t = load(os.path.join(d, label + ".csv"))
        if len(m) == 0:
            print(f"skip {label}: no data")
            continue
        small = m <= SMALL_MAX
        large = m >= LARGE_MIN
        ts = float(np.mean(t[small]))
        tw = float(np.polyfit(m[large], t[large], 1)[0]) if large.sum() >= 2 else float("nan")
        bw = 1.0 / tw / 1e6 if tw > 0 else float("nan")
        results.append((label, link_type(d, label, ts), ts, tw, bw))

        line, = ax1.loglog(m, t, "o", ms=4, label=label)
        mm = np.logspace(np.log10(m.min()), np.log10(m.max()), 200)
        ax1.loglog(mm, ts + mm * tw, "-", color=line.get_color(), lw=1)
        ax2.semilogx(m, m / t / 1e6, "o-", ms=4, label=label)

    ax1.set_xlabel("message size m (bytes)")
    ax1.set_ylabel("one-way time (s)")
    ax1.set_title("Ping-pong: one-way time, points = measured, lines = t_s + m t_w")
    ax1.grid(True, which="both", alpha=0.3)
    ax1.legend(fontsize=8)
    fig1.tight_layout()
    fig1.savefig(os.path.join(d, "pingpong_time.png"), dpi=150)

    ax2.set_xlabel("message size m (bytes)")
    ax2.set_ylabel("effective bandwidth m / t (MB/s)")
    ax2.set_title("Ping-pong: effective bandwidth")
    ax2.grid(True, which="both", alpha=0.3)
    ax2.legend(fontsize=8)
    fig2.tight_layout()
    fig2.savefig(os.path.join(d, "pingpong_bandwidth.png"), dpi=150)

    with open(os.path.join(d, "pingpong_table.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "link", "t_s_us", "t_w_s_per_byte", "bandwidth_MBps"])
        for r in results:
            w.writerow([r[0], r[1], f"{r[2]*1e6:.2f}", f"{r[3]:.4e}", f"{r[4]:.2f}"])

    md = ["| Case | Link | Latency t_s | Bandwidth 1/t_w |", "|---|---|---|---|"]
    for r in results:
        md.append(f"| {r[0]} | {r[1]} | {r[2]*1e6:,.1f} us | {r[4]:,.2f} MB/s |")
    open(os.path.join(d, "pingpong_table.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nplots and tables written to {d}")


if __name__ == "__main__":
    main()
