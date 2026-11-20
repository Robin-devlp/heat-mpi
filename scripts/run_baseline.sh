#!/bin/bash
# run_baseline.sh - Part 4, experiment 1: single-node baseline.
# Serial run time per step and per grid node on each VM, N = 512 ... 8192, 3 repetitions.
# Each VM is measured on its own (the serial program runs locally on that VM via ssh).
#
# Usage (as mpi on heat-robin):  bash scripts/run_baseline.sh [hosts] [steps]
#   hosts defaults to "heat-robin heat-elio heat-michel", steps to 500
set -uo pipefail
ROOT=/home/mpi/heat-mpi
BIN=$ROOT/build/heat
HOSTS=${1:-"heat-robin heat-elio heat-michel"}
STEPS=${2:-500}
NLIST="512 1024 2048 4096 8192"
REPS=3
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=$ROOT/results/perf/baseline_$STAMP
mkdir -p "$OUT"
CSV=$OUT/baseline.csv
echo "host,N,steps,rep,t_total,t_per_step,t_per_node" > "$CSV"
echo "# baseline date=$(date -Is) steps=$STEPS hosts=$HOSTS" | tee "$OUT/raw.txt"

for rep in $(seq 1 $REPS); do          # repetition loop outermost: drifts spread over all N
  for h in $HOSTS; do
    for N in $NLIST; do
      if [ "$h" = "$(hostname)" ]; then
        line=$("$BIN" --case 1 --N $N --r 0.25 --steps $STEPS --decomp serial < /dev/null)
      else
        line=$(ssh -n -o ConnectTimeout=10 "$h" "$BIN --case 1 --N $N --r 0.25 --steps $STEPS --decomp serial")
      fi
      echo "host=$h rep=$rep $line" | tee -a "$OUT/raw.txt"
      t=$(echo "$line" | grep -o 't_total=[0-9.e+-]*' | cut -d= -f2)
      [ -z "$t" ] && { echo "  (run failed)"; continue; }
      python3 -c "t=$t; s=$STEPS; n=($N-1)**2; print(f'$h,$N,$STEPS,$rep,{t:.6f},{t/s:.6e},{t/s/n:.6e}')" >> "$CSV"
    done
  done
done
echo "$STAMP" > "$ROOT/results/perf/LATEST_baseline"
echo "done -> $CSV"
