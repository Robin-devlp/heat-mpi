#!/bin/bash
# demo.sh - live demo: run case 1 or 2 across the 3 VMs, check that the result is the same
# as the serial one, and draw the heat map.
#
# Usage (as mpi on heat-robin):  bash scripts/demo.sh CASE [N] [P] [T] [DECOMP]
#   CASE    1 or 2
#   N       grid intervals          (default 64)
#   P       number of processes     (default 3 = one per VM, at most 10)
#   T       final time              (default 0.02)
#   DECOMP  strips or blocks        (default blocks)
set -euo pipefail
ROOT=/home/mpi/heat-mpi
BIN=$ROOT/build/heat
C=${1:?usage: demo.sh CASE [N] [P] [T] [DECOMP]}
N=${2:-64}
P=${3:-3}
T=${4:-0.02}
D=${5:-blocks}
OUT=$ROOT/results/demo
mkdir -p "$OUT"
printf "heat-robin slots=4\nheat-elio slots=2\nheat-michel slots=4\n" > "$OUT/hosts"

MPI=(mpirun -np "$P" --hostfile "$OUT/hosts" --map-by node
     --mca oob_tcp_if_include tailscale0 --mca btl_tcp_if_include tailscale0
     --mca btl self,vader,tcp --bind-to none)
NAME=case${C}_N${N}_P${P}_${D}

echo "== Processes per VM"
"${MPI[@]}" hostname < /dev/null | sort | uniq -c

echo "== Running case $C, N=$N, P=$P, T=$T, $D"
"${MPI[@]}" "$BIN" --case "$C" --N "$N" --T "$T" --decomp "$D" --out "$OUT/$NAME.bin" < /dev/null

echo "== Same result as the serial version?"
"$BIN" --case "$C" --N "$N" --T "$T" --decomp serial --out "$OUT/serial.bin" > /dev/null
if cmp -s "$OUT/serial.bin" "$OUT/$NAME.bin"; then echo "yes, identical"; else echo "NO, different"; fi
rm -f "$OUT/serial.bin"

echo "== Heat map"
python3 "$ROOT/scripts/plot_field.py" "$OUT/$NAME.bin" "$N" "$OUT/$NAME.png" \
    "case $C, N = $N, P = $P ($D), t = $T"
