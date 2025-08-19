#!/bin/bash
# 简单构建脚本 - 跳过TCP eBPF日志功能

set -e

echo "构建支持QUIC BBR包级别日志的secnetperf工具"
echo "================================================="

# 设置编译目录
echo "准备构建目录..."
rm -rf build
mkdir -p build && cd build

# 配置构建，仅启用QUIC BBR
echo "配置构建..."

# 添加定义以禁用TCP eBPF日志
cat > src/perf/lib/disable_tcp_ebpf.h << EOF
// 禁用TCP eBPF日志的头文件
#define DISABLE_TCP_EBPF_LOGGING 1
EOF

cmake -DCMAKE_BUILD_TYPE=Release \
      -DQUIC_BUILD_PERF=ON \
      -DQUIC_ENHANCED_PACKET_LOGGING=ON \
      ..

# 构建secnetperf
echo "开始构建..."
cmake --build . --target secnetperf -j$(nproc)

# 检查构建结果
if [ -f bin/Release/secnetperf ]; then
  echo "编译成功！secnetperf 位于 $(pwd)/bin/Release/secnetperf"
  
  echo "================ 使用指南 ================"
  echo "1. QUIC BBR日志使用方式："
  echo "   ./bin/Release/secnetperf -cc:bbr [其他参数]"
  echo ""
  echo "2. TCP 模式使用方式 (无日志)："
  echo "   ./bin/Release/secnetperf -tcp:1 [其他参数]"
  echo "==========================================="
else
  echo "构建失败，请检查错误信息"
  exit 1
fi 