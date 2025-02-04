#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"
source ${SCRIPT_DIR}/parse_args.sh $@

if [[ ! -d "$BUILD_DIR" ]]; then
    mkdir -p ${BUILD_DIR}; EXITCODE=$?
    if [ ${EXITCODE} -ne 0 ]; then exit ${EXITCODE}; fi
fi

pushd ${BUILD_DIR} > /dev/null

export CC=${HOST_DEPS_DIR}/gcc/bin/x86_64-unknown-linux-gnu-gcc
export CXX=${HOST_DEPS_DIR}/gcc/bin/x86_64-unknown-linux-gnu-g++
export LD_LIBRARY_PATH=${HOST_DEPS_DIR}/x86_64-unknown-linux-gnu/lib64:${LD_LIBRARY_PATH}
export HOUDINI_VER=${HOUDINI_VER}


${HOST_DEPS_DIR}/cmake/bin/cmake .. -DCMAKE_BUILD_TYPE=${CONFIG}; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then popd > /dev/null; exit ${EXITCODE}; fi

pushd ${BUILD_DIR}/HoudiniOmni > /dev/null; make; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then popd > /dev/null; exit ${EXITCODE}; fi

pushd ${BUILD_DIR}/HoudiniOmniPy > /dev/null; make; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then popd > /dev/null; exit ${EXITCODE}; fi

pushd ${BUILD_DIR}/OP_Omni > /dev/null; make; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then popd > /dev/null; exit ${EXITCODE}; fi

pushd ${BUILD_DIR}/FS_Omni > /dev/null; make; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then popd > /dev/null; exit ${EXITCODE}; fi

popd > /dev/null