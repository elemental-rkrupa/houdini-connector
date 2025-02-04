cmake_minimum_required( VERSION 3.13 )

project( HoudiniOmniPy )

set( module_name HoudiniOmniPy )

# Set rpath for Linux build
if (NOT WIN32)
    SET(CMAKE_INSTALL_RPATH "\$ORIGIN/../../lib")
endif()

pybind11_add_module(${module_name} HoudiniOmniPy.cpp)

target_link_libraries(${module_name} PRIVATE
    Houdini
    HoudiniOmni
)

# Check if the build type is Debug
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_include_directories( ${module_name} PRIVATE
        ${HoudiniOmni_SOURCE_DIR}
        ${HoudiniOmni_BINARY_DIR}
        ${CARB_SDK_DIR}/include
    )
else()
    target_include_directories( ${module_name} PRIVATE
        ${HoudiniOmni_SOURCE_DIR}
        ${HoudiniOmni_BINARY_DIR}
        ${CARB_SDK_DIR}/include
    )
endif()


set_target_properties( ${module_name} PROPERTIES
    OUTPUT_NAME "client" SUFFIX ${PY_BINDING_SUFFIX} PREFIX ""
    LIBRARY_OUTPUT_DIRECTORY ${BINARY_INSTALL_DIR}/${module_name}
    LINK_FLAGS_RELWITHDEBINFO "/INCREMENTAL:NO"
)

