# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# List of source files for the perflib static library.
set(SOURCES
    PerfClient.cpp
    PerfServer.cpp
    SecNetPerfMain.cpp
    Tcp.cpp
    tcp_logger.c
    tcp_ss_logger.c
)

# Define the perflib library target.
add_library(perflib STATIC ${SOURCES})

# Set the folder property for IDEs like Visual Studio.
set_property(TARGET perflib PROPERTY FOLDER "${QUIC_FOLDER_PREFIX}perf")

# Publicly link perflib, making its headers available to dependents.
target_link_libraries(perflib PUBLIC)

# Link perflib against other internal msquic libraries.
target_link_libraries(perflib PRIVATE inc warnings)

# Make the public headers of this directory available to other targets.
target_include_directories(perflib PUBLIC ${CMAKE_CURRENT_LIST_DIR} ../../inc)

# Suppress a specific warning in MSVC builds.
if(MSVC)
    target_compile_options(perflib PUBLIC /wd4459)
endif()