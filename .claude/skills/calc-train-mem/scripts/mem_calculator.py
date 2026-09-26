#!/usr/bin/env python3
"""
Memory Calculator for FSDP2 + SP Training.

Estimates max_allocated (theory peak) from model architecture and training config.
Device-agnostic: works for NPU and CUDA.

Formulas are validated against Qwen3.5-2B profiling data (exact match at 20.71 GiB).

Usage:
    # CLI
    python mem_calculator.py --total-params 2.04B --hidden 2048 ... --dp 4 --sp 1

    # Import
    from mem_calculator import calculate_memory, format_report
    result = calculate_memory(total_params=2.04e9, hidden_size=2048, ...)
    print(format_report(result))
"""

import argparse
import math
import sys
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ModelConfig:
    """Model architecture parameters."""
    total_params: int          # total parameters
    hidden_size: int           # D
    intermediate_size: int     # I (dense FFN) or I_e (per-expert MoE FFN)
    num_layers: int            # L
    vocab_size: int            # V
    seq_len: int               # S (packed)
    dtype: str = "bf16"        # bf16, fp16, fp32
    mlp_type: str = "swiglu"   # swiglu or standard
    tie_word_embeddings: bool = True

    # ViT (optional)
    vit_params: int = 0
    vit_hidden: int = 0       # D_v
    vit_intermediate: int = 0 # I_v
    vit_layers: int = 0       # L_v
    vit_seq_len: int = 0      # S_v
    vit_mlp_type: str = "standard"

    # MoE (optional)
    is_moe: bool = False
    num_experts: int = 0              # E (total experts, e.g. 256)
    num_experts_per_tok: int = 0      # K (activated per token, e.g. 8)
    shared_expert_intermediate_size: int = 0  # I_s (shared expert, default = I_e)

    # Hybrid attention (optional)
    linear_attention_fraction: float = 0.0  # fraction of layers using linear attention

    # MTP (optional)
    mtp_layers: int = 0  # extra MTP decoder layers


@dataclass
class TrainConfig:
    """Training / parallelism configuration."""
    dp_size: int = 1           # FSDP2 data-parallel size
    sp_size: int = 1           # ulysses sequence parallel size
    optimizer: str = "adamw"   # adamw (only supported in v1)
    logits_fused: bool = True  # True: fused kernel ~0; False: eager fp32 logits
    activation_checkpointing: bool = True
    max_unit_params: int = 0   # root FSDP unit params (auto-estimate if 0)


@dataclass
class MemoryBreakdown:
    """Result of memory calculation."""
    # Components
    model_states: float        # GiB
    fsdp_ag: float             # GiB
    fsdp_rs: float             # GiB
    text_checkpoints: float    # GiB
    vit_checkpoints: float     # GiB
    recompute_peak: float      # GiB (text)
    vit_recompute: float       # GiB (ViT, display only — not in theory peak)
    logits: float              # GiB

    # Derived
    comm_buffers: float        # GiB (AG + RS)
    activations: float         # GiB (ckpts + recompute + logits)
    theory_peak: float         # GiB (sum of all)

    # Metadata
    s_local: int
    bytes_per_param: int
    ag_bytes_multiplier: int

    def as_dict(self) -> dict:
        return {
            "model_states_giB": round(self.model_states, 2),
            "fsdp_ag_giB": round(self.fsdp_ag, 2),
            "fsdp_rs_giB": round(self.fsdp_rs, 2),
            "comm_buffers_giB": round(self.comm_buffers, 2),
            "text_checkpoints_giB": round(self.text_checkpoints, 2),
            "vit_checkpoints_giB": round(self.vit_checkpoints, 2),
            "recompute_peak_giB": round(self.recompute_peak, 2),
            "vit_recompute_giB": round(self.vit_recompute, 2),
            "logits_giB": round(self.logits, 2),
            "activations_giB": round(self.activations, 2),
            "theory_peak_giB": round(self.theory_peak, 2),
            "s_local": self.s_local,
        }


