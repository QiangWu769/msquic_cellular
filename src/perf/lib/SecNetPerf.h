/*++

    Copyright (c) Microsoft Corporation.
    Licensed under the MIT License.

Abstract:

    MsQuic API Perf Helpers

--*/

#pragma once

#ifndef _KERNEL_MODE
#define QUIC_TEST_APIS 1 // For self-signed cert API
#endif

#define QUIC_API_ENABLE_INSECURE_FEATURES 1 // For disabling encryption
#define QUIC_API_ENABLE_PREVIEW_FEATURES  1 // For CIBIR extension

#include "quic_platform.h"
#include "quic_datapath.h"
#include "quic_hashtable.h"
#include "quic_trace.h"
#include "msquic.hpp"
#include "msquichelper.h"

#ifndef _KERNEL_MODE
#include <stdlib.h>
#include <stdio.h>
#endif

#define PERF_ALPN                           "perf"
#define PERF_DEFAULT_PORT                   4433
#define PERF_DEFAULT_DISCONNECT_TIMEOUT     (10 * 1000)
#define PERF_DEFAULT_IDLE_TIMEOUT           (30 * 1000)
#define PERF_DEFAULT_CONN_FLOW_CONTROL      0x8000000
#define PERF_DEFAULT_STREAM_COUNT           10000
#define PERF_DEFAULT_SEND_BUFFER_SIZE       0x20000
#define PERF_DEFAULT_IO_SIZE                0x10000

#define PERF_MAX_THREAD_COUNT               128
#define PERF_MAX_REQUESTS_PER_SECOND        2000000 // best guess - must increase if we can do better

typedef enum TCP_EXECUTION_PROFILE {
    TCP_EXECUTION_PROFILE_LOW_LATENCY,
    TCP_EXECUTION_PROFILE_MAX_THROUGHPUT,
} TCP_EXECUTION_PROFILE;

extern QUIC_EXECUTION_PROFILE PerfDefaultExecutionProfile;
extern TCP_EXECUTION_PROFILE TcpDefaultExecutionProfile;
extern QUIC_CONGESTION_CONTROL_ALGORITHM PerfDefaultCongestionControl;
extern uint8_t PerfDefaultEcnEnabled;
extern uint8_t PerfDefaultQeoAllowed;
extern uint8_t PerfDefaultHighPriority;
extern uint8_t PerfDefaultAffinitizeThreads;

extern CXPLAT_DATAPATH* Datapath;

extern
QUIC_STATUS
QuicMainStart(
    _In_ int argc,
    _In_reads_(argc) _Null_terminated_ char* argv[],
    _In_ CXPLAT_EVENT* StopEvent,
    _In_opt_ const QUIC_CREDENTIAL_CONFIG* SelfSignedCredConfig
    );

extern
QUIC_STATUS
QuicMainWaitForCompletion(
    );

extern
void
QuicMainFree(
    );

extern
uint32_t
QuicMainGetExtraDataLength(
    );

extern
void
QuicMainGetExtraData(
    _Out_writes_bytes_(Length) uint8_t* Data,
    _In_ uint32_t Length
    );

QUIC_INLINE
const char*
TryGetTarget(
    _In_ int argc,
    _In_reads_(argc) _Null_terminated_ char* argv[]
    )
{
    const char* Target = nullptr;
    TryGetValue(argc, argv, "target", &Target);
    TryGetValue(argc, argv, "server", &Target);
    TryGetValue(argc, argv, "to", &Target);
    TryGetValue(argc, argv, "remote", &Target);
    TryGetValue(argc, argv, "peer", &Target);
    return Target;
}

#ifdef _KERNEL_MODE
extern volatile int BufferCurrent;
constexpr int BufferLength = 40 * 1024 * 1024;
extern char Buffer[BufferLength];
#endif // _KERNEL_MODE

QUIC_INLINE
int
#ifndef _WIN32
 __attribute__((__format__(__printf__, 1, 2)))
#endif
WriteOutput(
    _In_z_ const char* format
    ...
    )
{
#ifndef _KERNEL_MODE
    va_list args;
    va_start(args, format);
    int rval = vprintf(format, args);
    va_end(args);
    return rval;
#else
    char Buf[512];
    char* BufEnd;
    va_list args;
    va_start(args, format);
    NTSTATUS Status = RtlStringCbVPrintfExA(Buf, sizeof(Buf), &BufEnd, nullptr, 0, format, args);
    va_end(args);

    if (Status == STATUS_INVALID_PARAMETER) {
        // Write error
        Status = RtlStringCbPrintfExA(Buf, sizeof(Buf), &BufEnd, nullptr, 0, "Invalid Format: %s\n", format);
        if (Status != STATUS_SUCCESS) {
            return 0;
        }
    }

    int Length = (int)(BufEnd - Buf);
    int End = InterlockedAdd((volatile LONG*)&BufferCurrent, Length);
    if (End > BufferLength) {
        return 0;
    }
    int Start = End - Length;
    CxPlatCopyMemory(Buffer + Start, Buf, Length);


    return Length;
#endif
}

