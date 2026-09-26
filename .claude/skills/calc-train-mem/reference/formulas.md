# Memory Formulas Reference

> 已验证于: Qwen3.5-2B SFT (FSDP2, SP, NPU Ascend 910B2C)
> 理论 `max_allocated` = 20.71 GiB 与 torcn.npu.max_memory_allocated() **精确匹配**

## 符号

| Symbol | Meaning | Qwen3.5-2B Example |
|--------|---------|---------------------|
| P | total params | 2.04B |
| D | hidden_size | 2048 |
| I | intermediate_size | 6144 |
| L | num_layers | 24 |
| V | vocab_size | 248320 |
| S | seq_len (packed) | 32768 |
| S_local | S / sp_size (per-SP-rank tokens) | 32768 (SP=1), 16384 (SP=2) |
| DP | FSDP2 data-parallel size | 4 (SP=1), 2 (SP=2) |
| SP | ulysses sequence parallel size | 1 or 2 |
| D_v | ViT hidden_size | 1024 |
| I_v | ViT intermediate_size | 4096 |
| L_v | ViT num_blocks | 24 |
| S_v | ViT vision tokens (~pixel_values) | ~60000 |
| P_max | max_unit_params (root FSDP unit) | ~548M |
| | **MoE (optional)** | |
| E | num_experts (total) | 256 |
| K | num_experts_per_tok (activated) | 8 |
| I_e | per-expert FFN intermediate_size | 512 |
| I_s | shared expert intermediate_size | 512 |
| f | linear_attention_fraction | 0.75 (30/40 LA) |
| L_mtp | MTP decoder layers | 1 |

## 1. Model States (per GPU)

**AdamW, bf16 mixed precision with fp32 master:**

```
per_param_bytes = 2 (bf16 param) + 4 (fp32 master) + 2 (bf16 grad) + 4 (fp32 m) + 4 (fp32 v)
                = 16 bytes

per_gpu = P × 16 / DP
```

| Dtype | per_param_bytes |
|-------|----------------|
| bf16 mixed + AdamW | 16 |
| fp16 mixed + AdamW | 16 |
| fp32 full + AdamW | 4+4+4+4 = 16* |

> *fp32: 4 (param) + 4 (grad, no separate master) + 4 (m) + 4 (v) = 16. Same total, different split.

**Qwen3.5-2B (SP=1, DP=4):** 2.04B × 16 / 4 = **8.16 GiB** (实测 ≈ 8.00 GiB，headroom 来自 tied weights 共享存储)

## 2. FSDP2 Communication Buffers

### 2.1 All-Gather (Double Buffering)

**Root cause (code-verified, `torch/distributed/fsdp/_fully_shard/`):**

