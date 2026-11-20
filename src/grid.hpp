#pragma once
#include <cstddef>
#include <vector>

// A rectangular block of nodes stored in ONE contiguous array, row-major:
// row j is a line of constant y, and i (x direction) varies fastest.
// All access goes through idx(), the single indexing function (notes, Section 8.1).
struct Grid {
    int nx = 0;  // nodes per row (columns)
    int ny = 0;  // number of rows
    std::vector<double> u;

    Grid() = default;
    Grid(int nx_, int ny_) : nx(nx_), ny(ny_), u(static_cast<std::size_t>(nx_) * ny_, 0.0) {}

    std::size_t idx(int i, int j) const {
        return static_cast<std::size_t>(j) * nx + i;
    }
    double& operator()(int i, int j) { return u[idx(i, j)]; }
    double operator()(int i, int j) const { return u[idx(i, j)]; }
    double* row(int j) { return u.data() + idx(0, j); }
};