# ═══════════════════════════════════════════════════════════════════
# Core Calculation
# ═══════════════════════════════════════════════════════════════════

def _parse_param_count(val) -> int:
    """Parse parameter count: 2.04B, 548M, 2040000000, etc."""
    if isinstance(val, (int, float)):
        return int(val)
    val = str(val).strip().lower().replace(",", "").replace("_", "")
    multipliers = {"b": 1e9, "m": 1e6, "k": 1e3}
    for suffix, mult in multipliers.items():
        if val.endswith(suffix):
            return int(float(val[:-1]) * mult)
    return int(float(val))


def _giB(bytes_val: float) -> float:
    """Bytes → GiB."""
    return bytes_val / (1024 ** 3)


def _estimate_max_unit_params(model: ModelConfig) -> int:
    """
    Estimate root FSDP unit params when not explicitly provided.

    Root unit = everything NOT in _no_split_modules (i.e. non DecoderLayer/VisionBlock).
    Typically: embed_tokens + lm_head + ViT non-block + text norm/rotary.
    """
    # embed_tokens
    embed_params = model.vocab_size * model.hidden_size

    # lm_head (if not tied)
    lm_head_params = 0 if model.tie_word_embeddings else model.vocab_size * model.hidden_size

    # ViT non-block: patch_embed, pos_embed, merger, rotary_pos_emb (~10% of ViT params)
    vit_non_block = 0
    if model.vit_params > 0:
        # ViT blocks use ~90% of ViT params, non-block ≈ 10%
        vit_non_block = int(model.vit_params * 0.10)

    # Text non-block: final norm, rotary_emb (~negligible, <1M)
    text_non_block = model.hidden_size * 2  # final layernorm, ~negligible

    total = embed_params + lm_head_params + vit_non_block + text_non_block
    return total


