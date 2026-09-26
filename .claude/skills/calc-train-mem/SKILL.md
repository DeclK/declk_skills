---
name: calc-train-mem
description: 快速估算训练模型所需显存 —— 公式计算 max_allocated（理论峰值）。支持 NPU/CUDA 双平台、FSDP2 + SP。用户可调用 /calc-train-mem 来激活。
user-invocable: true
argument-hint: "[model_description | params]"
allowed-tools: "Bash, Read"
---

# Calc Train Mem — 训练显存估算 + 实测验证

基于已验证的精确公式，估算 FSDP2 + SP 训练的理论峰值显存 (`max_allocated`)，并提供 profiler 进行实测验证。

## 核心理念

```
公式计算 → max_allocated（理论精确值）
Profiler  → max_allocated / max_reserved / npu-smi gap
```

- **公式输出 = `max_allocated`**，是与 profiler 直接对比的目标。
- **公式不计算**: SP all-to-all、HCCL/NCCL persistent、allocator overhead、driver overhead —— 这些只能实测。
- 平台无关（NPU / CUDA），calculator 是纯数学。

## 工作流

### Step 1: 收集参数（交互式询问）

从用户输入中提取已知参数，**缺失的关键参数必须询问用户**。不要猜测。

**必须收集的参数:**

| 参数 | 说明 | 示例 |
|------|------|------|
| `total_params` | 模型总参数量 | 2.04B (或 2040000000) |
| `hidden_size` (D) | 隐藏层维度 | 2048 |
| `intermediate_size` (I) | FFN 中间层维度 | 6144 |
| `num_layers` (L) | decoder layer 数量 | 24 |
| `vocab_size` (V) | 词表大小 | 248320 |
| `seq_len` (S) | 训练序列长度 | 32768 |
| `dtype` | 训练精度 | bf16 / fp16 / fp32 |
| `dp_size` | FSDP2 data-parallel size | 4 |
| `sp_size` | Sequence Parallel size (ulysses) | 1 或 2 |
| `mlp_type` | MLP 结构 | swiglu (gate+up+down) / standard (fc1+fc2) |
| `logits_fused` | logits 是否用 fused kernel | true (Mojo/fused CE) / false (eager fp32) |
| `max_unit_params` | FSDP root unit 参数数（embed+lm_head 等非 layer 参数） | 548M |
| `tie_word_embeddings` | embed 和 lm_head 是否共享 | true / false |
| `activation_checkpointing` | 是否开启 activation checkpointing | true / false |

**ViT 参数（仅 VL 模型需要）:**

| 参数 | 说明 | 示例 |
|------|------|------|
| `vit_params` | ViT 总参数量 | 331M |
| `vit_hidden` (D_v) | ViT 隐藏层维度 | 1024 |
| `vit_intermediate` (I_v) | ViT FFN 中间层维度 | 4096 |
| `vit_layers` (L_v) | ViT block 数量 | 24 |
| `vit_seq_len` (S_v) | 平均 vision token 数量 | 60000 |
| `vit_mlp_type` | ViT MLP 结构 | standard (通常) |

**参数收集原则:**
- 如果用户提供了 `total_params` 和 `max_unit_params`，优先使用。
- 如果用户只知道架构参数（D/I/L/V），据此计算 `total_params` 和 `max_unit_params`。
- `max_unit_params` 估算: `vocab_size × hidden_size`（tied embeddings）+ ViT non-block 参数（如有 ViT）。
- 如果用户不能提供某个参数，用典型默认值并标注「估算」。

**⚠️ `total_params` 的准确获取：**

不要相信模型名或 config.json 手工推导。模型名里的数字可能严重偏离实际（如 Qwen3.5-"2B" 实际 2.27B）。GatedDeltaNet、Mamba、MTP 等非标准层会让手工估算差出几亿参数。

