// 2D block decomposition (Part 3).
//
// The P processes form a Py x Px Cartesian grid (MPI_Dims_create + MPI_Cart_create,
// non-periodic). Rows of interior nodes (j = 1..N-1) are split among the Py process rows
// and columns (i = 1..N-1) among the Px process columns, as evenly as possible (the first
// remainder ranks get one extra), exactly as in the strip version.
//
// Local array: (nly + 2) rows x (nlx + 2) columns, one ghost layer on each side.
//   local (li, lj)  <->  global (i0 - 1 + li, j0 - 1 + lj)
// Ghost layers on the outside of the plate hold the Dirichlet boundary values; their
// neighbour is MPI_PROC_NULL (from MPI_Cart_shift), so they are never overwritten.
// Rows are contiguous and sent directly; columns are sent with an MPI_Type_vector.
// Corner ghost values are not exchanged: the 5-point stencil never reads them.
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

// split 'count' items among 'parts' as evenly as possible; first (count % parts) get one extra
void split(int count, int parts, int k, int& n, int& first) {
    const int base = count / parts, extra = count % parts;
    n = base + (k < extra ? 1 : 0);
    first = k * base + std::min(k, extra);
}

struct BlockLayout {
    int nlx, nly;  // owned columns / rows
    int i0, j0;    // global index of the first owned column / row
};

BlockLayout block_of(int cx, int cy, int Px, int Py, int N) {
    BlockLayout b;
    split(N - 1, Px, cx, b.nlx, b.i0);
    split(N - 1, Py, cy, b.nly, b.j0);
    b.i0 += 1;  // interior starts at index 1
    b.j0 += 1;
    return b;
}

}  // namespace

