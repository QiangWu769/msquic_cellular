import re
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import os
from datetime import datetime
import numpy as np
from matplotlib.ticker import EngFormatter, MultipleLocator

def analyze_log(log_file, max_lines=None, time_window=0.1, aggregate=False):
    """解析MsQuic BBR日志格式，可选择是否按时间窗口聚合数据"""
    bbr_data = []
    retransmission_data = []
    
    line_count = 0
    print(f"Analyzing log file: {log_file}")
    
    with open(log_file, 'r') as f:
        for line in f:
            line_count += 1
            if max_lines and line_count > max_lines:
                break
                
            if line_count % 1000 == 0:
                print(f"Processed {line_count} lines...")
            
            # 解析BBR-LOG格式 或者 包含bbr={}的行
            is_bbr_log = "[BBR-LOG]" in line
            is_bbr_debug = "bbr={" in line
            
            if not (is_bbr_log or is_bbr_debug):
                continue
                
            try:
                # 解析时间戳
                time_sec = 0
                if is_bbr_log:
                    time_match = re.search(r'T=([\d\.]+) s', line)
                    if time_match:
                        time_sec = float(time_match.group(1))
                elif is_bbr_debug:
                    # 从debug日志中提取时间戳 (如果有的话)
                    ts_match = re.search(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)Z", line)
                    if ts_match:
                        ts_str = ts_match.group(1)
                        from datetime import datetime
                        timestamp = datetime.fromisoformat(ts_str.split('.')[0] + '.' + ts_str.split('.')[1][:6])
                        # 转换为相对时间秒（如果有起始时间的话）
                        if not hasattr(analyze_log, 'start_time'):
                            analyze_log.start_time = timestamp
                        time_sec = (timestamp - analyze_log.start_time).total_seconds()
                
                if time_sec == 0:
                    continue
                
                # 初始化所有指标
                send_mbps = 0
                recv_mbps = 0
                estbw_mbps = 0
                pacing_rate_mbps = 0
                delivery_rate_mbps = 0
                rtt_us = 0
                min_rtt_us = 0
                cwnd_bytes = 0
                inflight_bytes = 0
                lost_packets = 0
                bbr_state = "Unknown"
                pacing_gain = np.nan
                cwnd_gain = np.nan
                send_delay_us = 0
                ack_delay_us = 0
                
                if is_bbr_log:
                    # 处理 [BBR-LOG] 格式
                    # 提取发送速率
                    send_match = re.search(r'Send=([\d\.]+) Mbps', line)
                    if send_match:
                        send_mbps = float(send_match.group(1))
                    
                    # 提取接收速率
                    recv_match = re.search(r'Recv=([\d\.]+) Mbps', line)
                    if recv_match:
                        recv_mbps = float(recv_match.group(1))
                    
                    # 提取估计带宽
                    estbw_match = re.search(r'EstBW=([\d\.]+) Mbps', line)
                    if estbw_match:
                        estbw_mbps = float(estbw_match.group(1))
                    
                    # 提取Pacing Rate
                    pacing_match = re.search(r'PacingRate=([\d\.]+) Mbps', line)
                    if pacing_match:
                        pacing_rate_mbps = float(pacing_match.group(1))
                    
                    # 提取Delivery Rate
                    delivery_match = re.search(r'DeliveryRate=([\d\.]+) Mbps', line)
                    if delivery_match:
                        delivery_rate_mbps = float(delivery_match.group(1))
                    
                    # 提取RTT
                    rtt_match = re.search(r'RTT=(\d+) us', line)
                    if rtt_match:
                        rtt_us = int(rtt_match.group(1))
                    
                    # 提取MinRTT
                    min_rtt_match = re.search(r'MinRTT=(\d+) us', line)
                    if min_rtt_match:
                        min_rtt_us = int(min_rtt_match.group(1))
                    
                    # 提取CWND
                    cwnd_match = re.search(r'CWND=(\d+) B', line)
                    if cwnd_match:
                        cwnd_bytes = int(cwnd_match.group(1))
                    
                    # 提取InFlight
                    inflight_match = re.search(r'InFlight=(\d+) B', line)
                    if inflight_match:
                        inflight_bytes = int(inflight_match.group(1))
                    
                    # 提取Lost packets
                    lost_match = re.search(r'Lost=(\d+)', line)
                    if lost_match:
                        lost_packets = int(lost_match.group(1))
                    
                    # 提取BBR State
                    state_match = re.search(r'State=(\w+)', line)
                    if state_match:
                        bbr_state = state_match.group(1)
                    
                    # 提取Pacing Gain - 修复！
                    pacing_gain_match = re.search(r'PacingGain=([\d\.]+)x', line)
                    if pacing_gain_match:
                        pacing_gain = float(pacing_gain_match.group(1))
                    
                    # 提取CWND Gain - 修复！
                    cwnd_gain_match = re.search(r'CwndGain=([\d\.]+)x', line)
                    if cwnd_gain_match:
                        cwnd_gain = float(cwnd_gain_match.group(1))
                    
                    # 提取Send Delay
                    send_delay_match = re.search(r'SendDelay=(\d+) us', line)
                    if send_delay_match:
                        send_delay_us = int(send_delay_match.group(1))
                    
                    # 提取Ack Delay
                    ack_delay_match = re.search(r'AckDelay=(\d+) us', line)
                    if ack_delay_match:
                        ack_delay_us = int(ack_delay_match.group(1))
                
                elif is_bbr_debug:
                    # 处理 bbr={...} 格式 - 重点提取gain因子
                    bbr_match = re.search(r'bbr=\{([^}]+)\}', line)
                    if bbr_match:
                        bbr_content = bbr_match.group(1)
                        
                        # 提取BBR状态
                        state_match = re.search(r'state=(\w+)', bbr_content)
                        if state_match:
                            bbr_state = state_match.group(1)
                        
                        # 提取btlbw (带宽估计)
                        btlbw_match = re.search(r'btlbw=(\d+)', bbr_content)
                        if btlbw_match:
                            estbw_mbps = int(btlbw_match.group(1)) * 8 / 1_000_000  # 转换为Mbps
                        
                        # 提取pacing_rate
                        pacing_rate_match = re.search(r'pacing_rate=(\d+)', bbr_content)
                        if pacing_rate_match:
                            pacing_rate_mbps = int(pacing_rate_match.group(1)) * 8 / 1_000_000  # 转换为Mbps
                        
                        # 提取pacing_gain - 关键！
                        pacing_gain_match = re.search(r'pacing_gain=([\d\.]+)', bbr_content)
                        if pacing_gain_match:
                            pacing_gain = float(pacing_gain_match.group(1))
                        
                        # 提取cwnd_gain - 关键！
                        cwnd_gain_match = re.search(r'cwnd_gain=([\d\.]+)', bbr_content)
                        if cwnd_gain_match:
                            cwnd_gain = float(cwnd_gain_match.group(1))
                        
                        # 提取rtprop
                        rtprop_match = re.search(r'rtprop=Some\(([\d\.]+)ms\)', bbr_content)
                        if rtprop_match:
                            min_rtt_us = float(rtprop_match.group(1)) * 1000  # 转换为微秒
                    
                    # 从其他地方提取CWND和bytes_in_flight
                    cwnd_match = re.search(r'cwnd=(\d+)', line)
                    if cwnd_match:
                        cwnd_bytes = int(cwnd_match.group(1))
                    
                    inflight_match = re.search(r'bytes_in_flight=(\d+)', line)
                    if inflight_match:
                        inflight_bytes = int(inflight_match.group(1))
                
                # 添加数据点
                bbr_data.append({
                    'time_sec': time_sec,
                    'send_mbps': send_mbps,
                    'recv_mbps': recv_mbps,
                    'btlbw_mbps': estbw_mbps,
                    'pacing_rate_mbps': pacing_rate_mbps,
                    'delivery_rate_mbps': delivery_rate_mbps,
                    'rtt_ms': rtt_us / 1000.0,  # 转换为毫秒
                    'rtprop_ms': min_rtt_us / 1000.0,  # 转换为毫秒
                    'cwnd_kb': cwnd_bytes / 1024.0,  # 转换为KB
                    'bytes_in_flight_kb': inflight_bytes / 1024.0,  # 转换为KB
                    'lost_packets': lost_packets,
                    'bbr_state': bbr_state,
                    'pacing_gain': pacing_gain,  # 新增
                    'cwnd_gain': cwnd_gain,      # 新增
                    'send_delay_ms': send_delay_us / 1000.0,  # 新增：转换为毫秒
                    'ack_delay_ms': ack_delay_us / 1000.0     # 新增：转换为毫秒
                })
                
            except Exception as e:
                if line_count < 20:  # 只对前20行打印错误
                    print(f"Error parsing line {line_count}: {str(e)}")
                    print(f"Line content: {line[:100]}...")
    
    print(f"Finished processing {line_count} lines. Found {len(bbr_data)} BBR entries.")
    
    if not bbr_data:
        return None, None, None
    
    # 创建DataFrame
    bbr_df = pd.DataFrame(bbr_data)
    
    if aggregate:
        # 数据聚合处理：按时间窗口分组
        print(f"Aggregating data with time window: {time_window}s...")
        
        # 创建时间窗口标识符
        bbr_df['time_window'] = (bbr_df['time_sec'] / time_window).round() * time_window
        
        # 按时间窗口聚合数据
        agg_functions = {
            'time_sec': 'first',  # 使用第一个时间戳作为代表
            'send_mbps': 'mean',
            'recv_mbps': 'mean', 
            'btlbw_mbps': 'mean',
            'pacing_rate_mbps': 'mean',
            'delivery_rate_mbps': 'mean',
            'rtt_ms': 'mean',
            'rtprop_ms': 'min',  # MinRTT使用最小值
            'cwnd_kb': 'mean',
            'bytes_in_flight_kb': 'mean',
            'lost_packets': 'max',  # 丢包数使用最大值（累积）
            'bbr_state': 'last',  # BBR状态使用最后一个
            'pacing_gain': 'mean',  # 新增
            'cwnd_gain': 'mean',    # 新增
            'send_delay_ms': 'mean',  # 新增：发送延迟
            'ack_delay_ms': 'mean'    # 新增：ACK延迟
        }
        
        # 执行聚合
        bbr_df_final = bbr_df.groupby('time_window').agg(agg_functions).reset_index()
        
        # 按时间排序
        bbr_df_final = bbr_df_final.sort_values('time_sec').reset_index(drop=True)
        
        print(f"Data aggregated: {len(bbr_data)} -> {len(bbr_df_final)} data points")
    else:
        # 不聚合，使用所有原始数据点
        print("Keeping all original data points (no aggregation)...")
        bbr_df_final = bbr_df.sort_values('time_sec').reset_index(drop=True)
        print(f"Total data points: {len(bbr_df_final)}")
    
    # 基本的异常值过滤
    print("Filtering anomalous values...")
    
    # 过滤掉无效的RTT值
    bbr_df_final.loc[bbr_df_final['rtt_ms'] == 0, 'rtt_ms'] = np.nan
    bbr_df_final.loc[bbr_df_final['rtprop_ms'] == 0, 'rtprop_ms'] = np.nan
    
    # 过滤掉明显异常的RTT值（超过1000ms）
    bbr_df_final.loc[bbr_df_final['rtt_ms'] > 1000, 'rtt_ms'] = np.nan
    bbr_df_final.loc[bbr_df_final['rtprop_ms'] > 1000, 'rtprop_ms'] = np.nan
    
    # 过滤掉明显异常的带宽值（超过2000 Mbps）
    for col in ['btlbw_mbps', 'pacing_rate_mbps', 'delivery_rate_mbps']:
        if col in bbr_df_final.columns:
            bbr_df_final.loc[bbr_df_final[col] > 2000, col] = np.nan
    
    aggregation_status = "aggregated" if aggregate else "original"
    print(f"Final {aggregation_status} dataset: {len(bbr_df_final)} data points")
    
    # 处理重传数据（如果有的话）
    retransmission_df = None
    if retransmission_data:
        retransmission_df = pd.DataFrame(retransmission_data)
    
    return bbr_df_final, None, retransmission_df

