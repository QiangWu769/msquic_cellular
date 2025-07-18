//
// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
//

#pragma once

#include "quic_platform.h"

//
// 卡尔曼滤波器状态结构
//
typedef struct QUIC_KALMAN_FILTER {
    
    //
    // 状态估计值 (x)
    //
    double State;
    
    //
    // 状态估计误差协方差 (P)
    //
    double Covariance;
    
    //
    // 过程噪声协方差 (Q)
    //
    double ProcessNoise;
    
    //
    // 测量噪声协方差 (R)
    //
    double MeasurementNoise;
    
    //
    // 是否已初始化
    //
    BOOLEAN Initialized;
    
} QUIC_KALMAN_FILTER;

//
// 初始化卡尔曼滤波器
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
QuicKalmanFilterInitialize(
    _Out_ QUIC_KALMAN_FILTER* Filter,
    _In_ double InitialState,
    _In_ double InitialCovariance,
    _In_ double ProcessNoise,
    _In_ double MeasurementNoise
    );

//
// 重置卡尔曼滤波器
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
QuicKalmanFilterReset(
    _Inout_ QUIC_KALMAN_FILTER* Filter
    );

//
// 获取当前状态估计值
//
_IRQL_requires_max_(DISPATCH_LEVEL)
double
QuicKalmanFilterGetEstimate(
    _In_ const QUIC_KALMAN_FILTER* Filter
    );

//
// 更新卡尔曼滤波器
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
QuicKalmanFilterUpdate(
    _Inout_ QUIC_KALMAN_FILTER* Filter,
    _In_ double Measurement
    );

//
// 预测步骤（可选，用于动态系统）
//
_IRQL_requires_max_(DISPATCH_LEVEL)
void
QuicKalmanFilterPredict(
    _Inout_ QUIC_KALMAN_FILTER* Filter
    ); 