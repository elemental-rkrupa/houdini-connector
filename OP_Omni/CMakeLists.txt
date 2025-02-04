cmake_minimum_required( VERSION 3.13 )

project( OP_Omni )

set( library_name OP_Omni )

# Set rpath for Linux build
if (NOT WIN32)
    SET(CMAKE_INSTALL_RPATH "\$ORIGIN/../../omni/lib")
endif()

# Add a library and its source files.
add_library( ${library_name} SHARED
    CMD_Omni.cpp
    LOP_OmniLiveSync.cpp
    LOP_OmniLiveSync.h
)

# Link against the Houdini libraries, and add required include directories and
# compile definitions.
if (WIN32)
    target_link_libraries( ${library_name}
        Houdini
        HoudiniOmni
        ${HOUDINI_DIR}/custom/houdini/dsolib/hboost_python${PY_VER_INT}-mt-x64.lib
        ${PYTHON_LIBS_DIR}/python${PY_VER_INT}.lib
        ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_gf.lib
        ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_sdf.lib
        ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_tf.lib
        ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_usd.lib
        ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_usdGeom.lib
        ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_usdUtils.lib
        ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_vt.lib
        ${HOUDINI_DIR}/custom/houdini/dsolib/libpxr_arch.lib
    )
else ()
    target_link_libraries( ${library_name}
        Houdini
        HoudiniOmni
        ${HOUDINI_DIR}/dsolib/libhboost_python${PY_VER_INT}-mt-x64.so
        ${PYTHON_LIBRARY_DIR}/libpython${PY_VER_LIB}.so
        ${HOUDINI_DIR}/dsolib/libpxr_gf.so
        ${HOUDINI_DIR}/dsolib/libpxr_sdf.so
        ${HOUDINI_DIR}/dsolib/libpxr_tf.so
        ${HOUDINI_DIR}/dsolib/libpxr_usd.so
        ${HOUDINI_DIR}/dsolib/libpxr_usdGeom.so
        ${HOUDINI_DIR}/dsolib/libpxr_usdUtils.so
        ${HOUDINI_DIR}/dsolib/libpxr_vt.so
        ${HOUDINI_DIR}/dsolib/libpxr_arch.so
    )
endif(WIN32)

if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_include_directories( ${library_name} PRIVATE
        ${HoudiniOmni_SOURCE_DIR}
        ${HoudiniOmni_BINARY_DIR}
        ${PYTHON_INCLUDE_DIR}
        ${CARB_SDK_DIR}/include
    )
else()
    target_include_directories( ${library_name} PRIVATE
        ${HoudiniOmni_SOURCE_DIR}
        ${HoudiniOmni_BINARY_DIR}
        ${PYTHON_INCLUDE_DIR}
        ${CARB_SDK_DIR}/include
    )

endif()

set_target_properties( ${library_name} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${BINARY_INSTALL_DIR}/${library_name}
    ARCHIVE_OUTPUT_DIRECTORY ${BINARY_INSTALL_DIR}/${library_name}
)
