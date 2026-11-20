// heat - explicit finite-difference solver of the 2D heat equation u_t = u_xx + u_yy
// on [0,1]^2 with Dirichlet boundaries, serial or parallel (MPI).
#include <mpi.h>

#include <cmath>
#include <cstdio>

#include "io.hpp"
#include "params.hpp"
#include "problem.hpp"
#include "solvers.hpp"

namespace {

// Error norms of Case V against the exact solution at t_final (notes, Definition 7.1):
// e_inf = max |e_ij|,  e_2h = sqrt(dx*dy * sum e_ij^2).
void error_norms(const std::vector<double>& u, const Params& p, double& e_inf, double& e_2h) {
    const int N = p.N;
    e_inf = 0.0;
    double sum = 0.0;
    for (int j = 0; j <= N; ++j)
        for (int i = 0; i <= N; ++i) {
            const double e = u[static_cast<std::size_t>(j) * (N + 1) + i] -
                             exact_solution(i, j, N, p.t_final);
            e_inf = std::fmax(e_inf, std::fabs(e));
            sum += e * e;
        }
    e_2h = std::sqrt(p.h * p.h * sum);
}

}  // namespace

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank = 0, size = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    Params p;
    if (!parse_params(argc, argv, p, rank)) {
        MPI_Finalize();
        return 1;
    }

    RunResult res;
    switch (p.decomp) {
        case Decomp::Serial:
            if (size != 1) {
                if (rank == 0) std::fprintf(stderr, "heat: --decomp serial must run with 1 process\n");
                MPI_Finalize();
                return 1;
            }
            res = run_serial(p);
            break;
        case Decomp::Strips:
            res = run_strips(p);
            break;
        case Decomp::Blocks:
            res = run_blocks(p);
            break;
    }

    int status = 0;
    if (rank == 0) {
        if (!p.out.empty() && !write_field(p.out, res.field)) status = 1;

        std::printf("decomp=%s P=%d N=%d case=%s r=%.6g steps=%lld dt=%.6e T=%.6g "
                    "t_total=%.6f t_comp=%.6f t_comm=%.6f",
                    decomp_name(p.decomp), res.nprocs, p.N, case_name(p.problem), p.r,
                    p.steps, p.dt, p.t_final, res.t_total, res.t_comp, res.t_comm);
        if (!res.grid_desc.empty()) std::printf(" grid=%s", res.grid_desc.c_str());
        if (p.problem == Case::Verification) {
            double e_inf = 0.0, e_2h = 0.0;
            error_norms(res.field, p, e_inf, e_2h);
            std::printf(" err_inf=%.6e err_l2=%.6e", e_inf, e_2h);
        }
        std::printf("\n");
    }

    MPI_Finalize();
    return status;
}
