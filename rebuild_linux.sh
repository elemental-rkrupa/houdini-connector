#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"

${SCRIPT_DIR}/build_linux.sh $@ --rebuild; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then exit ${EXITCODE}; fi
