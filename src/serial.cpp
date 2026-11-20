// Serial reference solver (Part 1). Every parallel result is checked against it.
#include <mpi.h>

#include <utility>

#include "grid.hpp"
#include "problem.hpp"
#include "solvers.hpp"
#include "stencil.hpp"

RunResult run_serial(const Params& p) {
    const int N = p.N;
    const int n = N + 1;  // nodes per direction, boundary included

    // Two time levels. Boundary values are written into BOTH arrays once and never
    // updated (Dirichlet), so after any number of swaps the boundary is still correct.
    Grid u_old(n, n), u_new(n, n);
    for (int j = 0; j <= N; ++j)
        for (int i = 0; i <= N; ++i) {
            const double v = initial_value(p.problem, i, j, N);
            u_old(i, j) = v;
            u_new(i, j) = v;
        }

    const double r = p.r;
    const double t0 = MPI_Wtime();
    for (long long step = 0; step < p.steps; ++step) {
        const double* a = u_old.u.data();
        double* b = u_new.u.data();
        for (int j = 1; j < N; ++j) {
            for (int i = 1; i < N; ++i) {
                const std::size_t c = u_old.idx(i, j);
                b[c] = heat_update(a[c], a[c + 1], a[c - 1], a[c + n], a[c - n], r);
            }
        }
        std::swap(u_old.u, u_new.u);  // swaps the two buffers (pointers), no copy
    }
    const double t1 = MPI_Wtime();

    RunResult res;
    res.field = std::move(u_old.u);  // level n = steps
    res.t_total = t1 - t0;
    res.t_comp = res.t_total;
    res.t_comm = 0.0;
    res.nprocs = 1;
    return res;
}
