#!/bin/bash
# sync_and_build.sh - copy the project source from this VM to the other VMs
# (same path everywhere) and build it on every VM.
# Run as user mpi on the VM holding the main copy (heat-robin):
#   bash scripts/sync_and_build.sh
set -euo pipefail

ROOT=/home/mpi/heat-mpi
HOSTS=(heat-robin heat-elio heat-michel)
SELF=$(hostname)

cd "$ROOT"
for h in "${HOSTS[@]}"; do
    if [ "$h" != "$SELF" ]; then
        echo "== sync -> $h"
        ssh -n -o BatchMode=yes "$h" "mkdir -p $ROOT"
        rsync -a --delete --exclude build/ --exclude results/ --exclude llm_log/ \
              "$ROOT/" "$h:$ROOT/"
    fi
done

for h in "${HOSTS[@]}"; do
    echo "== build on $h"
    ssh -n -o BatchMode=yes "$h" \
        "cd $ROOT && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release > /dev/null && cmake --build build -j > build/build.log 2>&1 && echo ok || { tail -20 build/build.log; exit 1; }"
done