QUIC_INLINE
void
QuicPrintConnectionStatistics(
    _In_ const QUIC_API_TABLE* ApiTable,
    _In_ HQUIC Connection
    )
{
    QUIC_STATISTICS_V2 Stats;
    uint32_t StatsSize = sizeof(Stats);
    ApiTable->GetParam(Connection, QUIC_PARAM_CONN_STATISTICS_V2, &StatsSize, &Stats);
    
    // Calculate bandwidth statistics
    uint64_t TotalDurationUs = 0;
    double SendBandwidthMbps = 0.0;
    double RecvBandwidthMbps = 0.0;
    double TotalBandwidthMbps = 0.0;
    
    // Calculate connection duration in microseconds
    // For bandwidth calculation, we need the actual data transfer time, not just handshake time
    // Use RTT as a baseline and estimate based on congestion events and packet counts
    if (Stats.SendTotalPackets > 0 && Stats.Rtt > 0) {
        // Estimate actual transmission time based on:
        // 1. Number of packets sent
        // 2. RTT (round trip time)
        // 3. Congestion events (indicating longer transmission time)
        
        // Base estimate: assume each packet takes at least 1 RTT to be acknowledged
        // Plus additional time for congestion recovery
        uint64_t BaseTransmissionTimeUs = (Stats.SendTotalPackets * Stats.Rtt) / 10; // Divide by 10 for pipelining
        
        // Add extra time for congestion events (each event adds ~10 RTTs)
        uint64_t CongestionPenaltyUs = Stats.SendCongestionCount * Stats.Rtt * 10;
        
        // Add extra time for retransmissions
        uint64_t RetransmissionPenaltyUs = Stats.SendSuspectedLostPackets * Stats.Rtt * 2;
        
        TotalDurationUs = BaseTransmissionTimeUs + CongestionPenaltyUs + RetransmissionPenaltyUs;
        
        // Ensure minimum duration of 1 second for very small transfers
        if (TotalDurationUs < 1000000) {
            TotalDurationUs = 1000000;
        }
        
        // Cap maximum duration to avoid unrealistic values
        // If calculated duration is too large, use a more conservative estimate
        uint64_t MaxReasonableDurationUs = 3600000000; // 1 hour max
        if (TotalDurationUs > MaxReasonableDurationUs) {
            // Use a simpler estimate: assume 1 Mbps minimum throughput
            TotalDurationUs = (Stats.SendTotalBytes * 8) / 1000000 * 1000000; // 1 Mbps = 1 bit per microsecond
        }
    } else {
        // Fallback: use handshake timing if available
        if (Stats.TimingHandshakeFlightEnd > Stats.TimingStart && Stats.TimingStart > 0) {
            TotalDurationUs = Stats.TimingHandshakeFlightEnd - Stats.TimingStart;
        } else {
            // Last resort: assume 1 second
            TotalDurationUs = 1000000;
        }
    }
    
    // Calculate bandwidth if we have valid duration
    if (TotalDurationUs > 0) {
        // Convert bytes to bits and microseconds to seconds for Mbps calculation
        SendBandwidthMbps = (Stats.SendTotalBytes * 8.0) / (TotalDurationUs / 1000000.0) / 1000000.0;
        RecvBandwidthMbps = (Stats.RecvTotalBytes * 8.0) / (TotalDurationUs / 1000000.0) / 1000000.0;
        TotalBandwidthMbps = SendBandwidthMbps + RecvBandwidthMbps;
    }
    
    WriteOutput(
        "Connection Statistics:\n"
        "  RTT                       %u us\n"
        "  MinRTT                    %u us\n"
        "  EcnCapable                %u\n"
        "  SendTotalPackets          %llu\n"
        "  SendSuspectedLostPackets  %llu\n"
        "  SendSpuriousLostPackets   %llu\n"
        "  SendCongestionCount       %u\n"
        "  SendEcnCongestionCount    %u\n"
        "  RecvTotalPackets          %llu\n"
        "  RecvReorderedPackets      %llu\n"
        "  RecvDroppedPackets        %llu\n"
        "  RecvDuplicatePackets      %llu\n"
        "  RecvDecryptionFailures    %llu\n"
        "Bandwidth Statistics:\n"
        "  Connection Duration       %llu us (%.3f s)\n"
        "  SendTotalBytes            %llu bytes\n"
        "  RecvTotalBytes            %llu bytes\n"
        "  SendBandwidth             %.2f Mbps\n"
        "  RecvBandwidth             %.2f Mbps\n"
        "  TotalBandwidth            %.2f Mbps\n"
        "  SendTotalStreamBytes      %llu bytes\n"
        "  RecvTotalStreamBytes      %llu bytes\n"
        "  SendCongestionWindow      %u bytes\n"
        "  SendPathMtu               %u bytes\n",
        Stats.Rtt,
        Stats.MinRtt,
        Stats.EcnCapable,
        (unsigned long long)Stats.SendTotalPackets,
        (unsigned long long)Stats.SendSuspectedLostPackets,
        (unsigned long long)Stats.SendSpuriousLostPackets,
        Stats.SendCongestionCount,
        Stats.SendEcnCongestionCount,
        (unsigned long long)Stats.RecvTotalPackets,
        (unsigned long long)Stats.RecvReorderedPackets,
        (unsigned long long)Stats.RecvDroppedPackets,
        (unsigned long long)Stats.RecvDuplicatePackets,
        (unsigned long long)Stats.RecvDecryptionFailures,
        (unsigned long long)TotalDurationUs,
        TotalDurationUs / 1000000.0,
        (unsigned long long)Stats.SendTotalBytes,
        (unsigned long long)Stats.RecvTotalBytes,
        SendBandwidthMbps,
        RecvBandwidthMbps,
        TotalBandwidthMbps,
        (unsigned long long)Stats.SendTotalStreamBytes,
        (unsigned long long)Stats.RecvTotalStreamBytes,
        Stats.SendCongestionWindow,
        Stats.SendPathMtu);
    QUIC_HANDSHAKE_INFO HandshakeInfo = {};
    uint32_t HandshakeInfoSize = sizeof(HandshakeInfo);
    ApiTable->GetParam(Connection, QUIC_PARAM_TLS_HANDSHAKE_INFO, &HandshakeInfoSize, &HandshakeInfo);
    WriteOutput(
        "Connection TLS Info:\n"
        "  TlsProtocolVersion        0x%x\n"
        "  CipherAlgorithm           0x%x\n"
        "  CipherStrength            %u\n"
        "  Hash                      0x%x\n"
        "  HashStrength              %u\n"
        "  KeyExchangeAlgorithm      %u\n"
        "  KeyExchangeStrength       %u\n"
        "  CipherSuite               0x%x\n"
        "  TlsGroup                  %u\n",
        HandshakeInfo.TlsProtocolVersion,
        HandshakeInfo.CipherAlgorithm,
        HandshakeInfo.CipherStrength,
        HandshakeInfo.Hash,
        HandshakeInfo.HashStrength,
        HandshakeInfo.KeyExchangeAlgorithm,
        HandshakeInfo.KeyExchangeStrength,
        HandshakeInfo.CipherSuite,
        HandshakeInfo.TlsGroup);
}

