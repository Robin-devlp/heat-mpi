#include "params.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace {

void usage() {
    std::fprintf(stderr,
        "usage: heat --case 1|2|V --N <intervals> [--r <alpha*dt/h^2>]\n"
        "            (--T <final time> | --steps <n>) [--out <file>]\n"
        "            [--decomp serial|strips|blocks] [--allow-unstable]\n"
        "  --case 1        four hot edges (u=1), cold interior\n"
        "  --case 2        hot top and bottom (u=1, corners included), cold left/right (u=0)\n"
        "  --case V        verification: u0 = sin(pi x) sin(pi y), u=0 on the edges\n"
        "  --r             default 0.25; must satisfy r <= 1/4 (stability, Task 6.3)\n"
        "  --T             dt is chosen so that T/dt is an integer and r is not exceeded\n"
        "  --out           raw little-endian doubles, (N+1)x(N+1), row-major, no header\n"
        "  --allow-unstable  run even if r > 1/4 (only for the Task 6.7 experiment)\n"
        "  --dump-local    print every rank's local array incl. ghost rows (debug, small N)\n");
}

}  // namespace

const char* case_name(Case c) {
    switch (c) {
        case Case::Hot4: return "1";
        case Case::HotTopBottom: return "2";
        case Case::Verification: return "V";
    }
    return "?";
}

const char* decomp_name(Decomp d) {
    switch (d) {
        case Decomp::Serial: return "serial";
        case Decomp::Strips: return "strips";
        case Decomp::Blocks: return "blocks";
    }
    return "?";
}

bool parse_params(int argc, char** argv, Params& p, int rank) {
    const bool talk = (rank == 0);
    auto fail = [&](const char* msg, const char* arg = "") {
        if (talk) {
            std::fprintf(stderr, "heat: %s%s\n", msg, arg);
            usage();
        }
        return false;
    };

    for (int i = 1; i < argc; ++i) {
        const char* a = argv[i];
        auto val = [&]() -> const char* { return (i + 1 < argc) ? argv[++i] : nullptr; };
        if (!std::strcmp(a, "--case")) {
            const char* v = val();
            if (!v) return fail("missing value for --case");
            if (!std::strcmp(v, "1")) p.problem = Case::Hot4;
            else if (!std::strcmp(v, "2")) p.problem = Case::HotTopBottom;
            else if (!std::strcmp(v, "V") || !std::strcmp(v, "v")) p.problem = Case::Verification;
            else return fail("unknown case ", v);
        } else if (!std::strcmp(a, "--N")) {
            const char* v = val();
            if (!v) return fail("missing value for --N");
            p.N = std::atoi(v);
        } else if (!std::strcmp(a, "--r")) {
            const char* v = val();
            if (!v) return fail("missing value for --r");
            p.r_requested = std::atof(v);
        } else if (!std::strcmp(a, "--T")) {
            const char* v = val();
            if (!v) return fail("missing value for --T");
            p.T = std::atof(v);
        } else if (!std::strcmp(a, "--steps")) {
            const char* v = val();
            if (!v) return fail("missing value for --steps");
            p.steps = std::atoll(v);
        } else if (!std::strcmp(a, "--out")) {
            const char* v = val();
            if (!v) return fail("missing value for --out");
            p.out = v;
        } else if (!std::strcmp(a, "--decomp")) {
            const char* v = val();
            if (!v) return fail("missing value for --decomp");
            if (!std::strcmp(v, "serial")) p.decomp = Decomp::Serial;
            else if (!std::strcmp(v, "strips")) p.decomp = Decomp::Strips;
            else if (!std::strcmp(v, "blocks")) p.decomp = Decomp::Blocks;
            else return fail("unknown decomposition ", v);
        } else if (!std::strcmp(a, "--allow-unstable")) {
            p.allow_unstable = true;
        } else if (!std::strcmp(a, "--dump-local")) {
            p.dump_local = true;
        } else if (!std::strcmp(a, "--help") || !std::strcmp(a, "-h")) {
            if (talk) usage();
            return false;
        } else {
            return fail("unknown option ", a);
        }
    }

    if (p.N < 2) return fail("--N must be at least 2");
    if (!(p.r_requested > 0.0)) return fail("--r must be positive");
    if ((p.T > 0.0) == (p.steps > 0)) return fail("give exactly one of --T or --steps (positive)");

    // Stability (Task 6.3): G(theta,phi) = 1 - 4r(sin^2(theta/2) + sin^2(phi/2)); the worst
    // (checkerboard) mode theta = phi = pi gives G = 1 - 8r, and |G| <= 1 requires r <= 1/4.
    if (p.r_requested > R_MAX && !p.allow_unstable) {
        if (talk) {
            std::fprintf(stderr,
                "heat: refusing to run: r = %g exceeds the stability limit r <= 1/4.\n"
                "      For the explicit 5-point scheme the checkerboard mode is amplified by\n"
                "      |1 - 8r| = %g > 1 per step, so round-off errors grow exponentially.\n"
                "      Use --r 0.25 or smaller (or --allow-unstable for the Task 6.7 experiment).\n",
                p.r_requested, std::fabs(1.0 - 8.0 * p.r_requested));
        }
        return false;
    }

    p.h = 1.0 / p.N;
    const double h2 = p.h * p.h;
    if (p.T > 0.0) {
        // smallest integer number of steps with dt = T/steps <= r_requested * h^2
        double exact = p.T / (p.r_requested * h2);
        p.steps = static_cast<long long>(std::ceil(exact - 1e-9));
        if (p.steps < 1) p.steps = 1;
        p.dt = p.T / static_cast<double>(p.steps);
        p.t_final = p.T;
    } else {
        p.dt = p.r_requested * h2;
        p.t_final = p.dt * static_cast<double>(p.steps);
    }
    p.r = p.dt / h2;  // alpha = 1
    p.need_field = !p.out.empty() || p.problem == Case::Verification;
    return true;
}
