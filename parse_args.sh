#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"
BUILD_DIR=${SCRIPT_DIR}/_build
TARGET_DEPS_DIR=${BUILD_DIR}/target-deps
HOST_DEPS_DIR=${BUILD_DIR}/host-deps
PLATFORM=linux-x86_64

CONFIG=release
REBUILD=false
INSTALL=true
HOUDINI_FULL_VER=20.5.332
HOUDINI_VER=${HOUDINI_FULL_VER:0:4}
KEEP_STAGING=false


STAGING_DIR=${SCRIPT_DIR}/_staging

for i in "$@"; do
  case $i in
    -i|--install-dir)
      STAGING_DIR="$2/_staging"
      shift # past argument
      shift # past value
      ;;
    -d|--debug)
      CONFIG=Debug
      shift # past argument
      ;;
    -r|--rebuild)
      REBUILD=true
      shift # past argument
      ;;
    --no-install)
      INSTALL=false
      shift # past argument
      ;;
    --keep_staging)
      KEEP_STAGING=true
      shift # past argument
      ;;
    --hver)
      HOUDINI_FULL_VER=$2
      HOUDINI_VER=${HOUDINI_FULL_VER:0:4}
      if [ "${HOUDINI_VER}" == "19" ]; then HOUDINI_VER="19.0"; fi
      shift # past argument
      shift # past value
      ;;
    --no-install)
      INSTALL=false
      shift # past argument
      ;;
    -*|--*)
      #echo "Unknown argument $1"
      #exit 1
      ;;
  esac
done

HOUDINI_VER_DIR=${STAGING_DIR}/houdini${HOUDINI_VER}
HOUDINI_DIR=${HOUDINI_VER_DIR}/houdini
OMNI_BASE=${HOUDINI_VER_DIR}/omni

if [ ${HOUDINI_VER} == "19.5" ]; then
    PY_VER="3.9"
    PY_VER_INT="39"
    EXCLUDED_PY_VERS=("--exclude '*py*37*'" "--exclude '*py*38*'" "--exclude '*py*310*'" "--exclude '*py*311*'")
    HDK_PACKAGE_VER="19.5.773"
    USD_FLAVOR="houdini-22_05-ar2"
elif [ ${HOUDINI_VER} == "20.0" ]; then
    PY_VER="3.10"
    PY_VER_INT="310"
    EXCLUDED_PY_VERS=("--exclude '*py*37*'" "--exclude '*py*38*'" "--exclude '*py*39*'" "--exclude '*py*311*'")
    HDK_PACKAGE_VER="20.0.547"
    USD_FLAVOR="houdini-23_08"
elif [ ${HOUDINI_VER} == "20.5" ]; then
    PY_VER="3.11"
    PY_VER_INT="311"
    EXCLUDED_PY_VERS=("--exclude '*py*37*'" "--exclude '*py*38*'" "--exclude '*py*39*'" "--exclude '*py*310*'")
    HDK_PACKAGE_VER="20.5.332"
    USD_FLAVOR="houdini-24_03"
fi

HOUDINI_INSTALL=/opt/hfs${HOUDINI_FULL_VER}
HOUDINI_BIN=${HOUDINI_INSTALL}/bin
