#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"
source ${SCRIPT_DIR}/parse_args.sh $@

# HDAs - Houdini Eneine Test  -- Linux Not Supported yet
#echo "Running HDA (Houdini Engine)"
#echo "%~dp0repo.bat test --suite he_hdas"
#${SCRIPT_DIR}/repo.sh test --suite he_hdas; EXITCODE=$?
#if [ ${EXITCODE} -ne 0 ]; then exit ${EXITCODE}; fi


# pytests
echo "Running pytests"
${SCRIPT_DIR}/run_tests_pytest.sh $@; EXITCODE=$?
if [ ${EXITCODE} -ne 0 ]; then exit ${EXITCODE}; fi