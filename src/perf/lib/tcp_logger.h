/*++

    Copyright (c) Microsoft Corporation.
    Licensed under the MIT License.

Abstract:

    Public API for the TCP logger compatibility layer.
    This layer provides a consistent API regardless of whether 
    we're using eBPF or ss-based logging.

--*/

#pragma once

#include <stdint.h>  // For uint32_t, uint64_t, etc.

#ifdef __cplusplus
extern "C" {
#endif

// Make sure QUIC_STATUS and BOOLEAN are defined
#ifndef QUIC_STATUS
typedef unsigned int QUIC_STATUS;
#endif

#ifndef BOOLEAN
typedef unsigned char BOOLEAN;
#endif

// Define IRQL levels (to match Windows semantics)
#ifndef _IRQL_requires_max_
#define _IRQL_requires_max_(irql)
#endif

#ifndef _In_
#define _In_
#endif

#ifndef _In_opt_
#define _In_opt_
#endif

// Opaque logger structure
struct _TCP_LOGGER;
typedef struct _TCP_LOGGER TCP_LOGGER;

// Function prototypes - these match the original eBPF logger API
_IRQL_requires_max_(DISPATCH_LEVEL)
TCP_LOGGER* TcpLoggerGetDefault(void);

_IRQL_requires_max_(PASSIVE_LEVEL)
QUIC_STATUS
TcpLoggerInitialize(
    _In_ TCP_LOGGER* Logger,
    _In_ uint32_t MaxLogEntries,
    _In_ uint16_t TargetPort
    );

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerCleanup(_In_ TCP_LOGGER* Logger);

_IRQL_requires_max_(PASSIVE_LEVEL)
QUIC_STATUS TcpLoggerStart(_In_ TCP_LOGGER* Logger);

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerStop(_In_ TCP_LOGGER* Logger);

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerPrintAll(_In_ const TCP_LOGGER* Logger);

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerSetOutputOptions(
    _In_ TCP_LOGGER* Logger,
    _In_ BOOLEAN EnableConsoleOutput,
    _In_ uint32_t SamplingInterval
    );

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerSetLogFile(_In_ TCP_LOGGER* Logger, _In_ const char* FilePath);

#ifdef __cplusplus
}
#endif 