#!/usr/bin/env bash

SCRIPT_DIR="$(realpath $(dirname "${BASH_SOURCE}"))"
source ${SCRIPT_DIR}/parse_args.sh $@

mkdir -p ${HOUDINI_DIR}

if [ ! -d ${HOUDINI_DIR} ]
then
    echo "Could not find Houdini ${HOUDINI_VER} plugin folder ${HOUDINI_DIR}."
    exit 1
fi

echo Installing plugins for ${CONFIG} configuration.
CONFIG_DIR_NAME=`echo "${CONFIG}" | tr '[:upper:]' '[:lower:]'`


function link_files() {
    source_dir="$1"
    pattern="$2"
    target_dir="$3"

    if [ ! -d "$target_dir" ]; then
        echo "Target directory '$target_dir' does not exist."
        return 1
    fi

    source_pattern="$source_dir/$pattern"
    # Use find to get a list of files and directories matching the pattern
    find $source_pattern -maxdepth 0 -print0 | while read -d '' -r item; do
        linkname="`realpath --relative-to="$target_dir" "\`dirname $item\`"`"
        item_name=$(basename "$item")
        ln -s -f -T "$linkname/$item_name" "$target_dir/$item_name"
    done
}


function recursive_copy_exclude() {
    # Function to perform recursive copy with multiple exclude options
    # Usage: recursive_copy_exclude <source> <destination> [--exclude <pattern> ...]

    local source="$1"
    local destination="$2"
    local excludes=()

    shift 2

    # Parse options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --exclude)
                shift
                excludes+=("$1")
                ;;
            *)
                echo "Unknown option: $1"
                return 1
                ;;
        esac
        shift
    done

    # Check if source directory exists
    if [[ ! -d "$source" ]]; then
        echo "Source directory '$source' does not exist."
        return 1
    fi

    # Check if destination directory exists, create if not
    if [[ ! -d "$destination" ]]; then
        mkdir -p "$destination"
    fi

    # Build exclude options
    local exclude_options=""
    for exclude in "${excludes[@]}"; do
        exclude_options+=" --exclude=$exclude"
    done

    # Perform copy and remove exclude
    cp -r "$source/" "$destination"
    for exclude in "${excludes[@]}"; do
        find "$destination" -name "$exclude" -exec rm -rf {} +
    done
}

# Copy homni so files
mkdir -p ${HOUDINI_DIR}/dso/
cp -v ${BUILD_DIR}/OP_Omni/libOP_Omni.so ${HOUDINI_DIR}/dso/
mkdir -p ${HOUDINI_DIR}/dso/fs/
cp -v ${BUILD_DIR}/FS_Omni/libFS_Omni.so ${HOUDINI_DIR}/dso/fs/
mkdir -p ${OMNI_BASE}/lib/
cp -v ${BUILD_DIR}/HoudiniOmni/libHoudiniOmni.so ${OMNI_BASE}/lib/
mkdir -p ${OMNI_BASE}/python/homni/
cp -v ${BUILD_DIR}/HoudiniOmniPy/client.so ${OMNI_BASE}/python/homni/
# Copy __init__.py from scripts.
cp -v ${SCRIPT_DIR}/python/python_libs/homni/__init__.py ${OMNI_BASE}/python/homni/

# plugins files
mkdir -p ${OMNI_BASE}/plugins/
cp -v ${TARGET_DEPS_DIR}/carb_sdk_plugins/_build/${PLATFORM}/${CONFIG_DIR_NAME}/libcarb.so ${OMNI_BASE}/lib/

# python files
# Asset Validator python files
eval "recursive_copy_exclude ${TARGET_DEPS_DIR}/omni_asset_validator/python/omni ${OMNI_BASE}/python/ ${EXCLUDED_PY_VERS[@]}"

