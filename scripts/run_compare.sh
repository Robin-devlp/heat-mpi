#!/bin/bash
# run_compare.sh - correctness evidence: the field files written by the parallel versions
# must be bit-for-bit identical to the serial one (checked with cmp).
#
# Usage (as mpi on heat-robin):
#   bash scripts/run_compare.sh local  [decomps]   # all processes on this VM
#   bash scripts/run_compare.sh cluster [decomps]  # processes spread over the 3 VMs (--map-by node)
#   decomps defaults to "strips" (later: "strips blocks")
set -uo pipefail
ROOT=/home/mpi/heat-mpi
BIN=$ROOT/build/heat
MODE=${1:-local}
DECOMPS=${2:-strips}
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=$ROOT/results/compare/${MODE}_$STAMP
TMP=$ROOT/results/compare/tmp_$STAMP      # field files (same path on every VM; written by rank 0 only)
mkdir -p "$OUT" "$TMP"

MPI_FLAGS=(--mca oob_tcp_if_include tailscale0 --mca btl_tcp_if_include tailscale0
           --mca btl self,vader,tcp --bind-to none)
if [ "$MODE" = cluster ]; then
    HOSTFILE=$ROOT/hosts
    printf "heat-robin slots=4\nheat-elio slots=2\nheat-michel slots=4\n" > "$HOSTFILE"
    PLIST="1 2 3 4 5 6 8 10"
    PLACE=(--hostfile "$HOSTFILE" --map-by node)
else
    PLIST="1 2 3 4"
    PLACE=(--host "$(hostname):4")
fi

# N values chosen so that N-1 is and is not divisible by the P values above.
# Across VMs every exchange costs 20-150 ms, so the cluster test uses fewer N and steps.
if [ "$MODE" = cluster ]; then
    NLIST="9 31 100"
    STEPS=20
else
    NLIST="8 9 16 31 64 100"
    STEPS=50
fi
LOG=$OUT/compare.txt
pass=0; fail=0
{
    echo "# mode=$MODE decomps=$DECOMPS steps=$STEPS r=0.25 date=$(date -Is)"
    echo "# $(mpirun --version | head -1)"
} | tee "$LOG"

for c in 1 2 V; do
  for N in $NLIST; do
    ref=$TMP/serial_c${c}_N${N}.bin
    "$BIN" --case $c --N $N --r 0.25 --steps $STEPS --decomp serial --out "$ref" > /dev/null
    for d in $DECOMPS; do
      for P in $PLIST; do
        [ "$P" -gt $((N-1)) ] && continue
        f=$TMP/${d}_c${c}_N${N}_P${P}.bin
        line=$(mpirun -np $P "${PLACE[@]}" "${MPI_FLAGS[@]}" "$BIN" --case $c --N $N --r 0.25 \
               --steps $STEPS --decomp $d --out "$f" < /dev/null 2>"$OUT/last.err" | grep '^decomp=')
        if cmp -s "$ref" "$f"; then res=IDENTICAL; pass=$((pass+1)); else res=DIFFERENT; fail=$((fail+1)); fi
        printf "case=%s N=%-4s decomp=%-6s P=%-3s %s\n" "$c" "$N" "$d" "$P" "$res" | tee -a "$LOG"
        [ "$res" = DIFFERENT ] && echo "   $line" | tee -a "$LOG"
        rm -f "$f"
      done
    done
    rm -f "$ref"
  done
done
rmdir "$TMP" 2>/dev/null
echo "SUMMARY: $pass identical, $fail different" | tee -a "$LOG"