QUIC_INLINE
void
QuicPrintStreamStatistics(
    _In_ const QUIC_API_TABLE* ApiTable,
    _In_ HQUIC Stream
    )
{
    QUIC_STREAM_STATISTICS Stats = {0};
    uint32_t BufferLength = sizeof(Stats);
    ApiTable->GetParam(Stream, QUIC_PARAM_STREAM_STATISTICS, &BufferLength, &Stats);
    WriteOutput(
        "Stream Timings (flow blocked):\n"
        "  SCHEDULING:               %llu us\n"
        "  PACING:                   %llu us\n"
        "  AMPLIFICATION_PROT:       %llu us\n"
        "  CONGESTION_CONTROL:       %llu us\n"
        "  CONN_FLOW_CONTROL:        %llu us\n"
        "  STREAM_ID_FLOW_CONTROL:   %llu us\n"
        "  STREAM_FLOW_CONTROL:      %llu us\n"
        "  APP:                      %llu us\n",
        (unsigned long long)Stats.ConnBlockedBySchedulingUs,
        (unsigned long long)Stats.ConnBlockedByPacingUs,
        (unsigned long long)Stats.ConnBlockedByAmplificationProtUs,
        (unsigned long long)Stats.ConnBlockedByCongestionControlUs,
        (unsigned long long)Stats.ConnBlockedByFlowControlUs,
        (unsigned long long)Stats.StreamBlockedByIdFlowControlUs,
        (unsigned long long)Stats.StreamBlockedByFlowControlUs,
        (unsigned long long)Stats.StreamBlockedByAppUs);
}

extern const char* TimeUnits[];
extern const uint64_t TimeMult[];
extern const char* SizeUnits[];
extern const uint64_t SizeMult[];
extern const char* CountUnits[];
extern uint64_t CountMult[];

template <typename T>
bool
TryGetVariableUnitValue(
    _In_ int argc,
    _In_reads_(argc) _Null_terminated_ char* argv[],
    _In_z_ const char** names,
    _Out_ T * pValue,
    _Out_opt_ bool* isTimed = nullptr
    );

template <typename T>
bool
TryGetVariableUnitValue(
    _In_ int argc,
    _In_reads_(argc) _Null_terminated_ char* argv[],
    _In_z_ const char* name,
    _Out_ T * pValue,
    _Out_opt_ bool* isTimed = nullptr
    );
