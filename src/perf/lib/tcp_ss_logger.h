/*++

    Copyright (c) Microsoft Corporation.
    Licensed under the MIT License.

Abstract:

    Public API for the TCP socket statistics logger using ss command.

--*/

#pragma once

#include <stdint.h>  // For uint32_t, uint64_t, etc.

#ifdef __cplusplus
extern "C" {
#endif

// 直接定义 QUIC_STATUS，避免依赖 msquic_posix.h
#ifndef QUIC_STATUS
typedef unsigned int QUIC_STATUS;
#endif

// 定义 BOOLEAN
#ifndef BOOLEAN
typedef unsigned char BOOLEAN;
#endif

// BBR state/mode enum
typedef enum TCP_SS_BBR_STATE {
    TCP_BBR_STARTUP,
    TCP_BBR_DRAIN,
    TCP_BBR_PROBE_BW,
    TCP_BBR_PROBE_RTT,
    TCP_BBR_UNKNOWN
} TCP_SS_BBR_STATE;

// 日志条目数据结构，存储从ss命令提取的信息
typedef struct TCP_SS_LOG_ENTRY {
    uint64_t Timestamp;          // 时间戳 (ns)
    uint32_t SourceAddr;         // 源地址
    uint32_t DestAddr;           // 目标地址
    uint16_t SourcePort;         // 源端口
    uint16_t DestPort;           // 目标端口
    uint32_t SndCwnd;            // 发送拥塞窗口
    double   RttMs;              // RTT (ms)
    double   RttVarMs;           // RTT 方差 (ms)
    uint32_t PacketsInFlight;    // 传输中的包数量
    uint32_t LostPackets;        // 丢失的包数量
    uint32_t RetransSegs;        // 重传段数量
    uint32_t SackedSegs;         // SACK段数量
    double   SendRateBps;        // 发送速率 (bps)
    double   PacingRateBps;      // 调速速率 (bps)
    double   DeliveryRateBps;    // 传输速率 (bps)
    uint64_t BytesSent;          // 发送的字节数
    uint64_t BytesAcked;         // 已确认的字节数
    uint64_t BytesRetrans;       // 重传的字节数
    TCP_SS_BBR_STATE BbrState;   // BBR状态
    double   BbrBandwidthBps;    // BBR带宽估计 (bps)
    double   BbrMinRttMs;        // BBR最小RTT (ms)
    double   BbrPacingGain;      // BBR调速增益
    double   BbrCwndGain;        // BBR拥塞窗口增益
    BOOLEAN  IsBBR;              // 是否为BBR连接
} TCP_SS_LOG_ENTRY;

// 定义IRQL级别（模拟Windows内核的IRQL概念）
#ifndef _IRQL_requires_max_
#define _IRQL_requires_max_(irql)
#endif

#ifndef _In_
#define _In_
#endif

#ifndef _In_opt_
#define _In_opt_
#endif

// 不透明的日志器结构体指针
struct _TCP_SS_LOGGER;
typedef struct _TCP_SS_LOGGER TCP_SS_LOGGER;

// 函数原型
_IRQL_requires_max_(DISPATCH_LEVEL)
TCP_SS_LOGGER* TcpSsLoggerGetDefault(void);

_IRQL_requires_max_(PASSIVE_LEVEL)
QUIC_STATUS
TcpSsLoggerInitialize(
    _In_ TCP_SS_LOGGER* Logger,
    _In_ uint32_t MaxLogEntries,
    _In_ uint16_t TargetPort
    );

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpSsLoggerCleanup(_In_ TCP_SS_LOGGER* Logger);

_IRQL_requires_max_(PASSIVE_LEVEL)
QUIC_STATUS TcpSsLoggerStart(_In_ TCP_SS_LOGGER* Logger);

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpSsLoggerStop(_In_ TCP_SS_LOGGER* Logger);

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpSsLoggerPrintAll(_In_ const TCP_SS_LOGGER* Logger);

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpSsLoggerSetOutputOptions(
    _In_ TCP_SS_LOGGER* Logger,
    _In_ BOOLEAN EnableConsoleOutput,
    _In_ uint32_t SamplingInterval
    );

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpSsLoggerSetLogFile(_In_ TCP_SS_LOGGER* Logger, _In_ const char* FilePath);

#ifdef __cplusplus
}
#endif 