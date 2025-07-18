//
// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
//

#include "precomp.h"
#ifdef QUIC_CLOG
#include "bbr_packet_level_logging.c.clog.h"
#endif
#include "bbr_packet_level_logging.h"
#include "quic_platform.h"
#include <stdio.h>

//
// Constants
//
#define BBR_PACKET_LOG_DEFAULT_MAX_ENTRIES 10000
#define BBR_PACKET_LOG_PRINT_BUFFER_SIZE 512

// Global configuration for performance optimization
static uint32_t g_LogSamplingRate = 100;  // Log every 100 packets (was 1 = all packets)
static BOOLEAN g_EnableConsoleOutput = FALSE;  // Disable printf output for performance (was TRUE)
static uint32_t g_PacketCounter = 0;  // Counter for sampling
static BOOLEAN g_EnablePeriodicLogging = TRUE;  // Enable periodic summary logging
static uint32_t g_PeriodicLogInterval = 1000;  // Log summary every 1000 packets

//
// Helper function to convert BBR state to string
//
static const char*
BbrStateToString(BBR_STATE_NAME State)
{
    switch (State) {
        case BBR_STATE_NAME_STARTUP: return "STARTUP";
        case BBR_STATE_NAME_DRAIN: return "DRAIN";
        case BBR_STATE_NAME_PROBE_BW: return "PROBE_BW";
        case BBR_STATE_NAME_PROBE_RTT: return "PROBE_RTT";
        default: return "UNKNOWN";
    }
}

//
// Helper function to convert recovery state to string
//
static const char*
BbrRecoveryStateToString(BBR_RECOVERY_STATE_NAME State)
{
    switch (State) {
        case BBR_RECOVERY_STATE_NAME_NOT_RECOVERY: return "NOT_RECOVERY";
        case BBR_RECOVERY_STATE_NAME_CONSERVATIVE: return "CONSERVATIVE";
        case BBR_RECOVERY_STATE_NAME_GROWTH: return "GROWTH";
        default: return "UNKNOWN";
    }
}

//
// Helper function to convert event type to string
//
static const char*
BbrEventTypeToString(BBR_PACKET_EVENT_TYPE EventType)
{
    switch (EventType) {
        case BBR_PACKET_EVENT_SENT: return "PACKET_SENT";
        case BBR_PACKET_EVENT_ACKNOWLEDGED: return "PACKET_ACKED";
        case BBR_PACKET_EVENT_LOST: return "PACKET_LOST";
        case BBR_PACKET_EVENT_SPURIOUS_LOSS: return "SPURIOUS_LOSS";
        case BBR_PACKET_EVENT_STATE_CHANGE: return "STATE_CHANGE";
        case BBR_PACKET_EVENT_BANDWIDTH_UPDATE: return "BANDWIDTH_UPDATE";
        case BBR_PACKET_EVENT_RTT_UPDATE: return "RTT_UPDATE";
        case BBR_PACKET_EVENT_CWND_UPDATE: return "CWND_UPDATE";
        default: return "UNKNOWN";
    }
}

