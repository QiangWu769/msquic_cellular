#include "kalman_filter.h"

_IRQL_requires_max_(DISPATCH_LEVEL)
void
QuicKalmanFilterInitialize(
    _Out_ QUIC_KALMAN_FILTER* Filter,
    _In_ double InitialState,
    _In_ double InitialCovariance,
    _In_ double ProcessNoise,
    _In_ double MeasurementNoise
    )
{
    Filter->State = InitialState;
    Filter->Covariance = InitialCovariance;
    Filter->ProcessNoise = ProcessNoise;
    Filter->MeasurementNoise = MeasurementNoise;
    Filter->Initialized = TRUE;
}

_IRQL_requires_max_(DISPATCH_LEVEL)
void
QuicKalmanFilterReset(
    _Inout_ QUIC_KALMAN_FILTER* Filter
    )
{
    Filter->State = 0.0;
    Filter->Covariance = 1.0;
    Filter->Initialized = FALSE;
}

_IRQL_requires_max_(DISPATCH_LEVEL)
double
QuicKalmanFilterGetEstimate(
    _In_ const QUIC_KALMAN_FILTER* Filter
    )
{
    if (!Filter->Initialized) {
        return 0.0;
    }
    return Filter->State;
}

_IRQL_requires_max_(DISPATCH_LEVEL)
void
QuicKalmanFilterUpdate(
    _Inout_ QUIC_KALMAN_FILTER* Filter,
    _In_ double Measurement
    )
{
    if (!Filter->Initialized) {
        Filter->State = Measurement;
        Filter->Covariance = Filter->MeasurementNoise;
        Filter->Initialized = TRUE;
        return;
    }
    
    // 预测步骤
    double PredictedCovariance = Filter->Covariance + Filter->ProcessNoise;
    
    // 更新步骤
    double KalmanGain = PredictedCovariance / (PredictedCovariance + Filter->MeasurementNoise);
    Filter->State = Filter->State + KalmanGain * (Measurement - Filter->State);
    Filter->Covariance = (1.0 - KalmanGain) * PredictedCovariance;
    
    if (Filter->Covariance < 1e-9) {
        Filter->Covariance = 1e-9;
    }
}

_IRQL_requires_max_(DISPATCH_LEVEL)
void
QuicKalmanFilterPredict(
    _Inout_ QUIC_KALMAN_FILTER* Filter
    )
{
    if (!Filter->Initialized) {
        return;
    }
    Filter->Covariance += Filter->ProcessNoise;
} 