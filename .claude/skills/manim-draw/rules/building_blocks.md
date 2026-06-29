---
name: building_blocks
description: TextBox and NestedTextBox reusable components for building diagrams
metadata:
  tags: textbox, nested, layout, building-blocks
---

# Building Blocks

Reusable VGroup-based components for constructing diagrams. Copy these classes into your script, then compose them to build the desired figure.

## TextBox

Rounded rectangle with centered text. The box auto-fits the text, or uses a fixed size (text shrinks only on overflow).

```python
from manim import *

class TextBox(VGroup):
    def __init__(
        self,
        text: str,
        font_size: float = 48,
        font: str = "DejaVu Sans",
        box_width: float | None = None,
        box_height: float | None = None,
        corner_radius: float = 0.3,
        padding: float = 0.4,
        box_color: str = WHITE,
        text_color: str = WHITE,
        **kwargs,
    ):
        super().__init__(**kwargs)
        t = Text(text, font_size=font_size, font=font, color=text_color)

        if box_width is None:
            box_width = t.width + padding * 2
        if box_height is None:
            box_height = t.height + padding * 2

        avail_w = box_width - padding * 2
        avail_h = box_height - padding * 2
        scale = min(1.0, avail_w / t.width, avail_h / t.height)
        if scale < 1.0:
            t.scale(scale)

        box = RoundedRectangle(
            width=box_width,
            height=box_height,
            corner_radius=corner_radius,
            color=box_color,
        )
        box.move_to(t.get_center())
        self.add(box, t)
```

**Key parameters:**

| Param | Default | Purpose |
|-------|---------|---------|
| `box_width` / `box_height` | `None` (auto-fit) | Fix box size; text scales down on overflow |
| `corner_radius` | `0.3` | Roundness of the box corners |
| `padding` | `0.4` | Space between text and box edge |
| `box_color` / `text_color` | `WHITE` | Colors for border and text |

## NestedTextBox

A container box with its own header text (top-center aligned) and an internal content area for child boxes. Supports multiple layout strategies.

```python
from __future__ import annotations
import math
from manim import *

class NestedTextBox(VGroup):
    def __init__(
        self,
        text: str,
        font_size: float = 48,
        font: str = "DejaVu Sans",
        corner_radius: float = 0.3,
        padding: float = 0.4,
        child_gap: float = 0.3,
        box_color: str = WHITE,
        text_color: str = WHITE,
        layout_strategy: str = "horizontal",
        grid_threshold: int = 4,
        auto_flow: str = "horizontal",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._font_size = font_size
        self._font = font
        self._padding = padding
        self._child_gap = child_gap
        self._corner_radius = corner_radius
        self._box_color = box_color
        self._text_color = text_color
        self._layout_strategy = layout_strategy
        self._grid_threshold = grid_threshold
        self._auto_flow = auto_flow

        self.header = Text(text, font_size=font_size, font=font, color=text_color)
        self.content = VGroup()
        self.box: RoundedRectangle | None = None
        self._relayout()

    def add_text_box(self, child: VGroup) -> "NestedTextBox":
        self.content.add(child)
        self._relayout()
        return self

    def set_layout_strategy(self, strategy: str) -> "NestedTextBox":
        self._layout_strategy = strategy
        self._relayout()
        return self

    def _relayout(self) -> None:
        if self.box is not None:
            self.remove(self.box)

        n = len(self.content)
        if n > 0:
            self._arrange_content(n)
            content_w = self.content.width
            content_h = self.content.height
        else:
            content_w = 0.0
            content_h = 0.0

        total_w = max(self.header.width, content_w) + self._padding * 2
        total_h = self.header.height + content_h + self._padding * 2
        if n > 0:
            total_h += self._child_gap

        self.box = RoundedRectangle(
            width=total_w,
            height=total_h,
            corner_radius=self._corner_radius,
            color=self._box_color,
        )

        self.header.move_to(
            self.box.get_top() + DOWN * (self._padding + self.header.height / 2)
        )
        if n > 0:
            self.content.next_to(self.header, DOWN, buff=self._child_gap)

        self.submobjects = [self.box, self.header, self.content]

    def _arrange_content(self, n: int) -> None:
        strategy = self._layout_strategy

        if strategy == "vertical":
            self.content.arrange(DOWN, buff=self._child_gap)
        elif strategy == "square":
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            self.content.arrange_in_grid(rows=rows, cols=cols, buff=self._child_gap)
        elif strategy == "auto":
            t = self._grid_threshold
            if self._auto_flow == "vertical":
                rows = min(n, t)
                cols = math.ceil(n / rows)
            else:
                cols = min(n, t)
                rows = math.ceil(n / cols)
            self.content.arrange_in_grid(rows=rows, cols=cols, buff=self._child_gap)
        else:  # "horizontal" (default)
            self.content.arrange(RIGHT, buff=self._child_gap)
```