RunResult run_blocks(const Params& p) {
    int world_rank = 0, P = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &world_rank);
    MPI_Comm_size(MPI_COMM_WORLD, &P);
    const int N = p.N;

    // --- process grid: dims[0] = process rows (y direction), dims[1] = process columns (x)
    int dims[2] = {0, 0};
    MPI_Dims_create(P, 2, dims);
    const int Py = dims[0], Px = dims[1];
    if (Px > N - 1 || Py > N - 1) {
        if (world_rank == 0)
            std::fprintf(stderr, "heat: process grid %dx%d too large for N=%d\n", Py, Px, N);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    int periods[2] = {0, 0};
    MPI_Comm cart;
    MPI_Cart_create(MPI_COMM_WORLD, 2, dims, periods, /*reorder=*/0, &cart);
    int rank = 0, coords[2] = {0, 0};
    MPI_Comm_rank(cart, &rank);
    MPI_Cart_coords(cart, rank, 2, coords);
    const int cy = coords[0], cx = coords[1];
    int down, up, left, right;
    MPI_Cart_shift(cart, 0, 1, &down, &up);     // y direction: down = row below, up = row above
    MPI_Cart_shift(cart, 1, 1, &left, &right);  // x direction

    const BlockLayout b = block_of(cx, cy, Px, Py, N);
    const int nlx = b.nlx, nly = b.nly;
    const int W = nlx + 2;  // local row length

    // --- both time levels hold the initial data of all local nodes, ghosts included
    Grid u_old(W, nly + 2), u_new(W, nly + 2);
    for (int lj = 0; lj < nly + 2; ++lj)
        for (int li = 0; li < W; ++li) {
            const double v = initial_value(p.problem, b.i0 - 1 + li, b.j0 - 1 + lj, N);
            u_old(li, lj) = v;
            u_new(li, lj) = v;
        }

    // one column of owned nodes: nly values, one per row, stride = local row length
    MPI_Datatype column;
    MPI_Type_vector(nly, 1, W, MPI_DOUBLE, &column);
    MPI_Type_commit(&column);

    const double r = p.r;
    double t_comm = 0.0, t_comp = 0.0;
    MPI_Barrier(cart);
    const double t_start = MPI_Wtime();
    for (long long step = 0; step < p.steps; ++step) {
        const double tc0 = MPI_Wtime();
        double* a = u_old.u.data();
        // rows (contiguous, owned part only: columns 1..nlx)
        MPI_Sendrecv(a + u_old.idx(1, nly), nlx, MPI_DOUBLE, up, 0,
                     a + u_old.idx(1, 0), nlx, MPI_DOUBLE, down, 0, cart, MPI_STATUS_IGNORE);
        MPI_Sendrecv(a + u_old.idx(1, 1), nlx, MPI_DOUBLE, down, 1,
                     a + u_old.idx(1, nly + 1), nlx, MPI_DOUBLE, up, 1, cart, MPI_STATUS_IGNORE);
        // columns (strided, derived datatype, owned part only: rows 1..nly)
        MPI_Sendrecv(a + u_old.idx(nlx, 1), 1, column, right, 2,
                     a + u_old.idx(0, 1), 1, column, left, 2, cart, MPI_STATUS_IGNORE);
        MPI_Sendrecv(a + u_old.idx(1, 1), 1, column, left, 3,
                     a + u_old.idx(nlx + 1, 1), 1, column, right, 3, cart, MPI_STATUS_IGNORE);
        const double tc1 = MPI_Wtime();

        double* bnew = u_new.u.data();
        for (int lj = 1; lj <= nly; ++lj) {
            for (int li = 1; li <= nlx; ++li) {
                const std::size_t c = u_old.idx(li, lj);
                bnew[c] = heat_update(a[c], a[c + 1], a[c - 1], a[c + W], a[c - W], r);
            }
        }
        std::swap(u_old.u, u_new.u);
        const double tc2 = MPI_Wtime();
        t_comm += tc1 - tc0;
        t_comp += tc2 - tc1;
    }
    const double t_loop = MPI_Wtime() - t_start;

    RunResult res;
    res.nprocs = P;
    double local[3] = {t_loop, t_comp, t_comm}, maxv[3] = {0, 0, 0};
    MPI_Reduce(local, maxv, 3, MPI_DOUBLE, MPI_MAX, 0, cart);
    res.t_total = maxv[0];
    res.t_comp = maxv[1];
    res.t_comm = maxv[2];

    // --- assemble the full field on rank 0: pack owned block, gather, unpack
    if (p.need_field) {
        std::vector<double> mine(static_cast<std::size_t>(nlx) * nly);
        for (int lj = 1; lj <= nly; ++lj)
            for (int li = 1; li <= nlx; ++li)
                mine[static_cast<std::size_t>(lj - 1) * nlx + (li - 1)] = u_old(li, lj);

        std::vector<int> counts, displs;
        std::vector<double> all;
        if (rank == 0) {
            counts.resize(P);
            displs.resize(P);
            int off = 0;
            for (int k = 0; k < P; ++k) {
                int ck[2];
                MPI_Cart_coords(cart, k, 2, ck);
                const BlockLayout bk = block_of(ck[1], ck[0], Px, Py, N);
                counts[k] = bk.nlx * bk.nly;
                displs[k] = off;
                off += counts[k];
            }
            all.resize(off);
        }
        MPI_Gatherv(mine.data(), static_cast<int>(mine.size()), MPI_DOUBLE,
                    rank == 0 ? all.data() : nullptr, counts.data(), displs.data(), MPI_DOUBLE, 0, cart);

        if (rank == 0) {
            const int n = N + 1;
            res.field.assign(static_cast<std::size_t>(n) * n, 0.0);
            // boundary nodes never change
            for (int j = 0; j <= N; ++j)
                for (int i = 0; i <= N; ++i)
                    if (is_boundary(i, j, N))
                        res.field[static_cast<std::size_t>(j) * n + i] = initial_value(p.problem, i, j, N);
            for (int k = 0; k < P; ++k) {
                int ck[2];
                MPI_Cart_coords(cart, k, 2, ck);
                const BlockLayout bk = block_of(ck[1], ck[0], Px, Py, N);
                const double* src = all.data() + displs[k];
                for (int lj = 0; lj < bk.nly; ++lj)
                    for (int li = 0; li < bk.nlx; ++li)
                        res.field[static_cast<std::size_t>(bk.j0 + lj) * n + (bk.i0 + li)] =
                            src[static_cast<std::size_t>(lj) * bk.nlx + li];
            }
        }
    }

    if (rank == 0) res.grid_desc = std::to_string(Py) + "x" + std::to_string(Px);
    MPI_Type_free(&column);
    MPI_Comm_free(&cart);
    return res;
}
