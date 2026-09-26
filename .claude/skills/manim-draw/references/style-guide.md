# Manim Flowchart Style Guide

## Pre-draw Review Checklist

Before writing Manim code, answer these questions:

1. Is the source topology simple enough for Manim, or should Mermaid handle automatic graph layout?
2. Which source lines form one conceptual node?
3. What node types/properties matter for this topic?
4. Which text is the title and which text is body content?
5. Should a note be merged into a node or shown as its own state?
6. Is the flow short enough for one row, or should it snake-wrap?
7. Should the snake run horizontally by rows or vertically by columns?
8. Where should generated files live?

## Manim vs Mermaid Decision

Prefer Manim FlowChart when:

- There is one main line of flow.
- Nodes mainly connect to the next node.
- The diagram needs snake/serpentine layout.
- A simple sequence should snake horizontally by rows or vertically by columns.
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
- Body: details, transformations, comments that come from the source.
- If the source does not provide a body/detail line, leave the body empty; do not invent phrases such as `shard leaf experts` or `wrap expert layers`.

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

## User-provided chart content

For all user-provided chart content, including titles, node labels, body text, legends, table cells, lists, and stated relationships:

- Preserve the original wording and meaning as much as possible.
- Preserve the user's stated structure: order, grouping, containment, rows/columns, and edges.
- It is acceptable to add concise visual summary titles when needed, but do not rewrite the user's content just to make it sound smoother or more polished.
- Do not add inferred explanations, normalized terminology, extra nodes/edges/rows/columns, or unstated relationships unless the user explicitly approves them first.
- If a useful addition or semantic rewrite seems necessary, stop and ask the user before adding it.

## Horizontal vs vertical snake layout

`FlowChart` supports two snake orientations:

- `orientation="horizontal"`: chunks become rows. The first row flows left-to-right, the second row flows right-to-left, and row-transition arrows are vertical.
- `orientation="vertical"`: chunks become columns. The first column flows top-to-bottom, the second column flows bottom-to-top, and column-transition arrows are horizontal.

Use horizontal snake when the diagram should read like a wide process strip. Use vertical snake when the flow represents nested or scoped work and a subgroup should remain a clean contiguous visual region. For example, an `experts` group inside a larger `decoder_layer` group is often clearer as a vertical snake because the inner box can wrap only the consecutive expert nodes without covering unrelated outer-scope nodes.

Keep style consistent across orientations:

- Use the same `FlowNodeSpec` data model, node colors, typography, arrow style, and text-fitting rules.
- Keep `node_gap` as the within-row/within-column gap.
- Keep `row_gap` as the wrapped row/column gap, even in vertical orientation.
- Avoid manual coordinate fixes unless grouping boxes or non-flow annotations require them.

## Explanatory / grouping boxes

General rules:

- Prefer `LabeledBox` for semantic grouping and region labels. Do not create one-off helper boxes for a single diagram unless `LabeledBox` cannot express the needed layout.
- `LabeledBox` supports two label modes:
  - `label_mode="header"` (default): the label reserves space above/below the target and the box sizes around both. Corner positions (`top_left`, `top_right`, `bottom_left`, `bottom_right`) are supported. Use for structural region labels that must not overlap content.
  - `label_mode="overlay"`: the label floats on the box border without affecting layout. Explicit opt-in; supports `label_placement="inside"|"outside"` and `label_inset` (edge-to-edge). Only use when the caller verifies the corner is clear.

Use `LabeledBox` for post-layout callouts around a subplot or region. It should not replace semantic nodes; it adds context around already-arranged content.

Good uses:

- Box a whole `FlowChart` with a caption describing the phase or classification.
- Box a legend or side note.
- Box a nested chart inside a larger figure.

Style guidance:

- Keep `fill_opacity` low (`0.0` to `0.35`).
- Use dashed borders for optional explanatory notes.
- Use solid borders for structural containers.
- Prefer neutral strokes (`#94a3b8`, `#cbd5e1`) unless the box maps to a semantic category.
- Make labels short; long explanations should be a separate note box or split into title/body nodes.
- Do not include redundant diagram-type prefixes in visible titles. Prefer `apply from inside to outside` over `flowchart: apply from inside to outside`; prefer `model > layers > experts` over `containment: model > layers > experts`. The shape/layout already communicates the type.
- Labels should remain simple text by default; do not add background fills behind labels unless the user explicitly requests a background option.
- Do not use outside label placement implicitly; if outside labels are needed, use `label_mode="overlay"` with explicit `label_placement="outside"`.

Example:

```python
notes = LabeledBox(
    VGroup(flow, legend).arrange(DOWN, buff=0.25),
    label="policy and dtype transitions",
    label_position="top_left",
    label_mode="header",
    dashed=True,
    fill_color="#f8fafc",
    fill_opacity=0.22,
    stroke_color="#94a3b8",
)
```

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

## Text fitting without scaling

Do not shrink a single node's text to fit. Use fixed title/body font sizes throughout the chart. If a label is too large for its node, fix it by changing content or geometry, with one-line labels preferred:

1. First try a concise one-line title and one-line body.
2. Increase node width for isolated long identifiers or transformations.
3. Shorten verbose wording before wrapping.
4. Add explicit line breaks only when many labels are long, the row would become too wide, or the break improves readability.
5. Increase node height consistently when several labels are multi-line.
6. Move explanatory detail to a legend, note, or `LabeledBox`.

Per-node `scale_to_fit_width`/`scale_to_fit_height` makes font sizes inconsistent and should be considered a bug. Excessive line wrapping is also a style bug: prefer a wider node or shorter wording when only one or two nodes are long.

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
