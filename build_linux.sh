#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"
source ${SCRIPT_DIR}/parse_args.sh $@

# Rebuild
if [ ${REBUILD} = true ] ; then
    rm -rf ${BUILD_DIR}
    if [ ${KEEP_STAGING} = false ] ; then
        rm -rf ${STAGING_DIR}
    fi
fi

pushd "${SCRIPT_DIR}" > /dev/null

${SCRIPT_DIR}/get_dependencies.sh $@; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then popd > /dev/null; exit ${EXITCODE}; fi

${SCRIPT_DIR}/cmake_linux_build.sh $@; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then popd > /dev/null; exit ${EXITCODE}; fi

if [ ${INSTALL} = true ] ; then
    ${SCRIPT_DIR}/install.sh $@; EXITCODE=$?
    if [ ${EXITCODE} -ne 0 ]; then popd > /dev/null; exit ${EXITCODE}; fi
fi

popd > /dev/null

echo "< Build script succeeded >"