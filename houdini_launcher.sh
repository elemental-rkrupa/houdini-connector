#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"
source ${SCRIPT_DIR}/parse_args.sh $@

# Disable the omniverse.json package, so we can set all variables
# and paths in this script.
export HOMNI_DISABLE_PACKAGE="1"
#export HOUDINI_PACKAGE_VERBOSE="1"

export HOMNI="${HOUDINI_VER_DIR}"
export HOUDINI_PATH="${HOMNI}/houdini:&"

export OMNI_ROOT="${HOMNI}/omni"
export CARB_APP_PATH="${OMNI_ROOT}"
export PYTHONPATH="${OMNI_ROOT}/python:${OMNI_ROOT}/carb_sdk_plugins/bindings-python:${OMNI_ROOT}/omni_usd_resolver/bindings-python:${OMNI_ROOT}/omni_client_library/bindings-python:${PYTHONPATH}"
export HOUDINI_USD_DSO_PATH="${OMNI_ROOT}/omni_usd_resolver/usd/omniverse/resources:${HOUDINI_USD_DSO_PATH}:&"

#export LD_LIBRARY_PATH="${OMNI_ROOT}/lib:${OMNI_ROOT}/omni_usd_resolver:${OMNI_ROOT}/omni_client_library:${LD_LIBRARY_PATH}"

export HOMNI_ENABLE_EXPERIMENTAL=1
export HOMNI_DEFAULT_CONNECTIONS="localhost"
export HOMNI_ENABLE_LOGFILE=1

export HOUDINI_DSO_ERROR=2

# Enable TF_DEBUG to tell Houdini to print the plugin.json it loads
# export TF_DEBUG=OMNI_USD_*
# export TF_DEBUG=SDF_LAYER

#export HOMNI_LOGLEVEL=0

# 19.0.720
# 19.5.605

new_args=""
# Remove --hver and --debug args
for i in "$@"; do
  case $i in
    -d|--debug)
      shift # past argument
      ;;
    --hver)
      shift # past argument
      shift # past value
      ;;
    -*|--*)
      #echo "Unknown argument $1"
      #exit 1
      new_args=${new_args}+" "+ $i
      ;;
  esac
done

echo "${HOUDINI_BIN}/houdini $@"
${HOUDINI_BIN}/houdini $@

#ld _staging/houdini19.5/lib/omni_connect_sdk/python/omni/connect/ui/_omni_connect_ui.cpython-39-x86_64-linux-gnu.so
#ld _staging/houdini19.5/lib/omni_connect_sdk/python/omni/connect/core/_omni_connect_core.cpython-39-x86_64-linux-gnu.so
#ldd _staging/houdini20.0/omni/lib/libomni_connect_core.so
