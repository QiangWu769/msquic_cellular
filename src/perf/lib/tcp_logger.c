#include "tcp_logger.h"
#include "tcp_ss_logger.h"
#include <stddef.h>  // 添加此行以定义NULL
#include "msquic.h" // 添加此行以获取QUIC状态码定义

// 此实现是一个兼容层，将原有的eBPF日志器API映射到新的ss日志器API

// 简单的包装结构体，将TCP_LOGGER映射到TCP_SS_LOGGER
struct _TCP_LOGGER {
    TCP_SS_LOGGER* SsLogger;
};

// 全局默认实例
static TCP_LOGGER g_TcpLogger = {0};

_IRQL_requires_max_(DISPATCH_LEVEL)
TCP_LOGGER* TcpLoggerGetDefault(void) {
    if (g_TcpLogger.SsLogger == NULL) {
        g_TcpLogger.SsLogger = TcpSsLoggerGetDefault();
    }
    return &g_TcpLogger;
}

_IRQL_requires_max_(PASSIVE_LEVEL)
QUIC_STATUS
TcpLoggerInitialize(
    _In_ TCP_LOGGER* Logger,
    _In_ uint32_t MaxLogEntries,
    _In_ uint16_t TargetPort
    )
{
    if (Logger == NULL) return QUIC_STATUS_INVALID_PARAMETER;
    return TcpSsLoggerInitialize(Logger->SsLogger, MaxLogEntries, TargetPort);
}

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerCleanup(_In_ TCP_LOGGER* Logger) {
    if (Logger == NULL) return;
    TcpSsLoggerCleanup(Logger->SsLogger);
}

_IRQL_requires_max_(PASSIVE_LEVEL)
QUIC_STATUS TcpLoggerStart(_In_ TCP_LOGGER* Logger) {
    if (Logger == NULL) return QUIC_STATUS_INVALID_PARAMETER;
    return TcpSsLoggerStart(Logger->SsLogger);
}

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerStop(_In_ TCP_LOGGER* Logger) {
    if (Logger == NULL) return;
    TcpSsLoggerStop(Logger->SsLogger);
}

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerPrintAll(_In_ const TCP_LOGGER* Logger) {
    if (Logger == NULL) return;
    TcpSsLoggerPrintAll(Logger->SsLogger);
}

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerSetOutputOptions(
    _In_ TCP_LOGGER* Logger,
    _In_ BOOLEAN EnableConsoleOutput,
    _In_ uint32_t SamplingInterval
    )
{
    if (Logger == NULL) return;
    TcpSsLoggerSetOutputOptions(Logger->SsLogger, EnableConsoleOutput, SamplingInterval);
}

_IRQL_requires_max_(PASSIVE_LEVEL)
void TcpLoggerSetLogFile(_In_ TCP_LOGGER* Logger, _In_ const char* FilePath) {
    if (Logger == NULL) return;
    TcpSsLoggerSetLogFile(Logger->SsLogger, FilePath);
} 