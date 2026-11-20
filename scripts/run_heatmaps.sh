#!/bin/bash
# run_heatmaps.sh - fields of Case 1 and Case 2 at several times, for the report and the demo.
# Runs on this VM only (blocks, 4 processes), then plots everything with plot_heatmaps.py.
#
# Usage (as mpi on heat-robin):  bash scripts/run_heatmaps.sh [N]
set -euo pipefail
ROOT=/home/mpi/heat-mpi
BIN=$ROOT/build/heat
N=${1:-128}
TLIST="0.005 0.02 0.05 0.2"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=$ROOT/results/heatmaps/$STAMP
mkdir -p "$OUT"

MPI=(mpirun -np 4 --host "$(hostname):4" --bind-to none --mca btl self,vader)
LOG=$OUT/runs.txt
echo "# N=$N r=0.25 decomp=blocks P=4 date=$(date -Is)" | tee "$LOG"
for c in 1 2; do
  for T in $TLIST; do
    "${MPI[@]}" "$BIN" --case $c --N $N --r 0.25 --T $T --decomp blocks \
        --out "$OUT/case${c}_T${T}.bin" < /dev/null | grep '^decomp=' | tee -a "$LOG"
  done
done
python3 "$ROOT/scripts/plot_heatmaps.py" "$OUT" "$N" "$TLIST" | tee -a "$LOG"
echo "$STAMP" > "$ROOT/results/heatmaps/LATEST"
