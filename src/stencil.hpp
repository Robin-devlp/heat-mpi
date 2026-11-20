#pragma once
// The explicit update rule of the 2D heat equation (background notes, Task 5.2):
//
//   u_new(i,j) = u(i,j) + r * ( u(i+1,j) + u(i-1,j) + u(i,j+1) + u(i,j-1) - 4 u(i,j) ),
//   r = alpha * dt / h^2.
//
// This is the ONLY place the formula is written. Serial, strips and blocks all call it,
// so every version performs the same floating-point operations in the same order and
// the outputs are bit-for-bit identical (together with -ffp-contract=off).

inline double heat_update(double c, double east, double west, double north, double south, double r) {
    return c + r * (((east + west) + (north + south)) - 4.0 * c);
}
