#!/usr/bin/env python3
"""
RTT分布分析工具
用于分析BBR日志中RTT测量值的分布情况
"""

import re
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import numpy as np
from collections import defaultdict

def analyze_rtt_distribution(log_file, max_lines=None):
    """分析RTT分布"""
    rtt_data = []
    line_count = 0
    
    print(f"Analyzing RTT distribution in: {log_file}")
    
    with open(log_file, 'r') as f:
        for line in f:
            line_count += 1
            if max_lines and line_count > max_lines:
                break
                
            if line_count % 1000 == 0:
                print(f"Processed {line_count} lines...")
            
            if "[BBR-LOG]" in line:
                try:
                    # 解析时间戳
                    time_match = re.search(r'T=([\d\.]+) s', line)
                    if not time_match:
                        continue
                    time_sec = float(time_match.group(1))
                    
                    # 解析RTT
                    rtt_match = re.search(r'RTT=(\d+) us', line)
                    if not rtt_match:
                        continue
                    rtt_us = int(rtt_match.group(1))
                    rtt_ms = rtt_us / 1000.0
                    
                    # 解析MinRTT
                    min_rtt_us = 0
                    min_rtt_match = re.search(r'MinRTT=(\d+) us', line)
                    if min_rtt_match:
                        min_rtt_us = int(min_rtt_match.group(1))
                    min_rtt_ms = min_rtt_us / 1000.0
                    
                    rtt_data.append({
                        'time_sec': time_sec,
                        'rtt_ms': rtt_ms,
                        'min_rtt_ms': min_rtt_ms,
                        'time_int': int(time_sec)  # 整数秒
                    })
                    
                except Exception as e:
                    continue
    
    if not rtt_data:
        print("No RTT data found!")
        return
    
    df = pd.DataFrame(rtt_data)
    print(f"Found {len(df)} RTT measurements")
    
    # 分析同一时间点的RTT分布
    analyze_concurrent_measurements(df)
    
    # 绘制详细分析图表
    plot_rtt_analysis(df)
    
    return df

def analyze_concurrent_measurements(df):
    """分析同一时间点的RTT测量"""
    print("\n=== RTT测量密度分析 ===")
    
    # 按0.1秒窗口分组
    df['time_window_100ms'] = (df['time_sec'] / 0.1).round() * 0.1
    window_counts = df.groupby('time_window_100ms').size()
    
    print(f"0.1秒时间窗口统计:")
    print(f"  最大测量次数: {window_counts.max()}")
    print(f"  平均测量次数: {window_counts.mean():.1f}")
    print(f"  有多次测量的窗口数: {(window_counts > 1).sum()}")
    
    # 找出测量密度最高的时间段
    max_window = window_counts.idxmax()
    max_data = df[df['time_window_100ms'] == max_window]
    
    print(f"\n最密集的0.1秒窗口 (t={max_window:.1f}s):")
    print(f"  测量次数: {len(max_data)}")
    print(f"  RTT范围: {max_data['rtt_ms'].min():.1f} - {max_data['rtt_ms'].max():.1f} ms")
    print(f"  RTT标准差: {max_data['rtt_ms'].std():.1f} ms")
    
    # 按1秒窗口分组
    second_counts = df.groupby('time_int').size()
    print(f"\n1秒时间窗口统计:")
    print(f"  最大测量次数: {second_counts.max()}")
    print(f"  平均测量次数: {second_counts.mean():.1f}")
    
    # RTT变异性分析
    print(f"\n=== RTT变异性分析 ===")
    print(f"总体RTT统计:")
    print(f"  平均值: {df['rtt_ms'].mean():.1f} ms")
    print(f"  标准差: {df['rtt_ms'].std():.1f} ms")
    print(f"  最小值: {df['rtt_ms'].min():.1f} ms")
    print(f"  最大值: {df['rtt_ms'].max():.1f} ms")
    print(f"  中位数: {df['rtt_ms'].median():.1f} ms")
    
    # 分析RTT跳变
    df_sorted = df.sort_values('time_sec')
    rtt_diff = df_sorted['rtt_ms'].diff().abs()
    large_jumps = rtt_diff > 20  # 超过20ms的跳变
    
    print(f"\nRTT跳变分析:")
    print(f"  >20ms跳变次数: {large_jumps.sum()}")
    print(f"  最大跳变: {rtt_diff.max():.1f} ms")

