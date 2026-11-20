#!/bin/bash
# run_unstable.sh - Task 6.7: run with a time step 5% above the stability bound
# (r = 1.05 * 1/4 = 0.2625) and look at the solution after several step counts.
# Also runs the same steps with the stable r = 0.25 for comparison.
set -euo pipefail
ROOT=/home/mpi/heat-mpi
BIN=$ROOT/build/heat
OUT=$ROOT/results/unstable/$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"
N=64
for S in 20 60 120 200; do
    "$BIN" --case 1 --N $N --r 0.2625 --steps $S --allow-unstable --out "$OUT/unstable_s$S.bin" | tee -a "$OUT/runs.txt"
done
"$BIN" --case 1 --N $N --r 0.25 --steps 200 --out "$OUT/stable_s200.bin" | tee -a "$OUT/runs.txt"
echo "--- refusing check (must fail without --allow-unstable):"
"$BIN" --case 1 --N $N --r 0.2625 --steps 10 2>&1 | head -3 | tee -a "$OUT/runs.txt" || true
python3 "$ROOT/scripts/plot_unstable.py" "$OUT" $N