FSDP2 stores params as independent `DTensor` objects (unlike FSDP1's permanent `FlatParameter`). During all-gather, params are **temporarily flattened** into one buffer for a single efficient `all_gather_into_tensor`, then `split_with_sizes_copy` copies back to individual `nn.Parameter` outputs. **Both buffers coexist during the copy.**

```
Buffer 1: Flat AG communication buffer
  → torch.empty((numel × world_size,), dtype=bf16)  [fsdp_collectives.py:153]

Buffer 2: Per-param outputs
  → [torch.empty([numel × world_size], ...) for each param]  [fsdp_param.py:448-450]

Both alive during split_with_sizes_copy [fsdp_collectives.py:288-289]
```

```
AG_per_gpu = P_max × 2 bytes (bf16) × 2 (double buffering)
           = P_max × 4 bytes
```

**Qwen3.5-2B:** 548M × 4 bytes = **2.04 GiB**

### 2.2 Reduce-Scatter

Gradient reduction happens in **fp32** (`MixedPrecisionPolicy(reduce_dtype=torch.float32)`). The `reduce_scatter_input` buffer holds the full unsharded gradient in fp32 before reduction.

```
RS_per_gpu = P_max × 4 bytes (fp32)
```

**Qwen3.5-2B:** 548M × 4 bytes = **2.04 GiB**

### 2.3 AG + RS 共存

Backward 时序 (`_fsdp_param_group.py`):
```
pre_backward:  all_gather → bf16 AG buf
backward:      compute grads → bf16 grads  
reshard:       free AG buf
post_backward: alloc reduce_scatter_input fp32 → reduce_scatter → free
```

AG 和 RS **对同一 unit 不共存**。但 `reduce_scatter_state` 跨 step 持久化（前一个 step 的 RS buffer 在当前 step backward 期间仍持有引用）。

**保守估计** (additive): AG(2.04) + RS(2.04) = **4.08 GiB** — 与实测 `max_allocated` 精确匹配（参见 Qwen3.5-2B 验证）。

## 3. Activations

### 3.1 Checkpointed Inputs (Activation Checkpointing)

每层存 1 个 input tensor (bf16) 作为 backward recompute 的起点:

```
text_ckpt  = L × S_local × D × 2 bytes
ViT_ckpt   = L_v × S_v × D_v × 2 bytes (不受 SP 影响)
```

**Qwen3.5-2B (SP=1):** 24 × 32768 × 2048 × 2 = **3.00 GiB**
**Qwen3.5-2B (SP=2):** 24 × 16384 × 2048 × 2 = **1.50 GiB**

### 3.2 Recompute Peak (1 Decoder Layer)

Backward 时从 checkpoint 重算 1 个 layer 的 forward，autograd 保存所有中间量。按 forward 路径逐算子推导：

#### Full Attention 部分: 7 × [S_local, D]

| # | Tensor | Shape | 来源 |
|---|--------|-------|------|
| 1 | ln_output | [S, D] | q/k/v_proj 共享输入 |
| 2 | Q | [S, D] | Flash Attn backward |
| 3 | K | [S, D] | Flash Attn backward |
| 4 | V | [S, D] | Flash Attn backward |
| 5 | flash_output | [S, D] | o_proj 输入 + FA backward |
| 6 | post_ln_input | [S, D] | post_attn_layernorm backward |
| 7 | post_ln_output | [S, D] | gate/up_proj 共享输入 |

**= 14 × S_local × D bytes (bf16)**

Flash Attention **不物化** attention score matrix `[S, S]`。

#### MLP 部分 (SwiGLU: gate+up+SiLU+down): 4 × [S_local, I]

| # | Tensor | Shape | 来源 |
|---|--------|-------|------|
| 8 | gate | [S, I] | SiLU backward |
| 9 | up | [S, I] | mul backward |
| 10 | SiLU(gate) | [S, I] | mul backward |
| 11 | act (SiLU×up) | [S, I] | down_proj backward |

**= 8 × S_local × I bytes (bf16)** for SwiGLU

#### MLP 部分 (Standard: fc1+gelu+fc2): 2 × [S_local, I]

| # | Tensor | Shape | 来源 |
|---|--------|-------|------|
| 8 | fc1_out | [S, I] | gelu backward |
| 9 | gelu_out | [S, I] | fc2 backward |

**= 4 × S_local × I bytes (bf16)** for Standard MLP

#### 汇总

| MLP Type | Formula |
|----------|---------|
| SwiGLU (gate+up+down) | `14 × S_local × D + 8 × S_local × I` |
| Standard (fc1+fc2) | `14 × S_local × D + 4 × S_local × I` |

**Qwen3.5-2B text (SP=1, SwiGLU):** 14×32768×2048 + 8×32768×6144 = 0.875 + 1.500 = **2.375 GiB**
**Qwen3.5-2B ViT (Standard):** 14×60000×1024 + 4×60000×4096 = 0.805 + 0.918 = **1.72 GiB**

> **Activation Gradients 不计入峰值:** Backward 释放 fwd activations 的同时创建等大的 grad tensors，直接复用刚释放的内存 → net 0。

### 3.3 Peak 时序

```
LLM Backward Peak:  text_ckpt + ViT_ckpt + text_recompute
                    (ViT recompute 不重叠：在 LLM backward 之后)
                    SP=1: 3.00 + 2.75 + 2.38 = 8.13 GiB
                    SP=2: 1.50 + 2.75 + 1.19 = 5.44 GiB

ViT Backward Peak:   ViT_ckpt + ViT_recompute = 2.75 + 1.72 = 4.47 GiB
                     (< LLM peak, 不计入总体峰值)
```

## 4. Logits

| 路径 | 显存 | 说明 |
|------|------|------|
| Fused kernel (Mojo/Flash CE) | **0** | tile-by-tile F.linear+softmax+CE, 不物化 fp32 logits |
| Chunked CE | ~S_local × V × 4 / chunk_count | 沿 seq 分 chunk, 每 chunk 独立计算 |
| Eager CE | S_local × V × 4 bytes | 完整 fp32 logits [S_local, V] |

**Qwen3.5-2B eager (SP=1):** 32768 × 248320 × 4 = **30.3 GiB** — 无法训练！
**Qwen3.5-2B fused:** 0 GiB — veomni Mojo kernel

## 7. Global Formula

### Dense Model

```
THEORY PEAK =
    P × 16 / DP                              ← Model States
  + P_max × 8                                ← FSDP2 Comm (AG×2 bf16 + RS fp32)
  + L × S_local × D × 2                      ← Text Checkpoints
  + (L_v × S_v × D_v × 2)                    ← ViT Checkpoints (if any)
  + (14 × S_local × D + K × S_local × I)     ← Recompute Peak (1 layer, bf16)
  + logits_bytes                              ← Logits (0 if fused)
```
where `K = 8` for SwiGLU, `K = 4` for Standard MLP.

### MoE Model

```
THEORY PEAK =
    P × 16 / DP
  + P_max × 8
  + (L + L_mtp) × S_local × D × 2            ← Text + MTP Checkpoints
  + (L_v × S_v × D_v × 2)                    ← ViT Checkpoints
  + attn_avg + mlp_moe                        ← Recompute Peak (1 layer)
  + logits_bytes

  attn_avg = [(1-f)×14 + f×10] × S_local × D   (f = linear_attn fraction)

  mlp_moe =
    K × S_local × (2D + 4×I_e) × 2             ← routed experts
  + S_local × (D + 4×I_s) × 2                  ← shared expert
  + E × K × S_local × 8                        ← expert mask (int64)
  + S_local × (E + K) × 2                      ← router + routing weights
```

## 4. MoE Recompute Peak

MoE (Mixture of Experts) 的 recompute peak 与 dense MLP 有本质区别。核心差异在于 **`num_experts_per_tok` (K) 直接倍增 MLP activations**。

### 4.1 代码路径 (`Qwen2MoeSparseMoeBlock.forward`)

```
① Router:     gate(S,D) → router_logits(S,E) → softmax → topk(K) → routing_weights(S,K)
② Mask:       expert_mask = one_hot(selected_experts).permute → (E, K, S) int64
③ Shared:     shared_expert(S,D) → gate_out(S,I_s), up_out(S,I_s), act_gate(S,I_s), gated(S,I_s)
              → shared_mlp_output(S,D) × sigmoid(gate_logit) → (S,D)
④ Routed:     for each expert ∈ [0, E):
                current_state = hidden_states[top_x]           → (S_e, D)
                expert_layer: gate_out(S_e,I_e), up_out(S_e,I_e), act_gate(S_e,I_e), gated(S_e,I_e)
                expert_output = down_proj(gated)               → (S_e, D)
                current_hidden = expert_output × routing_weight  → accumulated
⑤ Output:     final = final_hidden + shared_out
```

### 4.2 Autograd-Saved Tensors (per layer recompute)

所有 256 个 expert 的 forward 依次执行后，autograd graph 中**所有 expert 的中间量同时存活**（在 backward 逐一释放前达到峰值）。

| # | Tensor | Shape | Count | Source |
|---|--------|-------|-------|--------|
| | **Attention (同 §3.2)** | | | |
| 1-7 | ... | [S_local, D] × 7 | bf16 | §3.2 已验证 |
| | **Shared Expert (SwiGLU)** | | | |
| 8 | gate_out | [S, I_s] | bf16 | SiLU backward |
| 9 | up_out | [S, I_s] | bf16 | mul backward |
| 10 | SiLU(gate_out) | [S, I_s] | bf16 | mul backward |
| 11 | gated | [S, I_s] | bf16 | down_proj backward |
| 12 | shared_mlp_output | [S, D] | bf16 | sigmoid-mul backward |
| | **Router** | | | |
| 13 | router_logits | [S, E] | bf16 | softmax backward |
| 14 | routing_weights | [S, K] | bf16 | expert-mul backward |
| | **Expert Mask** | | | |
| 15 | expert_mask | [E, K, S] | int64 | one_hot → permute |
| | **Routed Experts (Σ over all E experts)** | | | |
| 16 | current_state | [S_e, D] × Σ | bf16 | gate/up_proj backward |
| 17 | gate_out | [S_e, I_e] × Σ | bf16 | SiLU backward |
| 18 | up_out | [S_e, I_e] × Σ | bf16 | mul backward |
| 19 | act_gate | [S_e, I_e] × Σ | bf16 | mul backward |
| 20 | gated | [S_e, I_e] × Σ | bf16 | down_proj backward |
| 21 | expert_output | [S_e, D] × Σ | bf16 | routing-weight mul backward |

> Σ over all experts: Σ S_e = K × S (每个 token 去 K 个 experts)

### 4.3 MoE MLP Recompute Formula

```
routed  = K × S_local × (2D + 4×I_e) × 2   bytes
shared  = S_local × (D + 4×I_s) × 2         bytes
mask    = E × K × S_local × 8               bytes  (int64)
router  = S_local × (E + K) × 2             bytes  (bf16)
────────────────────────────────────────────
mlp_moe = routed + shared + mask + router
```

加上 attention（含 hybrid attention）:

```
attn_avg = [(1-f)×14 + f×10] × S_local × D    (f = linear_attention_fraction)
recompute = attn_avg + mlp_moe
```

### 4.4 K 的倍增效应

Dense swiglu MLP (I=相同):
```
mlp_dense = 8 × S_local × I  = 8 × 32768 × 512 = 0.125 GiB
```

MoE MLP (K=8):
```
mlp_moe   ≈ 8 × 32768 × (2×2048 + 4×512) × 2  + ...  ≈ 3.77 GiB
```

**MoE MLP ≈ 30× 同尺寸 dense MLP**。K 是关键乘数。

## 5. ViT Recompute Peak

ViT backward 在 text backward **之后**发生，**不计入总峰值**。

### 5.1 ViT Attention (fused QKV + Flash Attn)

| # | Tensor | Shape | Source |
|---|--------|-------|--------|
| 1 | norm1_out | [S_v, D_v] | qkv Linear backward (fused) |
| 2 | Q | [S_v, D_v] | Flash Attn backward |
| 3 | K | [S_v, D_v] | Flash Attn backward |
| 4 | V | [S_v, D_v] | Flash Attn backward |
| 5 | attn_out | [S_v, D_v] | proj Linear backward |

**= 10 × S_v × D_v bytes (bf16)**

### 5.2 ViT MLP (Standard: fc1→GELU→fc2)

| # | Tensor | Shape | Source |
|---|--------|-------|--------|
| 6 | post_norm_input | [S_v, D_v] | norm2 backward |
| 7 | norm2_out | [S_v, D_v] | fc1 Linear backward |
| 8 | fc1_out | [S_v, I_v] | GELU backward |
| 9 | gelu_out | [S_v, I_v] | fc2 Linear backward |

**= 4 × S_v × D_v + 4 × S_v × I_v bytes (bf16)** for standard MLP

若为 SwiGLU: **4 × S_v × D_v + 8 × S_v × I_v**

### 5.3 ViT Formula

```
vit_recompute = 14 × S_v × D_v + K_v × S_v × I_v
```
where `K_v = 4` (standard) or `K_v = 8` (swiglu).

## 6. 不在公式内的量

以下显存占用与具体实现和硬件相关，**没有闭合形式的精确公式**，其大小无法由架构参数直接推导。只能通过 profiler 实测。

| 量 | 说明 | 获取方式 |
|----|------|---------|
| SP All-to-All buffers | Ulysses SP 的 all-to-all 通信临时 buffer | `max_allocated` − theory（需 profiler） |
| HCCL/NCCL persistent buffers | 集合通信库的持久化 ring/pipeline buffer | memory snapshot 分析 |
| Allocator overhead (frag) | Caching allocator 缓存池碎片，受可变 tensor shape 影响 | `max_reserved − max_allocated` |
| CANN/CUDA driver overhead | 设备驱动层不可追踪的隐式分配 | `npu-smi − max_reserved` |
| GatedDeltaNet/SSM intermediates | 线性注意力量纲为 10SD（approximation），实际取决于具体实现 | 逐层 profiling |
| MoE EP All-to-All | Expert Parallelism 的 token dispatch/combine | 逐场景实测 (EP 开启时) |
| MoE Expert Load Imbalance | 非均匀 token 分配导致部分 expert buffer 偏大 | memory snapshot |

> **注意：上表中任何"典型值"都不可靠。** 这些量依赖于硬件代际（如 910B vs 910B2C）、CANN/CUDA 版本、HCCL/NCCL 版本、HCCL 配置（HCCL_GRAPH_OP_RUN_FLUSH_CONFIG 等）、torch 版本等组合。一个模型上的实测值不能线性外推到另一个模型。公式能做到的是给出 `max_allocated` 的精确上界；上界与 `npu-smi` 之间的 gap 必须逐场景实测。

### 实测层级对应

```
npu-smi / nvidia-smi
├─ max_reserved (torch cache pool)
│  ├─ max_allocated = THEORY PEAK ← 公式精确计算 ✅
│  └─ allocator overhead (fragmentation + cached blocks)
└─ driver overhead (CANN/CUDA)
```

## 8. 验证记录

| Model | P (exact) | Config | Theory (max_allocated) | Measured (max_allocated) | Δ |
|-------|-----------|--------|----------------------|-------------------------|---|
| Qwen3.5-2B | **2.27B** | SP=1, DP=4, S=32768, P_max=548M | **20.68 GiB** | **20.71 GiB** | +0.03 |
| Qwen3.5-2B | **2.27B** | SP=2, DP=4, S=32768, P_max=548M | **17.99 GiB** | TBD | — |
| Qwen3.5-35B-A3B | **35.95B** | SP=1, DP=32, S=32768, P_max=1.06B, MoE(E=256,K=8,I_e=512,I_s=512), f=0.75, MTP=1, ViT(S_v=64k) | **37.93 GiB** | TBD | — |

> 注：
> - **P 来源**：checkpoint safetensors header 精确统计（2,274,069,824 params），非模型名"2B"或 config.json 手工估算。
> - Theory 与 Measured 的 0.03 GiB 残差来自公式未覆盖的项（SP all-to-all、HCCL persistent 等，§6），量级可忽略。**公式本身没有漏算。**

### 踩坑记录：不要相信模型名里的参数

Qwen3.5-**2B** 实际是 2.27B。差异来源：
- 18/24 层是 GatedDeltaNet（每层 ~111M），比 6 层 Full Attention（每层 ~52M）大了一倍
- 另有 1 个 MTP layer（~61M）
- 从 config.json 按标准 decoder layer 公式手工估算 = 1.98B，漏了 ~290M

**教训**：`total_params` 优先从 safetensors header 统计，或 `sum(p.numel() for p in model.parameters())`。

*Last updated: 2026-07-22*
