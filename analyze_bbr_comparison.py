#!/usr/bin/env python3
import re
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple

def parse_bbr_log(filepath: str) -> Dict:
    """解析BBR日志文件"""
    data = {
        'timestamps': [],
        'send_rates': [],
        'recv_rates': [],
        'total_rates': [],
        'est_bw': [],
        'pacing_rates': [],
        'pacing_gains': [],
        'cwnd_gains': [],
        'delivery_rates': [],
        'rtts': [],
        'min_rtts': [],
        'cwnds': [],
        'in_flights': [],
        'lost_packets': [],
        'states': [],
        'sent_packets': [],
        'sent_bytes': [],
        'recv_packets': [],
        'recv_bytes': []
    }
    
    pattern = re.compile(
        r'\[BBR-LOG\] T=(\d+\.\d+) s, Send=(\d+\.\d+) Mbps, Recv=(\d+\.\d+) Mbps, '
        r'Total=(\d+\.\d+) Mbps, EstBW=(\d+\.\d+) Mbps, PacingRate=(\d+\.\d+) Mbps, '
        r'PacingGain=(\d+\.\d+)x, CwndGain=(\d+\.\d+)x, DeliveryRate=(\d+\.\d+) Mbps, '
        r'RTT=(\d+) us, MinRTT=(\d+) us, CWND=(\d+) B, InFlight=(\d+) B, '
        r'Lost=(\d+), State=(\w+), Pkts=(\d+)/(\d+), Bytes=(\d+)/(\d+)'
    )
    
    with open(filepath, 'r') as f:
        for line in f:
            match = pattern.match(line.strip())
            if match:
                data['timestamps'].append(float(match.group(1)))
                data['send_rates'].append(float(match.group(2)))
                data['recv_rates'].append(float(match.group(3)))
                data['total_rates'].append(float(match.group(4)))
                data['est_bw'].append(float(match.group(5)))
                data['pacing_rates'].append(float(match.group(6)))
                data['pacing_gains'].append(float(match.group(7)))
                data['cwnd_gains'].append(float(match.group(8)))
                data['delivery_rates'].append(float(match.group(9)))
                data['rtts'].append(float(match.group(10)))
                data['min_rtts'].append(float(match.group(11)))
                data['cwnds'].append(int(match.group(12)))
                data['in_flights'].append(int(match.group(13)))
                data['lost_packets'].append(int(match.group(14)))
                data['states'].append(match.group(15))
                data['sent_packets'].append(int(match.group(16)))
                data['recv_packets'].append(int(match.group(17)))
                data['sent_bytes'].append(int(match.group(18)))
                data['recv_bytes'].append(int(match.group(19)))
    
    return data

def aggregate_4conn_data(data: Dict) -> Dict:
    """聚合4连接数据，按时间窗口合并"""
    # 将数据按0.1秒窗口聚合
    window_size = 0.1
    timestamps = np.array(data['timestamps'])
    
    # 确定时间窗口
    min_time = min(timestamps)
    max_time = max(timestamps)
    windows = np.arange(min_time, max_time + window_size, window_size)
    
    aggregated = {
        'timestamps': [],
        'send_rates': [],
        'recv_rates': [],
        'total_rates': [],
        'est_bw': [],
        'pacing_rates': [],
        'pacing_gains': [],
        'cwnd_gains': [],
        'delivery_rates': [],
        'rtts': [],
        'min_rtts': [],
        'cwnds': [],
        'in_flights': [],
        'lost_packets': [],
        'states': [],
        'connection_count': []
    }
    
    for i in range(len(windows) - 1):
        window_start = windows[i]
        window_end = windows[i + 1]
        
        # 找到在当前窗口内的数据点
        mask = (timestamps >= window_start) & (timestamps < window_end)
        window_indices = np.where(mask)[0]
        
        if len(window_indices) == 0:
            continue
            
        # 聚合数据
        aggregated['timestamps'].append(window_start + window_size/2)
        aggregated['send_rates'].append(np.sum([data['send_rates'][i] for i in window_indices]))
        aggregated['recv_rates'].append(np.sum([data['recv_rates'][i] for i in window_indices]))
        aggregated['total_rates'].append(np.sum([data['total_rates'][i] for i in window_indices]))
        aggregated['est_bw'].append(np.mean([data['est_bw'][i] for i in window_indices]))
        aggregated['pacing_rates'].append(np.sum([data['pacing_rates'][i] for i in window_indices]))
        aggregated['pacing_gains'].append(np.mean([data['pacing_gains'][i] for i in window_indices]))
        aggregated['cwnd_gains'].append(np.mean([data['cwnd_gains'][i] for i in window_indices]))
        aggregated['delivery_rates'].append(np.sum([data['delivery_rates'][i] for i in window_indices]))
        aggregated['rtts'].append(np.mean([data['rtts'][i] for i in window_indices]))
        aggregated['min_rtts'].append(np.min([data['min_rtts'][i] for i in window_indices]))
        aggregated['cwnds'].append(np.sum([data['cwnds'][i] for i in window_indices]))
        aggregated['in_flights'].append(np.sum([data['in_flights'][i] for i in window_indices]))
        aggregated['lost_packets'].append(np.sum([data['lost_packets'][i] for i in window_indices]))
        
        # 状态：取最常见的状态
        states_in_window = [data['states'][i] for i in window_indices]
        most_common_state = max(set(states_in_window), key=states_in_window.count)
        aggregated['states'].append(most_common_state)
        aggregated['connection_count'].append(len(window_indices))
    
    return aggregated

