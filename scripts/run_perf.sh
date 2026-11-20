#!/bin/bash
# run_perf.sh - Part 4, experiments 2-4: strong scaling, weak scaling, communication share.
#
#   strong: N = 512, 2048, 8192; strips and blocks; P = 1 .. all slots;
#           placement --map-by node (round-robin over VMs) and --map-by slot (fill each VM first)
#   weak:   about 1024 x 1024 interior nodes per process, N = 1 + round(1024*sqrt(P)); --map-by node
#   every run is repeated REPS times; the repetition loop is outermost, so that if the batch is
#   interrupted every configuration still has at least the first repetitions, and slow drifts of
#   the network are spread over all configurations instead of hitting one of them.
#   t_comm / t_total of each run gives the communication share (experiment 4).
#
# Results are appended to perf.csv as soon as each run finishes. Running the script again with
# the same output folder skips the runs already done (resume after an interruption).
#
# Usage (as mpi on heat-robin):
#   bash scripts/run_perf.sh                 # full batch, new folder results/perf/run_<stamp>
#   bash scripts/run_perf.sh <folder>        # resume that folder
#   QUICK=1 bash scripts/run_perf.sh         # quick test of the script on this VM only
set -uo pipefail
ROOT=/home/mpi/heat-mpi
BIN=$ROOT/build/heat
STEPS=${STEPS:-200}
REPS=${REPS:-3}

if [ "${QUICK:-0}" = 1 ]; then
    HOSTS="$(hostname)"; HOSTLINE="$(hostname) slots=4"; PMAX=4
    STRONG_N="64 128"; WEAK_BASE=64; STEPS=20; REPS=1
else
    HOSTS="heat-robin heat-elio heat-michel"
    HOSTLINE="heat-robin slots=4
heat-elio slots=2
heat-michel slots=4"
    PMAX=10
    STRONG_N="512 2048 8192"; WEAK_BASE=1024
fi

if [ $# -ge 1 ]; then OUT=$1; else OUT=$ROOT/results/perf/run_$(date +%Y%m%d-%H%M%S); fi
mkdir -p "$OUT"
HOSTFILE=$OUT/hosts
printf "%s\n" "$HOSTLINE" > "$HOSTFILE"
CSV=$OUT/perf.csv
RAW=$OUT/raw.txt
NET=$OUT/network.txt
[ -f "$CSV" ] || echo "exp,decomp,map,N,P,steps,rep,t_total,t_comp,t_comm,comm_share,grid,status" > "$CSV"
echo "# start $(date -Is) steps=$STEPS reps=$REPS hosts=$HOSTS $(mpirun --version | head -1)" >> "$RAW"

MPI_FLAGS=(--mca oob_tcp_if_include tailscale0 --mca btl_tcp_if_include tailscale0
           --mca btl self,vader,tcp --bind-to none)

done_already() {   # $1 = key "exp,decomp,map,N,P,steps,rep"
    grep -q "^$1,.*,ok$" "$CSV"
}

net_snapshot() {   # direct or relayed (DERP) path between the VMs, as seen from this VM
    { echo "== $(date -Is) $1"; tailscale status; for h in $HOSTS; do
        [ "$h" = "$(hostname)" ] || timeout 15 tailscale ping -c 1 "$h"; done; } >> "$NET" 2>&1
}

one_run() {        # $1 exp  $2 decomp  $3 map  $4 N  $5 P  $6 rep
    local key="$1,$2,$3,$4,$5,$STEPS,$6"
    done_already "$key" && return
    local status=ok line
    mpirun -np "$5" --hostfile "$HOSTFILE" --map-by "$3" "${MPI_FLAGS[@]}" \
           "$BIN" --case 1 --N "$4" --r 0.25 --steps "$STEPS" --decomp "$2" \
           < /dev/null > "$OUT/last.out" 2>>"$OUT/errors.txt"
    line=$(grep '^decomp=' "$OUT/last.out")
    [ -z "$line" ] && status=failed
    echo "$(date +%H:%M:%S) $key $status $line" | tee -a "$RAW"
    local tt tc tm g share
    tt=$(echo "$line" | grep -o 't_total=[0-9.e+-]*' | cut -d= -f2)
    tc=$(echo "$line" | grep -o 't_comp=[0-9.e+-]*' | cut -d= -f2)
    tm=$(echo "$line" | grep -o 't_comm=[0-9.e+-]*' | cut -d= -f2)
    g=$(echo "$line" | grep -o 'grid=[0-9x]*' | cut -d= -f2)
    share=""
    [ -n "$tt" ] && share=$(python3 -c "print(f'{$tm/$tt:.4f}' if $tt > 0 else '')")
    echo "$key,$tt,$tc,$tm,$share,$g,$status" >> "$CSV"
}

for rep in $(seq 1 $REPS); do
    net_snapshot "rep $rep"
    # strong scaling
    for N in $STRONG_N; do
        for d in strips blocks; do
            for map in node slot; do
                for P in $(seq 1 $PMAX); do
                    [ "$P" = 1 ] && [ "$map" = slot ] && continue   # P=1 is the same run for both
                    one_run strong $d $map $N $P $rep
                done
            done
        done
    done
    # weak scaling
    for d in strips blocks; do
        for P in $(seq 1 $PMAX); do
            N=$(python3 -c "import math; print(1 + round($WEAK_BASE*math.sqrt($P)))")
            one_run weak $d node $N $P $rep
        done
    done
done
net_snapshot "end"
echo "# end $(date -Is)" >> "$RAW"
echo "$(basename "$OUT")" > "$ROOT/results/perf/LATEST_run"
echo "done -> $CSV  ($(grep -c ',ok$' "$CSV") ok, $(grep -vc ',ok$' "$CSV") other incl. header)"