def calculate_memory(model: ModelConfig, train: TrainConfig) -> MemoryBreakdown:
    """
    Calculate theoretical max_allocated for FSDP2 + SP training.

    Returns MemoryBreakdown with all components in GiB.
    """

    # ── Derived values ──
    S_local = model.seq_len // train.sp_size

    # bytes per param for model states (AdamW, mixed precision)
    if model.dtype in ("bf16", "fp16"):
        # bf16 param + fp32 master + bf16 grad + fp32 m + fp32 v
        bytes_per_param = 2 + 4 + 2 + 4 + 4  # = 16
        param_dtype_bytes = 2
    elif model.dtype == "fp32":
        # fp32 param + fp32 grad + fp32 m + fp32 v
        bytes_per_param = 4 + 4 + 4 + 4  # = 16
        param_dtype_bytes = 4
    else:
        raise ValueError(f"Unknown dtype: {model.dtype}")

    # max_unit_params
    max_unit = train.max_unit_params
    if max_unit <= 0:
        max_unit = _estimate_max_unit_params(model)

    # AG multiplier: 2 (bf16) × 2 (double buffering) = 4 bytes per max_unit param
    ag_bytes = param_dtype_bytes * 2
    # RS: 4 bytes (fp32 reduce_dtype)
    rs_bytes = 4

    # ── 1. Model States ──
    model_states_bytes = model.total_params * bytes_per_param / train.dp_size
    model_states = _giB(model_states_bytes)

    # ── 2. FSDP2 Communication Buffers ──
    ag_gib = _giB(max_unit * ag_bytes)
    rs_gib = _giB(max_unit * rs_bytes)
    comm_buffers = ag_gib + rs_gib

    # ── 3. Activations ──

    # Text checkpoints (activation checkpointing: 1 tensor per layer)
    if train.activation_checkpointing:
        text_ckpt = _giB(model.num_layers * S_local * model.hidden_size * 2)  # bf16
        # MTP checkpoints
        mtp_ckpt = _giB(model.mtp_layers * S_local * model.hidden_size * 2)
    else:
        text_ckpt = _giB(model.num_layers * S_local * model.hidden_size * 2 * 2)
        mtp_ckpt = _giB(model.mtp_layers * S_local * model.hidden_size * 2 * 2)

    # ViT checkpoints
    vit_ckpt = 0.0
    if model.vit_layers > 0:
        vit_ckpt = _giB(model.vit_layers * model.vit_seq_len * model.vit_hidden * 2)

    # ── Text Recompute Peak (1 decoder layer) ──

    # Attention part: average across full-attention and linear-attention layers
    fa_frac = 1.0 - model.linear_attention_fraction
    la_frac = model.linear_attention_fraction
    # Full attention: 7 tensors × bf16 = 14 S D
    # Linear attention (GatedDeltaNet): ~5 tensors × bf16 = 10 S D
    attn_bytes = (fa_frac * 14 + la_frac * 10) * S_local * model.hidden_size

    # MLP part
    if model.is_moe:
        # ── MoE MLP (per-layer recompute peak) ──
        # All 256 experts' autograd-saved intermediates coexist in the graph
        # at the end of recompute forward (before backward frees them one-by-one).
        K = model.num_experts_per_tok
        E = model.num_experts
        I_e = model.intermediate_size          # per-expert FFN intermediate
        I_s = model.shared_expert_intermediate_size
        if I_s <= 0:
            I_s = I_e  # default: same as routed expert

        D = model.hidden_size
        S_x = S_local

        # Routed experts: each token → K experts
        #   Per expert saves: x(S_e,D) + gate_out(S_e,I_e) + up_out(S_e,I_e)
        #                     + act_gate(S_e,I_e) + gated(S_e,I_e)
        #                     + expert_output(S_e,D)  (for routing-weight mul backward)
        #   Σ over all experts: K × S_x × (2D + 4×I_e) × 2  bytes (bf16)
        routed_bytes = K * S_x * (2 * D + 4 * I_e) * 2

        # Shared expert (SwiGLU, processes ALL tokens):
        #   gate_out(S_x,I_s) + up_out(S_x,I_s) + act_gate(S_x,I_s) + gated(S_x,I_s)
        shared_bytes = S_x * (D + 4 * I_s) * 2

        # Expert mask: one_hot → (E, K, S_x) int64
        mask_bytes = E * K * S_x * 8

        # Router logits (S_x, E) bf16 + routing_weights (S_x, K) bf16
        router_bytes = S_x * E * 2 + S_x * K * 2

        mlp_bytes = routed_bytes + shared_bytes + mask_bytes + router_bytes

    else:
        # ── Dense MLP ──
        if model.mlp_type == "swiglu":
            # gate_out + up_out + act_gate + gated = 4 × [S, I] bf16 = 8 S I
            mlp_bytes = 8 * S_local * model.intermediate_size
        else:
            # fc1_out + gelu_out = 2 × [S, I] bf16 = 4 S I
            mlp_bytes = 4 * S_local * model.intermediate_size

    recompute = _giB(attn_bytes + mlp_bytes)

    # ── ViT Recompute Peak (1 ViT block, display only — not in theory peak) ──
    # ViT backward happens AFTER text backward, so vit_recompute does not overlap
    # with the text recompute peak.
    vit_recomp = 0.0
    if model.vit_layers > 0:
        S_v = model.vit_seq_len
        D_v = model.vit_hidden
        I_v = model.vit_intermediate
        # ViT Attention (fused QKV + Flash Attn): 5 tensors × bf16 = 10 S_v D_v
        vit_attn = 10 * S_v * D_v
        # ViT MLP
        if model.vit_mlp_type == "swiglu":
            # concat of attn intermediates (2×D_v) + MLP intermediates (4×I_v)
            vit_mlp = 4 * S_v * D_v + 8 * S_v * I_v
        else:
            # standard: norm intermediates (2×D_v) + fc1_out + gelu_out (2×I_v)
            vit_mlp = 4 * S_v * D_v + 4 * S_v * I_v
        vit_recomp = _giB(vit_attn + vit_mlp)

    # ── 4. Logits ──
    logits = 0.0
    if not train.logits_fused:
        # eager fp32 logits: S_local × V × 4 bytes
        logits = _giB(S_local * model.vocab_size * 4)

    # ── Totals ──
    activations = text_ckpt + mtp_ckpt + vit_ckpt + recompute + logits
    theory_peak = model_states + comm_buffers + activations

    return MemoryBreakdown(
        model_states=model_states,
        fsdp_ag=ag_gib,
        fsdp_rs=rs_gib,
        text_checkpoints=text_ckpt + mtp_ckpt,
        vit_checkpoints=vit_ckpt,
        recompute_peak=recompute,
        vit_recompute=vit_recomp,
        logits=logits,
        comm_buffers=comm_buffers,
        activations=activations,
        theory_peak=theory_peak,
        s_local=S_local,
        bytes_per_param=bytes_per_param,
        ag_bytes_multiplier=ag_bytes,
    )


