#include "problem.hpp"

#include <cmath>

namespace {
const double PI = std::acos(-1.0);
}

bool is_boundary(int i, int j, int N) {
    return i == 0 || j == 0 || i == N || j == N;
}

double initial_value(Case c, int i, int j, int N) {
    const double h = 1.0 / N;
    switch (c) {
        case Case::Hot4:
            // all four edges held at 1, interior starts cold
            return is_boundary(i, j, N) ? 1.0 : 0.0;
        case Case::HotTopBottom:
            // bottom (j=0) and top (j=N) edges at 1, corners included;
            // left (i=0) and right (i=N) edges at 0; interior cold
            if (j == 0 || j == N) return 1.0;
            return 0.0;
        case Case::Verification:
            // u = 0 on the edges (set exactly, sin(pi) is not exactly 0 in floating point)
            if (is_boundary(i, j, N)) return 0.0;
            return std::sin(PI * (i * h)) * std::sin(PI * (j * h));
    }
    return 0.0;
}

double exact_solution(int i, int j, int N, double t) {
    if (is_boundary(i, j, N)) return 0.0;
    const double h = 1.0 / N;
    return std::sin(PI * (i * h)) * std::sin(PI * (j * h)) * std::exp(-2.0 * PI * PI * t);
}
