// pingpong.cpp - measure MPI point-to-point latency and bandwidth (project Part 0, step 6).
//
// Rank 0 sends a message of m bytes to rank 1, which sends it straight back.
// For each m = 8 B ... max (powers of two) the round trip is repeated many times
// and averaged. The one-way time is half the round trip; the model
// t_msg(m) = t_s + m * t_w is fitted afterwards (scripts/fit_pingpong.py).
//
// Usage:  mpirun -np 2 ... ./pingpong [--max-bytes N] [--target-time S]
//                                    [--min-reps N] [--max-reps N]
// Output (stdout of rank 0): a few "# key=value" header lines, then CSV:
//   bytes,reps,rtt_avg_s,rtt_min_s,oneway_avg_s,bandwidth_MBps
#include <mpi.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace {

struct Options {
    long long max_bytes = 16LL * 1024 * 1024;  // 16 MB
    double target_time = 2.0;                  // seconds of timed round trips per size
    int min_reps = 10;
    int max_reps = 10000;
};

Options parse(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&](const char* name) -> const char* {
            if (i + 1 >= argc) {
                std::fprintf(stderr, "missing value for %s\n", name);
                MPI_Abort(MPI_COMM_WORLD, 1);
            }
            return argv[++i];
        };
        if (a == "--max-bytes") o.max_bytes = std::atoll(next("--max-bytes"));
        else if (a == "--target-time") o.target_time = std::atof(next("--target-time"));
        else if (a == "--min-reps") o.min_reps = std::atoi(next("--min-reps"));
        else if (a == "--max-reps") o.max_reps = std::atoi(next("--max-reps"));
        else {
            std::fprintf(stderr, "unknown option %s\n", a.c_str());
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
    }
    return o;
}

// One round trip of 'bytes' bytes between rank 0 and rank 1.
// Returns the elapsed time measured on rank 0 (0 on rank 1).
double round_trip(std::vector<char>& buf, int bytes, int rank) {
    const int tag = 0;
    if (rank == 0) {
        double t0 = MPI_Wtime();
        MPI_Send(buf.data(), bytes, MPI_BYTE, 1, tag, MPI_COMM_WORLD);
        MPI_Recv(buf.data(), bytes, MPI_BYTE, 1, tag, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        return MPI_Wtime() - t0;
    }
    MPI_Recv(buf.data(), bytes, MPI_BYTE, 0, tag, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    MPI_Send(buf.data(), bytes, MPI_BYTE, 0, tag, MPI_COMM_WORLD);
    return 0.0;
}

}  // namespace

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank = 0, size = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    if (size != 2) {
        if (rank == 0) std::fprintf(stderr, "pingpong needs exactly 2 processes (got %d)\n", size);
        MPI_Finalize();
        return 1;
    }
    const Options opt = parse(argc, argv);

    char name[MPI_MAX_PROCESSOR_NAME];
    int len = 0;
    MPI_Get_processor_name(name, &len);
    char other[MPI_MAX_PROCESSOR_NAME] = {0};
    if (rank == 0) {
        MPI_Recv(other, MPI_MAX_PROCESSOR_NAME, MPI_CHAR, 1, 99, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    } else {
        MPI_Send(name, len + 1, MPI_CHAR, 0, 99, MPI_COMM_WORLD);
    }

    std::vector<char> buf(static_cast<size_t>(opt.max_bytes), 'x');

    if (rank == 0) {
        std::printf("# rank0=%s rank1=%s\n", name, other);
        std::printf("# max_bytes=%lld target_time=%g min_reps=%d max_reps=%d wtick=%g\n",
                    opt.max_bytes, opt.target_time, opt.min_reps, opt.max_reps, MPI_Wtick());
        std::printf("bytes,reps,rtt_avg_s,rtt_min_s,oneway_avg_s,bandwidth_MBps\n");
        std::fflush(stdout);
    }

    for (long long m = 8; m <= opt.max_bytes; m *= 2) {
        const int bytes = static_cast<int>(m);

        // Warm-up (connection setup, page faults) and a rough timing estimate.
        double est = 0.0;
        for (int w = 0; w < 3; ++w) est = round_trip(buf, bytes, rank);

        // Rank 0 chooses the repetition count so each size takes ~target_time.
        int reps = opt.min_reps;
        if (rank == 0 && est > 0.0) {
            double r = opt.target_time / est;
            reps = static_cast<int>(std::min<double>(opt.max_reps, std::max<double>(opt.min_reps, r)));
        }
        MPI_Bcast(&reps, 1, MPI_INT, 0, MPI_COMM_WORLD);

        MPI_Barrier(MPI_COMM_WORLD);
        double total = 0.0, best = 1e300;
        for (int k = 0; k < reps; ++k) {
            double t = round_trip(buf, bytes, rank);
            total += t;
            best = std::min(best, t);
        }

        if (rank == 0) {
            double rtt = total / reps;
            double oneway = rtt / 2.0;
            double bw = (static_cast<double>(m) / oneway) / 1e6;  // MB/s, 1 MB = 1e6 bytes
            std::printf("%lld,%d,%.9e,%.9e,%.9e,%.6f\n", m, reps, rtt, best, oneway, bw);
            std::fflush(stdout);
        }
    }

    MPI_Finalize();
    return 0;
}
