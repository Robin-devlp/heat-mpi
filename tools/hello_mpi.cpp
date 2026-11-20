// hello_mpi.cpp - MPI "hello world": every process prints its rank, the number of
// processes and the VM it runs on. Used to check the cluster before the solver (spec step 5).
#include <mpi.h>
#include <cstdio>
int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank, size, len;
    char name[MPI_MAX_PROCESSOR_NAME];
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    MPI_Get_processor_name(name, &len);
    std::printf("rank %d of %d on %s\n", rank, size, name);
    MPI_Finalize();
    return 0;
}
