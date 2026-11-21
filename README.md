# Parallel 2D heat diffusion with MPI over Tailscale

Solves the 2D heat equation on the unit square with the explicit 5-point scheme,
in three versions: serial, 1D strips and 2D blocks (MPI). The parallel versions give
exactly the same result as the serial one.

Team: Robin Ghassibeh (231463)
      Michel Abou Rahal (230952)
      Elio Maroun (230316)


## What you need

Ubuntu 24.04 with:

    sudo apt install build-essential cmake git openmpi-bin libopenmpi-dev python3-numpy python3-matplotlib

For the cluster: every VM in the same Tailscale network, passwordless SSH between all VMs,
and the project at the same path on every VM (we use /home/mpi/heat-mpi).


## Build

    cmake -S . -B build
    cmake --build build

This makes three programs: build/heat (the solver), build/pingpong (network test) and
build/hello_mpi (prints rank, number of processes and VM name, to test the cluster).


## Run on one VM

Serial:

    ./build/heat --case 1 --N 512 --steps 500 --decomp serial

Parallel, 4 processes on this VM:

    mpirun -np 4 --use-hwthread-cpus ./build/heat --case 1 --N 512 --steps 500 --decomp blocks

--use-hwthread-cpus lets MPI use all the VM's CPUs (without it, MPI counts only half of them on our VMs).


## Run on the cluster

1. Copy hosts.example to hosts and put your own VM names and CPU counts in it.
2. Build the program on every VM (scripts/sync_and_build.sh copies the code and builds on all 3 VMs).
3. Run:

        mpirun -np 10 --hostfile hosts --map-by node \
          --mca oob_tcp_if_include tailscale0 --mca btl_tcp_if_include tailscale0 \
          --mca btl self,vader,tcp --bind-to none \
          ./build/heat --case 2 --N 1024 --steps 500 --decomp blocks --out u.bin

The --mca options make MPI use the Tailscale network. --map-by node puts the processes on
the VMs in turn; --map-by slot fills one VM before using the next.


## Options of heat

| Option | Meaning | Default |
|---|---|---|
| --case 1, 2 or V | 1: all four edges at 1. 2: top and bottom at 1, left and right at 0. V: test problem with a known exact solution. | 1 |
| --N n | number of intervals in each direction (h = 1/N) | 64 |
| --r r | r = dt / h^2. Must be at most 0.25, otherwise the program refuses to run. | 0.25 |
| --T t | final time. dt is chosen so that T/dt is a whole number and r is not exceeded. | |
| --steps n | number of time steps (give either --T or --steps) | |
| --out file | write the final field to this file | no file |
| --decomp d | serial, strips or blocks | serial |
| --allow-unstable | run even if r > 0.25 (only for the instability experiment, Task 6.7) | off |
| --dump-local | print each process's local array with its ghost rows (debugging, small N) | off |

Serial must be run with 1 process.


## Output

The program prints one line, for example:

    decomp=blocks P=4 N=512 case=1 r=0.25 steps=500 dt=... T=... t_total=... t_comp=... t_comm=... grid=2x2

t_total is the time of the time-stepping loop, t_comp the computing part and t_comm the
halo exchange part (maximum over the processes). For case V it also prints the errors
err_inf and err_l2.

The --out file holds the full (N+1) x (N+1) grid as raw little-endian doubles, row by row
(row j is the line y = j h), no header. To draw it:

    python3 scripts/plot_field.py u.bin 1024


## Scripts

| Script | What it does |
|---|---|
| sync_and_build.sh | copy the code to the other VMs and build on all of them |
| run_pingpong.sh, fit_pingpong.py | network test (latency and bandwidth of every pair of VMs) and its table and plots |
| run_convergence.sh, plot_convergence.py | convergence study on case V (Task 7.2) |
| run_unstable.sh, plot_unstable.py | run with r 5% above the limit (Task 6.7) |
| run_compare.sh | check that strips and blocks give the same file as serial, for many P and N |
| run_heatmaps.sh, plot_heatmaps.py, plot_field.py | heat maps of cases 1 and 2 |
| run_baseline.sh | serial speed of each VM (Part 4) |
| run_perf.sh | strong and weak scaling runs on the cluster (Part 4) |
| analyze_perf.py | performance model, plots and tables for Part 4 |
| math_tasks.py | computed results of the background-notes Tasks 3.2(c), 3.5, 4.1 and 6.7 |
| demo.sh, demo.ps1 | live demo: run case 1 or 2 on the 3 VMs, check it against serial, show the heat map |

The shell scripts run on heat-robin as user mpi and use the path /home/mpi/heat-mpi and our
VM names. Change these at the top of a script to use it elsewhere.


## Demo

From PowerShell on Robin's laptop, in the project folder:

    .\scripts\demo.ps1 1                     # case 1, N=64, 3 processes (one per VM), t = 0.02
    .\scripts\demo.ps1 2 64 6 0.02 strips    # case 2, N=64, 6 processes, strips

The arguments are: case, N, P, final time, strips or blocks. The script shows how many
processes run on each VM, runs the case, checks that the result is identical to the serial
version, and opens the heat map. With the defaults it takes about 30 seconds.


## Results

All raw outputs, tables and plots are in results/:

- raw/hello: hello world on the 3 VMs
- raw/pingpong: network measurements
- convergence: convergence study
- unstable: instability experiment
- compare: serial vs parallel checks
- heatmaps: heat maps
- demo: pictures from the demo runs
- perf: baseline, scaling runs and the analysis (perf/run_20261119/analysis)
- math_tasks: tables and plots of the background-notes Tasks
