#!/usr/bin/env bash
TOOLS_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"

"${TOOLS_DIR}/../repo.sh" package -m houdini-connector-launcher

"${TOOLS_DIR}/../repo.sh" package -m omni_houdini_native_setup

exit $?