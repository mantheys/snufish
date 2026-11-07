#!/usr/bin/env bash
# Builds the pinned SQuIDS and nuSQuIDS into ./local (needs g++, GSL and HDF5 headers, e.g.
# apt install libgsl-dev libhdf5-dev). Their configure scripts need bash, not sh.
set -euo pipefail
cd "$(dirname "$0")"
SQUIDS_TAG=v1.3.1      # commit f9e6182
NUSQUIDS_TAG=v1.13.3   # commit 104914d
PREFIX="$PWD/local"
mkdir -p build
[ -d build/SQuIDS ] || git clone -q https://github.com/jsalvado/SQuIDS build/SQuIDS
[ -d build/nuSQuIDS ] || git clone -q https://github.com/arguelles/nuSQuIDS build/nuSQuIDS
git -C build/SQuIDS checkout -q "$SQUIDS_TAG"
git -C build/nuSQuIDS checkout -q "$NUSQUIDS_TAG"
(cd build/SQuIDS && bash ./configure --prefix="$PREFIX" && make -j"$(nproc)" && make install)
(cd build/nuSQuIDS && bash ./configure --prefix="$PREFIX" --with-squids="$PREFIX" && make -j"$(nproc)" && make install)
