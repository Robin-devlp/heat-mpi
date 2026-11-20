cmake_minimum_required(VERSION 3.20)
project(heat_mpi LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
# -O3 for speed; -ffp-contract=off so no fused multiply-adds are generated
# (required by the spec: identical floating-point results on every machine).
set(CMAKE_CXX_FLAGS_RELEASE "-O3")
add_compile_options(-ffp-contract=off -Wall -Wextra)

find_package(MPI REQUIRED COMPONENTS CXX)

add_executable(heat
  src/main.cpp
  src/params.cpp
  src/problem.cpp
  src/io.cpp
  src/serial.cpp
  src/strips.cpp
  src/blocks.cpp)
target_include_directories(heat PRIVATE src)
target_link_libraries(heat PRIVATE MPI::MPI_CXX)

add_executable(hello_mpi tools/hello_mpi.cpp)
target_link_libraries(hello_mpi PRIVATE MPI::MPI_CXX)

add_executable(pingpong tools/pingpong.cpp)
target_link_libraries(pingpong PRIVATE MPI::MPI_CXX)