def calculate_statistics(data: Dict) -> Dict:
    """计算统计信息"""
    stats = {}
    
    # 基本统计
    stats['duration'] = max(data['timestamps']) - min(data['timestamps'])
    stats['sample_count'] = len(data['timestamps'])
    
    # 吞吐量统计
    stats['avg_total_rate'] = np.mean(data['total_rates'])
    stats['max_total_rate'] = np.max(data['total_rates'])
    stats['avg_send_rate'] = np.mean(data['send_rates'])
    stats['avg_recv_rate'] = np.mean(data['recv_rates'])
    
    # 延迟统计
    stats['avg_rtt'] = np.mean(data['rtts']) / 1000  # 转换为ms
    stats['min_rtt'] = np.min(data['min_rtts']) / 1000
    stats['avg_min_rtt'] = np.mean(data['min_rtts']) / 1000
    
    # CWND和InFlight统计
    stats['avg_cwnd'] = np.mean(data['cwnds']) / 1024  # 转换为KB
    stats['max_cwnd'] = np.max(data['cwnds']) / 1024
    stats['avg_inflight'] = np.mean(data['in_flights']) / 1024
    
    # 损失统计
    stats['total_lost'] = np.sum(data['lost_packets'])
    stats['loss_events'] = np.sum(np.array(data['lost_packets']) > 0)
    
    # 状态分布
    states = data['states']
    state_counts = {}
    for state in states:
        state_counts[state] = state_counts.get(state, 0) + 1
    stats['state_distribution'] = state_counts
    
    return stats

def analyze_comparison():
    """主分析函数"""
    # 解析两个日志文件
    print("解析日志文件...")
    single_conn_data = parse_bbr_log('bbr_logs/bbr_log.txt')
    four_conn_data = parse_bbr_log('bbr_logs/4connsbbr_log.txt')
    
    # 聚合4连接数据
    print("聚合4连接数据...")
    four_conn_aggregated = aggregate_4conn_data(four_conn_data)
    
    # 计算统计信息
    print("计算统计信息...")
    single_stats = calculate_statistics(single_conn_data)
    four_stats = calculate_statistics(four_conn_aggregated)
    
    # 打印比较结果
    print("\n" + "="*60)
    print("BBR 单连接 vs 4连接 性能对比分析")
    print("="*60)
    
    print(f"\n【基本信息】")
    print(f"单连接 - 持续时间: {single_stats['duration']:.2f}s, 采样数: {single_stats['sample_count']}")
    print(f"4连接  - 持续时间: {four_stats['duration']:.2f}s, 采样数: {four_stats['sample_count']}")
    
    print(f"\n【吞吐量对比】")
    print(f"平均总吞吐量:")
    print(f"  单连接: {single_stats['avg_total_rate']:.2f} Mbps")
    print(f"  4连接:  {four_stats['avg_total_rate']:.2f} Mbps")
    print(f"  提升:   {(four_stats['avg_total_rate']/single_stats['avg_total_rate']-1)*100:.1f}%")
    
    print(f"\n最大吞吐量:")
    print(f"  单连接: {single_stats['max_total_rate']:.2f} Mbps")
    print(f"  4连接:  {four_stats['max_total_rate']:.2f} Mbps")
    print(f"  提升:   {(four_stats['max_total_rate']/single_stats['max_total_rate']-1)*100:.1f}%")
    
    print(f"\n【延迟对比】")
    print(f"平均RTT:")
    print(f"  单连接: {single_stats['avg_rtt']:.2f} ms")
    print(f"  4连接:  {four_stats['avg_rtt']:.2f} ms")
    
    print(f"最小RTT:")
    print(f"  单连接: {single_stats['min_rtt']:.2f} ms")
    print(f"  4连接:  {four_stats['min_rtt']:.2f} ms")
    
    print(f"\n【拥塞窗口对比】")
    print(f"平均CWND:")
    print(f"  单连接: {single_stats['avg_cwnd']:.1f} KB")
    print(f"  4连接:  {four_stats['avg_cwnd']:.1f} KB")
    
    print(f"最大CWND:")
    print(f"  单连接: {single_stats['max_cwnd']:.1f} KB")
    print(f"  4连接:  {four_stats['max_cwnd']:.1f} KB")
    
    print(f"平均InFlight:")
    print(f"  单连接: {single_stats['avg_inflight']:.1f} KB")
    print(f"  4连接:  {four_stats['avg_inflight']:.1f} KB")
    
    print(f"\n【丢包对比】")
    print(f"总丢包数:")
    print(f"  单连接: {single_stats['total_lost']}")
    print(f"  4连接:  {four_stats['total_lost']}")
    
    print(f"丢包事件数:")
    print(f"  单连接: {single_stats['loss_events']}")
    print(f"  4连接:  {four_stats['loss_events']}")
    
    print(f"\n【状态分布】")
    print("单连接状态分布:")
    for state, count in single_stats['state_distribution'].items():
        pct = count / single_stats['sample_count'] * 100
        print(f"  {state}: {count} ({pct:.1f}%)")
    
    print("4连接状态分布:")
    for state, count in four_stats['state_distribution'].items():
        pct = count / four_stats['sample_count'] * 100
        print(f"  {state}: {count} ({pct:.1f}%)")
    
    # 创建可视化图表
    print(f"\n生成对比图表...")
    create_comparison_plots(single_conn_data, four_conn_aggregated, single_stats, four_stats)
    
    return single_stats, four_stats

