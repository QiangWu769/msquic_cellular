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
    packet_lost_events = []  # 存储丢包事件
    
    # 添加计数器来跟踪各种事件类型
    sent_count = 0
    acked_count = 0
    lost_count = 0
    other_count = 0
    
    # 跟踪上一个ACK事件的TotalLost值
    last_ack_total_lost = 0
    
    line_count = 0
    print(f"Analyzing log file: {log_file}")
    
    with open(log_file, 'r') as f:
        for line in f:
            line_count += 1
            if max_lines and line_count > max_lines:
                break
                
            if line_count % 1000 == 0:
                print(f"Processed {line_count} lines...")
            
            # 处理BBR-PKT-SENT、BBR-PKT-ACKED和BBR-PKT-LOST格式的日志
            is_bbr_pkt_sent = "[BBR-PKT-SENT]" in line
            is_bbr_pkt_acked = "[BBR-PKT-ACKED]" in line
            is_bbr_pkt_lost = "[BBR-PKT-LOST]" in line
            
            # 更新事件计数
            if is_bbr_pkt_sent:
                sent_count += 1
            elif is_bbr_pkt_acked:
                acked_count += 1
            elif is_bbr_pkt_lost:
                lost_count += 1
            else:
                other_count += 1
            
            try:
                # 解析时间戳
                time_match = re.search(r'T=([\d\.]+) s', line)
                if not time_match:
                    continue
                    
                time_sec = float(time_match.group(1))
                
                # 提取包号和大小
                pkt_match = re.search(r'PKT=(\d+)', line)
                size_match = re.search(r'Size=(\d+) B', line)
                packet_number = int(pkt_match.group(1)) if pkt_match else 0
                packet_size = int(size_match.group(1)) if size_match else 0
                
                # 提取TotalLost
                total_sent_match = re.search(r'TotalSent=(\d+)', line)
                total_lost_match = re.search(r'TotalLost=(\d+)', line)
                total_sent = int(total_sent_match.group(1)) if total_sent_match else 0
                total_lost = int(total_lost_match.group(1)) if total_lost_match else 0
                
                # 更新ACK事件的TotalLost
                if is_bbr_pkt_acked:
                    last_ack_total_lost = total_lost
                    continue
                
                if not (is_bbr_pkt_sent or is_bbr_pkt_lost):
                    continue
                    
                # 提取估计带宽
                estbw_match = re.search(r'EstBW=([\d\.]+) Mbps', line)
                estbw_mbps = float(estbw_match.group(1)) if estbw_match else 0
                
                # 提取Pacing Rate
                pacing_match = re.search(r'PacingRate=([\d\.]+) Mbps', line)
                pacing_rate_mbps = float(pacing_match.group(1)) if pacing_match else 0
                
                # 提取Delivery Rate
                delivery_match = re.search(r'DeliveryRate=([\d\.]+) Mbps', line)
                delivery_rate_mbps = float(delivery_match.group(1)) if delivery_match else 0
                
                # 提取RTT
                rtt_match = re.search(r'RTT=(\d+) us', line)
                rtt_us = int(rtt_match.group(1)) if rtt_match else 0
                
                # 提取MinRTT
                min_rtt_match = re.search(r'MinRTT=(\d+) us', line)
                min_rtt_us = int(min_rtt_match.group(1)) if min_rtt_match else 0
                
                # 提取CWND
                cwnd_match = re.search(r'CWND=(\d+) B', line)
                cwnd_bytes = int(cwnd_match.group(1)) if cwnd_match else 0
                
                # 提取InFlight
                inflight_match = re.search(r'InFlight=(\d+) B', line)
                inflight_bytes = int(inflight_match.group(1)) if inflight_match else 0
                
                # 提取Loss率和丢包数
                loss_rate_match = re.search(r'Loss=([\d\.]+)%', line)
                loss_rate = float(loss_rate_match.group(1)) if loss_rate_match else 0.0
                
                # 提取BBR State
                state_match = re.search(r'State=(\w+)', line)
                bbr_state = state_match.group(1) if state_match else "Unknown"
                
                # 提取Send Delay和Ack Delay
                send_delay_match = re.search(r'SendDelay=(\d+) us', line)
                ack_delay_match = re.search(r'AckDelay=(\d+) us', line)
                send_delay_us = int(send_delay_match.group(1)) if send_delay_match else 0
                ack_delay_us = int(ack_delay_match.group(1)) if ack_delay_match else 0
                
                # 提取PacingGain和CwndGain
                pacing_gain_match = re.search(r'PacingGain=([\d\.]+)x', line)
                cwnd_gain_match = re.search(r'CwndGain=([\d\.]+)x', line)
                pacing_gain = float(pacing_gain_match.group(1)) if pacing_gain_match else 0
                cwnd_gain = float(cwnd_gain_match.group(1)) if cwnd_gain_match else 0
                
                if is_bbr_pkt_sent:
                    # 处理所有SENT事件，不再仅限于ACK后的第一个
                    # 创建数据点
                    data_point = {
                        'time_sec': time_sec,
                        'packet_number': packet_number,
                        'packet_size': packet_size,
                        'send_mbps': 0,  # 这些字段在新日志中没有，设为0
                        'recv_mbps': 0,
                        'btlbw_mbps': estbw_mbps,
                        'pacing_rate_mbps': pacing_rate_mbps,
                        'delivery_rate_mbps': delivery_rate_mbps,
                        'rtt_ms': rtt_us / 1000.0,  # 转换为毫秒
                        'rtprop_ms': min_rtt_us / 1000.0,  # 转换为毫秒
                        'cwnd_kb': cwnd_bytes / 1024.0,  # 转换为KB
                        'bytes_in_flight_kb': inflight_bytes / 1024.0,  # 转换为KB
                        'lost_packets': total_lost,
                        'loss_rate': loss_rate,  # 保存丢包率
                        'bbr_state': bbr_state,
                        'pacing_gain': pacing_gain,  # 使用从日志中提取的增益因子
                        'cwnd_gain': cwnd_gain,
                        'send_delay_ms': send_delay_us / 1000.0,  # 转换为毫秒
                        'ack_delay_ms': ack_delay_us / 1000.0,     # 转换为毫秒
                        'raw_log': line.strip(),  # 保存原始日志行
                        'is_valid': True  # 所有SENT事件都标记为有效
                    }
                    
                    # 将数据点添加到列表
                    bbr_data.append(data_point)
                
                # 如果是丢包事件，记录丢包信息
                if is_bbr_pkt_lost:
                    # 计算这次丢包事件的实际丢包数（相对于上一个ACK事件）
                    actual_lost_packets = total_lost - last_ack_total_lost
                    if actual_lost_packets < 0:
                        actual_lost_packets = 1  # 防止出现负数，至少丢了1个包
                        
                    persistent_congestion = "YES" in line if "PersistentCongestion=YES" in line else False
                    packet_lost_events.append({
                        'time_sec': time_sec,
                        'packet_number': packet_number,
                        'packet_size': packet_size,
                        'lost_packets': actual_lost_packets,  # 这次事件的实际丢包数
                        'total_lost': total_lost,             # 保留累计丢包数用于参考
                        'total_sent': total_sent,
                        'loss_rate': loss_rate,
                        'persistent_congestion': persistent_congestion,
                        'pacing_gain': pacing_gain,           # 添加pacing_gain
                        'cwnd_gain': cwnd_gain,               # 添加cwnd_gain
                        'raw_log': line.strip()  # 保存原始日志行
                    })
                
            except Exception as e:
                if line_count < 20:  # 只对前20行打印错误
                    print(f"Error parsing line {line_count}: {str(e)}")
                    print(f"Line content: {line[:100]}...")
    
    # 打印详细的事件统计
    print(f"\n=== Detailed Event Statistics ===")
    print(f"Total lines: {line_count}")
    print(f"SENT events: {sent_count} ({sent_count/line_count*100:.1f}%)")
    print(f"ACKED events: {acked_count} ({acked_count/line_count*100:.1f}%)")
    print(f"LOST events: {lost_count} ({lost_count/line_count*100:.1f}%)")
    print(f"Other lines: {other_count} ({other_count/line_count*100:.1f}%)")
    print(f"Total sampled SENT events: {len(bbr_data)} ({len(bbr_data)/sent_count*100:.1f}% of SENT)")
    print(f"=== End of Event Statistics ===\n")
    
    print(f"Finished processing {line_count} lines. Found {len(bbr_data)} SENT events and {len(packet_lost_events)} packet loss events.")
    
    if not bbr_data:
        return None, None, None
    
    # 创建DataFrame
    bbr_df = pd.DataFrame(bbr_data)
    
    # 按时间排序
    bbr_df = bbr_df.sort_values('time_sec').reset_index(drop=True)
    
    # 将所有采样点的具体数值输出到TXT文件
    output_txt_file = os.path.splitext(log_file)[0] + "_sampling_points.txt"
    with open(output_txt_file, 'w') as f:
        f.write("=== BBR Sampling Points Detailed Data ===\n")
        f.write(f"Total sampling points: {len(bbr_df)}\n")
        f.write(f"Data sampling method: All SENT events\n\n")
        
        f.write("No.,Time(s),PacketNo,Size(B),EstBW(Mbps),PacingRate(Mbps),DeliveryRate(Mbps),RTT(ms),MinRTT(ms),CWND(KB),BytesInFlight(KB),LostPackets,LossRate(%),BBRState,SendDelay(ms),AckDelay(ms),PacingGain,CwndGain\n")
        
        for i, row in bbr_df.iterrows():
            f.write(f"{i+1},{row['time_sec']:.3f},{row['packet_number']},{row['packet_size']:.0f},{row['btlbw_mbps']:.2f},{row['pacing_rate_mbps']:.2f},{row['delivery_rate_mbps']:.2f},{row['rtt_ms']:.2f},{row['rtprop_ms']:.2f},{row['cwnd_kb']:.2f},{row['bytes_in_flight_kb']:.2f},{row['lost_packets']},{row['loss_rate']:.2f},{row['bbr_state']},{row['send_delay_ms']:.2f},{row['ack_delay_ms']:.2f},{row['pacing_gain']:.2f},{row['cwnd_gain']:.2f}\n")
        
        f.write("\n=== Raw Log Lines ===\n")
        for i, row in bbr_df.iterrows():
            if 'raw_log' in row:
                f.write(f"{i+1}: {row['raw_log']}\n")
    
    print(f"Sampling points detailed data saved to: {output_txt_file}")
    
    if aggregate:
        # 数据聚合处理：按时间窗口分组
        print(f"Aggregating data with time window: {time_window}s...")
        
        # 创建时间窗口标识符
        bbr_df['time_window'] = (bbr_df['time_sec'] / time_window).round() * time_window
        
        # 按时间窗口聚合数据 - 使用平均值而不是累加
        agg_functions = {
            'time_sec': 'first',  # 使用第一个时间戳作为代表
            'packet_number': 'max',
            'packet_size': 'mean',
            'send_mbps': 'mean',
            'recv_mbps': 'mean', 
            'btlbw_mbps': 'mean',  # 使用平均值
            'pacing_rate_mbps': 'mean',  # 使用平均值
            'delivery_rate_mbps': 'mean',  # 使用平均值
            'rtt_ms': 'mean',
            'rtprop_ms': 'min',  # MinRTT使用最小值
            'cwnd_kb': 'mean',
            'bytes_in_flight_kb': 'mean',
            'lost_packets': 'max',  # 丢包数使用最大值（累积）
            'loss_rate': 'mean',    # 使用平均丢包率
            'bbr_state': 'last',    # BBR状态使用最后一个
            'pacing_gain': 'mean',
            'cwnd_gain': 'mean',
            'send_delay_ms': 'mean',
            'ack_delay_ms': 'mean',
            'is_valid': 'all'       # 保留有效性标记
        }
        
        # 执行聚合
        bbr_df_final = bbr_df.groupby('time_window').agg(agg_functions).reset_index()
        
        # 按时间排序
        bbr_df_final = bbr_df_final.sort_values('time_sec').reset_index(drop=True)
        
        print(f"Data aggregated: {len(bbr_data)} -> {len(bbr_df_final)} data points")
    else:
        # 不聚合，使用所有原始数据点
        print("Keeping all original data points (no aggregation)...")
        bbr_df_final = bbr_df
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
    
    # 创建丢包事件DataFrame
    packet_lost_df = None
    if packet_lost_events:
        packet_lost_df = pd.DataFrame(packet_lost_events)
        print(f"Found {len(packet_lost_df)} packet loss events")
    
    return bbr_df_final, None, packet_lost_df