def plot_four_charts(bbr_df, delivery_rate_df, retransmission_df, output_file, aggregated=False, rtt_style='scatter'):
    """绘制BBR分析图表 - 包含延迟分析的完整图表集合"""
    if bbr_df is None:
        print("No BBR data to plot.")
        return
    
    # 对于非聚合的大数据集，进行采样以提高性能
    original_length = len(bbr_df)
    if not aggregated and len(bbr_df) > 50000:
        print(f"Large dataset detected ({original_length} points). Sampling for visualization...")
        sample_rate = max(1, len(bbr_df) // 20000)
        bbr_df_plot = bbr_df.iloc[::sample_rate].copy()
        print(f"Sampled {len(bbr_df_plot)} points from {original_length} (every {sample_rate} points)")
    else:
        bbr_df_plot = bbr_df
        print(f"Plotting all {len(bbr_df_plot)} data points")
    
    # 提高绘图性能
    plt.rcParams['path.simplify'] = True
    plt.rcParams['path.simplify_threshold'] = 0.8
    plt.rcParams['agg.path.chunksize'] = 10000
    
    # 确定需要的子图数量
    num_subplots = 7  # 基础图表数量（增加了延迟图）
    if retransmission_df is not None and not retransmission_df.empty:
        num_subplots += 1  # 添加丢包图
    
    # 创建竖直排列的子图 - 学习示例代码的布局
    fig, axes = plt.subplots(num_subplots, 1, figsize=(12, num_subplots * 4), dpi=120)
    plt.subplots_adjust(hspace=0.3)
    
    # 确保axes是数组形式
    if num_subplots == 1:
        axes = [axes]
    
    # 为标题设置统一样式
    title_style = dict(fontsize=14, fontweight='bold', 
                     bbox=dict(facecolor='white', alpha=0.8, edgecolor='lightgray', boxstyle='round,pad=0.5'))
    
    current_ax_idx = 0
    
    # 图1: 带宽估计和传输速率
    ax1 = axes[current_ax_idx]
    current_ax_idx += 1
    
    if 'btlbw_mbps' in bbr_df_plot.columns:
        ax1.plot(bbr_df_plot['time_sec'], bbr_df_plot['btlbw_mbps'], 'b-', linewidth=1.5, label='BtlBw (Mbps)')
    
    if 'pacing_rate_mbps' in bbr_df_plot.columns:
        ax1.plot(bbr_df_plot['time_sec'], bbr_df_plot['pacing_rate_mbps'], 'g--', linewidth=1.2, label='Pacing Rate (Mbps)')
        
        # 添加平均pacing rate的水平线
        avg_pacing_rate = bbr_df['pacing_rate_mbps'].mean()
        if not np.isnan(avg_pacing_rate):
            ax1.axhline(y=avg_pacing_rate, color='orange', linestyle=':', linewidth=2, 
                       alpha=0.8, label=f'Avg Pacing Rate ({avg_pacing_rate:.2f} Mbps)')
    
    if 'delivery_rate_mbps' in bbr_df_plot.columns:
        ax1.plot(bbr_df_plot['time_sec'], bbr_df_plot['delivery_rate_mbps'], 'r-', linewidth=1.2, label='Delivery Rate (Mbps)')
    
    # 标记状态转换
    if 'bbr_state' in bbr_df_plot.columns:
        state_changes = bbr_df_plot[bbr_df_plot['bbr_state'] != bbr_df_plot['bbr_state'].shift(1)]
        for _, row in state_changes.iterrows():
            ax1.axvline(x=row['time_sec'], color='red', linestyle='--', alpha=0.7)
            ax1.text(row['time_sec'], ax1.get_ylim()[1]*0.9, row['bbr_state'], 
                    rotation=90, ha='right', bbox=dict(facecolor='white', alpha=0.8))
    
    # 添加统计信息
    stats_text = ""
    if 'btlbw_mbps' in bbr_df.columns:
        avg_btlbw = bbr_df['btlbw_mbps'].mean()
        max_btlbw = bbr_df['btlbw_mbps'].max()
        min_btlbw = bbr_df['btlbw_mbps'].min()
        stats_text += f"Avg BtlBw: {avg_btlbw:.2f} Mbps\n"
        stats_text += f"Max BtlBw: {max_btlbw:.2f} Mbps\n"
        stats_text += f"Min BtlBw: {min_btlbw:.2f} Mbps\n\n"
    
    if 'pacing_rate_mbps' in bbr_df.columns:
        avg_pacing_rate = bbr_df['pacing_rate_mbps'].mean()
        max_pacing_rate = bbr_df['pacing_rate_mbps'].max()
        min_pacing_rate = bbr_df['pacing_rate_mbps'].min()
        stats_text += f"Avg Pacing Rate: {avg_pacing_rate:.2f} Mbps\n"
        stats_text += f"Max Pacing Rate: {max_pacing_rate:.2f} Mbps\n"
        stats_text += f"Min Pacing Rate: {min_pacing_rate:.2f} Mbps\n\n"
    
    if 'delivery_rate_mbps' in bbr_df.columns:
        avg_delivery = bbr_df['delivery_rate_mbps'].mean()
        max_delivery = bbr_df['delivery_rate_mbps'].max()
        stats_text += f"Avg Delivery: {avg_delivery:.2f} Mbps\nMax Delivery: {max_delivery:.2f} Mbps"
    
    if stats_text:
        ax1.text(0.02, 0.95, stats_text, transform=ax1.transAxes, 
                verticalalignment='top', bbox=dict(facecolor='white', alpha=0.7))
    
    ax1.set_ylabel('Bandwidth (Mbps)')
    ax1.set_title('Congestion Control Bandwidth Estimation and Delivery Rate', **title_style)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')
    
    # 图2: RTT测量
    ax2 = axes[current_ax_idx]
    current_ax_idx += 1
    
    if 'rtprop_ms' in bbr_df_plot.columns:
        ax2.plot(bbr_df_plot['time_sec'], bbr_df_plot['rtprop_ms'], 'r-', linewidth=1.0, label='RTprop (ms)')
    
    if 'rtt_ms' in bbr_df_plot.columns:
        ax2.plot(bbr_df_plot['time_sec'], bbr_df_plot['rtt_ms'], 'purple', linewidth=2.0, label='Latest RTT (ms)')
    
    # 添加RTT统计信息框
    stats_text = ""
    if 'rtprop_ms' in bbr_df.columns and not bbr_df['rtprop_ms'].isnull().all():
        avg_rtprop = bbr_df['rtprop_ms'].mean()
        median_rtprop = bbr_df['rtprop_ms'].median()
        max_rtprop = bbr_df['rtprop_ms'].max()
        min_rtprop = bbr_df['rtprop_ms'].min()
        stats_text += f"RTprop (ms):\n  Avg: {avg_rtprop:.2f}\n  Median: {median_rtprop:.2f}\n  Max: {max_rtprop:.2f}\n  Min: {min_rtprop:.2f}\n\n"

    if 'rtt_ms' in bbr_df.columns and not bbr_df['rtt_ms'].isnull().all():
        avg_latest_rtt = bbr_df['rtt_ms'].mean()
        median_latest_rtt = bbr_df['rtt_ms'].median()
        max_latest_rtt = bbr_df['rtt_ms'].max()
        min_latest_rtt = bbr_df['rtt_ms'].min()
        stats_text += f"Latest RTT (ms):\n  Avg: {avg_latest_rtt:.2f}\n  Median: {median_latest_rtt:.2f}\n  Max: {max_latest_rtt:.2f}\n  Min: {min_latest_rtt:.2f}"

    if stats_text:
        ax2.text(0.02, 0.95, stats_text, transform=ax2.transAxes, 
                verticalalignment='top', bbox=dict(facecolor='white', alpha=0.7))
    
    ax2.set_ylabel('RTT (ms)')
    ax2.set_title('RTT Measurements', **title_style)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right')
    
    # 图3: BBR状态机
    ax3 = axes[current_ax_idx]
    current_ax_idx += 1
    
    if 'bbr_state' in bbr_df_plot.columns:
        states = bbr_df_plot['bbr_state'].unique()
        state_map = {state: i for i, state in enumerate(states)}
        bbr_df_plot['state_num'] = bbr_df_plot['bbr_state'].map(state_map)
        
        ax3.plot(bbr_df_plot['time_sec'], bbr_df_plot['state_num'], 'purple', drawstyle='steps-post', linewidth=2, label='BBR State')
        ax3.set_yticks(range(len(states)))
        ax3.set_yticklabels(states)
        ax3.set_ylabel('BBR State')
        
        # 添加RTprop到右侧Y轴
        ax3b = ax3.twinx()
        if 'rtprop_ms' in bbr_df_plot.columns:
            ax3b.plot(bbr_df_plot['time_sec'], bbr_df_plot['rtprop_ms'], 'r-', linewidth=1.2, label='RTprop (ms)')
            ax3b.set_ylabel('RTprop (ms)', color='r')
            ax3b.tick_params(axis='y', labelcolor='r')
        
        # 添加状态转换标记
        state_changes = bbr_df_plot[bbr_df_plot['bbr_state'] != bbr_df_plot['bbr_state'].shift(1)]
        for _, row in state_changes.iterrows():
            time_str = f"{row['time_sec']:.1f}s"
            ax3.text(row['time_sec'], state_map[row['bbr_state']], 
                    f"{row['bbr_state']}\n{time_str}", 
                    ha='center', va='bottom', 
                    bbox=dict(facecolor='lightyellow', alpha=0.8))
        
        # 合并两个图例
        lines3, labels3 = ax3.get_legend_handles_labels()
        lines3b, labels3b = ax3b.get_legend_handles_labels()
        ax3.legend(lines3 + lines3b, labels3 + labels3b, loc='upper right')
    
    ax3.set_title('Congestion Control State Machine and RTprop', **title_style)
    ax3.grid(True, alpha=0.3)
    
    # 图4: BBR增益因子 - 修复增益因子绘图问题
    ax4 = axes[current_ax_idx]
    current_ax_idx += 1
    
    # 先绘制状态变化背景
    if 'bbr_state' in bbr_df_plot.columns:
        state_colors = {'Startup': 'lightyellow', 'Drain': 'lightblue', 'ProbeBW': 'lightgreen', 'ProbeRTT': 'mistyrose'}
        current_state = None
        start_time = None
        
        for i, row in bbr_df_plot.iterrows():
            if current_state != row['bbr_state']:
                if current_state is not None and start_time is not None:
                    end_time = row['time_sec']
                    color = state_colors.get(current_state, 'white')
                    ax4.axvspan(start_time, end_time, alpha=0.2, color=color)
                    
                    # 在区域中心添加状态标签
                    mid_time = (start_time + end_time) / 2
                    ax4.text(mid_time, 0.05, current_state, 
                            transform=ax4.get_xaxis_transform(),
                            ha='center', va='bottom', fontsize=8,
                            bbox=dict(boxstyle='round', fc='white', alpha=0.8))
                
                current_state = row['bbr_state']
                start_time = row['time_sec']
        
        # 处理最后一个状态
        if current_state is not None and start_time is not None:
            end_time = bbr_df_plot['time_sec'].max()
            color = state_colors.get(current_state, 'white')
            ax4.axvspan(start_time, end_time, alpha=0.2, color=color)
            
            mid_time = (start_time + end_time) / 2
            ax4.text(mid_time, 0.05, current_state, 
                    transform=ax4.get_xaxis_transform(),
                    ha='center', va='bottom', fontsize=8,
                    bbox=dict(boxstyle='round', fc='white', alpha=0.8))
    
    # 绘制增益因子 - 修复数据问题
    gain_plotted = False
    if 'pacing_gain' in bbr_df_plot.columns:
        # 检查是否有有效的pacing_gain数据
        valid_pacing_mask = (~bbr_df_plot['pacing_gain'].isnull()) & (bbr_df_plot['pacing_gain'] > 0) & (bbr_df_plot['pacing_gain'] < 10)
        if valid_pacing_mask.any():
            ax4.plot(bbr_df_plot['time_sec'], bbr_df_plot['pacing_gain'], 'g-', linewidth=1.5, label='Pacing Gain')
            gain_plotted = True
            print(f"Found {valid_pacing_mask.sum()} valid pacing_gain values")
    
    if 'cwnd_gain' in bbr_df_plot.columns:
        # 检查是否有有效的cwnd_gain数据
        valid_cwnd_mask = (~bbr_df_plot['cwnd_gain'].isnull()) & (bbr_df_plot['cwnd_gain'] > 0) & (bbr_df_plot['cwnd_gain'] < 10)
        if valid_cwnd_mask.any():
            ax4.plot(bbr_df_plot['time_sec'], bbr_df_plot['cwnd_gain'], 'r--', linewidth=1.5, label='CWND Gain')
            gain_plotted = True
            print(f"Found {valid_cwnd_mask.sum()} valid cwnd_gain values")
    
    # 如果没有有效的增益数据，显示提示信息
    if not gain_plotted:
        # 显示调试信息
        pacing_gain_info = "No pacing_gain column"
        cwnd_gain_info = "No cwnd_gain column"
        
        if 'pacing_gain' in bbr_df_plot.columns:
            pacing_gain_count = (~bbr_df_plot['pacing_gain'].isnull()).sum()
            pacing_gain_info = f"pacing_gain: {pacing_gain_count} non-null values"
            if pacing_gain_count > 0:
                sample_values = bbr_df_plot['pacing_gain'].dropna().head(5).tolist()
                pacing_gain_info += f", samples: {sample_values}"
        
        if 'cwnd_gain' in bbr_df_plot.columns:
            cwnd_gain_count = (~bbr_df_plot['cwnd_gain'].isnull()).sum()
            cwnd_gain_info = f"cwnd_gain: {cwnd_gain_count} non-null values"
            if cwnd_gain_count > 0:
                sample_values = bbr_df_plot['cwnd_gain'].dropna().head(5).tolist()
                cwnd_gain_info += f", samples: {sample_values}"
        
        ax4.text(0.5, 0.5, f'No valid gain factor data available\n{pacing_gain_info}\n{cwnd_gain_info}', 
                transform=ax4.transAxes, ha='center', va='center', fontsize=10,
                bbox=dict(facecolor='white', alpha=0.8))
    
    # 为状态转换添加垂直线和时间标签
    if 'bbr_state' in bbr_df_plot.columns:
        state_changes = bbr_df_plot[bbr_df_plot['bbr_state'] != bbr_df_plot['bbr_state'].shift(1)]
        for _, row in state_changes.iterrows():
            ax4.axvline(x=row['time_sec'], color='darkgoldenrod', linestyle='--', alpha=0.6, linewidth=1.0)
            time_str = f"{row['time_sec']:.1f}s"
            ax4.text(row['time_sec'], -0.05, time_str, 
                    transform=ax4.get_xaxis_transform(),
                    ha='center', va='top', fontsize=8,
                    bbox=dict(boxstyle='round', fc='white', ec='black', alpha=0.9, pad=0.4))
    
    # 设置y轴的合理范围
    if gain_plotted:
        ax4.set_ylim(0, 4)  # BBR增益因子通常在0-4之间
    
    ax4.set_ylabel('Gain Factor')
    if gain_plotted:
        ax4.legend(loc='upper right')
    ax4.grid(True, alpha=0.3)
    ax4.set_title('BBR State Transitions and Gain Factors', **title_style)
    
    # 图5: 拥塞窗口 - 移除利用率黄线，避免遮挡统计信息
    ax5 = axes[current_ax_idx]
    current_ax_idx += 1
    
    if 'cwnd_kb' in bbr_df_plot.columns:
        ax5.plot(bbr_df_plot['time_sec'], bbr_df_plot['cwnd_kb'], 'b-', linewidth=2.0, label='CWND')
    if 'bytes_in_flight_kb' in bbr_df_plot.columns:
        ax5.plot(bbr_df_plot['time_sec'], bbr_df_plot['bytes_in_flight_kb'], 'r-', linewidth=1.5, label='Bytes in Flight')
    
    # 添加状态转换垂直线
    if 'bbr_state' in bbr_df_plot.columns:
        state_changes = bbr_df_plot[bbr_df_plot['bbr_state'] != bbr_df_plot['bbr_state'].shift(1)]
        for _, row in state_changes.iterrows():
            ax5.axvline(x=row['time_sec'], color='darkgoldenrod', linestyle='--', alpha=0.6, linewidth=1.0)
            ax5.text(row['time_sec'], ax5.get_ylim()[1]*0.9, row['bbr_state'], 
                    rotation=90, ha='right', va='top', fontsize=8,
                    bbox=dict(facecolor='white', alpha=0.8))
    
    # 添加CWND统计信息 - 放置在右上角避免遮挡
    stats_text = ""
    if 'cwnd_kb' in bbr_df.columns:
        median_cwnd = bbr_df['cwnd_kb'].median()
        max_cwnd = bbr_df['cwnd_kb'].max()
        min_cwnd = bbr_df['cwnd_kb'].min()
        stats_text += f"CWND (KB):\n  Median: {median_cwnd:.2f}\n  Max: {max_cwnd:.2f}\n  Min: {min_cwnd:.2f}\n\n"
    if 'bytes_in_flight_kb' in bbr_df.columns:
        avg_bif = bbr_df['bytes_in_flight_kb'].mean()
        max_bif = bbr_df['bytes_in_flight_kb'].max()
        min_bif = bbr_df['bytes_in_flight_kb'].min()
        stats_text += f"Bytes in Flight (KB):\n  Avg: {avg_bif:.2f}\n  Max: {max_bif:.2f}\n  Min: {min_bif:.2f}\n"
        if 'cwnd_kb' in bbr_df.columns:
            median_util = (bbr_df['bytes_in_flight_kb'] / bbr_df['cwnd_kb'] * 100).median()
            stats_text += f"Median Utilization: {median_util:.1f}%"
    
    if stats_text:
        ax5.text(0.98, 0.98, stats_text, transform=ax5.transAxes, 
                verticalalignment='top', horizontalalignment='right', bbox=dict(facecolor='white', alpha=0.7))
    
    ax5.set_ylabel('Size (KB)')
    ax5.set_title('Congestion Window', **title_style)
    ax5.grid(True, alpha=0.3)
    ax5.legend(loc='upper left')
    
    # 图6: Send Delay 和 Ack Delay - 新增的延迟分析图
    ax6 = axes[current_ax_idx]
    current_ax_idx += 1
    
    delay_plotted = False
    if 'send_delay_ms' in bbr_df_plot.columns:
        # 检查是否有有效的send_delay数据
        valid_send_mask = (~bbr_df_plot['send_delay_ms'].isnull()) & (bbr_df_plot['send_delay_ms'] > 0) & (bbr_df_plot['send_delay_ms'] < 10000)
        if valid_send_mask.any():
            ax6.plot(bbr_df_plot['time_sec'], bbr_df_plot['send_delay_ms'], 'g-', linewidth=1.5, 
                    label='Send Delay (ms)', alpha=0.8)
            delay_plotted = True
            print(f"Found {valid_send_mask.sum()} valid send_delay values")
    
    if 'ack_delay_ms' in bbr_df_plot.columns:
        # 检查是否有有效的ack_delay数据
        valid_ack_mask = (~bbr_df_plot['ack_delay_ms'].isnull()) & (bbr_df_plot['ack_delay_ms'] > 0) & (bbr_df_plot['ack_delay_ms'] < 10000)
        if valid_ack_mask.any():
            ax6.plot(bbr_df_plot['time_sec'], bbr_df_plot['ack_delay_ms'], 'orange', linewidth=1.5, 
                    label='Ack Delay (ms)', alpha=0.8, linestyle='--')
            delay_plotted = True
            print(f"Found {valid_ack_mask.sum()} valid ack_delay values")
    
    # 添加状态转换垂直线
    if 'bbr_state' in bbr_df_plot.columns:
        state_changes = bbr_df_plot[bbr_df_plot['bbr_state'] != bbr_df_plot['bbr_state'].shift(1)]
        for _, row in state_changes.iterrows():
            ax6.axvline(x=row['time_sec'], color='darkgoldenrod', linestyle='--', alpha=0.6, linewidth=1.0)
            ax6.text(row['time_sec'], ax6.get_ylim()[1]*0.9, row['bbr_state'], 
                    rotation=90, ha='right', va='top', fontsize=8,
                    bbox=dict(facecolor='white', alpha=0.8))
    
    # 如果有延迟数据，添加统计信息
    if delay_plotted:
        stats_text = ""
        if 'send_delay_ms' in bbr_df.columns and not bbr_df['send_delay_ms'].isnull().all():
            avg_send_delay = bbr_df['send_delay_ms'].mean()
            max_send_delay = bbr_df['send_delay_ms'].max()
            median_send_delay = bbr_df['send_delay_ms'].median()
            stats_text += f"Send Delay (ms):\n  Avg: {avg_send_delay:.2f}\n  Max: {max_send_delay:.2f}\n  Median: {median_send_delay:.2f}\n\n"
        
        if 'ack_delay_ms' in bbr_df.columns and not bbr_df['ack_delay_ms'].isnull().all():
            avg_ack_delay = bbr_df['ack_delay_ms'].mean()
            max_ack_delay = bbr_df['ack_delay_ms'].max()
            median_ack_delay = bbr_df['ack_delay_ms'].median()
            stats_text += f"Ack Delay (ms):\n  Avg: {avg_ack_delay:.2f}\n  Max: {max_ack_delay:.2f}\n  Median: {median_ack_delay:.2f}"
        
        if stats_text:
            ax6.text(0.02, 0.98, stats_text, transform=ax6.transAxes, 
                    verticalalignment='top', bbox=dict(facecolor='white', alpha=0.8))
        
        ax6.legend(loc='upper right')
    else:
        # 显示调试信息
        send_delay_info = "No send_delay_ms column"
        ack_delay_info = "No ack_delay_ms column"
        
        if 'send_delay_ms' in bbr_df_plot.columns:
            send_delay_count = (~bbr_df_plot['send_delay_ms'].isnull()).sum()
            send_delay_info = f"send_delay_ms: {send_delay_count} non-null values"
            if send_delay_count > 0:
                sample_values = bbr_df_plot['send_delay_ms'].dropna().head(5).tolist()
                send_delay_info += f", samples: {[f'{v:.2f}' for v in sample_values]}"
        
        if 'ack_delay_ms' in bbr_df_plot.columns:
            ack_delay_count = (~bbr_df_plot['ack_delay_ms'].isnull()).sum()
            ack_delay_info = f"ack_delay_ms: {ack_delay_count} non-null values"
            if ack_delay_count > 0:
                sample_values = bbr_df_plot['ack_delay_ms'].dropna().head(5).tolist()
                ack_delay_info += f", samples: {[f'{v:.2f}' for v in sample_values]}"
        
        ax6.text(0.5, 0.5, f'No valid delay data available\n{send_delay_info}\n{ack_delay_info}', 
                transform=ax6.transAxes, ha='center', va='center', fontsize=10,
                bbox=dict(facecolor='white', alpha=0.8))
    
    ax6.set_ylabel('Delay (ms)')
    ax6.set_title('BBR Send and Ack Delays (for Delivery Rate Calculation)', **title_style)
    ax6.grid(True, alpha=0.3)
    
    # 图7: 丢包事件 - 只显示每个时刻的丢包，不显示累计和丢包率
    ax7 = axes[current_ax_idx]
    current_ax_idx += 1
    
    if 'lost_packets' in bbr_df_plot.columns and not bbr_df_plot['lost_packets'].isnull().all():
        # 计算每个时刻的新增丢包数
        if len(bbr_df_plot) > 1:
            lost_diff = bbr_df_plot['lost_packets'].diff().fillna(0)
            lost_diff = lost_diff.clip(lower=0)  # 确保非负值
            
            # 绘制每个时刻的丢包事件
            ax7.plot(bbr_df_plot['time_sec'], lost_diff, 'r-', linewidth=1.5, label='Packet Loss per Sample', alpha=0.8)
            ax7.scatter(bbr_df_plot['time_sec'][lost_diff > 0], lost_diff[lost_diff > 0], 
                       c='red', s=20, alpha=0.8, label='Loss Events')
        
        # 添加丢包统计信息
        total_losses = bbr_df['lost_packets'].iloc[-1] if len(bbr_df) > 0 else 0
        total_time = bbr_df['time_sec'].iloc[-1] - bbr_df['time_sec'].iloc[0] if len(bbr_df) > 1 else 1
        avg_loss_rate = total_losses / total_time if total_time > 0 else 0
        
        if len(bbr_df_plot) > 1:
            loss_events = (lost_diff > 0).sum()
            max_loss_per_sample = lost_diff.max()
            stats_text = f"Total Lost Packets: {int(total_losses)}\nLoss Events: {loss_events}\nMax Loss/Sample: {int(max_loss_per_sample)}\nAvg Loss Rate: {avg_loss_rate:.2f}/sec"
        else:
            stats_text = f"Total Lost Packets: {int(total_losses)}"
        
        ax7.text(0.02, 0.98, stats_text, transform=ax7.transAxes, 
                verticalalignment='top', bbox=dict(facecolor='white', alpha=0.8))
        
        ax7.legend(loc='upper right')
    else:
        ax7.text(0.5, 0.5, 'No packet loss data available', 
                transform=ax7.transAxes, ha='center', va='center', fontsize=12,
                bbox=dict(facecolor='white', alpha=0.8))
    
    ax7.set_ylabel('Packet Loss per Sample')
    ax7.set_title('Packet Loss Events', **title_style)
    ax7.grid(True, alpha=0.3)
    
    # 图8: 重传事件图 - 学习示例代码的重传画法
    if retransmission_df is not None and not retransmission_df.empty:
        ax8 = axes[current_ax_idx]
        current_ax_idx += 1
        
        # 计算重传事件的分布 - 学习示例代码
        bin_size = 1.0  # 1秒为一个bin
        max_time = retransmission_df['time_sec'].max()
        min_time = retransmission_df['time_sec'].min()
        bins = np.arange(min_time, max_time + bin_size, bin_size)
        hist, bin_edges = np.histogram(retransmission_df['time_sec'], bins=bins)
        
        # 绘制重传频率
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        ax8.bar(bin_centers, hist, width=bin_size*0.8, alpha=0.7, color='red', edgecolor='darkred')
        
        ax8.set_ylabel('Packet losses per second')
        ax8.set_title('Packet Loss Events Over Time', **title_style)
        ax8.grid(True, alpha=0.3)
        
        # 添加统计信息 - 学习示例代码
        total_losses = len(retransmission_df)
        total_duration = max_time - min_time if max_time > min_time else max_time
        avg_loss_per_sec = total_losses / total_duration if total_duration > 0 else 0
        
        # 计算丢包率（如果有BBR数据的话）
        loss_rate_text = ""
        if 'packet_number' in retransmission_df.columns:
            max_packet = retransmission_df['packet_number'].max()
            if max_packet:
                loss_rate = (total_losses / max_packet) * 100
                loss_rate_text = f"\nLoss rate: {loss_rate:.3f}%"
        
        ax8.text(0.02, 0.98, f'Total: {total_losses} lost packets\nAvg: {avg_loss_per_sec:.2f}/sec{loss_rate_text}', 
                transform=ax8.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # 为所有子图设置统一的X轴格式
    for ax_idx in range(current_ax_idx):
        ax = axes[ax_idx]
        if bbr_df_plot is not None and not bbr_df_plot.empty:
            total_duration = bbr_df_plot['time_sec'].max() - bbr_df_plot['time_sec'].min()
            
            if total_duration <= 30:
                ax.xaxis.set_major_locator(MultipleLocator(5))
            elif total_duration <= 120:
                ax.xaxis.set_major_locator(MultipleLocator(10))
            elif total_duration <= 600:
                ax.xaxis.set_major_locator(MultipleLocator(30))
            else:
                ax.xaxis.set_major_locator(MultipleLocator(60))
            
            ax.grid(True, which='major', axis='x', linestyle='-', alpha=0.3)
    
    # 只在最底部的子图显示x轴标签
    for ax_idx in range(current_ax_idx - 1):
        axes[ax_idx].set_xlabel('')
    
    # 最后一个子图显示x轴标签
    axes[current_ax_idx - 1].set_xlabel('Time (seconds)')
    
    # 添加数据信息到图表标题
    if not aggregated and original_length != len(bbr_df_plot):
        fig.suptitle(f'BBR Analysis - All Original Data Points (Showing {len(bbr_df_plot):,} of {original_length:,} points)', 
                    fontsize=16, fontweight='bold', y=0.98)
    elif not aggregated:
        fig.suptitle(f'BBR Analysis - All Original Data Points ({len(bbr_df_plot):,} points)', 
                    fontsize=16, fontweight='bold', y=0.98)
    else:
        fig.suptitle(f'BBR Analysis - Aggregated Data ({len(bbr_df_plot):,} points)', 
                    fontsize=16, fontweight='bold', y=0.98)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Charts saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="BBR 4-Chart Analyzer")
    parser.add_argument("log_file", help="Path to the log file")
    parser.add_argument("--output", help="Output image path")
    parser.add_argument("--max-lines", type=int, help="Maximum lines to process")
    parser.add_argument("--time-window", type=float, default=0.1, help="Time window for data aggregation in seconds (default: 0.1)")
    parser.add_argument("--aggregate", action="store_true", help="Aggregate data points by time window")
    parser.add_argument("--rtt-style", choices=['scatter', 'line', 'density', 'percentiles'], 
                       default='scatter', help="RTT visualization style (default: scatter)")
    args = parser.parse_args()
    
    # 确定输出文件路径
    output_file = args.output
    if not output_file:
        basename = os.path.basename(args.log_file).split('.')[0]
        suffix = "_aggregated" if args.aggregate else "_all_points"
        output_file = f"{basename}_bbr_4charts{suffix}.png"
    
    # 分析日志 - 默认使用所有数据点，除非指定--aggregate
    aggregate_data = args.aggregate
    bbr_df, delivery_rate_df, retransmission_df = analyze_log(args.log_file, args.max_lines, args.time_window, aggregate_data)
    
    if bbr_df is None:
        print("No BBR data found in log file.")
        return
    
    # 绘制BBR分析图表（包含延迟分析）
    plot_four_charts(bbr_df, delivery_rate_df, retransmission_df, output_file, aggregate_data, args.rtt_style)
    
    # 打印基本统计信息
    print(f"\n📊 Analysis Summary:")
    print(f"   Total BBR entries: {len(bbr_df)}")
    print(f"   Duration: {bbr_df['time_sec'].max():.2f} seconds")
    
    if 'bbr_state' in bbr_df.columns:
        state_counts = bbr_df['bbr_state'].value_counts()
        print(f"   BBR State Distribution:")
        for state, count in state_counts.items():
            percentage = (count / len(bbr_df)) * 100
            print(f"     {state}: {count} ({percentage:.1f}%)")
    
    if retransmission_df is not None and not retransmission_df.empty:
        print(f"   Total packet losses: {len(retransmission_df)}")
    else:
        print(f"   No packet loss events detected")

if __name__ == "__main__":
    plt.switch_backend('agg')
    main() 