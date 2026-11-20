#pragma once
#include "params.hpp"

// Initial and boundary values of the three test problems, as functions of the global
// node indices (i, j), 0 <= i, j <= N, with x = i*h and y = j*h.
// Every decomposition uses these same functions, so all versions start from identical data.

bool is_boundary(int i, int j, int N);

// Value at node (i,j) at t = 0: the boundary value on the edges, the initial
// condition inside.
double initial_value(Case c, int i, int j, int N);

// Exact solution of the verification problem (Case V): sin(pi x) sin(pi y) exp(-2 pi^2 t).
double exact_solution(int i, int j, int N, double t);
