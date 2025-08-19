# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set(SOURCES
    quic_gtest.cpp
    quic_gtest.h
)

add_executable(msquictest ${SOURCES})

target_include_directories(msquictest PRIVATE ${PROJECT_SOURCE_DIR}/src/test)

set_property(TARGET msquictest PROPERTY FOLDER "${QUIC_FOLDER_PREFIX}tests")
set_property(TARGET msquictest APPEND PROPERTY BUILD_RPATH "$ORIGIN")

target_link_libraries(msquictest msquic testlib)

if (BUILD_SHARED_LIBS)
    target_link_libraries(msquictest msquic_platform)
endif()

target_link_libraries(msquictest inc gtest logging base_link)

if (WIN32)
    target_link_libraries(msquictest oldnames)
endif()

# At least /W3 must be used on all windows builds to pass compliance
if(MSVC)
    target_compile_options(msquictest PRIVATE /W3 /bigobj)
endif()

add_test(NAME msquictest
         COMMAND msquictest
         WORKING_DIRECTORY ${QUIC_OUTPUT_DIR})

# Client Upload Test Program
add_executable(quic_client_upload_test quic_client_upload_test.c)

target_include_directories(quic_client_upload_test PRIVATE ${PROJECT_SOURCE_DIR}/src/inc)

set_property(TARGET quic_client_upload_test PROPERTY FOLDER "${QUIC_FOLDER_PREFIX}tests")
set_property(TARGET quic_client_upload_test APPEND PROPERTY BUILD_RPATH "$ORIGIN")

target_link_libraries(quic_client_upload_test msquic)

if (BUILD_SHARED_LIBS)
    target_link_libraries(quic_client_upload_test msquic_platform)
endif()

target_link_libraries(quic_client_upload_test inc logging base_link)

if (WIN32)
    target_link_libraries(quic_client_upload_test oldnames)
endif()

# At least /W3 must be used on all windows builds to pass compliance
if(MSVC)
    target_compile_options(quic_client_upload_test PRIVATE /W3)
endif()
