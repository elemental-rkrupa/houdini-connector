cmake_minimum_required( VERSION 3.13 )

project( HoudiniOmni )

set( library_name HoudiniOmni )

# Set rpath for Linux build
if (NOT WIN32)
    SET(CMAKE_INSTALL_RPATH "\$ORIGIN/../../lib")
endif()

# Add a library and its source files.
add_library( ${library_name} SHARED
    HoudiniOmni.h
    HoudiniOmniResultTypes.h
    HoudiniOmniTypes.h
    HoudiniOmniUtils.h
    HoudiniOmniVersion.h
    HoudiniOmni.cpp
)

# Generate houdiniomni_export.h header for macros for exporting the HoudiniOmni symbols.
include(GenerateExportHeader)
generate_export_header( ${library_name} )

if (WIN32)
    target_link_libraries( ${library_name}
        optimized ${OMNI_CLIENT_DIR}/release/omniclient.lib
        debug ${OMNI_CLIENT_DIR}/debug/omniclient.lib
        optimized ${CARB_SDK_DIR}/_build/windows-x86_64/release/carb.lib
        debug ${CARB_SDK_DIR}/_build/windows-x86_64/debug/carb.lib
    )
else ()
    target_link_libraries( ${library_name}
        optimized ${OMNI_CLIENT_DIR}/release/libomniclient.so
        debug ${OMNI_CLIENT_DIR}/debug/libomniclient.so
        optimized ${CARB_SDK_DIR}/_build/linux-x86_64/release/libcarb.so
        debug ${CARB_SDK_DIR}/_build/linux-x86_64/debug/libcarb.so
    )
endif(WIN32)

# Check if the build type is Debug
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_include_directories( ${library_name} PRIVATE
        ${CMAKE_CURRENT_BINARY_DIR}
        ${OMNI_CLIENT_DIR}/include
        ${CARB_SDK_DIR}/include
    )
else()
    target_include_directories( ${library_name} PRIVATE
        ${CMAKE_CURRENT_BINARY_DIR}
        ${OMNI_CLIENT_DIR}/include
        ${CARB_SDK_DIR}/include
    )
endif()


set_target_properties( ${library_name} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${BINARY_INSTALL_DIR}/${library_name}
    ARCHIVE_OUTPUT_DIRECTORY ${BINARY_INSTALL_DIR}/${library_name}
)