//
// Helper function to extract BBR state information
//
static void
ExtractBbrStateInfo(
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc,
    _Out_ BBR_PACKET_LOG_ENTRY* Entry
    )
{
    // Get connection and BBR structures
    QUIC_CONNECTION* Connection = QuicCongestionControlGetConnection(Cc);
    const QUIC_CONGESTION_CONTROL_BBR* Bbr = &Cc->Bbr;
    const QUIC_PATH* Path = &Connection->Paths[0];
    
    // Map BBR state to logging enum
    switch (Bbr->BbrState) {
        case 0: Entry->BbrState = BBR_STATE_NAME_STARTUP; break;  // BBR_STATE_STARTUP
        case 1: Entry->BbrState = BBR_STATE_NAME_DRAIN; break;    // BBR_STATE_DRAIN
        case 2: Entry->BbrState = BBR_STATE_NAME_PROBE_BW; break; // BBR_STATE_PROBE_BW
        case 3: Entry->BbrState = BBR_STATE_NAME_PROBE_RTT; break; // BBR_STATE_PROBE_RTT
        default: Entry->BbrState = BBR_STATE_NAME_STARTUP; break;
    }
    
    // Map recovery state to logging enum
    switch (Bbr->RecoveryState) {
        case 0: Entry->RecoveryState = BBR_RECOVERY_STATE_NAME_NOT_RECOVERY; break;
        case 1: Entry->RecoveryState = BBR_RECOVERY_STATE_NAME_CONSERVATIVE; break;
        case 2: Entry->RecoveryState = BBR_RECOVERY_STATE_NAME_GROWTH; break;
        default: Entry->RecoveryState = BBR_RECOVERY_STATE_NAME_NOT_RECOVERY; break;
    }
    
    // Extract bandwidth information
    Entry->EstimatedBandwidth = BbrCongestionControlGetBandwidth(Cc);
    Entry->MaxBandwidth = Entry->EstimatedBandwidth; // Use current as max for now
    
    // Extract delivery rate from recent ACK events
    Entry->DeliveryRate = Bbr->RecentDeliveryRate;
    
    // If no recent delivery rate is available, fall back to estimated bandwidth
    if (Entry->DeliveryRate == 0) {
        Entry->DeliveryRate = Entry->EstimatedBandwidth;
    }
    
    Entry->BandwidthSampleValid = TRUE;
    
    // Extract RTT information
    Entry->SmoothedRtt = Path->GotFirstRttSample ? Path->SmoothedRtt : 0;
    Entry->MinRtt = Bbr->MinRtt;
    Entry->LatestRtt = Path->GotFirstRttSample ? Path->LatestRttSample : 0;
    
    // Extract congestion window information
    Entry->CongestionWindow = BbrCongestionControlGetCongestionWindow(Cc);
    Entry->BytesInFlight = Bbr->BytesInFlight;
    Entry->BytesInFlightMax = Bbr->BytesInFlightMax;
    
    // Extract loss information
    Entry->TotalPacketsSent = Connection->Stats.Send.TotalPackets;
    Entry->TotalPacketsLost = Connection->Stats.Send.SuspectedLostPackets;
    Entry->LossRate = Entry->TotalPacketsSent > 0 ? 
        (uint32_t)((Entry->TotalPacketsLost * 10000) / Entry->TotalPacketsSent) : 0;
    
    // Extract pacing information
    Entry->PacingRate = Entry->EstimatedBandwidth * Bbr->PacingGain / 256;
    Entry->PacingGain = Bbr->PacingGain;
    
    // Extract additional context
    Entry->IsAppLimited = BbrCongestionControlIsAppLimited(Cc);
    Entry->SendQuantum = (uint32_t)Bbr->SendQuantum;
}

//
// Initialize the BBR packet level logger
//
_IRQL_requires_max_(PASSIVE_LEVEL)
QUIC_STATUS
BbrPacketLevelLoggingInitialize(
    _Out_ BBR_PACKET_LOGGER* Logger,
    _In_ uint32_t MaxEntries
    )
{
    if (Logger == NULL) {
        return QUIC_STATUS_INVALID_PARAMETER;
    }
    
    if (MaxEntries == 0) {
        MaxEntries = BBR_PACKET_LOG_DEFAULT_MAX_ENTRIES;
    }
    
    CxPlatZeroMemory(Logger, sizeof(BBR_PACKET_LOGGER));
    
    Logger->Entries = (BBR_PACKET_LOG_ENTRY*)CxPlatAlloc(
        MaxEntries * sizeof(BBR_PACKET_LOG_ENTRY), 'gLrB');
    if (Logger->Entries == NULL) {
        return QUIC_STATUS_OUT_OF_MEMORY;
    }
    
    CxPlatZeroMemory(Logger->Entries, MaxEntries * sizeof(BBR_PACKET_LOG_ENTRY));
    
    Logger->MaxEntries = MaxEntries;
    Logger->CurrentIndex = 0;
    Logger->TotalEntries = 0;
    Logger->Enabled = TRUE;
    
    CxPlatLockInitialize(&Logger->Lock);
    
    return QUIC_STATUS_SUCCESS;
}

//
// Cleanup the BBR packet level logger
//
_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingCleanup(
    _In_ BBR_PACKET_LOGGER* Logger
    )
{
    if (Logger == NULL) {
        return;
    }
    
    CxPlatLockUninitialize(&Logger->Lock);
    
    if (Logger->Entries != NULL) {
        CxPlatFree(Logger->Entries, 'gLrB');
        Logger->Entries = NULL;
    }
    
    Logger->Enabled = FALSE;
    Logger->MaxEntries = 0;
    Logger->CurrentIndex = 0;
    Logger->TotalEntries = 0;
}

//
// Configuration functions for performance optimization
//
_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingSetSamplingRate(
    _In_ uint32_t SamplingRate
    )
{
    g_LogSamplingRate = SamplingRate;
}

_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingSetConsoleOutput(
    _In_ BOOLEAN EnableConsoleOutput
    )
{
    g_EnableConsoleOutput = EnableConsoleOutput;
}

