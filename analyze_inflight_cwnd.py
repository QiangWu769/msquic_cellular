#!/usr/bin/env python3
import re
import os

def analyze_inflight_cwnd(log_file_path):
    """
    分析BBR日志文件，统计InFlight > CWND的情况
    """
    if not os.path.exists(log_file_path):
        print(f"错误：找不到日志文件 {log_file_path}")
        return
    
    total_samples = 0
    over_cwnd_samples = 0
    cwnd_inflight_pairs = []
    
    # 正则表达式匹配CWND和InFlight值
    pattern = r'CWND=([0-9]+) B, InFlight=([0-9]+) B'
    
    print(f"正在分析日志文件: {log_file_path}")
    print("-" * 60)
    
    with open(log_file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            match = re.search(pattern, line)
            if match:
                cwnd = int(match.group(1))
                inflight = int(match.group(2))
                
                total_samples += 1
                cwnd_inflight_pairs.append((cwnd, inflight))
                
                if inflight > cwnd:
                    over_cwnd_samples += 1
                    # 显示前几个超过CWND的样本
                    if over_cwnd_samples <= 10:
                        percentage = (inflight / cwnd - 1) * 100
                        print(f"样本 {total_samples}: CWND={cwnd:,} B, InFlight={inflight:,} B "
                              f"(超过 {percentage:.1f}%)")
    
    print("-" * 60)
    print(f"总样本数: {total_samples:,}")
    print(f"InFlight > CWND 的样本数: {over_cwnd_samples:,}")
    
    if total_samples > 0:
        percentage = (over_cwnd_samples / total_samples) * 100
        print(f"超过CWND的样本比例: {percentage:.2f}%")
        
        # 计算统计信息
        if cwnd_inflight_pairs:
            utilizations = [inflight / cwnd for cwnd, inflight in cwnd_inflight_pairs]
            avg_utilization = sum(utilizations) / len(utilizations) * 100
            max_utilization = max(utilizations) * 100
            
            print(f"平均CWND利用率: {avg_utilization:.2f}%")
            print(f"最大CWND利用率: {max_utilization:.2f}%")
            
            # 找到最大利用率的样本
            max_idx = utilizations.index(max(utilizations))
            max_cwnd, max_inflight = cwnd_inflight_pairs[max_idx]
            print(f"最大利用率样本: CWND={max_cwnd:,} B, InFlight={max_inflight:,} B")
    else:
        print("未找到有效的CWND/InFlight数据")

if __name__ == "__main__":
    # 查找BBR日志文件
    log_paths = [
        "bbr_logs/bbr_log.txt",
        "bbr_log.txt",
        "logs/bbr_log.txt"
    ]
    
    log_file = None
    for path in log_paths:
        if os.path.exists(path):
            log_file = path
            break
    
    if log_file:
        analyze_inflight_cwnd(log_file)
    else:
        print("未找到BBR日志文件，尝试的路径:")
        for path in log_paths:
            print(f"  - {path}")
        print("\n请确保日志文件存在于以上路径之一") 