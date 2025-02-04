cmake_minimum_required( VERSION 3.13 )

set( exe_name test_he_load_usd )

project ( ${exe_name} )

add_executable (${exe_name} test_he_load_usd.cpp)

# Link against the Houdini libraries, and add required include directories and
# compile definitions.
target_link_libraries( ${exe_name} 
    Houdini
)

set_target_properties( ${exe_name} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${BINARY_INSTALL_DIR}/Tests
    # Put project in "Tests" Visual Studio folder.
    FOLDER Tests
)
