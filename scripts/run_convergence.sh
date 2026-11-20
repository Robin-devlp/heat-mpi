#!/bin/bash
# run_convergence.sh - convergence study, background notes Task 7.2 / project Part 1.
# Test V to T = 0.05 for N = 16, 32, 64, 128, 256 with r kept fixed.
# r = 0.2 is used because then T/dt = 0.05 N^2 / 0.2 = N^2/4 is an exact integer for
# every N above, so r is identical on all grids (and below the limit 1/4).
# Output: results/convergence/<timestamp>/runs.txt (+ table and plot via plot_convergence.py)
set -euo pipefail
ROOT=/home/mpi/heat-mpi
BIN=$ROOT/build/heat
OUT=$ROOT/results/convergence/$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"
for N in 16 32 64 128 256; do
    "$BIN" --case V --N "$N" --r 0.2 --T 0.05 --decomp serial | tee -a "$OUT/runs.txt"
done
python3 "$ROOT/scripts/plot_convergence.py" "$OUT"
