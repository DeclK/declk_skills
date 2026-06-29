# Manim Flowchart Style Guide

## Pre-draw Review Checklist

Before writing Manim code, answer these questions:

1. Is the source topology simple enough for Manim, or should Mermaid handle automatic graph layout?
2. Which source lines form one conceptual node?
3. What node types/properties matter for this topic?
4. Which text is the title and which text is body content?
5. Should a note be merged into a node or shown as its own state?
6. Is the flow short enough for one row, or should it snake-wrap?
7. Where should generated files live?

## Manim vs Mermaid Decision

Prefer Manim FlowChart when:

- There is one main line of flow.
- Nodes mainly connect to the next node.
- The diagram needs snake/serpentine layout.
- You need precise control over fonts, arrows, node sizes, frame fitting, or nested containers.
- The final artifact is a polished static image.

Prefer Mermaid when:

- The diagram is a graph rather than a line.
- There are many nodes or cross edges.
- There are branches, joins, fan-in/fan-out, or complex dependencies.
- Automatic layout will be more reliable and attractive than manual coordinates.

## Node Merging Heuristics

Merge lines when they describe one operation:

- Operation label plus data transformation.
- Operation label plus one short note.
- Step title plus one short effect/result.

Keep lines separate when they describe different operations, decisions, loops, or independent states.

## Node Types

Node types are topic-specific. Examples:

- Data movement vs computation.
- User action vs system action.
- Input/output vs model vs synchronization.
- State vs transition vs decision.
- Normal path vs error/retry path.

Use the smallest useful number of visual categories. Do not add a new color for every noun.

## Label Style

Recommended node label:

- Title: short, bold, larger.
- Body: details, transformations, comments.

Examples:

```text
Title: Load Input (I/O)
Body: batch -> tokens
```

```text
Title: Forward / Backward (Train)
Body: 使用 bf16 计算
```

For exact identifiers, prefer plain code-like Latin text in the body; the template renders it with JetBrains Mono.

## Visual Defaults

Base colors:

```python
COMM_FILL = "#ecfdf5"
COMM_STROKE = "#059669"
COMPUTE_FILL = "#f5f3ff"
COMPUTE_STROKE = "#7c3aed"
SYNC_FILL = "#eff6ff"
SYNC_STROKE = "#2563eb"
GROUP_FILL = "#f8fafc"
GROUP_STROKE = "#cbd5e1"
TEXT_COLOR = "#111827"
ARROW_COLOR = "#475569"
```

These names are defaults only. Rename/re-map `kind` values to match the current topic.

## Typography Pitfalls

- Avoid assembling CJK and Latin as separate `Text` mobjects; baseline and spaces become inconsistent.
- Use one `MarkupText` object with font spans.
- Tune `LATIN_BODY_RISE_EM` only after inspecting the rendered PNG.
- If a title overflows, widen the node first; do not rely only on global scaling.

## Arrow Pitfalls

ManimCE `Arrow` changes tip/stroke with length unless max ratios are overridden. Always set:

```python
max_tip_length_to_length_ratio=1.0
max_stroke_width_to_length_ratio=100
```

Then choose fixed `stroke_width` and `tip_length`.
