#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"
source ${SCRIPT_DIR}/parse_args.sh $@

if [[ ! -d "$BUILD_DIR" ]]; then
    mkdir -p ${BUILD_DIR}; EXITCODE=$?
    if [ ${EXITCODE} -ne 0 ]; then exit ${EXITCODE}; fi
fi


echo "${SCRIPT_DIR}/repo.sh --set-token hdkversion:${HDK_PACKAGE_VER} --set-token pyver:py${PY_VER_INT} --set-token usd_flavor:${USD_FLAVOR} build --fetch-only -r"
${SCRIPT_DIR}/repo.sh --set-token hdkversion:${HDK_PACKAGE_VER} --set-token pyver:py${PY_VER_INT} --set-token usd_flavor:${USD_FLAVOR} build --fetch-only -r; EXITCODE=$?


if [ ${EXITCODE} -ne 0 ]; then exit ${EXITCODE}; fi
