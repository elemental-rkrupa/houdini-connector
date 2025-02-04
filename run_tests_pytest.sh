#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"
source ${SCRIPT_DIR}/parse_args.sh $@


export HOMNI_DISABLE_PACKAGE="1"

export HOMNI="${HOUDINI_VER_DIR}"
export HOUDINI_PATH="${HOMNI}/houdini:&"

export OMNI_ROOT="${HOMNI}/omni"
export PYTHONPATH="${OMNI_ROOT}/python:${OMNI_ROOT}/carb_sdk_plugins/bindings-python:${OMNI_ROOT}/omni_usd_resolver/bindings-python:${OMNI_ROOT}/omni_client_library/bindings-python:${PYTHONPATH}"
export HOUDINI_USD_DSO_PATH="${OMNI_ROOT}/omni_usd_resolver/usd/omniverse/resources:${HOUDINI_USD_DSO_PATH}:&"

export LD_LIBRARY_PATH="${OMNI_ROOT}/lib:${OMNI_ROOT}/omni_usd_resolver:${OMNI_ROOT}/omni_client_library:${LD_LIBRARY_PATH}"

export HOMNI_ENABLE_EXPERIMENTAL=1
export HOMNI_DEFAULT_CONNECTIONS="localhost"
export HOMNI_ENABLE_LOGFILE=1

export HOUDINI_DSO_ERROR=2
export TEST_ID=$RANDOM
export HOMNI_LOGLEVEL=0
#export TF_DEBUG=SDF_LAYER

export PM_PYTHON_EXT=${HOUDINI_BIN}/hython

echo Running pytest "${SCRIPT_DIR}/repo.sh test --suite pytests"
${SCRIPT_DIR}/repo.sh test --suite pytests