# Copy target-deps/{packages} to staging/{package}
mkdir -p ${OMNI_BASE}/omni_usd_resolver/
cp -rv ${TARGET_DEPS_DIR}/omni_usd_resolver/${CONFIG_DIR_NAME}/* ${OMNI_BASE}/omni_usd_resolver/
mkdir -p ${OMNI_BASE}/omni_client_library/
cp -rv ${TARGET_DEPS_DIR}/omni_client_library/${CONFIG_DIR_NAME}/*.so ${OMNI_BASE}/omni_client_library/
eval "recursive_copy_exclude ${TARGET_DEPS_DIR}/omni_client_library/${CONFIG_DIR_NAME}/bindings-python/ ${OMNI_BASE}/omni_client_library/ ${EXCLUDED_PY_VERS[@]}"
mkdir -p ${OMNI_BASE}/carb_sdk_plugins/bindings-python/
eval "recursive_copy_exclude ${TARGET_DEPS_DIR}/carb_sdk_plugins/_build/${PLATFORM}/${CONFIG_DIR_NAME}/bindings-python/ ${OMNI_BASE}/carb_sdk_plugins/ ${EXCLUDED_PY_VERS[@]}"

# Link package .so to lib
link_files "${OMNI_BASE}/omni_usd_resolver/" "*.so" "${OMNI_BASE}/lib/"
link_files "${OMNI_BASE}/omni_client_library/" "*.so" "${OMNI_BASE}/lib/"

# Copy python modules and pythonrc.py
mkdir -p ${HOUDINI_DIR}/python${PY_VER}libs/
cp -v ${SCRIPT_DIR}/python/python_libs/pythonrc.py ${HOUDINI_DIR}/python${PY_VER}libs/
cp -v -r ${SCRIPT_DIR}/python/python_libs/homni ${HOUDINI_DIR}/python${PY_VER}libs/

# Copy python scripts
mkdir -p ${HOUDINI_DIR}/scripts/
cp -v ${SCRIPT_DIR}/assets/scripts/menu_omni_connect.py ${HOUDINI_DIR}/scripts/
cp -v ${SCRIPT_DIR}/assets/scripts/menu_omni_panel.py ${HOUDINI_DIR}/scripts/
cp -v ${SCRIPT_DIR}/assets/scripts/afterscenesave.py ${HOUDINI_DIR}/scripts/
# Copy python_panels
mkdir -p ${HOUDINI_DIR}/python_panels/
cp -v ${SCRIPT_DIR}/assets/python_panels/Omniverse.pypanel ${HOUDINI_DIR}/python_panels/
cp -v ${SCRIPT_DIR}/assets/python_panels/AssetValidator.pypanel ${HOUDINI_DIR}/python_panels/

# Helps
mkdir -p ${HOUDINI_DIR}/help/ && cp -v ${SCRIPT_DIR}/houdini-help/command.help ${HOUDINI_DIR}/help/
mkdir -p ${HOUDINI_DIR}/help/nodes/lop/ && cp -v ${SCRIPT_DIR}/assets/help/nodes/lop/* ${HOUDINI_DIR}/help/nodes/lop/
mkdir -p ${HOUDINI_DIR}/help/nodes/other/ && cp -v ${SCRIPT_DIR}/assets/help/nodes/other/* ${HOUDINI_DIR}/help/nodes/other/

# Icons
mkdir -p ${HOUDINI_DIR}/config/Icons/
cp -v ${SCRIPT_DIR}/assets/config/Icons/nvidia-omniverse.ico ${HOUDINI_DIR}/config/Icons/
cp -v ${SCRIPT_DIR}/assets/config/Icons/LOP_omni_live_sync.png ${HOUDINI_DIR}/config/Icons/

# Presets
mkdir -p ${HOUDINI_DIR}/presets/Driver/
cp -v ${SCRIPT_DIR}/assets/presets/Driver/usd.idx ${HOUDINI_DIR}/presets/Driver/
mkdir -p ${HOUDINI_DIR}/presets/Lop/
cp -v ${SCRIPT_DIR}/assets/presets/Lop/usd_rop.idx ${HOUDINI_DIR}/presets/Lop/
cp -v ${SCRIPT_DIR}/assets/presets/Lop/copyproperty.idx ${HOUDINI_DIR}/presets/Lop/
cp -v ${SCRIPT_DIR}/assets/presets/Lop/editproperties.idx ${HOUDINI_DIR}/presets/Lop/
mkdir -p ${HOUDINI_DIR}/presets/Vop/
cp -v ${SCRIPT_DIR}/assets/presets/Vop/mdlomnihair.idx ${HOUDINI_DIR}/presets/Vop/
cp -v ${SCRIPT_DIR}/assets/presets/Vop/mdlomnisurface_lite.idx ${HOUDINI_DIR}/presets/Vop/
cp -v ${SCRIPT_DIR}/assets/presets/Vop/mdlomnisurface.idx ${HOUDINI_DIR}/presets/Vop/

# Toolbar
mkdir -p ${HOUDINI_DIR}/toolbar/ && cp -v ${SCRIPT_DIR}/assets/toolbar/omni.shelf ${HOUDINI_DIR}/toolbar/
# menu xmls
cp -v ${SCRIPT_DIR}/assets/MainMenuCommon.xml ${HOUDINI_DIR}/
cp -v ${SCRIPT_DIR}/assets/PARMmenu.xml ${HOUDINI_DIR}/

# USD Python plugins
mkdir -p ${HOUDINI_DIR}/husdplugins/outputprocessors/
cp -v ${SCRIPT_DIR}/assets/husdplugins/outputprocessors/omnitextureexport.py ${HOUDINI_DIR}/husdplugins/outputprocessors/
cp -v ${SCRIPT_DIR}/assets/husdplugins/outputprocessors/omnicheckpoints.py ${HOUDINI_DIR}/husdplugins/outputprocessors/
cp -v ${SCRIPT_DIR}/assets/husdplugins/outputprocessors/omnimdlproperties.py ${HOUDINI_DIR}/husdplugins/outputprocessors/
cp -v ${SCRIPT_DIR}/assets/husdplugins/outputprocessors/omnisimplerelativepaths.py ${HOUDINI_DIR}/husdplugins/outputprocessors/
cp -v ${SCRIPT_DIR}/assets/husdplugins/outputprocessors/omniusdformat.py ${HOUDINI_DIR}/husdplugins/outputprocessors/

mkdir -p ${HOUDINI_DIR}/husdplugins/shadertranslators/
cp -v ${SCRIPT_DIR}/assets/husdplugins/shadertranslators/mdl.py ${HOUDINI_DIR}/husdplugins/shadertranslators/

# OTLs
mkdir -p ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/mdl_omnipbr_vop.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/mdl_omnivolumedensity_vop.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/mdl_omniglass_vop.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/mdl_omnihair_vop.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/mdl_omnipbrclearcoat_vop.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/mdl_omnisurface_vop.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/mdl_omnisurfacelite_vop.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/omni_editmdl.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/object_omni_examplePowerlines.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/omni_liveeditbreak.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/omni_loader.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/omni_validator.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/omni_lights.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/omni_conform.hda ${HOUDINI_DIR}/otls/
cp -v ${SCRIPT_DIR}/assets/otls/sop_omni_frustum.hda ${HOUDINI_DIR}/otls/

# Version specific files
if [ ${HOUDINI_VER} == "19.0" ]; then
    mkdir -p ${HOUDINI_DIR}/presets/Lop/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/presets/Lop/usd_rop.idx ${HOUDINI_DIR}/presets/Lop/
    mkdir -p ${HOUDINI_DIR}/presets/Driver/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/presets/Driver/usd.idx ${HOUDINI_DIR}/presets/Driver/
    mkdir -p ${HOUDINI_DIR}/otls/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/otls/omni_editmdl.hda ${HOUDINI_DIR}/otls/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/otls/omni_validator.hda ${HOUDINI_DIR}/otls/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/otls/omni_lights.hda ${HOUDINI_DIR}/otls/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/otls/object_omni_examplePowerlines.hda ${HOUDINI_DIR}/otls/
fi
if [ ${HOUDINI_VER} == "19.5" ]; then
    mkdir -p ${HOUDINI_DIR}/presets/Lop/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/presets/Lop/usd_rop.idx ${HOUDINI_DIR}/presets/Lop/
    mkdir -p ${HOUDINI_DIR}/presets/Driver/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/presets/Driver/usd.idx ${HOUDINI_DIR}/presets/Driver/
    mkdir -p ${HOUDINI_DIR}/otls/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/otls/omni_editmdl.hda ${HOUDINI_DIR}/otls/
    cp -v ${SCRIPT_DIR}/assets${HOUDINI_VER}/otls/object_omni_examplePowerlines.hda ${HOUDINI_DIR}/otls/
fi
