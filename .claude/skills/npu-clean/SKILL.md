---
name: npu-clean
description: 训练前清理 NPU/HCCL 环境。杀残留训练进程、清理 IPC 共享内存/信号量、释放 HCCL socket 端口、清 NPU 设备缓存。用户可调用 /npu-clean 来激活。
user-invocable: true
allowed-tools: "Bash"
---

# NPU Clean — 训练前清理 NPU/HCCL 环境

NPU 多卡训练（torchrun / deepspeed）启动前，清理上次训练残留的资源，避免卡死或端口冲突。

## 执行流程

### Step 1: 运行清理脚本

```bash
bash "$SKILL_DIR/npu_clean.sh"
```

### Step 2: 检查结果

脚本执行完毕后，确认：
- 残留训练进程已被 kill
- IPC 资源已释放
- HCCL socket 端口已清理
- NPU 设备缓存已清空

## 清理内容

1. **残留进程** — `pkill -9` 匹配 `train_qwen`、`torchrun`、`python.*train`
2. **IPC 资源** — `ipcrm -a` 清理共享内存和信号量
3. **Socket 连接** — `fuser -k` 释放 HCCL 端口范围 (60000-60050, 61000-61050)
4. **NPU 缓存** — `torch.npu.empty_cache()` 清空所有 NPU 设备缓存
5. **等待释放** — sleep 3s 确保资源完全回收

## 与 npu-zombie-clean 的区别

| 维度 | `/npu-clean` (本 skill) | `/npu-zombie-clean` |
|------|------------------------|---------------------|
| 时机 | 训练**前**预防性清理 | 训练**异常退出后**清理僵尸 |
| 对象 | 残留活进程 + IPC + Socket + NPU 缓存 | 仅 `<defunct>` 僵尸进程 |
| 手段 | `pkill -9` 直接杀 | 先 SIGCHLD 回收，再 kill 父进程 |
| 安全机制 | 无（训练前放心清） | 默认 dry-run，排除平台服务 |

两者互补，建议训练前跑 `/npu-clean`，异常退出后有僵尸时跑 `/npu-zombie-clean --kill`。
