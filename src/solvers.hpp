#pragma once
#include <string>
#include <vector>

#include "params.hpp"

struct RunResult {
    std::vector<double> field;  // full (N+1)x(N+1) field on rank 0 (empty elsewhere)
    double t_total = 0.0;       // time-stepping loop, max over ranks
    double t_comp = 0.0;        // computation part, max over ranks
    double t_comm = 0.0;        // halo exchange part, max over ranks
    int nprocs = 1;
    std::string grid_desc;      // process grid "PyxPx" (blocks only)
};

RunResult run_serial(const Params& p);
RunResult run_strips(const Params& p);
RunResult run_blocks(const Params& p);