def plot_four_charts(bbr_df, delivery_rate_df, retransmission_df, output_file, aggregated=False, rtt_style='scatter'):
    """绘制BBR分析图表 - 包含延迟分析和丢包分析的完整图表集合"""
    if bbr_df is None:
        print("No BBR data to plot.")
        return
    
    # 对于非聚合的大数据集，进行采样以提高性能
    original_length = len(bbr_df)
    # 不再对大数据集进行采样，始终使用全部数据点
    bbr_df_plot = bbr_df
    print(f"Plotting all {len(bbr_df_plot)} data points")
    
    # 提高绘图性能
    plt.rcParams['path.simplify'] = True
    plt.rcParams['path.simplify_threshold'] = 0.8
    plt.rcParams['agg.path.chunksize'] = 10000
    
    # 设置高质量绘图样式
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # 确定需要的子图数量
    num_subplots = 7  # 基础图表数量（6个原有图表 + 1个合并的丢包图表）
    
    # 创建竖直排列的子图
    fig, axes = plt.subplots(num_subplots, 1, figsize=(14, num_subplots * 3.5), dpi=150)
    plt.subplots_adjust(hspace=0.35)  # 增大子图间距，使标题和坐标轴不重叠
    
    # 确保axes是数组形式
    if num_subplots == 1:
        axes = [axes]
    
    # 为标题设置统一样式
    title_style = dict(fontsize=14, fontweight='bold', 
                     bbox=dict(facecolor='white', alpha=0.9, edgecolor='lightgray', boxstyle='round,pad=0.5'))
    
    current_ax_idx = 0
    
    # 图1: 带宽估计和传输速率
    ax1 = axes[current_ax_idx]
    current_ax_idx += 1
    
    # 只使用有效的SENT点进行统计计算
    valid_df = bbr_df[bbr_df['is_valid']] if 'is_valid' in bbr_df.columns else bbr_df
    
    # Filter valid values for statistics calculation
    btlbw_filtered = valid_df['btlbw_mbps'][valid_df['btlbw_mbps'] > 1] if 'btlbw_mbps' in valid_df.columns else pd.Series()
    pacing_rate_filtered = valid_df['pacing_rate_mbps'][valid_df['pacing_rate_mbps'] > 1] if 'pacing_rate_mbps' in valid_df.columns else pd.Series()
    delivery_rate_filtered = valid_df['delivery_rate_mbps'][valid_df['delivery_rate_mbps'] > 1] if 'delivery_rate_mbps' in valid_df.columns else pd.Series()
    
    # 计算非零值的百分比
    btlbw_nonzero_pct = len(btlbw_filtered) / len(valid_df) * 100 if len(valid_df) > 0 and 'btlbw_mbps' in valid_df.columns else 0
    pacing_nonzero_pct = len(pacing_rate_filtered) / len(valid_df) * 100 if len(valid_df) > 0 and 'pacing_rate_mbps' in valid_df.columns else 0
    delivery_nonzero_pct = len(delivery_rate_filtered) / len(valid_df) * 100 if len(valid_df) > 0 and 'delivery_rate_mbps' in valid_df.columns else 0
    
    if 'btlbw_mbps' in bbr_df_plot.columns:
        ax1.plot(bbr_df_plot['time_sec'], bbr_df_plot['btlbw_mbps'], 'b-', linewidth=1.5, label='BtlBw (Mbps)')
    
    if 'pacing_rate_mbps' in bbr_df_plot.columns:
        ax1.plot(bbr_df_plot['time_sec'], bbr_df_plot['pacing_rate_mbps'], 'g--', linewidth=1.2, label='Pacing Rate (Mbps)')
        
        # 添加平均pacing rate的水平线
        if len(pacing_rate_filtered) > 0:
            avg_pacing_rate = pacing_rate_filtered.mean()
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
    if 'btlbw_mbps' in valid_df.columns:
        avg_btlbw = btlbw_filtered.mean() if len(btlbw_filtered) > 0 else 0
        max_btlbw = btlbw_filtered.max() if len(btlbw_filtered) > 0 else 0
        min_btlbw = btlbw_filtered.min() if len(btlbw_filtered) > 0 else 0
        stats_text += f"Avg BtlBw: {avg_btlbw:.2f} Mbps\n"
        stats_text += f"Max BtlBw: {max_btlbw:.2f} Mbps\n"
        stats_text += f"Min BtlBw: {min_btlbw:.2f} Mbps\n\n"
    
    if 'pacing_rate_mbps' in valid_df.columns:
        avg_pacing_rate = pacing_rate_filtered.mean() if len(pacing_rate_filtered) > 0 else 0
        max_pacing_rate = pacing_rate_filtered.max() if len(pacing_rate_filtered) > 0 else 0
        min_pacing_rate = pacing_rate_filtered.min() if len(pacing_rate_filtered) > 0 else 0
        stats_text += f"Avg Pacing Rate: {avg_pacing_rate:.2f} Mbps\n"
        stats_text += f"Max Pacing Rate: {max_pacing_rate:.2f} Mbps\n"
        stats_text += f"Min Pacing Rate: {min_pacing_rate:.2f} Mbps\n\n"
    
    if 'delivery_rate_mbps' in valid_df.columns:
        avg_delivery = delivery_rate_filtered.mean() if len(delivery_rate_filtered) > 0 else 0
        max_delivery = delivery_rate_filtered.max() if len(delivery_rate_filtered) > 0 else 0
        min_delivery = delivery_rate_filtered.min() if len(delivery_rate_filtered) > 0 else 0
        stats_text += f"Avg Delivery: {avg_delivery:.2f} Mbps\n"
        stats_text += f"Max Delivery: {max_delivery:.2f} Mbps\n"
        stats_text += f"Min Delivery: {min_delivery:.2f} Mbps"
    
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
    
    # 添加RTT统计信息框 - 使用valid_df替代bbr_df
    stats_text = ""
    if 'rtprop_ms' in valid_df.columns and not valid_df['rtprop_ms'].isnull().all():
        avg_rtprop = valid_df['rtprop_ms'].mean()
        median_rtprop = valid_df['rtprop_ms'].median()
        max_rtprop = valid_df['rtprop_ms'].max()
        min_rtprop = valid_df['rtprop_ms'].min()
        stats_text += f"RTprop (ms):\n  Avg: {avg_rtprop:.2f}\n  Median: {median_rtprop:.2f}\n  Max: {max_rtprop:.2f}\n  Min: {min_rtprop:.2f}\n\n"

    if 'rtt_ms' in valid_df.columns and not valid_df['rtt_ms'].isnull().all():
        avg_latest_rtt = valid_df['rtt_ms'].mean()
        median_latest_rtt = valid_df['rtt_ms'].median()
        max_latest_rtt = valid_df['rtt_ms'].max()
        min_latest_rtt = valid_df['rtt_ms'].min()
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
    
    # 添加CWND统计信息 - 放置在右上角避免遮挡，使用valid_df
    stats_text = ""
    if 'cwnd_kb' in valid_df.columns:
        median_cwnd = valid_df['cwnd_kb'].median()
        max_cwnd = valid_df['cwnd_kb'].max()
        min_cwnd = valid_df['cwnd_kb'].min()
        stats_text += f"CWND (KB):\n  Median: {median_cwnd:.2f}\n  Max: {max_cwnd:.2f}\n  Min: {min_cwnd:.2f}\n\n"
    if 'bytes_in_flight_kb' in valid_df.columns:
        avg_bif = valid_df['bytes_in_flight_kb'].mean()
        max_bif = valid_df['bytes_in_flight_kb'].max()
        min_bif = valid_df['bytes_in_flight_kb'].min()
        stats_text += f"Bytes in Flight (KB):\n  Avg: {avg_bif:.2f}\n  Max: {max_bif:.2f}\n  Min: {min_bif:.2f}\n"
        if 'cwnd_kb' in valid_df.columns:
            median_util = (valid_df['bytes_in_flight_kb'] / valid_df['cwnd_kb'] * 100).median()
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
    
    # 如果有延迟数据，添加统计信息 - 使用valid_df
    if delay_plotted:
        stats_text = ""
        if 'send_delay_ms' in valid_df.columns and not valid_df['send_delay_ms'].isnull().all():
            avg_send_delay = valid_df['send_delay_ms'].mean()
            max_send_delay = valid_df['send_delay_ms'].max()
            median_send_delay = valid_df['send_delay_ms'].median()
            stats_text += f"Send Delay (ms):\n  Avg: {avg_send_delay:.2f}\n  Max: {max_send_delay:.2f}\n  Median: {median_send_delay:.2f}\n\n"
        
        if 'ack_delay_ms' in valid_df.columns and not valid_df['ack_delay_ms'].isnull().all():
            avg_ack_delay = valid_df['ack_delay_ms'].mean()
            max_ack_delay = valid_df['ack_delay_ms'].max()
            median_ack_delay = valid_df['ack_delay_ms'].median()
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
    
    # 图7: 合并后的丢包分析图 - 显示丢包事件数量和丢包总数
    ax7 = axes[current_ax_idx]
    current_ax_idx += 1
    
    if retransmission_df is not None and not retransmission_df.empty:
        # 使用柱状图代替散点图来显示丢包事件
        # 创建时间桶（bins）- 根据总时长设置合理的桶大小
        total_duration = retransmission_df['time_sec'].max() - retransmission_df['time_sec'].min()
        
        # 动态调整bin大小
        if total_duration <= 1.0:
            bin_size = 0.01  # 10ms
        elif total_duration <= 5.0:
            bin_size = 0.05  # 50ms
        elif total_duration <= 10.0:
            bin_size = 0.1   # 100ms
        elif total_duration <= 60.0:
            bin_size = 0.5   # 500ms
        else:
            bin_size = 1.0   # 1s
        
        # 创建时间桶
        min_time = retransmission_df['time_sec'].min()
        max_time = retransmission_df['time_sec'].max()
        
        # 确保至少有一个bin
        if max_time == min_time:
            max_time = min_time + bin_size
        
        # 确保时间范围与总日志数据一致，以便与其他图表对齐
        if bbr_df is not None and not bbr_df.empty:
            global_min_time = bbr_df['time_sec'].min()
            global_max_time = bbr_df['time_sec'].max()
            
            if global_min_time < min_time:
                min_time = global_min_time
            
            if global_max_time > max_time:
                max_time = global_max_time
            
        bins = np.arange(min_time, max_time + bin_size, bin_size)
        
        # 计算bin中心点位置（用于绘图）
        bin_centers = (bins[:-1] + bins[1:]) / 2
        
        # 创建一个新的DataFrame，按时间bin分组并聚合丢包数据
        bin_indices = np.digitize(retransmission_df['time_sec'], bins) - 1
        
        # 确保索引在有效范围内
        bin_indices = np.clip(bin_indices, 0, len(bins)-2)
        
        # 创建包含bin索引和丢包数的DataFrame
        binned_data = pd.DataFrame({
            'bin_idx': bin_indices,
            'lost_packets': retransmission_df['lost_packets']
        })
        
        # Group by bin and aggregate lost packets
        agg_data = binned_data.groupby('bin_idx').agg({
            'lost_packets': 'sum',  # Calculate total lost packets in each bin
        }).reset_index()
        
        # 计算每个bin中的事件数量
        event_counts = binned_data.groupby('bin_idx').size().reset_index(name='event_count')
        
        # 合并丢包数和事件数
        agg_data = pd.merge(agg_data, event_counts, on='bin_idx', how='left')
        
        # 创建完整的bin数组（包括没有丢包的bin）
        full_bin_data = pd.DataFrame({
            'bin_idx': range(len(bins) - 1),
            'bin_center': bin_centers
        })
        
        # 合并数据
        merged_data = full_bin_data.merge(agg_data, on='bin_idx', how='left').fillna(0)
        
        # 创建双Y轴图表
        ax7b = ax7.twinx()
        
        # 绘制柱状图 - 显示每个时间段内的事件数量
        bar_container = ax7.bar(merged_data['bin_center'], merged_data['event_count'], 
               width=bin_size*0.8, alpha=0.6, color='blue', edgecolor='darkblue', 
               label='Loss Events Count')
        
        # 使用折线图显示每个时间段内的总丢包数，只在有丢包的点显示标记
        # 先画线
        line = ax7b.plot(merged_data['bin_center'], merged_data['lost_packets'], 'r-', 
                       linewidth=1.5, label='Total Packets Lost', alpha=0.8)
        
        # 只在有丢包的点上添加标记
        nonzero_loss = merged_data[merged_data['lost_packets'] > 0]
        if not nonzero_loss.empty:
            ax7b.scatter(nonzero_loss['bin_center'], nonzero_loss['lost_packets'],
                      color='r', s=25, zorder=5, label='_nolegend_')
        
        # 添加单个事件的丢包情况（使用茎状图）
        if len(retransmission_df) < 100:  # 仅在事件较少时显示单个事件详情
            markerline, stemlines, baseline = ax7b.stem(retransmission_df['time_sec'], 
                                                      retransmission_df['lost_packets'],
                                                      linefmt='r--', markerfmt='.', basefmt=' ',
                                                      label='Individual Loss Events')
            plt.setp(markerline, markersize=3, alpha=0.6)
            plt.setp(stemlines, linewidth=0.8, alpha=0.4)
        
        # 添加统计信息
        total_loss_events = len(retransmission_df)
        total_lost_packets = retransmission_df['lost_packets'].sum()
        total_duration = max_time - min_time if max_time > min_time else bin_size
        avg_loss_events_per_sec = total_loss_events / total_duration if total_duration > 0 else 0
        avg_packets_lost_per_sec = total_lost_packets / total_duration if total_duration > 0 else 0
        
        stats_text = f"Total Loss Events: {total_loss_events}\n"
        stats_text += f"Total Packets Lost: {int(total_lost_packets)}\n"
        stats_text += f"Avg Events Rate: {avg_loss_events_per_sec:.2f} events/sec\n"
        stats_text += f"Avg Loss Rate: {avg_packets_lost_per_sec:.2f} pkts/sec"
        
        if 'persistent_congestion' in retransmission_df.columns:
            persistent_count = retransmission_df['persistent_congestion'].sum()
            if persistent_count > 0:
                stats_text += f"\nPersistent Congestion Events: {persistent_count}"
        
        # 计算丢包率（基于事件）
        if 'total_sent' in retransmission_df.columns and 'total_lost' in retransmission_df.columns:
            if len(retransmission_df) > 0:
                last_record = retransmission_df.iloc[-1]
                if last_record['total_sent'] > 0:
                    total_loss_rate = (last_record['total_lost'] / last_record['total_sent']) * 100
                    stats_text += f"\nOverall Loss Rate: {total_loss_rate:.3f}%"
        
        ax7.text(0.02, 0.98, stats_text, transform=ax7.transAxes, 
                verticalalignment='top', bbox=dict(facecolor='white', alpha=0.8))
        
        # 设置Y轴标签，使用与其他图表一致的颜色
        ax7.set_ylabel('Loss Events Count')
        
        ax7b.set_ylabel('Packets Lost')
        
        # 合并两个图例
        lines1, labels1 = ax7.get_legend_handles_labels()
        lines2, labels2 = ax7b.get_legend_handles_labels()
        ax7.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
        # 明确设置X轴时间刻度
        # 根据总时长动态设置主刻度和次刻度
        if total_duration <= 1.0:
            ax7.xaxis.set_major_locator(MultipleLocator(0.2))
            ax7.xaxis.set_minor_locator(MultipleLocator(0.05))
        elif total_duration <= 5.0:
            ax7.xaxis.set_major_locator(MultipleLocator(1.0))
            ax7.xaxis.set_minor_locator(MultipleLocator(0.2))
        elif total_duration <= 10.0:
            ax7.xaxis.set_major_locator(MultipleLocator(5.0))
            ax7.xaxis.set_minor_locator(MultipleLocator(1.0))
        elif total_duration <= 60.0:
            ax7.xaxis.set_major_locator(MultipleLocator(10.0))
            ax7.xaxis.set_minor_locator(MultipleLocator(2.0))
        else:
            ax7.xaxis.set_major_locator(MultipleLocator(30.0))
            ax7.xaxis.set_minor_locator(MultipleLocator(10.0))
        
        # 设置网格线
        ax7.grid(True, which='major', axis='both', linestyle='-', alpha=0.5)
        ax7.grid(True, which='minor', axis='x', linestyle=':', alpha=0.2)
        
        # 找出持续拥塞事件并在图上标记
        if 'persistent_congestion' in retransmission_df.columns:
            persistent_events = retransmission_df[retransmission_df['persistent_congestion'] == True]
            if len(persistent_events) > 0:
                for _, row in persistent_events.iterrows():
                    ax7.axvline(x=row['time_sec'], color='darkred', linestyle='-', alpha=0.6, linewidth=1.5)
                    ax7.text(row['time_sec'], ax7.get_ylim()[1]*0.95, "PersistentCongestion", 
                            rotation=90, ha='right', va='top', fontsize=8, color='darkred',
                            bbox=dict(facecolor='white', alpha=0.8))
        
    else:
        ax7.text(0.5, 0.5, 'No packet loss events data available', 
                transform=ax7.transAxes, ha='center', va='center', fontsize=12,
                bbox=dict(facecolor='white', alpha=0.8))
    
    ax7.set_title('Packet Loss Analysis: Events Count and Total Lost Packets', **title_style)
    
    # 确保最后一个图的X轴标签显示
    ax7.set_xlabel('Time (seconds)')
    
    # 为所有子图设置统一的X轴格式
    for ax_idx in range(current_ax_idx):
        ax = axes[ax_idx]
        if bbr_df_plot is not None and not bbr_df_plot.empty:
            total_duration = bbr_df_plot['time_sec'].max() - bbr_df_plot['time_sec'].min()
            
            # 根据总时长动态设置主刻度和次刻度
            if total_duration <= 1.0:
                ax.xaxis.set_major_locator(MultipleLocator(0.2))
                ax.xaxis.set_minor_locator(MultipleLocator(0.05))
            elif total_duration <= 5.0:
                ax.xaxis.set_major_locator(MultipleLocator(1.0))
                ax.xaxis.set_minor_locator(MultipleLocator(0.2))
            elif total_duration <= 30.0:
                ax.xaxis.set_major_locator(MultipleLocator(5.0))
                ax.xaxis.set_minor_locator(MultipleLocator(1.0))
            elif total_duration <= 60.0:
                ax.xaxis.set_major_locator(MultipleLocator(10.0))
                ax.xaxis.set_minor_locator(MultipleLocator(2.0))
            elif total_duration <= 600.0:
                ax.xaxis.set_major_locator(MultipleLocator(60.0))
                ax.xaxis.set_minor_locator(MultipleLocator(15.0))
            else:
                ax.xaxis.set_major_locator(MultipleLocator(120.0))
                ax.xaxis.set_minor_locator(MultipleLocator(30.0))
            
            # 设置网格线
            ax.grid(True, which='major', axis='x', linestyle='-', alpha=0.5)
            ax.grid(True, which='minor', axis='x', linestyle=':', alpha=0.2)
            ax.grid(True, which='major', axis='y', alpha=0.3)
    
    # 只在最底部的子图显示x轴标签
    for ax_idx in range(current_ax_idx - 1):
        axes[ax_idx].set_xlabel('')
        # 保留刻度但隐藏刻度标签（可选）
        # axes[ax_idx].tick_params(axis='x', which='both', labelbottom=False)
    
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