# ═══════════════════════════════════════════════════════════════════
# Output Formatting
# ═══════════════════════════════════════════════════════════════════

def format_report(model: ModelConfig, train: TrainConfig, mem: MemoryBreakdown) -> str:
    """Generate formatted memory breakdown report."""

    dtype_name = {"bf16": "bf16 mixed (fp32 master)", "fp16": "fp16 mixed (fp32 master)",
                  "fp32": "fp32 full"}.get(model.dtype, model.dtype)

    lines = []
    lines.append("")
    lines.append("=" * 68)
    lines.append("  calc-train-mem: Memory Estimate")
    lines.append("  Target: max_allocated (device-agnostic, NPU or CUDA)")
    lines.append("=" * 68)
    lines.append("")
    lines.append(f"  Model:  {model.total_params/1e9:.2f}B params, "
                 f"D={model.hidden_size}, I={model.intermediate_size}, "
                 f"L={model.num_layers}, V={model.vocab_size}")
    if model.is_moe:
        lines.append(f"         MoE: E={model.num_experts}, K={model.num_experts_per_tok}, "
                     f"I_e={model.intermediate_size}, I_s={model.shared_expert_intermediate_size or model.intermediate_size}")
    lines.append(f"         S={model.seq_len}, dtype={model.dtype}, "
                 f"MLP={model.mlp_type}, logits={'fused' if train.logits_fused else 'eager fp32'}")
    if model.linear_attention_fraction > 0:
        lines.append(f"         Hybrid Attn: {1-model.linear_attention_fraction:.0%} FA + "
                     f"{model.linear_attention_fraction:.0%} LA (GatedDeltaNet)")
    if model.mtp_layers > 0:
        lines.append(f"         MTP layers: {model.mtp_layers}")
    if model.vit_layers > 0:
        lines.append(f"  ViT:    {model.vit_params/1e6:.0f}M params, "
                     f"D_v={model.vit_hidden}, I_v={model.vit_intermediate}, "
                     f"L_v={model.vit_layers}, S_v≈{model.vit_seq_len}, "
                     f"MLP={model.vit_mlp_type}")
    lines.append(f"  Train:  FSDP2, DP={train.dp_size}, SP={train.sp_size}, "
                 f"{train.optimizer.upper()}, AC={'on' if train.activation_checkpointing else 'off'}")
    lines.append(f"         S_local = S/SP = {model.seq_len}/{train.sp_size} = {mem.s_local}")
    lines.append("")

    def row(name, giB, formula=""):
        f = f"  ({formula})" if formula else ""
        return f"  {name:<32} {giB:>7.2f} GiB  {f}"

    lines.append("-" * 68)
    lines.append(f"  1. Model States (per GPU, ÷ DP={train.dp_size})")
    lines.append("-" * 68)
    lines.append(row("Weights (bf16)", model.total_params * 2 / train.dp_size / 1e9 / (1024**3/1e9),
                     f"P×2B/{train.dp_size}"))
    if model.dtype in ("bf16", "fp16"):
        lines.append(row("Weights master (fp32)", model.total_params * 4 / train.dp_size / 1024**3,
                         f"P×4B/{train.dp_size}"))
    lines.append(row("Gradients (bf16)", model.total_params * 2 / train.dp_size / 1024**3,
                     f"P×2B/{train.dp_size}"))
    lines.append(row("Optimizer m+v (fp32)", model.total_params * 8 / train.dp_size / 1024**3,
                     f"P×8B/{train.dp_size}"))
    lines.append(f"  {'─' * 58}")
    lines.append(row("Subtotal", mem.model_states, f"P×{mem.bytes_per_param}B/{train.dp_size}"))

    lines.append("")
    lines.append("-" * 68)
    lines.append(f"  2. FSDP2 Communication Buffers")
    lines.append("-" * 68)
    max_unit_display = train.max_unit_params if train.max_unit_params > 0 else _estimate_max_unit_params(model)
    param_dtype_bytes = 2 if model.dtype in ("bf16", "fp16") else 4
    lines.append(row("All-Gather (bf16, 2× root)", mem.fsdp_ag,
                     f"P_max×{param_dtype_bytes}B×2"))
    lines.append(row("Reduce-Scatter (fp32 root)", mem.fsdp_rs,
                     f"P_max×4B"))
    lines.append(f"  {'─' * 58}")
    lines.append(row("Subtotal", mem.comm_buffers,
                     f"P_max={max_unit_display/1e6:.0f}M params"))

    lines.append("")
    lines.append("-" * 68)
    lines.append(f"  3. Activations (S_local = {mem.s_local})")
    lines.append("-" * 68)
    if model.mtp_layers > 0:
        lines.append(row("Text Checkpoints", mem.text_checkpoints,
                         f"(L={model.num_layers}+MTP={model.mtp_layers})×S_local×D×2B"))
    else:
        lines.append(row("Text Checkpoints", mem.text_checkpoints,
                         f"L×S_local×D×2B"))
    if model.vit_layers > 0:
        lines.append(row("ViT Checkpoints", mem.vit_checkpoints,
                         f"L_v×S_v×D_v×2B (不受 SP 影响)"))
    if model.is_moe:
        mlp_label = (f"attn={((1-model.linear_attention_fraction)*14 + model.linear_attention_fraction*10):.0f}SD"
                     f" + MoE(K×S×(2D+4I_e)×2 + ...)")
        lines.append(row("Recompute Peak (1 layer)", mem.recompute_peak, mlp_label))
    else:
        mlp_label = "SwiGLU 14SD+8SI" if model.mlp_type == "swiglu" else "Standard 14SD+4SI"
        lines.append(row("Recompute Peak (1 layer)", mem.recompute_peak, mlp_label))
    if model.vit_layers > 0:
        vit_mlp_label = ("Standard 10S_vD_v+4S_vD_v+4S_vI_v"
                         if model.vit_mlp_type == "standard"
                         else "SwiGLU 10S_vD_v+4S_vD_v+8S_vI_v")
        lines.append(row("ViT Recompute (1 block)", mem.vit_recompute,
                         vit_mlp_label + " (not in peak³)"))
    if mem.logits > 0:
        lines.append(row("Logits (eager fp32)", mem.logits, "S_local×V×4B"))
    else:
        lines.append(row("Logits (fused kernel)", 0.0, ""))
    lines.append(f"  {'─' * 58}")
    lines.append(row("Subtotal", mem.activations))

    lines.append("")
    lines.append("=" * 68)
    lines.append(f"  THEORY PEAK (max_allocated)      {mem.theory_peak:>7.2f} GiB")
    lines.append("=" * 68)
    lines.append("")
    lines.append("  Above: formula-derived. Each component has a closed-form expression")
    lines.append("  in terms of (P, D, I, L, V, S, DP, SP, P_max).")
    lines.append("")
    if model.vit_layers > 0:
        lines.append("  ³ ViT recompute happens AFTER text backward — does not add to peak.")
    lines.append("")
    lines.append("  Not included in THEORY PEAK (implementation / hardware dependent,")
    lines.append("  no closed-form formula — must be measured with a profiler):")
    lines.append("")
    lines.append("    - SP All-to-All communication buffers")
    lines.append("    - HCCL / NCCL persistent communication buffers")
    lines.append("    - Caching allocator overhead (reserved − allocated)")
    lines.append("    - Device driver overhead (npu-smi − max_reserved)")
    if model.is_moe:
        lines.append("    - EP (Expert Parallelism) all-to-all buffers (if EP enabled)")
    if model.linear_attention_fraction > 0:
        lines.append("    - GatedDeltaNet/SSM intermediates (approximated as 10SD)")
    lines.append("")
    lines.append("  ─────────────────────────────────────────────")
    lines.append("  To measure the full picture:")
    lines.append("    MEM_PROFILE=1 torchrun ... train.py")
    lines.append("    → Compare max_allocated with THEORY PEAK above.")
    lines.append("    → max_reserved captures allocator overhead.")
    lines.append("    → npu-smi / nvidia-smi captures driver overhead.")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def _parse_args():
    p = argparse.ArgumentParser(
        description="calc-train-mem: estimate FSDP2+SP training memory (max_allocated)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Qwen3.5-2B SP=1
  python mem_calculator.py --total-params 2.04B --hidden 2048 --intermediate 6144 \\
      --layers 24 --vocab 248320 --seq-len 32768 --dtype bf16 --dp 4 --sp 1 \\
      --max-unit-params 548M --tie-embeddings \\
      --vit-params 331M --vit-hidden 1024 --vit-intermediate 4096 --vit-layers 24 --vit-seq-len 60000

  # Qwen3.5-2B SP=2
  python mem_calculator.py --total-params 2.04B --hidden 2048 --intermediate 6144 \\
      --layers 24 --vocab 248320 --seq-len 32768 --dtype bf16 --dp 2 --sp 2 \\
      --max-unit-params 548M --tie-embeddings \\
      --vit-params 331M --vit-hidden 1024 --vit-intermediate 4096 --vit-layers 24 --vit-seq-len 60000

  # Simple model (no ViT, from architecture only)
  python mem_calculator.py --total-params 7B --hidden 4096 --intermediate 11008 \\
      --layers 32 --vocab 128000 --seq-len 4096 --dtype bf16 --dp 4 --sp 1 \\
      --mlp-type swiglu --logits-fused --tie-embeddings
        """
    )

    # Model params
    g = p.add_argument_group("Model Architecture")
    g.add_argument("--total-params", type=str, required=True, help="Total params (e.g. 2.04B, 548M)")
    g.add_argument("--hidden", type=int, required=True, help="Hidden size (D)")
    g.add_argument("--intermediate", type=int, required=True, help="Intermediate size (I)")
    g.add_argument("--layers", type=int, required=True, help="Number of decoder layers (L)")
    g.add_argument("--vocab", type=int, required=True, help="Vocabulary size (V)")
    g.add_argument("--seq-len", type=int, required=True, help="Training sequence length (S)")
    g.add_argument("--dtype", type=str, default="bf16", choices=["bf16", "fp16", "fp32"])
    g.add_argument("--mlp-type", type=str, default="swiglu", choices=["swiglu", "standard"])
    g.add_argument("--tie-embeddings", action="store_true", default=False,
                   help="embed_tokens and lm_head share weights")

    # Training params
    g = p.add_argument_group("Training / Parallelism")
    g.add_argument("--dp", type=int, required=True, help="FSDP2 data-parallel size")
    g.add_argument("--sp", type=int, default=1, help="Sequence Parallel size (ulysses, default=1)")
    g.add_argument("--logits-fused", action="store_true", default=True,
                   help="Logits via fused kernel (default)")
    g.add_argument("--logits-eager", action="store_true", default=False,
                   help="Logits via eager fp32 cross-entropy")
    g.add_argument("--no-activation-checkpointing", action="store_true", default=False)
    g.add_argument("--max-unit-params", type=str, default="0",
                   help="Root FSDP unit params (auto-estimate if 0)")

    # ViT
    g = p.add_argument_group("ViT (Vision Transformer, optional)")
    g.add_argument("--vit-params", type=str, default="0")
    g.add_argument("--vit-hidden", type=int, default=0)
    g.add_argument("--vit-intermediate", type=int, default=0)
    g.add_argument("--vit-layers", type=int, default=0)
    g.add_argument("--vit-seq-len", type=int, default=0)
    g.add_argument("--vit-mlp-type", type=str, default="standard", choices=["swiglu", "standard"])

    # MoE
    g = p.add_argument_group("MoE (Mixture of Experts, optional)")
    g.add_argument("--num-experts", type=int, default=0,
                   help="Total number of experts (E)")
    g.add_argument("--experts-per-tok", type=int, default=0,
                   help="Experts activated per token (K)")
    g.add_argument("--shared-expert-intermediate", type=int, default=0,
                   help="Shared expert FFN intermediate size (I_s, default = --intermediate)")

    # Hybrid attention
    g = p.add_argument_group("Hybrid Attention (optional)")
    g.add_argument("--linear-attention-fraction", type=float, default=0.0,
                   help="Fraction of layers using linear attention (e.g. 0.75 for 30/40 LA)")

    # MTP
    g = p.add_argument_group("MTP (Multi-Token Prediction, optional)")
    g.add_argument("--mtp-layers", type=int, default=0,
                   help="Number of extra MTP decoder layers")

    return p.parse_args()


def main():
    args = _parse_args()

    is_moe = args.num_experts > 0 and args.experts_per_tok > 0

    model = ModelConfig(
        total_params=_parse_param_count(args.total_params),
        hidden_size=args.hidden,
        intermediate_size=args.intermediate,
        num_layers=args.layers,
        vocab_size=args.vocab,
        seq_len=args.seq_len,
        dtype=args.dtype,
        mlp_type=args.mlp_type,
        tie_word_embeddings=args.tie_embeddings,
        vit_params=_parse_param_count(args.vit_params),
        vit_hidden=args.vit_hidden,
        vit_intermediate=args.vit_intermediate,
        vit_layers=args.vit_layers,
        vit_seq_len=args.vit_seq_len,
        vit_mlp_type=args.vit_mlp_type,
        is_moe=is_moe,
        num_experts=args.num_experts,
        num_experts_per_tok=args.experts_per_tok,
        shared_expert_intermediate_size=args.shared_expert_intermediate,
        linear_attention_fraction=args.linear_attention_fraction,
        mtp_layers=args.mtp_layers,
    )

    train = TrainConfig(
        dp_size=args.dp,
        sp_size=args.sp,
        optimizer="adamw",
        logits_fused=not args.logits_eager,
        activation_checkpointing=not args.no_activation_checkpointing,
        max_unit_params=_parse_param_count(args.max_unit_params),
    )

    mem = calculate_memory(model, train)
    report = format_report(model, train, mem)
    print(report)

    # Return data as JSON for programmatic use
    import json
    result = {
        "config": {
            "total_params": model.total_params,
            "hidden": model.hidden_size,
            "intermediate": model.intermediate_size,
            "layers": model.num_layers,
            "vocab": model.vocab_size,
            "seq_len": model.seq_len,
            "s_local": mem.s_local,
            "dtype": model.dtype,
            "dp": train.dp_size,
            "sp": train.sp_size,
            "mlp_type": model.mlp_type,
            "logits_fused": train.logits_fused,
        },
        "breakdown": mem.as_dict(),
    }
    print(f"<!-- JSON: {json.dumps(result)} -->")

    return mem


if __name__ == "__main__":
    main()
