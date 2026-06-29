# Example: FSDP flow notes to compact Mermaid

## Input Markdown

```text
All-Gather (通信)
   [W_shard] ──► [W_full]

Forward (计算)

Reshard (计算)
   [W_full] ──► [W_shard]
   💡 activation 保留完整

All-Gather (通信)
   [W_shard] ──► [W_full]

Backward (计算)
    计算 X & W grad

Reduce-Scatter (通信)
   [G_full] ──► [G_shard]
```

## Review

- Merge each operation with its tensor transformation.
- Use two categories: `通信` and `计算`.
- Keep titles as written: `All-Gather (通信)`, `Forward (计算)`, `Reshard (计算)`, `Backward (计算)`, `Reduce-Scatter (通信)`.
- Merge `💡 activation 保留完整` into the `Reshard (计算)` node and render it as `💡 activation 保留完整`.
- Remove `[]` around symbols to reduce clutter.
- Use `<code>` for `W_shard`, `W_full`, `G_full`, `G_shard`.
- Split into `Forward` and `Backward` rows for compact layout.

## Output Mermaid

```mermaid
flowchart TB
    subgraph FWD[Forward]
        direction LR
        A["<div style='min-width:250px'><span style='font-size:22px; white-space:nowrap'><b>All-Gather (通信)</b></span><br/><code>W_shard</code> → <code>W_full</code></div>"]
        B["<div style='min-width:250px'><span style='font-size:22px; white-space:nowrap'><b>Forward (计算)</b></span></div>"]
        C["<div style='min-width:250px'><span style='font-size:22px; white-space:nowrap'><b>Reshard (计算)</b></span><br/><code>W_full</code> → <code>W_shard</code><br/>💡 activation 保留完整</div>"]
        A --> B --> C
    end

    subgraph BWD[Backward]
        direction LR
        D["<div style='min-width:250px'><span style='font-size:22px; white-space:nowrap'><b>All-Gather (通信)</b></span><br/><code>W_shard</code> → <code>W_full</code></div>"]
        E["<div style='min-width:250px'><span style='font-size:22px; white-space:nowrap'><b>Backward (计算)</b></span><br/>计算 X &amp; W grad</div>"]
        F["<div style='min-width:280px'><span style='font-size:22px; white-space:nowrap'><b>Reduce-Scatter (通信)</b></span><br/><code>G_full</code> → <code>G_shard</code></div>"]
        D --> E --> F
    end

    FWD --> BWD

    classDef comm fill:#ecfdf5,stroke:#059669,stroke-width:2px,color:#111827;
    classDef compute fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px,color:#111827;

    class A,D,F comm;
    class B,C,E compute;
```
