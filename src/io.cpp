#include "io.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {
bool host_is_little_endian() {
    const std::uint16_t one = 1;
    unsigned char b;
    std::memcpy(&b, &one, 1);
    return b == 1;
}
}  // namespace

bool write_field(const std::string& path, const std::vector<double>& u) {
    if (!host_is_little_endian()) {
        std::fprintf(stderr, "heat: big-endian host not supported for output\n");
        return false;
    }
    std::FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) {
        std::perror(path.c_str());
        return false;
    }
    const std::size_t n = std::fwrite(u.data(), sizeof(double), u.size(), f);
    const bool ok = (n == u.size()) && (std::fclose(f) == 0);
    if (!ok) std::fprintf(stderr, "heat: error writing %s\n", path.c_str());
    return ok;
}
