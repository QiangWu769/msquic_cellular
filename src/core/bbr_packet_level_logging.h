//
// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
//

#pragma once

#include "quic_platform.h"

#ifdef __cplusplus
extern "C" {
#endif

//
// Forward declarations
//
struct QUIC_CONGESTION_CONTROL;

//
// External function declarations needed for BBR state extraction
//
uint64_t
BbrCongestionControlGetBandwidth(
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc
    );

uint32_t
BbrCongestionControlGetCongestionWindow(
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc
    );

BOOLEAN
BbrCongestionControlIsAppLimited(
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc
    );

struct QUIC_CONNECTION*
QuicCongestionControlGetConnection(
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc
    );



//
// BBR Packet Level Logging Event Types
//
typedef enum BBR_PACKET_EVENT_TYPE {
    BBR_PACKET_EVENT_SENT = 0,
    BBR_PACKET_EVENT_ACKNOWLEDGED = 1,
    BBR_PACKET_EVENT_LOST = 2,
    BBR_PACKET_EVENT_SPURIOUS_LOSS = 3,
    BBR_PACKET_EVENT_STATE_CHANGE = 4,
    BBR_PACKET_EVENT_BANDWIDTH_UPDATE = 5,
    BBR_PACKET_EVENT_RTT_UPDATE = 6,
    BBR_PACKET_EVENT_CWND_UPDATE = 7
} BBR_PACKET_EVENT_TYPE;

//
// BBR State Names for Logging
//
typedef enum BBR_STATE_NAME {
    BBR_STATE_NAME_STARTUP = 0,
    BBR_STATE_NAME_DRAIN = 1,
    BBR_STATE_NAME_PROBE_BW = 2,
    BBR_STATE_NAME_PROBE_RTT = 3
} BBR_STATE_NAME;

//
// BBR Recovery State Names for Logging
//
typedef enum BBR_RECOVERY_STATE_NAME {
    BBR_RECOVERY_STATE_NAME_NOT_RECOVERY = 0,
    BBR_RECOVERY_STATE_NAME_CONSERVATIVE = 1,
    BBR_RECOVERY_STATE_NAME_GROWTH = 2
} BBR_RECOVERY_STATE_NAME;

//
// BBR Packet Level Log Entry
//
typedef struct BBR_PACKET_LOG_ENTRY {
    uint64_t Timestamp;                     // Microseconds since epoch
    BBR_PACKET_EVENT_TYPE EventType;        // Type of event
    uint64_t PacketNumber;                  // QUIC packet number
    uint32_t PacketSize;                    // Size of packet in bytes
    
    // BBR State Information
    BBR_STATE_NAME BbrState;                // Current BBR state
    BBR_RECOVERY_STATE_NAME RecoveryState;  // Current recovery state
    
    // Bandwidth Information
    uint64_t EstimatedBandwidth;            // Estimated bandwidth in bps
    uint64_t MaxBandwidth;                  // Maximum observed bandwidth
    uint64_t DeliveryRate;                  // Current delivery rate in bps
    BOOLEAN BandwidthSampleValid;           // Whether bandwidth sample is valid
    
    // RTT Information
    uint64_t SmoothedRtt;                   // Smoothed RTT in microseconds
    uint64_t MinRtt;                        // Minimum RTT in microseconds
    uint64_t LatestRtt;                     // Latest RTT measurement
    
    // Congestion Window Information
    uint32_t CongestionWindow;              // Current congestion window
    uint32_t BytesInFlight;                 // Bytes currently in flight
    uint32_t BytesInFlightMax;              // Maximum bytes in flight
    
    // Loss Information
    uint64_t TotalPacketsSent;              // Total packets sent so far
    uint64_t TotalPacketsLost;              // Total packets lost so far
    uint32_t LossRate;                      // Loss rate in basis points (0-10000)
    
    // Pacing Information
    uint64_t PacingRate;                    // Current pacing rate
    uint32_t PacingGain;                    // Current pacing gain
    
    // Additional Context
    BOOLEAN IsAppLimited;                   // Whether application limited
    uint32_t SendQuantum;                   // Send quantum size
    
} BBR_PACKET_LOG_ENTRY;

//
// BBR Packet Level Logger
//
typedef struct BBR_PACKET_LOGGER {
    BOOLEAN Enabled;                        // Whether logging is enabled
    uint32_t MaxEntries;                    // Maximum number of log entries
    uint32_t CurrentIndex;                  // Current log entry index
    uint32_t TotalEntries;                  // Total entries logged
    BBR_PACKET_LOG_ENTRY* Entries;          // Array of log entries
    CXPLAT_LOCK Lock;                       // Lock for thread safety
} BBR_PACKET_LOGGER;

//
// Function Declarations
//

//
// Initialize the BBR packet level logger
//
_IRQL_requires_max_(PASSIVE_LEVEL)
QUIC_STATUS
BbrPacketLevelLoggingInitialize(
    _Out_ BBR_PACKET_LOGGER* Logger,
    _In_ uint32_t MaxEntries
    );

//
// Cleanup the BBR packet level logger
//
_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingCleanup(
    _In_ BBR_PACKET_LOGGER* Logger
    );

//
// Performance optimization functions
//

//
// Set logging sampling rate to reduce performance impact
// SamplingRate: Log every N packets (1 = all packets, 10 = every 10th packet)
//
void
BbrPacketLevelLoggingSetSamplingRate(
    _In_ uint32_t SamplingRate
    );

//
// Enable/disable console output for performance
// Setting to FALSE will still log to memory but skip printf calls
//
void
BbrPacketLevelLoggingSetConsoleOutput(
    _In_ BOOLEAN EnableConsoleOutput
    );

//
// Record a packet sent event
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
BbrPacketLevelLoggingRecordPacketSent(
    _In_ BBR_PACKET_LOGGER* Logger,
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc,
    _In_ uint64_t PacketNumber,
    _In_ uint32_t PacketSize
    );

//
// Record a packet acknowledged event
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
BbrPacketLevelLoggingRecordPacketAcknowledged(
    _In_ BBR_PACKET_LOGGER* Logger,
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc,
    _In_ uint64_t PacketNumber,
    _In_ uint32_t PacketSize,
    _In_ uint64_t AckTime
    );

//
// Record a packet lost event
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
BbrPacketLevelLoggingRecordPacketLost(
    _In_ BBR_PACKET_LOGGER* Logger,
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc,
    _In_ uint64_t PacketNumber,
    _In_ uint32_t PacketSize
    );

//
// Record a BBR state change event
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
BbrPacketLevelLoggingRecordStateChange(
    _In_ BBR_PACKET_LOGGER* Logger,
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc,
    _In_ BBR_STATE_NAME OldState,
    _In_ BBR_STATE_NAME NewState
    );

//
// Print all log entries to console
//
_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingPrintAll(
    _In_ const BBR_PACKET_LOGGER* Logger
    );

//
// Get the current log statistics
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
BbrPacketLevelLoggingGetStats(
    _In_ const BBR_PACKET_LOGGER* Logger,
    _Out_ uint32_t* TotalEntries,
    _Out_ uint32_t* CurrentIndex
    );

//
// Clear all log entries
//
_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingClear(
    _In_ BBR_PACKET_LOGGER* Logger
    );

#ifdef __cplusplus
}
#endif 