_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingSetPeriodicLogging(
    _In_ BOOLEAN EnablePeriodicLogging,
    _In_ uint32_t IntervalPackets
    )
{
    g_EnablePeriodicLogging = EnablePeriodicLogging;
    g_PeriodicLogInterval = IntervalPackets;
}

//
// Helper function to determine if we should log this packet
//
static BOOLEAN
ShouldLogPacket(void)
{
    g_PacketCounter++;
    return (g_PacketCounter % g_LogSamplingRate == 0);
}



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
    )
{
    if (Logger == NULL || !Logger->Enabled || Logger->Entries == NULL) {
        return;
    }
    
    // Check if we should log this packet based on sampling rate
    if (!ShouldLogPacket()) {
        return;
    }
    
    CxPlatLockAcquire(&Logger->Lock);
    
    BBR_PACKET_LOG_ENTRY* Entry = &Logger->Entries[Logger->CurrentIndex];
    
    // Basic event information
    Entry->Timestamp = CxPlatTimeUs64();
    Entry->EventType = BBR_PACKET_EVENT_SENT;
    Entry->PacketNumber = PacketNumber;
    Entry->PacketSize = PacketSize;
    
    // Extract BBR state information
    ExtractBbrStateInfo(Cc, Entry);
    
    // Update indices
    Logger->CurrentIndex = (Logger->CurrentIndex + 1) % Logger->MaxEntries;
    if (Logger->TotalEntries < Logger->MaxEntries) {
        Logger->TotalEntries++;
    }
    
    CxPlatLockRelease(&Logger->Lock);
    
    // Print immediate log entry for debugging
    if (g_EnableConsoleOutput) {
        printf("[%llu] %s: PKT=%llu SIZE=%u BBR=%s RECOVERY=%s BW=%llu bps DeliveryRate=%llu bps PacingRate=%llu bps CWND=%u SmoothedRTT=%llu us LatestRTT=%llu us MinRTT=%llu us InFlight=%u Loss=%u.%02u%% AppLimited=%s\n",
            (unsigned long long)Entry->Timestamp,
            BbrEventTypeToString(Entry->EventType),
            (unsigned long long)Entry->PacketNumber,
            Entry->PacketSize,
            BbrStateToString(Entry->BbrState),
            BbrRecoveryStateToString(Entry->RecoveryState),
            (unsigned long long)Entry->EstimatedBandwidth,
            (unsigned long long)Entry->DeliveryRate,
            (unsigned long long)Entry->PacingRate,
            Entry->CongestionWindow,
            (unsigned long long)Entry->SmoothedRtt,
            (unsigned long long)Entry->LatestRtt,
            (unsigned long long)Entry->MinRtt,
            Entry->BytesInFlight,
            Entry->LossRate / 100,
            Entry->LossRate % 100,
            Entry->IsAppLimited ? "YES" : "NO");
    }
}

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
    )
{
    if (Logger == NULL || !Logger->Enabled || Logger->Entries == NULL) {
        return;
    }
    
    // Check if we should log this packet based on sampling rate
    if (!ShouldLogPacket()) {
        return;
    }
    
    CxPlatLockAcquire(&Logger->Lock);
    
    BBR_PACKET_LOG_ENTRY* Entry = &Logger->Entries[Logger->CurrentIndex];
    
    // Basic event information
    Entry->Timestamp = AckTime;
    Entry->EventType = BBR_PACKET_EVENT_ACKNOWLEDGED;
    Entry->PacketNumber = PacketNumber;
    Entry->PacketSize = PacketSize;
    
    // Extract BBR state information
    ExtractBbrStateInfo(Cc, Entry);
    
    // Update indices
    Logger->CurrentIndex = (Logger->CurrentIndex + 1) % Logger->MaxEntries;
    if (Logger->TotalEntries < Logger->MaxEntries) {
        Logger->TotalEntries++;
    }
    
    CxPlatLockRelease(&Logger->Lock);
    
    // Print immediate log entry for debugging
    if (g_EnableConsoleOutput) {
        printf("[%llu] %s: PKT=%llu SIZE=%u BBR=%s RECOVERY=%s BW=%llu bps DeliveryRate=%llu bps PacingRate=%llu bps CWND=%u SmoothedRTT=%llu us LatestRTT=%llu us MinRTT=%llu us InFlight=%u Loss=%u.%02u%% AppLimited=%s\n",
            (unsigned long long)Entry->Timestamp,
            BbrEventTypeToString(Entry->EventType),
            (unsigned long long)Entry->PacketNumber,
            Entry->PacketSize,
            BbrStateToString(Entry->BbrState),
            BbrRecoveryStateToString(Entry->RecoveryState),
            (unsigned long long)Entry->EstimatedBandwidth,
            (unsigned long long)Entry->DeliveryRate,
            (unsigned long long)Entry->PacingRate,
            Entry->CongestionWindow,
            (unsigned long long)Entry->SmoothedRtt,
            (unsigned long long)Entry->LatestRtt,
            (unsigned long long)Entry->MinRtt,
            Entry->BytesInFlight,
            Entry->LossRate / 100,
            Entry->LossRate % 100,
            Entry->IsAppLimited ? "YES" : "NO");
    }
}

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
    )
{
    if (Logger == NULL || !Logger->Enabled || Logger->Entries == NULL) {
        return;
    }
    
    // Check if we should log this packet based on sampling rate
    if (!ShouldLogPacket()) {
        return;
    }
    
    CxPlatLockAcquire(&Logger->Lock);
    
    BBR_PACKET_LOG_ENTRY* Entry = &Logger->Entries[Logger->CurrentIndex];
    
    // Basic event information
    Entry->Timestamp = CxPlatTimeUs64();
    Entry->EventType = BBR_PACKET_EVENT_LOST;
    Entry->PacketNumber = PacketNumber;
    Entry->PacketSize = PacketSize;
    
    // Extract BBR state information
    ExtractBbrStateInfo(Cc, Entry);
    
    // Update indices
    Logger->CurrentIndex = (Logger->CurrentIndex + 1) % Logger->MaxEntries;
    if (Logger->TotalEntries < Logger->MaxEntries) {
        Logger->TotalEntries++;
    }
    
    CxPlatLockRelease(&Logger->Lock);
    
    // Print immediate log entry for debugging with emphasis on loss
    if (g_EnableConsoleOutput) {
        printf("[%llu] %s: *** PKT=%llu SIZE=%u BBR=%s RECOVERY=%s BW=%llu bps DeliveryRate=%llu bps PacingRate=%llu bps CWND=%u SmoothedRTT=%llu us LatestRTT=%llu us MinRTT=%llu us InFlight=%u Loss=%u.%02u%% AppLimited=%s ***\n",
            (unsigned long long)Entry->Timestamp,
            BbrEventTypeToString(Entry->EventType),
            (unsigned long long)Entry->PacketNumber,
            Entry->PacketSize,
            BbrStateToString(Entry->BbrState),
            BbrRecoveryStateToString(Entry->RecoveryState),
            (unsigned long long)Entry->EstimatedBandwidth,
            (unsigned long long)Entry->DeliveryRate,
            (unsigned long long)Entry->PacingRate,
            Entry->CongestionWindow,
            (unsigned long long)Entry->SmoothedRtt,
            (unsigned long long)Entry->LatestRtt,
            (unsigned long long)Entry->MinRtt,
            Entry->BytesInFlight,
            Entry->LossRate / 100,
            Entry->LossRate % 100,
            Entry->IsAppLimited ? "YES" : "NO");
    }
}

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
    )
{
    if (Logger == NULL || !Logger->Enabled || Logger->Entries == NULL) {
        return;
    }
    
    // Check if we should log this packet based on sampling rate
    if (!ShouldLogPacket()) {
        return;
    }
    
    CxPlatLockAcquire(&Logger->Lock);
    
    BBR_PACKET_LOG_ENTRY* Entry = &Logger->Entries[Logger->CurrentIndex];
    
    // Basic event information
    Entry->Timestamp = CxPlatTimeUs64();
    Entry->EventType = BBR_PACKET_EVENT_STATE_CHANGE;
    Entry->PacketNumber = 0; // N/A for state change
    Entry->PacketSize = 0;   // N/A for state change
    
    // Extract BBR state information
    ExtractBbrStateInfo(Cc, Entry);
    
    // Update indices
    Logger->CurrentIndex = (Logger->CurrentIndex + 1) % Logger->MaxEntries;
    if (Logger->TotalEntries < Logger->MaxEntries) {
        Logger->TotalEntries++;
    }
    
    CxPlatLockRelease(&Logger->Lock);
    
    // Print state change with emphasis
    if (g_EnableConsoleOutput) {
        printf("[%llu] %s: ### %s -> %s ### BW=%llu bps DeliveryRate=%llu bps PacingRate=%llu bps CWND=%u SmoothedRTT=%llu us LatestRTT=%llu us MinRTT=%llu us InFlight=%u Loss=%u.%02u%% AppLimited=%s\n",
            (unsigned long long)Entry->Timestamp,
            BbrEventTypeToString(Entry->EventType),
            BbrStateToString(OldState),
            BbrStateToString(NewState),
            (unsigned long long)Entry->EstimatedBandwidth,
            (unsigned long long)Entry->DeliveryRate,
            (unsigned long long)Entry->PacingRate,
            Entry->CongestionWindow,
            (unsigned long long)Entry->SmoothedRtt,
            (unsigned long long)Entry->LatestRtt,
            (unsigned long long)Entry->MinRtt,
            Entry->BytesInFlight,
            Entry->LossRate / 100,
            Entry->LossRate % 100,
            Entry->IsAppLimited ? "YES" : "NO");
    }
}