### Layout Strategies

| Strategy | Behavior |
|----------|----------|
| `"horizontal"` | Single row, left to right (default) |
| `"vertical"` | Single column, top to bottom |
| `"square"` | Square grid, columns = ceil(sqrt(n)) |
| `"auto"` | Flows in `auto_flow` direction, wraps after `grid_threshold` items per row/col |

### Auto Flow

When `layout_strategy="auto"`:
- `auto_flow="horizontal"` (default): max `grid_threshold` items per row, wraps to next row
- `auto_flow="vertical"`: max `grid_threshold` items per column, wraps to next column

### Nesting

Both `TextBox` and `NestedTextBox` can be added to a `NestedTextBox` via `add_text_box()`. The outer box auto-expands to contain all children. Supports method chaining:

```python
outer = NestedTextBox("Outer", layout_strategy="horizontal")
outer.add_text_box(TextBox("A")).add_text_box(TextBox("B"))

inner = NestedTextBox("Inner")
inner.add_text_box(TextBox("X")).add_text_box(TextBox("Y"))
outer.add_text_box(inner)
```

## Tree Layout

`TreeNode` + `TreeLayout` provide automatic mind-map layout. Build a tree of nodes,
pass the root to `TreeLayout`, and it positions everything level-by-level with
gentle bezier curves connecting parents to children.

### TreeNode

Wraps any `Mobject` as the visual content of a node. Supports method chaining
and parsing from ASCII tree descriptions.

```python
class TreeNode:
    def __init__(self, content: Mobject, key: str = "", description: str = "") -> None:
        self.content = content
        self.key = key
        self.description = description  # shown as annotation by TreeLayout
        self.parent: TreeNode | None = None
        self.children: list[TreeNode] = []

    def add_child(self, child: TreeNode) -> TreeNode:
        child.parent = self
        self.children.append(child)
        return self

    @staticmethod
    def from_text(text: str, node_factory) -> TreeNode:
        """Parse an ASCII tree description.

        Lines determine depth. Tree-drawing chars (├──, └──, │) are
        stripped. Text after ``#`` on each line becomes that node's
        ``description``.
        """
```

### TreeLayout

Two-pass auto-layout engine supporting horizontal (left-to-right) and
vertical (top-down) orientations.

```python
class TreeLayout(VGroup):
    def __init__(
        self,
        root: TreeNode,
        orientation: str = "horizontal",
        level_spacing: float | None = None,
        node_spacing: float = 0.25,
        line_color: str = WHITE,
        line_stroke_opacity: float = 0.5,
        line_stroke_width: float = 1.5,
        min_level_gap: float = 0.6,
        show_descriptions: bool = True,
        description_font_size: float = 20,
        description_color: str = "#AAAAAA",
        description_gap: float = 0.15,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        # ... runs two-pass layout + bezier curves + descriptions + assembles VGroup
```

**Key parameters:**

