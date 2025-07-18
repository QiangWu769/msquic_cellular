# BBR 数据包传输状态日志记录实现

## 概述

本实现在 MsQuic 的 BBR 拥塞控制算法中添加了详细的数据包传输日志记录功能，能够记录每次数据包传输时的 BBR 状态信息，包括带宽、RTT、拥塞窗口和丢包信息。

## 实现细节

### 1. 核心功能函数

在 `src/core/bbr.c` 中添加了新的日志记录函数：

```c
_IRQL_requires_max_(DISPATCH_LEVEL)
void
BbrCongestionControlLogPacketSent(
    _In_ const QUIC_CONGESTION_CONTROL* Cc,
    _In_ uint32_t PacketSize
    )
```

该函数记录以下 BBR 状态信息：
- **PacketSize**: 数据包大小（字节）
- **EstimatedBandwidth**: 估计带宽（字节/秒）
- **SmoothedRtt**: 平滑 RTT（微秒）
- **MinRtt**: 最小 RTT（微秒）
- **CongestionWindow**: 拥塞窗口大小（字节）
- **BytesInFlight**: 当前在途字节数
- **PacketsInFlight**: 当前在途数据包数
- **BbrState**: BBR 状态（STARTUP, DRAIN, PROBE_BW, PROBE_RTT）
- **RecoveryState**: 恢复状态
- **TotalPacketsSent**: 总发送数据包数
- **TotalPacketsLost**: 总丢失数据包数
- **LossRate**: 丢包率（百分比）

### 2. 拥塞控制接口更新

#### 2.1 接口定义 (`src/core/congestion_control.h`)

添加了新的函数指针到拥塞控制结构体：

```c
void (*QuicCongestionControlLogPacketSent)(
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc,
    _In_ uint32_t PacketSize
    );
```

以及对应的内联函数：

```c
_IRQL_requires_max_(DISPATCH_LEVEL)
QUIC_INLINE
void
QuicCongestionControlLogPacketSent(
    _In_ const struct QUIC_CONGESTION_CONTROL* Cc,
    _In_ uint32_t PacketSize
    )
```

#### 2.2 BBR 实现

在 BBR 拥塞控制结构体中设置函数指针：

```c
.QuicCongestionControlLogPacketSent = BbrCongestionControlLogPacketSent,
```

#### 2.3 Cubic 实现

Cubic 算法不需要数据包级别的日志记录，因此设置为 NULL：

```c
.QuicCongestionControlLogPacketSent = NULL,
```

### 3. 调用时机

在 `BbrCongestionControlOnDataSent` 函数中，每次数据包发送时调用日志记录函数：

```c
// Log BBR state for each packet transmission
BbrCongestionControlLogPacketSent(Cc, NumRetransmittableBytes);
```

### 4. 事件跟踪和日志

#### 4.1 ETW 清单更新 (`src/manifest/MsQuicEtw.man`)

添加了新的 ETW 事件定义：

- **事件**: `QuicConnBbrPacketSent` (值: 5196)
- **模板**: `tid_CONN_BBR_PACKET_SENT`
- **消息格式**: `[conn][%1] BBR_TX: PktSize=%2 BW=%3 RTT=%4 MinRTT=%5 CWnd=%6 InFlight=%7 PktsInFlight=%8 State=%9 RState=%10 TotalSent=%11 TotalLost=%12 LossRate=%13%%`

#### 4.2 CLOG 头文件更新

更新了生成的日志头文件：
- `src/generated/linux/bbr.c.clog.h`
- `src/generated/linux/bbr.c.clog.h.lttng.h`

添加了 `ConnBbrPacketSent` 跟踪事件的宏定义和 LTTng 跟踪点。

## 使用方法

### 1. 编译

确保在编译 MsQuic 时启用了 BBR 拥塞控制和日志记录功能。

### 2. 运行时配置

使用 BBR 拥塞控制算法：

```c
QUIC_SETTINGS Settings = {0};
Settings.CongestionControlAlgorithm = QUIC_CONGESTION_CONTROL_ALGORITHM_BBR;
Settings.IsSet.CongestionControlAlgorithm = TRUE;
```

### 3. 日志收集

#### Linux (LTTng)
```bash
# 启用跟踪
lttng create msquic-session
lttng enable-event --userspace CLOG_BBR_C:ConnBbrPacketSent
lttng start

# 运行应用程序
./your_quic_application

# 停止跟踪
lttng stop
lttng view > bbr_packet_logs.txt
```

#### Windows (ETW)
使用 WPA (Windows Performance Analyzer) 或其他 ETW 工具收集 `QuicConnBbrPacketSent` 事件。

## 日志输出示例

```
[conn][0x7f8c4c000000] BBR_TX: PktSize=1200 BW=12500000 RTT=25000 MinRTT=20000 CWnd=14400 InFlight=2400 PktsInFlight=2 State=0 RState=0 TotalSent=150 TotalLost=2 LossRate=1%
```

这表示：
- 数据包大小：1200 字节
- 估计带宽：12.5 MB/s
- 平滑 RTT：25 毫秒
- 最小 RTT：20 毫秒
- 拥塞窗口：14400 字节
- 在途字节：2400 字节
- 在途数据包：2 个
- BBR 状态：STARTUP (0)
- 恢复状态：NOT_RECOVERY (0)
- 总发送：150 个数据包
- 总丢失：2 个数据包
- 丢包率：1%

## 性能考虑

- 日志记录仅在 BBR 算法中启用
- 使用高效的跟踪机制（ETW/LTTng）
- 在生产环境中可通过配置禁用详细日志记录
- 对网络性能影响最小

## 扩展性

该实现为其他拥塞控制算法（如 Cubic）提供了扩展接口，可以根据需要添加类似的日志记录功能。 