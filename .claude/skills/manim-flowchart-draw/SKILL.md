---
name: manim-flowchart-draw
description: Create polished ManimCE flowchart diagrams for simple, mostly-linear processes that need flexible visual control, snake/serpentine wrapping, title/body nodes, mixed CJK/Latin typography, fixed-size arrows, and rendered PNG output. Use when a Mermaid graph would be overkill or too automatic, especially for one main path with few cross edges; prefer mermaid-draw instead for large graphs with many nodes, branches, cross-links, or complex automatic layout needs.
---

# Manim Flowchart Draw

## Purpose

Use this skill to turn a prose/Markdown process description into a compact ManimCE flowchart when the diagram is simple in topology but needs precise visual control: custom node boxes, title/body typography, snake wrapping, nested groups, fixed-size arrows, and final image inspection.

This skill complements `mermaid-draw`:

- Use **Mermaid** for complex graphs: many nodes, branches, cross-links, or when automatic layout is more valuable than manual control.
- Use **Manim FlowChart** for simple or mostly-linear flows: one main path, few/no cross edges, and a need for snake layout or precise visual polish.

## Workflow

1. **Review before drawing** using the same discipline as `mermaid-draw`:
   - Identify which source lines form one conceptual node.
   - Decide each node's role/type in this topic. Do not hard-code categories like communication/compute; the categories are topic-specific.
   - Split each node into a short title and a body line.
   - Merge short notes into the nearest relevant node unless they are independent states/decisions.
   - Decide whether Manim is appropriate; switch to Mermaid if the graph has many branches or cross edges.
2. **Choose layout**:
   - Short linear flows: one row.
   - Longer linear flows: use `max_nodes_per_line` and snake/serpentine wrapping.
   - Multiple independent sections: use multiple `FlowChart`s or nested/grouped charts.
3. **Create a dedicated diagram folder** and copy `assets/flowchart_scene.py` as the starting script.
4. **Edit only the data and small style parameters first**:
   - Replace `ExampleFlow` data with `FlowNodeSpec(...)` items.
   - Adjust `kind`, `width`, `max_nodes_per_line`, `node_gap`, `row_gap`, and title.
   - Add a legend only if it helps explain node types.
5. **Render and inspect**:
   - Run `python <diagram>.py`.
   - Inspect the PNG next to the script.
   - Iterate on node widths, row gaps, font rise, and arrows until visually clean.

## Template

Start from:

```text
assets/flowchart_scene.py
```

The template includes:

- `FlowNodeSpec`: title/body/kind node declarations.
- `FlowNode`: rounded title/body boxes.
- `FlowChart`: snake-wrapped reusable flowchart with optional container.
- `mixed_text()`: one `MarkupText` object per label, using Pango spans.
- Self-rendering Manim bootstrap using `-sql`, local `.venv` if present, and a local `media/` directory.

Minimal data shape:

```python
flow = FlowChart(
    [
        FlowNodeSpec("Load Input (I/O)", "batch -> tokens", "io"),
        FlowNodeSpec("Encode (Model)", "tokens -> hidden", "model"),
        FlowNodeSpec("Sync State (Cluster)", "rank local -> global", "sync"),
    ],
    title="example flow",
    max_nodes_per_line=4,
    show_container=True,
)
```

## Design Rules

### Node semantics

Use node `kind` to represent topic-specific properties. Examples: `io`, `model`, `sync`, `state`, `control`, `compute`, `comm`, `error`, `decision`. Do not assume every diagram needs exactly `通信` and `计算`; those were only one topic's categories.

Use the smallest useful number of visual categories. Two or three categories are usually enough. Add more colors only when it improves comprehension more than it increases clutter.

### Node content

- Merge an operation and its immediate transformation into one node.
- Keep titles short and stable; put details in the body.
- Prefer body transformations like `input -> output` or `W_shard -> W_full`.
- Preserve user wording where possible, but remove decorative clutter like unnecessary brackets if it improves readability.
- Increase node width for long titles instead of letting titles overflow.

### Layout selection

Use Manim FlowChart when the path is simple and mostly sequential. Use Mermaid when the diagram is a graph: many cross-links, branches, fan-in/fan-out, or nested dependencies where automatic layout will be better.

For Manim:

- Use `max_nodes_per_line` for snake wrapping.
- Keep `node_gap` and `row_gap` visually even.
- Align wrap endpoints vertically so the row transition arrow is straight.
- Fit the final group to frame with `fit_to_frame()`.

### Typography

Defaults:

```python
CJK_FONT = "LXGW WenKai"
LATIN_FONT = "JetBrains Mono"
```

Rules:

- Render mixed labels as a single `MarkupText` object with Pango font spans. Do not manually arrange separate `Text` mobjects for each language run.
- Use `LXGW WenKai` for CJK spans.
- Use `JetBrains Mono` for Latin/code/symbol spans.
- Body text passes `latin_rise_em=LATIN_BODY_RISE_EM` to optically align code snippets inside CJK text. Tune this constant by visual inspection when needed.

### Arrows

ManimCE `Arrow` scales tip and stroke based on length by default. For consistent diagrams, keep visual arrow size fixed and vary only connector length:

```python
Arrow(
    start,
    end,
    stroke_width=2.2,
    tip_length=0.12,
    max_tip_length_to_length_ratio=1.0,
    max_stroke_width_to_length_ratio=100,
)
```

Use direct arrows for adjacent logical items. If the flow needs many non-adjacent connectors, reconsider Mermaid.

## Rendering Requirements

- Diagram scripts must be self-executing: `python diagram.py` renders the PNG.
- Use `manim -sql` for fast static rendering.
- Pass `--media_dir <diagram-folder>/media` so Manim cache stays local.
- Copy the final PNG next to the script.
- Inspect the rendered image and iterate.

If fonts are missing, install or document these packages/fonts:

- `LXGW WenKai` for CJK.
- `JetBrains Mono` for Latin/code.

If Manim is not available, create a local venv in the diagram folder and install Manim there, or use an existing project Manim venv. The bundled template contains this repository's fallback venv path only as a local convenience; update or remove it when copying the skill to another machine.

## Optional References

Read `references/style-guide.md` when converting rough notes into node/title/body/category decisions or when deciding whether to use Mermaid or Manim.
