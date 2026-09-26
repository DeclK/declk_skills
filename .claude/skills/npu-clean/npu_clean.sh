#!/bin/bash
# NPU/HCCL 清理脚本 - 在训练前运行，避免卡死
#
# Usage:
#   /npu-clean          # 直接执行清理
#
# Cleans: residual training processes, IPC resources, socket connections, NPU device cache

set -e

echo "=== NPU/HCCL 清理脚本 ==="

# 1. 清理残留的 Python 进程
echo "清理残留的 Python 训练进程..."
pkill -9 -f "train_qwen" || true
pkill -9 -f "torchrun" || true
pkill -9 -f "python.*train" || true
sleep 1

# 2. 清理共享内存和信号量
echo "清理 IPC 资源..."
ipcrm -a 2>/dev/null || true
sleep 1

# 3. 清理 socket 残留
echo "清理 socket 连接..."
# 清理 HCCL 端口范围内的残留连接
for port in {60000..60050} {61000..61050}; do
    fuser -k ${port}/tcp 2>/dev/null || true
done
sleep 1

# 4. 清理 NPU 设备
echo "清理 NPU 设备..."
python3 -c "
import torch
import torch_npu

try:
    for i in range(torch.npu.device_count()):
        torch.npu.set_device(i)
        torch.npu.empty_cache()
    print(f'已清理 {torch.npu.device_count()} 个 NPU 设备的缓存')
except Exception as e:
    print(f'NPU 清理警告: {e}')
" 2>/dev/null || true

# 5. 等待资源完全释放
echo "等待资源完全释放..."
sleep 1

echo "=== 清理完成 ==="