def plot_rtt_analysis(df):
    """绘制RTT详细分析图表"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # 图1: RTT时间序列（散点图）
    ax1 = axes[0, 0]
    ax1.scatter(df['time_sec'], df['rtt_ms'], alpha=0.6, s=1)
    if 'min_rtt_ms' in df.columns and df['min_rtt_ms'].sum() > 0:
        ax1.plot(df['time_sec'], df['min_rtt_ms'], 'b-', linewidth=1, alpha=0.7, label='Min RTT')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('RTT (ms)')
    ax1.set_title('RTT Time Series (All Measurements)')
    ax1.grid(True, alpha=0.3)
    if 'min_rtt_ms' in df.columns and df['min_rtt_ms'].sum() > 0:
        ax1.legend()
    
    # 图2: RTT直方图
    ax2 = axes[0, 1]
    ax2.hist(df['rtt_ms'], bins=50, alpha=0.7, edgecolor='black')
    ax2.axvline(df['rtt_ms'].mean(), color='red', linestyle='--', label=f'Mean: {df["rtt_ms"].mean():.1f}ms')
    ax2.axvline(df['rtt_ms'].median(), color='green', linestyle='--', label=f'Median: {df["rtt_ms"].median():.1f}ms')
    ax2.set_xlabel('RTT (ms)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('RTT Distribution')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # 图3: 测量密度（每秒测量次数）
    ax3 = axes[1, 0]
    second_counts = df.groupby('time_int').size()
    ax3.plot(second_counts.index, second_counts.values, 'o-', markersize=3)
    ax3.set_xlabel('Time (seconds)')
    ax3.set_ylabel('Measurements per second')
    ax3.set_title('RTT Measurement Frequency')
    ax3.grid(True, alpha=0.3)
    
    # 图4: RTT变化率
    ax4 = axes[1, 1]
    df_sorted = df.sort_values('time_sec').reset_index(drop=True)
    rtt_diff = df_sorted['rtt_ms'].diff().abs()
    ax4.plot(df_sorted['time_sec'][1:], rtt_diff[1:], alpha=0.6, linewidth=0.5)
    ax4.set_xlabel('Time (seconds)')
    ax4.set_ylabel('RTT Change (ms)')
    ax4.set_title('RTT Variation Over Time')
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('rtt_analysis.png', dpi=150, bbox_inches='tight')
    print(f"\nRTT分析图表已保存到: rtt_analysis.png")
    
    # 额外分析：显示最密集的时间段
    analyze_dense_periods(df)

def analyze_dense_periods(df, window_size=0.1):
    """分析RTT测量最密集的时间段"""
    print(f"\n=== 密集测量时间段分析 ===")
    
    # 创建时间窗口
    df['time_window'] = (df['time_sec'] / window_size).round() * window_size
    window_stats = df.groupby('time_window').agg({
        'rtt_ms': ['count', 'mean', 'std', 'min', 'max']
    }).round(2)
    
    window_stats.columns = ['count', 'mean_rtt', 'std_rtt', 'min_rtt', 'max_rtt']
    
    # 找出测量次数最多的前5个窗口
    top_dense = window_stats.nlargest(5, 'count')
    
    print(f"测量最密集的5个{window_size}秒窗口:")
    print(top_dense)
    
    # 找出RTT变异最大的窗口
    high_variance = window_stats[window_stats['count'] >= 3].nlargest(5, 'std_rtt')
    if not high_variance.empty:
        print(f"\nRTT变异最大的5个窗口(>=3次测量):")
        print(high_variance)

def main():
    parser = argparse.ArgumentParser(description="RTT Distribution Analyzer")
    parser.add_argument("log_file", help="Path to the BBR log file")
    parser.add_argument("--max-lines", type=int, help="Maximum lines to process")
    args = parser.parse_args()
    
    df = analyze_rtt_distribution(args.log_file, args.max_lines)
    
    if df is not None:
        print(f"\n分析完成！")
        print(f"主要发现:")
        print(f"1. 同一时间点出现多个RTT值是正常的网络现象")
        print(f"2. RTT测量频率反映了网络活动强度")
        print(f"3. RTT变异性显示了网络质量的稳定性")

if __name__ == "__main__":
    plt.switch_backend('agg')  # 用于服务器环境
    main() 