//
// Print all log entries to console
//
_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingPrintAll(
    _In_ const BBR_PACKET_LOGGER* Logger
    )
{
    if (Logger == NULL || !Logger->Enabled || Logger->Entries == NULL) {
        printf("BBR Packet Logger: Not initialized or disabled\n");
        return;
    }
    
    CxPlatLockAcquire((CXPLAT_LOCK*)&Logger->Lock);
    
    printf("\n=== BBR Packet Level Log Summary ===\n");
    printf("Total Entries: %u\n", Logger->TotalEntries);
    printf("Max Entries: %u\n", Logger->MaxEntries);
    printf("Current Index: %u\n", Logger->CurrentIndex);
    printf("=====================================\n");
    
    uint32_t StartIndex = 0;
    uint32_t Count = Logger->TotalEntries;
    
    // If we've wrapped around, start from the oldest entry
    if (Logger->TotalEntries == Logger->MaxEntries) {
        StartIndex = Logger->CurrentIndex;
    }
    
    for (uint32_t i = 0; i < Count; i++) {
        uint32_t Index = (StartIndex + i) % Logger->MaxEntries;
        const BBR_PACKET_LOG_ENTRY* Entry = &Logger->Entries[Index];
        
        printf("[%llu] %s: PKT=%llu SIZE=%u BBR=%s RECOVERY=%s BW=%llu bps DeliveryRate=%llu bps PacingRate=%llu bps CWND=%u SmoothedRTT=%llu us LatestRTT=%llu us MinRTT=%llu us InFlight=%u Loss=%u.%02u%% AppLimited=%s\n",
            (unsigned long long)Entry->Timestamp,
            BbrEventTypeToString(Entry->EventType),
            (unsigned long long)Entry->PacketNumber,
            Entry->PacketSize,
            BbrStateToString(Entry->BbrState),
            BbrRecoveryStateToString(Entry->RecoveryState),
            (unsigned long long)Entry->EstimatedBandwidth,
            (unsigned long long)Entry->DeliveryRate,
            (unsigned long long)Entry->PacingRate,
            Entry->CongestionWindow,
            (unsigned long long)Entry->SmoothedRtt,
            (unsigned long long)Entry->LatestRtt,
            (unsigned long long)Entry->MinRtt,
            Entry->BytesInFlight,
            Entry->LossRate / 100,
            Entry->LossRate % 100,
            Entry->IsAppLimited ? "YES" : "NO");
    }
    
    printf("=====================================\n\n");
    
    CxPlatLockRelease((CXPLAT_LOCK*)&Logger->Lock);
}

//
// Get the current log statistics
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
BbrPacketLevelLoggingGetStats(
    _In_ const BBR_PACKET_LOGGER* Logger,
    _Out_ uint32_t* TotalEntries,
    _Out_ uint32_t* CurrentIndex
    )
{
    if (Logger == NULL || TotalEntries == NULL || CurrentIndex == NULL) {
        return;
    }
    
    *TotalEntries = Logger->TotalEntries;
    *CurrentIndex = Logger->CurrentIndex;
}

//
// Clear all log entries
//
_IRQL_requires_max_(PASSIVE_LEVEL)
void
BbrPacketLevelLoggingClear(
    _In_ BBR_PACKET_LOGGER* Logger
    )
{
    if (Logger == NULL || Logger->Entries == NULL) {
        return;
    }
    
    CxPlatLockAcquire(&Logger->Lock);
    
    CxPlatZeroMemory(Logger->Entries, Logger->MaxEntries * sizeof(BBR_PACKET_LOG_ENTRY));
    Logger->CurrentIndex = 0;
    Logger->TotalEntries = 0;
    
    CxPlatLockRelease(&Logger->Lock);
    
    printf("BBR Packet Logger: All entries cleared\n");
} 