| Param | Default | Purpose |
|-------|---------|---------|
| `orientation` | `"horizontal"` | Layout direction: `"horizontal"` (left-to-right) or `"vertical"` (top-down) |
| `level_spacing` | `None` (auto) | Distance between levels; auto-computed from max node width + `min_level_gap` |
| `node_spacing` | `0.25` | Vertical gap between sibling subtrees (horizontal) / horizontal gap (vertical) |
| `min_level_gap` | `0.6` | Minimum gap between levels when `level_spacing` is auto |
| `line_*` | various | Styling for bezier connection curves |
| `show_descriptions` | `True` | Whether to render node descriptions |
| `description_font_size` | `20` | Font size for description text |
| `description_color` | `"#AAAAAA"` | Color for description text and connector lines |
| `description_gap` | `0.15` | Gap between node and its description |
| `max_description_width` | `None` | Default max width for descriptions; longer text wraps to multiple lines |

**Orientation notes:**

- `"horizontal"` — root at left, children to the right. **Preferred for mind maps and architecture diagrams.** Bezier curves bow horizontally.
- `"vertical"` — root at top, children below. Preferred for org charts and classical hierarchy trees. Bezier curves bow vertically.

### Node Descriptions

Each `TreeNode` can carry a `description` string. `TreeLayout` auto-renders these as
small annotation text connected by a thin line:

| Node type | Horizontal placement | Vertical placement |
|-----------|---------------------|--------------------|
| Leaf (no children) | RIGHT of node | BELOW node |
| Parent (has children) | ABOVE node | LEFT of node |

Set descriptions via the `#` comment syntax in `from_text()`. Prefix the
description with `[N]` to set a per-node `max_description_width` (in Manim units)
that the text wraps within:

```python
root = TreeNode.from_text('''
    Open-VeOmni/         # Top-level orchestration
    ├── veomni/          # Core framework
    │   ├── trainer/     # [3.0] Training loop — this long text wraps at 3.0 units
    │   └── data/        # Dataset pipeline
    └── tasks/           # Task definitions
''', make_box)
```

Or programmatically:

```python
root = TreeNode(TextBox("Root"), key="root", description="Top-level")
root.add_child(TreeNode(TextBox("Leaf"), key="leaf",
    description="A long description that should wrap",
    max_description_width=3.0))
```

When `max_description_width` is `None` (default), the description renders as a
single line. Set it on `TreeLayout` for a global default, or per-node (which
takes priority).

### Usage Example

```python
# Parse from ASCII tree description with # comments as descriptions
VEOMNI_TREE = """
    Open-VeOmni/         # Top-level orchestration framework
    ├── veomni/          # Core training framework
    │   ├── trainer/     # Training loop orchestration
    │   ├── distributed/ # Multi-GPU communication
    │   ├── data/        # Dataset loading & preprocessing
    │   ├── models/      # Model definitions & loading
    │   └── schedulers/  # Learning rate scheduling
    ├── tasks/           # Task entry points
"""

def make_box(text: str) -> TextBox:
    return TextBox(text, box_color=BLUE, fill_color=BLUE_FILL, fill_opacity=0.25)

root = TreeNode.from_text(VEOMNI_TREE, make_box)

# Layout, fit, and add to scene
layout = TreeLayout(root, orientation="horizontal")
layout.scale_to_fit_width(config.frame_width - 2)
layout.scale_to_fit_height(config.frame_height - 2)
layout.move_to(ORIGIN)
self.add(layout)
```

### Design Notes

- **No dependency on UniformArrow** — TreeLayout uses `CubicBezier` curves, not arrows
- Bezier curves are S-shaped, bowing from parent outward toward each child
- `from_text()` strips tree-drawing chars (`├──`, `└──`, `│   `); text after `#` becomes `node.description`; `[N]` prefix sets per-node `max_description_width`
- Descriptions are auto-positioned: leaves in flow direction, parents perpendicular (above/left)
- Descriptions auto-wrap when `max_description_width` is set (per-node or layout default)
- Description connector lines are thin (0.5px) and semi-transparent (0.4 opacity)
- Node content can be any `Mobject`: `TextBox`, `NestedTextBox`, custom `VGroup`, etc.
- The tree must be fully built before creating `TreeLayout`
- For cross-branch dependencies not captured by the tree, add manual edges after layout
