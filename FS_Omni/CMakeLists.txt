cmake_minimum_required( VERSION 3.13 )

project( FS_Omni )

set( library_name FS_Omni )


# Set rpath for Linux build
if (NOT WIN32)
    SET(CMAKE_INSTALL_RPATH "\$ORIGIN/../../../omni/lib")
endif()

# Add a library and its source files.
add_library( ${library_name} SHARED
    FS_Omni.h
    FS_Omni.cpp
    FS_OmniInfoHelper.h
    FS_OmniInfoHelper.cpp
    FS_OmniReadHelper.h
    FS_OmniReadHelper.cpp
    FS_OmniWriteHelper.h
    FS_OmniWriteHelper.cpp
)

# Link against the Houdini libraries, and add required include directories and
# compile definitions.
target_link_libraries( ${library_name}
    Houdini
    HoudiniOmni
)

if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_include_directories( ${library_name} PRIVATE
        ${HoudiniOmni_SOURCE_DIR}
        ${HoudiniOmni_BINARY_DIR}
        ${CARB_SDK_DIR}/include
    )
else()
    target_include_directories( ${library_name} PRIVATE
        ${HoudiniOmni_SOURCE_DIR}
        ${HoudiniOmni_BINARY_DIR}
        ${CARB_SDK_DIR}/include
    )

endif()
set_target_properties( ${library_name} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${BINARY_INSTALL_DIR}/${library_name}
    ARCHIVE_OUTPUT_DIRECTORY ${BINARY_INSTALL_DIR}/${library_name}
)