def create_comparison_plots(single_data, four_data, single_stats, four_stats):
    """创建对比图表"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # 吞吐量对比
    axes[0,0].plot(single_data['timestamps'], single_data['total_rates'], 
                   label=f'单连接 (avg: {single_stats["avg_total_rate"]:.1f} Mbps)', alpha=0.7)
    axes[0,0].plot(four_data['timestamps'], four_data['total_rates'], 
                   label=f'4连接 (avg: {four_stats["avg_total_rate"]:.1f} Mbps)', alpha=0.7)
    axes[0,0].set_xlabel('时间 (s)')
    axes[0,0].set_ylabel('总吞吐量 (Mbps)')
    axes[0,0].set_title('吞吐量对比')
    axes[0,0].legend()
    axes[0,0].grid(True, alpha=0.3)
    
    # RTT对比
    axes[0,1].plot(single_data['timestamps'], np.array(single_data['rtts'])/1000, 
                   label=f'单连接 (avg: {single_stats["avg_rtt"]:.1f} ms)', alpha=0.7)
    axes[0,1].plot(four_data['timestamps'], np.array(four_data['rtts'])/1000, 
                   label=f'4连接 (avg: {four_stats["avg_rtt"]:.1f} ms)', alpha=0.7)
    axes[0,1].set_xlabel('时间 (s)')
    axes[0,1].set_ylabel('RTT (ms)')
    axes[0,1].set_title('RTT延迟对比')
    axes[0,1].legend()
    axes[0,1].grid(True, alpha=0.3)
    
    # CWND对比
    axes[1,0].plot(single_data['timestamps'], np.array(single_data['cwnds'])/1024, 
                   label=f'单连接 (avg: {single_stats["avg_cwnd"]:.1f} KB)', alpha=0.7)
    axes[1,0].plot(four_data['timestamps'], np.array(four_data['cwnds'])/1024, 
                   label=f'4连接 (avg: {four_stats["avg_cwnd"]:.1f} KB)', alpha=0.7)
    axes[1,0].set_xlabel('时间 (s)')
    axes[1,0].set_ylabel('CWND (KB)')
    axes[1,0].set_title('拥塞窗口对比')
    axes[1,0].legend()
    axes[1,0].grid(True, alpha=0.3)
    
    # InFlight对比
    axes[1,1].plot(single_data['timestamps'], np.array(single_data['in_flights'])/1024, 
                   label=f'单连接 (avg: {single_stats["avg_inflight"]:.1f} KB)', alpha=0.7)
    axes[1,1].plot(four_data['timestamps'], np.array(four_data['in_flights'])/1024, 
                   label=f'4连接 (avg: {four_stats["avg_inflight"]:.1f} KB)', alpha=0.7)
    axes[1,1].set_xlabel('时间 (s)')
    axes[1,1].set_ylabel('InFlight (KB)')
    axes[1,1].set_title('在途数据对比')
    axes[1,1].legend()
    axes[1,1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('bbr_logs/bbr_comparison.png', dpi=300, bbox_inches='tight')
    print(f"图表已保存至: bbr_logs/bbr_comparison.png")

if __name__ == "__main__":
    analyze_comparison() 