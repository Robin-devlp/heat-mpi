#pragma once
#include <string>
#include <vector>

// Writes the full (N+1)x(N+1) field as raw little-endian doubles, row-major
// (row j = line y = y_j, i varies fastest), no header. Returns false on error.
bool write_field(const std::string& path, const std::vector<double>& u);
