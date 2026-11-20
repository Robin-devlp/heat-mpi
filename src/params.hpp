#pragma once
#include <string>

// Stability limit of the explicit 2D scheme (background notes, Task 6.3):
// all Fourier modes are damped iff r = alpha*dt/h^2 <= 1/4.
constexpr double R_MAX = 0.25;

enum class Case { Hot4, HotTopBottom, Verification };  // --case 1, 2, V
enum class Decomp { Serial, Strips, Blocks };

struct Params {
    Case problem = Case::Hot4;
    Decomp decomp = Decomp::Serial;
    int N = 64;                 // intervals per direction, h = 1/N, nodes 0..N
    double r_requested = 0.25;  // alpha*dt/h^2 asked for on the command line
    double T = -1.0;            // final time (if --T given)
    long long steps = -1;       // number of steps (if --steps given)
    std::string out;            // output field file (empty = none)
    bool allow_unstable = false;
    bool dump_local = false;    // print every rank's local array (debugging, small N only)
    bool need_field = false;    // gather the full field on rank 0 (set when --out or case V)

    // derived by finalize():
    double h = 0.0;
    double dt = 0.0;
    double r = 0.0;             // r actually used (<= r_requested)
    double t_final = 0.0;
};

// Parses argv. On error prints a message (on rank 0) and returns false.
bool parse_params(int argc, char** argv, Params& p, int rank);

const char* case_name(Case c);
const char* decomp_name(Decomp d);
