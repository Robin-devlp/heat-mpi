#!/bin/bash
# run_pingpong.sh - Part 0 step 6: ping-pong for two processes on the same VM
# (each VM) and for every pair of VMs. Raw output is kept in results/raw/pingpong/<timestamp>/.
# Run as user mpi on heat-robin, after scripts/sync_and_build.sh:
#   bash scripts/run_pingpong.sh            # all cases
#   bash scripts/run_pingpong.sh same       # only same-VM cases
#   bash scripts/run_pingpong.sh cross      # only cross-VM pairs
set -uo pipefail

ROOT=/home/mpi/heat-mpi
BIN=$ROOT/build/pingpong
WHICH=${1:-all}
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=$ROOT/results/raw/pingpong/$STAMP
mkdir -p "$OUT"

# btl: self + vader (shared memory, used between processes on the same VM)
#      + tcp (between VMs, restricted to the Tailscale interface).
MPI_FLAGS=(--mca oob_tcp_if_include tailscale0
           --mca btl_tcp_if_include tailscale0
           --mca btl self,vader,tcp
           --bind-to none)

HOSTS=(heat-robin heat-elio heat-michel)
PAIRS=("heat-robin heat-elio" "heat-robin heat-michel" "heat-elio heat-michel")

{
    echo "date=$(date -Is)"
    echo "mpirun=$(mpirun --version | head -1)"
    echo "flags=${MPI_FLAGS[*]}"
} > "$OUT/info.txt"

run_case() {   # $1 = label, $2 = --host argument, $3 = host that runs tailscale ping, $4 = ping target
    local label=$1 hostarg=$2 from=${3:-} to=${4:-}
    echo "== $label ($(date +%H:%M:%S))"
    if [ -n "$from" ]; then
        ssh -n -o BatchMode=yes "$from" "tailscale ping -c 5 $to" > "$OUT/${label}_tailscale_ping.txt" 2>&1
        tail -2 "$OUT/${label}_tailscale_ping.txt"
    fi
    mpirun --host "$hostarg" -np 2 "${MPI_FLAGS[@]}" "$BIN" < /dev/null \
        > "$OUT/${label}.csv" 2> "$OUT/${label}.err"
    echo "   exit=$?  rows=$(grep -c '^[0-9]' "$OUT/${label}.csv")"
}

if [ "$WHICH" = all ] || [ "$WHICH" = same ]; then
    for h in "${HOSTS[@]}"; do
        run_case "same_${h}" "${h}:2"
    done
fi

if [ "$WHICH" = all ] || [ "$WHICH" = cross ]; then
    for p in "${PAIRS[@]}"; do
        set -- $p
        run_case "cross_${1}__${2}" "${1},${2}" "$1" "$2"
    done
fi

echo "== done. results in $OUT"
echo "$OUT" > "$ROOT/results/raw/pingpong/LATEST"
