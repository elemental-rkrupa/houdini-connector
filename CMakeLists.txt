cmake_minimum_required( VERSION 3.13 )

# Enable support for generating Visual Studio folders.
set_property(GLOBAL PROPERTY USE_FOLDERS ON)

# Get Houdini and Python version
set(HOUDINI_VER $ENV{HOUDINI_VER})
if (NOT ${HOUDINI_VER})
    set(HOUDINI_VER "20.0")
endif ()

if (${HOUDINI_VER} STREQUAL "19.0")
    set(PY_VER_LIB "3.7m")
    set(PY_VER_INT "37")
elseif(${HOUDINI_VER} STREQUAL "19.5")
    set(PY_VER_LIB "3.9")
    set(PY_VER_INT "39")
elseif(${HOUDINI_VER} STREQUAL "20.0")
    set(PY_VER_LIB "3.10")
    set(PY_VER_INT "310")
elseif(${HOUDINI_VER} STREQUAL "20.5")
    set(PY_VER_LIB "3.11")
    set(PY_VER_INT "311")
    set(HAPI_7 ON)
    add_definitions(-DHAPI_7)
endif ()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(DEPENDENCIES_DIR "${CMAKE_SOURCE_DIR}/_build/target-deps")
set(OMNI_CLIENT_DIR "${DEPENDENCIES_DIR}/omni_client_library")
set(CARB_SDK_DIR "${DEPENDENCIES_DIR}/carb_sdk_plugins")
set(BINARY_INSTALL_DIR "${CMAKE_SOURCE_DIR}/_build")
set(HOUDINI_DIR "${DEPENDENCIES_DIR}/houdini_hdk")
set(PYTHON_INCLUDE_DIR "${HOUDINI_DIR}/python${PY_VER_INT}/include")
set(PYTHON_LIBRARY_DIR "${HOUDINI_DIR}/python${PY_VER_INT}/lib")
set(PYTHON_LIBS_DIR "${HOUDINI_DIR}/python${PY_VER_INT}/libs")

if (WIN32)
    set(PYTHON_EXECUTABLE "${HOUDINI_DIR}/python${PY_VER_INT}/python.exe")
    set(PY_BINDING_SUFFIX ".pyd")
else ()
    # Set rpath for Linux build
    set(CMAKE_SKIP_BUILD_RPATH  FALSE)
    set(CMAKE_INSTALL_RPATH_USE_LINK_PATH  TRUE)
    set(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)
    set(CMAKE_BUILD_RPATH_USE_ORIGIN TRUE)

    set(PYTHON_EXECUTABLE "${HOUDINI_DIR}/python${PY_VER_INT}/bin/python3.11")
    set(PY_BINDING_SUFFIX ".so")

    # as per vfxplatform.
    add_compile_definitions(_GLIBCXX_USE_CXX11_ABI=0)
endif (WIN32)


project(houdini-omni-plugin)

# CMAKE_PREFIX_PATH must contain the path to the toolkit/cmake subdirectory of
# the Houdini installation.
list( APPEND CMAKE_PREFIX_PATH "${HOUDINI_DIR}/toolkit/cmake" )

# Locate Houdini's libraries and header files.
# Registers an imported library target named 'Houdini'.
find_package( Houdini REQUIRED )

set(PYBIND11_DIR "${DEPENDENCIES_DIR}/pybind11")

add_subdirectory(${PYBIND11_DIR})

if (WIN32)
    # Suppress getenv "unsafe" warnings.
    add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
    # Suppress deprecated tbb/atomic.h and tbb/task.h warnings.
    add_compile_definitions(TBB_SUPPRESS_DEPRECATED_MESSAGES)
endif()

# Note that HoudiniOmni must be added first, because the CMakeLists for OP_Omni
# and FS_Omni reference ${HoudiniOmni_SOURCE_DIR} and ${HoudiniOmni_BINARY_DIR}.  The
# alternative is to use 'set' above to define our owm variables for these paths.
add_subdirectory(HoudiniOmni)
add_subdirectory(HoudiniOmniPy)
add_subdirectory(OP_Omni)
add_subdirectory(FS_Omni)
add_subdirectory(Tests)




