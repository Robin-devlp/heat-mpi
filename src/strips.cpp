// 1D strip decomposition (Part 2).
//
// The N-1 interior rows (j = 1 .. N-1) are split among the P ranks in contiguous strips,
// as evenly as possible: the first (N-1) mod P ranks get one extra row. Rank 0 owns the
// bottom strip, rank P-1 the top one.
//
// Local array: (nlocal + 2) rows of N+1 values.
//   local row 0           = ghost row below (copy of the lower neighbour's top row,
//                           or the plate's bottom boundary row j = 0 on rank 0)
//   local rows 1..nlocal  = owned rows, global j = j0 .. j0+nlocal-1
//   local row nlocal+1    = ghost row above (copy of the upper neighbour's bottom row,
//                           or the plate's top boundary row j = N on rank P-1)
// Columns i = 0 and i = N are Dirichlet boundary values and are never updated.
#include <mpi.h>

#include <algorithm>
#include <cstdio>
#include <utility>
#include <vector>

#include "grid.hpp"
#include "problem.hpp"
#include "solvers.hpp"
#include "stencil.hpp"

namespace {

struct StripLayout {
    int nlocal;  // owned rows
    int j0;      // global index of the first owned row
};

StripLayout strip_of(int rank, int P, int N) {
    const int rows = N - 1;
    const int base = rows / P;
    const int extra = rows % P;
    StripLayout s;
    s.nlocal = base + (rank < extra ? 1 : 0);
    s.j0 = 1 + rank * base + std::min(rank, extra);
    return s;
}

void dump_local(const Grid& g, int rank, int P, int j0, const char* label) {
    // print each rank's local array, ghost rows included, in rank order
    for (int k = 0; k < P; ++k) {
        if (k == rank) {
            std::printf("--- %s: rank %d, owned global rows %d..%d (local rows 1..%d), ghosts at local 0 and %d\n",
                        label, rank, j0, j0 + g.ny - 3, g.ny - 2, g.ny - 1);
            for (int l = g.ny - 1; l >= 0; --l) {
                const char* tag = (l == 0 || l == g.ny - 1) ? "ghost" : "own  ";
                std::printf("  %s l=%2d (j=%2d):", tag, l, j0 - 1 + l);
                for (int i = 0; i < g.nx; ++i) std::printf(" %8.5f", g(i, l));
                std::printf("\n");
            }
            std::fflush(stdout);
        }
        MPI_Barrier(MPI_COMM_WORLD);
    }
}

}  // namespace

RunResult run_strips(const Params& p) {
    int rank = 0, P = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &P);
    const int N = p.N;
    const int n = N + 1;  // values per row

    if (P > N - 1) {
        if (rank == 0) std::fprintf(stderr, "heat: strips need P <= N-1 (P=%d, N=%d)\n", P, N);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    const StripLayout s = strip_of(rank, P, N);
    const int nl = s.nlocal;
    const int up = (rank + 1 < P) ? rank + 1 : MPI_PROC_NULL;  // owns the rows above
    const int down = (rank > 0) ? rank - 1 : MPI_PROC_NULL;   // owns the rows below

    // Fill both time levels with the initial data of the global rows j0-1 .. j0+nl.
    // For rank 0 / P-1 the outer ghost row is the plate boundary row and keeps its
    // Dirichlet value, because MPI_PROC_NULL receives never overwrite it.
    Grid u_old(n, nl + 2), u_new(n, nl + 2);
    for (int l = 0; l < nl + 2; ++l) {
        const int j = s.j0 - 1 + l;
        for (int i = 0; i <= N; ++i) {
            const double v = initial_value(p.problem, i, j, N);
            u_old(i, l) = v;
            u_new(i, l) = v;
        }
    }

    const double r = p.r;
    double t_comm = 0.0, t_comp = 0.0;
    MPI_Barrier(MPI_COMM_WORLD);
    const double t_start = MPI_Wtime();
    for (long long step = 0; step < p.steps; ++step) {
        // --- halo exchange (rows are contiguous: one message of N+1 doubles, no packing)
        const double tc0 = MPI_Wtime();
        // (1) my top owned row goes up; I receive my bottom ghost row from below
        MPI_Sendrecv(u_old.row(nl), n, MPI_DOUBLE, up, 0,
                     u_old.row(0), n, MPI_DOUBLE, down, 0,
                     MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        // (2) my bottom owned row goes down; I receive my top ghost row from above
        MPI_Sendrecv(u_old.row(1), n, MPI_DOUBLE, down, 1,
                     u_old.row(nl + 1), n, MPI_DOUBLE, up, 1,
                     MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        const double tc1 = MPI_Wtime();

        // --- update the owned rows with the same stencil and operand order as serial
        const double* a = u_old.u.data();
        double* b = u_new.u.data();
        for (int l = 1; l <= nl; ++l) {
            for (int i = 1; i < N; ++i) {
                const std::size_t c = u_old.idx(i, l);
                b[c] = heat_update(a[c], a[c + 1], a[c - 1], a[c + n], a[c - n], r);
            }
        }
        std::swap(u_old.u, u_new.u);
        const double tc2 = MPI_Wtime();
        t_comm += tc1 - tc0;
        t_comp += tc2 - tc1;
    }
    const double t_loop = MPI_Wtime() - t_start;

    if (p.dump_local) dump_local(u_old, rank, P, s.j0, "after last step");

    RunResult res;
    res.nprocs = P;
    double local[3] = {t_loop, t_comp, t_comm}, maxv[3] = {0, 0, 0};
    MPI_Reduce(local, maxv, 3, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
    res.t_total = maxv[0];
    res.t_comp = maxv[1];
    res.t_comm = maxv[2];

    // --- assemble the full field on rank 0 (only when it is needed)
    if (p.need_field) {
        std::vector<int> counts, displs;
        if (rank == 0) {
            res.field.assign(static_cast<std::size_t>(n) * n, 0.0);
            counts.resize(P);
            displs.resize(P);
            for (int k = 0; k < P; ++k) {
                const StripLayout sk = strip_of(k, P, N);
                counts[k] = sk.nlocal * n;
                displs[k] = sk.j0 * n;
            }
        }
        MPI_Gatherv(u_old.row(1), nl * n, MPI_DOUBLE,
                    rank == 0 ? res.field.data() : nullptr, counts.data(), displs.data(), MPI_DOUBLE,
                    0, MPI_COMM_WORLD);
        if (rank == 0) {
            // the two boundary rows j = 0 and j = N never change
            for (int i = 0; i <= N; ++i) {
                res.field[i] = initial_value(p.problem, i, 0, N);
                res.field[static_cast<std::size_t>(N) * n + i] = initial_value(p.problem, i, N, N);
            }
        }
    }
    return res;
}
