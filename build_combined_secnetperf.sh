#!/bin/bash
# 构建同时支持QUIC BBR和TCP eBPF日志的secnetperf工具

set -e

echo "构建支持QUIC BBR和TCP eBPF日志的secnetperf工具"
echo "================================================="

# 安装必要的依赖
echo "检查依赖项..."
if ! dpkg -l | grep -q libbpf-dev; then
  echo "安装libbpf-dev..."
  apt-get update
  apt-get install -y libbpf-dev libelf-dev
fi

# 设置编译目录
echo "准备构建目录..."
cd ~/msquic
rm -rf build
mkdir -p build && cd build

# 配置构建，启用QUIC BBR和TCP eBPF日志
echo "配置构建..."
cmake -DCMAKE_BUILD_TYPE=Release \
      -DQUIC_ENABLE_LOGGING=0 \
      -DQUIC_BUILD_PERF=ON \
      -DQUIC_ENHANCED_PACKET_LOGGING=ON \
      -DQUIC_TLS=openssl \
      -DCMAKE_C_FLAGS="-DDISABLE_TCP_EBPF_LOGGING" \
      -DCMAKE_CXX_FLAGS="-DDISABLE_TCP_EBPF_LOGGING" \
      ..

# 构建secnetperf
echo "开始构建..."
cmake --build . --target secnetperf -j$(nproc)

# 检查构建结果
if [ -f bin/Release/secnetperf ]; then
  echo "编译成功！secnetperf 位于 $(pwd)/bin/Release/secnetperf"
  
  # 返回到项目根目录
  cd ..
  
  # 运行安装脚本来编译eBPF程序
  echo "正在编译eBPF程序..."
  ./install_tcp_ebpf_logging.sh
  
  echo "================ 使用指南 ================"
  echo "1. QUIC BBR日志使用方式："
  echo "   ./build/bin/Release/secnetperf -cc:bbr [其他参数]"
  echo ""
  echo "2. TCP eBPF日志使用方式："
  echo "   sudo ./build/bin/Release/secnetperf -tcp:1 -tcplog:1 [其他参数]"
  echo ""
  echo "注意：TCP eBPF日志需要root权限"
  echo "==========================================="
else
  echo "构建失败，请检查错误信息"
  exit 1
fi 