推荐方式（按优先级）：
1. **Safetensors checkpoint**：读取 header 中的 shape 求和（`total_size / 2` for bf16）
2. **模型 loaded**：`sum(p.numel() for p in model.parameters())`
3. **HuggingFace model card**：`num_params` 字段
4. **别无选择时**：让用户自行提供，并明确标注来源和可信度

### Step 2: 运行 Calculator

```bash
python "$SKILL_DIR/scripts/mem_calculator.py" \
  --total-params 2040000000 \
  --hidden 2048 --intermediate 6144 --layers 24 \
  --vocab 248320 --seq-len 32768 --dtype bf16 \
  --dp 4 --sp 1 \
  --mlp-type swiglu --logits-fused \
  --max-unit-params 548000000 \
  --tie-embeddings \
  --activation-checkpointing \
  --vit-params 331000000 --vit-hidden 1024 --vit-intermediate 4096 \
  --vit-layers 24 --vit-seq-len 60000 --vit-mlp-type standard
```

### Step 3: 解读输出

Calculator 输出分两段：

**上半段（精确公式）:**
```
1. Model States      →  params × 16 bytes / DP
2. FSDP2 Comm Buffers →  max_unit × (2×2 bf16 + 4 fp32) bytes  
3. Activations       →  checkpoints + recompute peak
─────────────────────────────────
THEORY PEAK          →  max_allocated (exact)
```

**下半段（提示实测）:**
```
这些量不由公式计算，需 profiler 实测:
  + Allocator overhead  (reserved − allocated)
  + Driver overhead     (npu-smi − max_reserved)
```

### Step 4: 可选 — 提供 Profiler 指导

如果用户需要实测验证，**不要自动修改训练脚本**。提供以下指导：

```bash
# 1. 确保 mem_profiler.py 可导入
cp "$SKILL_DIR/scripts/mem_profiler.py" /path/to/project/

# 2. 在训练脚本中注入探针（用户自行操作）：
```

给用户展示如何在训练脚本中添加：

```python
# === 在训练脚本中注入 ===
import os
if os.environ.get("MEM_PROFILE", ""):
    from mem_profiler import print_memory_breakdown, reset_peak_stats, MemorySnapshot

# After optimizer init:
print_memory_breakdown("after-optimizer-init")
reset_peak_stats()

# After each training step (fwd+bwd+optimizer):
print_memory_breakdown("after-fwd-bwd-step1")

# Optional snapshot:
if os.environ.get("MEM_SNAPSHOT", ""):
    with MemorySnapshot(output_dir="./mem_snapshots", tag="step2"):
        loss = model(**batch).loss
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
```

然后运行：
```bash
MEM_PROFILE=1 torchrun ... train.py
# 或
MEM_PROFILE=1 MEM_SNAPSHOT=1 torchrun ... train.py
```

**Compare 理论 vs 实测：**
```
理论 max_allocated → 计算器输出的 THEORY PEAK
实测 max_allocated → profiler 打印的 "max_allocated (peak)"
→ 两者应精确匹配

实测 max_reserved → profiler 打印的 "max_reserved (peak)"
实测 npu-smi     → 外部监控（npu-smi info / nvidia-smi）
→ max_reserved + driver overhead ≈ npu-smi
```

## 参考

- 公式推导: `reference/formulas.md`
- Calculator 源码: `scripts/mem_calculator.py`
- Profiler 源码: `scripts/mem_profiler.py`

## 限制（v1）

- **仅 FSDP2** — 不支持 FSDP1 / TP / PP
- **仅 SP (ulysses)** — SP size 通过 `S_local = S / sp_size` 影响 activation
- **仅 AdamW** — 优化器状态 = 8 bytes/param (m+v fp32)
- **仅 bf16/fp16 mixed precision** — 含 fp32 master weights
- **假设 activation checkpointing 开启** — 每层仅存 1 个 checkpoint tensor
- **不计算**: all-to-all、HCCL/NCCL persistent、allocator overhead、driver overhead
- **公式针对 full attention decoder layer** — GatedDeltaNet/Mamba 等变体未建模
