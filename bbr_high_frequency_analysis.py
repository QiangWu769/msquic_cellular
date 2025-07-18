#!/usr/bin/env python3
"""
BBR高频网络变化分析
模拟每2秒网络条件变化的场景，对比最大值和平均值滤波器的表现
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

def generate_high_frequency_network():
    """生成每2秒变化的网络带宽模式"""
    # 总时长60秒，每2秒一个变化周期
    total_time = 60
    change_interval = 2
    sample_rate = 10  # 每秒10个采样点
    
    time = np.linspace(0, total_time, total_time * sample_rate)
    bandwidth = np.zeros_like(time)
    
    # 定义每2秒的带宽模式（模拟5G网络的实际变化）
    bw_patterns = [200, 80, 150, 40, 180, 60, 120, 30, 160, 90, 
                   140, 50, 190, 70, 110, 45, 170, 85, 130, 55,
                   175, 65, 145, 35, 185, 75, 125, 25, 165, 95]
    
    for i, pattern_bw in enumerate(bw_patterns):
        start_idx = int(i * change_interval * sample_rate)
        end_idx = int((i + 1) * change_interval * sample_rate)
        if end_idx > len(bandwidth):
            break
            
        # 在每个2秒周期内添加一些噪声和微变化
        segment = time[start_idx:end_idx]
        noise = np.random.normal(0, pattern_bw * 0.1, len(segment))
        micro_changes = pattern_bw * 0.2 * np.sin(4 * np.pi * (segment - segment[0]))
        
        bandwidth[start_idx:end_idx] = pattern_bw + noise + micro_changes
    
    return time, bandwidth

def apply_max_filter_windowed(data, window_size_seconds=10, sample_rate=10):
    """应用基于时间窗口的最大值滤波器"""
    window_samples = int(window_size_seconds * sample_rate)
    filtered = np.zeros_like(data)
    
    for i in range(len(data)):
        start_idx = max(0, i - window_samples + 1)
        filtered[i] = np.max(data[start_idx:i+1])
    
    return filtered

def apply_avg_filter_windowed(data, window_size_seconds=10, sample_rate=10):
    """应用基于时间窗口的平均值滤波器"""
    window_samples = int(window_size_seconds * sample_rate)
    filtered = np.zeros_like(data)
    
    for i in range(len(data)):
        start_idx = max(0, i - window_samples + 1)
        filtered[i] = np.mean(data[start_idx:i+1])
    
    return filtered

def calculate_delay_impact(bandwidth_true, bandwidth_est, send_rate):
    """计算延迟影响"""
    # 简化的队列延迟模型：当发送速率超过真实带宽时产生排队延迟
    queue_buildup = np.maximum(0, send_rate - bandwidth_true)
    # 累积队列长度（字节）
    queue_length = np.cumsum(queue_buildup) / 10  # 除以采样率转换为秒
    # 队列延迟（毫秒）
    queue_delay = queue_length / (bandwidth_true + 1) * 1000  # 避免除零
    
    return queue_delay

def simulate_probebw_with_high_frequency():
    """模拟高频变化下的ProbeBW行为"""
    time, true_bw = generate_high_frequency_network()
    
    # 应用不同的滤波器
    max_bw_est = apply_max_filter_windowed(true_bw)
    avg_bw_est = apply_avg_filter_windowed(true_bw)
    
    # 模拟BBR增益循环（简化版，每8秒一个完整周期）
    cycle_length = 8  # 秒
    gains = []
    gain_pattern = [1.25, 0.75, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]  # 8个阶段
    
    for t in time:
        cycle_pos = (t % cycle_length) / cycle_length
        gain_idx = int(cycle_pos * len(gain_pattern))
        gains.append(gain_pattern[gain_idx])
    
    gains = np.array(gains)
    
    # 计算发送速率
    max_send_rate = max_bw_est * gains
    avg_send_rate = avg_bw_est * gains
    
    # 计算延迟影响
    max_delay = calculate_delay_impact(true_bw, max_bw_est, max_send_rate)
    avg_delay = calculate_delay_impact(true_bw, avg_bw_est, avg_send_rate)
    
    return time, true_bw, max_bw_est, avg_bw_est, max_send_rate, avg_send_rate, max_delay, avg_delay, gains

def plot_detailed_analysis():
    """绘制详细的高频分析图"""
    time, true_bw, max_bw_est, avg_bw_est, max_send_rate, avg_send_rate, max_delay, avg_delay, gains = simulate_probebw_with_high_frequency()
    
    fig = plt.figure(figsize=(16, 12))
    gs = GridSpec(4, 2, figure=fig, hspace=0.4, wspace=0.3)
    
    # 1. 真实带宽和估计带宽
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(time, true_bw, 'k-', linewidth=2, label='真实带宽', alpha=0.7)
    ax1.plot(time, max_bw_est, 'r-', linewidth=2, label='最大值滤波器估计')
    ax1.plot(time, avg_bw_est, 'b-', linewidth=2, label='平均值滤波器估计')
    ax1.set_title('高频网络变化下的带宽估计 (每2秒变化)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('带宽 (Mbps)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 添加变化点标记
    for i in range(0, 60, 2):
        ax1.axvline(x=i, color='gray', linestyle='--', alpha=0.3)
    
    # 2. BBR增益循环
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(time, gains, 'g-', linewidth=2)
    ax2.set_title('BBR增益循环', fontweight='bold')
    ax2.set_ylabel('增益系数')
    ax2.set_ylim(0.5, 1.5)
    ax2.grid(True, alpha=0.3)
    
    # 3. 发送速率对比
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.plot(time, true_bw, 'k--', alpha=0.5, label='网络容量')
    ax3.plot(time, max_send_rate, 'r-', linewidth=2, label='最大值滤波器')
    ax3.plot(time, avg_send_rate, 'b-', linewidth=2, label='平均值滤波器')
    ax3.set_title('发送速率对比', fontweight='bold')
    ax3.set_ylabel('发送速率 (Mbps)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. 队列延迟对比
    ax4 = fig.add_subplot(gs[2, :])
    ax4.plot(time, max_delay, 'r-', linewidth=2, label='最大值滤波器延迟')
    ax4.plot(time, avg_delay, 'b-', linewidth=2, label='平均值滤波器延迟')
    ax4.set_title('队列延迟对比', fontweight='bold')
    ax4.set_ylabel('延迟 (ms)')
    ax4.set_xlabel('时间 (秒)')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. 带宽利用率窗口分析
    ax5 = fig.add_subplot(gs[3, 0])
    window_size = 50  # 5秒窗口
    max_utilization = []
    avg_utilization = []
    time_windows = []
    
    for i in range(window_size, len(time)):
        window_true = true_bw[i-window_size:i]
        window_max_send = max_send_rate[i-window_size:i]
        window_avg_send = avg_send_rate[i-window_size:i]
        
        # 计算有效利用率（不超过真实带宽的部分）
        max_util = np.mean(np.minimum(window_max_send, window_true)) / np.mean(window_true) * 100
        avg_util = np.mean(np.minimum(window_avg_send, window_true)) / np.mean(window_true) * 100
        
        max_utilization.append(max_util)
        avg_utilization.append(avg_util)
        time_windows.append(time[i])
    
    ax5.plot(time_windows, max_utilization, 'r-', linewidth=2, label='最大值滤波器')
    ax5.plot(time_windows, avg_utilization, 'b-', linewidth=2, label='平均值滤波器')
    ax5.set_title('带宽利用率 (5秒滑动窗口)', fontweight='bold')
    ax5.set_ylabel('利用率 (%)')
    ax5.set_xlabel('时间 (秒)')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    # 6. 过载程度分析
    ax6 = fig.add_subplot(gs[3, 1])
    max_overload = np.maximum(0, max_send_rate - true_bw) / true_bw * 100
    avg_overload = np.maximum(0, avg_send_rate - true_bw) / true_bw * 100
    
    ax6.plot(time, max_overload, 'r-', linewidth=2, label='最大值滤波器')
    ax6.plot(time, avg_overload, 'b-', linewidth=2, label='平均值滤波器')
    ax6.set_title('过载程度 (发送速率超出网络容量)', fontweight='bold')
    ax6.set_ylabel('过载百分比 (%)')
    ax6.set_xlabel('时间 (秒)')
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    
    plt.suptitle('BBR在高频网络变化下的详细行为分析', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig('bbr_high_frequency_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    return time, true_bw, max_bw_est, avg_bw_est, max_delay, avg_delay

def calculate_performance_metrics(time, true_bw, max_bw_est, avg_bw_est, max_delay, avg_delay):
    """计算详细的性能指标"""
    print("=" * 60)
    print("BBR高频网络变化性能分析报告")
    print("=" * 60)
    
    # 带宽估计准确性
    max_mae = np.mean(np.abs(max_bw_est - true_bw))
    avg_mae = np.mean(np.abs(avg_bw_est - true_bw))
    
    print(f"\n📊 带宽估计准确性 (平均绝对误差):")
    print(f"   最大值滤波器: {max_mae:.2f} Mbps")
    print(f"   平均值滤波器: {avg_mae:.2f} Mbps")
    print(f"   平均值滤波器准确性提升: {((max_mae - avg_mae) / max_mae * 100):.1f}%")
    
    # 延迟性能
    max_delay_avg = np.mean(max_delay)
    avg_delay_avg = np.mean(avg_delay)
    max_delay_p95 = np.percentile(max_delay, 95)
    avg_delay_p95 = np.percentile(avg_delay, 95)
    
    print(f"\n⏱️  延迟性能:")
    print(f"   最大值滤波器 - 平均延迟: {max_delay_avg:.2f} ms")
    print(f"   平均值滤波器 - 平均延迟: {avg_delay_avg:.2f} ms")
    print(f"   延迟改善: {((max_delay_avg - avg_delay_avg) / max_delay_avg * 100):.1f}%")
    print(f"   最大值滤波器 - P95延迟: {max_delay_p95:.2f} ms")
    print(f"   平均值滤波器 - P95延迟: {avg_delay_p95:.2f} ms")
    print(f"   P95延迟改善: {((max_delay_p95 - avg_delay_p95) / max_delay_p95 * 100):.1f}%")
    
    # 稳定性分析
    max_stability = np.std(max_bw_est)
    avg_stability = np.std(avg_bw_est)
    
    print(f"\n📈 估计稳定性 (标准差):")
    print(f"   最大值滤波器: {max_stability:.2f} Mbps")
    print(f"   平均值滤波器: {avg_stability:.2f} Mbps")
    print(f"   稳定性提升: {((max_stability - avg_stability) / max_stability * 100):.1f}%")
    
    # 响应时间分析
    # 计算对网络变化的响应时间（简化分析）
    change_points = list(range(0, 60, 2))  # 每2秒的变化点
    max_response_times = []
    avg_response_times = []
    
    for cp in change_points[1:]:  # 跳过第一个点
        cp_idx = int(cp * 10)  # 转换为数组索引
        if cp_idx < len(true_bw) - 20:  # 确保有足够的后续数据
            # 在变化点后2秒内寻找滤波器响应
            window = slice(cp_idx, cp_idx + 20)
            true_change = np.mean(true_bw[window]) - true_bw[cp_idx - 1]
            
            if abs(true_change) > 10:  # 只考虑显著变化
                max_response = np.mean(max_bw_est[window]) - max_bw_est[cp_idx - 1]
                avg_response = np.mean(avg_bw_est[window]) - avg_bw_est[cp_idx - 1]
                
                max_response_times.append(abs(max_response / true_change) if true_change != 0 else 0)
                avg_response_times.append(abs(avg_response / true_change) if true_change != 0 else 0)
    
    if max_response_times and avg_response_times:
        print(f"\n⚡ 响应性能 (变化跟踪比率):")
        print(f"   最大值滤波器: {np.mean(max_response_times):.3f}")
        print(f"   平均值滤波器: {np.mean(avg_response_times):.3f}")
    
    print(f"\n💡 总结:")
    print(f"   在每2秒变化的高频网络环境中:")
    print(f"   • 平均值滤波器在延迟控制方面显著优于最大值滤波器")
    print(f"   • 平均值滤波器提供更稳定的带宽估计")
    print(f"   • 最大值滤波器容易过度反应，导致不必要的延迟")
    print("=" * 60)

if __name__ == "__main__":
    print("开始BBR高频网络变化分析...")
    
    # 生成和分析数据
    results = plot_detailed_analysis()
    
    # 计算性能指标
    calculate_performance_metrics(*results)
    
    print("\n分析完成！生成的文件: bbr_high_frequency_analysis.png") 