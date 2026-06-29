"""
Template for manim-draw diagrams.

Copy this file, rename MyScene and SCENE_CLASS, then run:
    python <this_file>.py

Includes TextBox, NestedTextBox, TreeNode, and TreeLayout building blocks.
"""

from __future__ import annotations
import math
from manim import *


# ═══════════════════════════════════════════════════════════════════════════════
# Building Blocks — copy from rules/building_blocks.md
# ═══════════════════════════════════════════════════════════════════════════════

class TextBox(VGroup):
    """圆角框 + 居中文字。"""

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


class NestedTextBox(VGroup):
    """可嵌套文本框。header 置顶，子 box 按 layout_strategy 排列。"""

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
        else:  # "horizontal"
            self.content.arrange(RIGHT, buff=self._child_gap)


# ═══════════════════════════════════════════════════════════════════════════════
# Tree Layout — copy from rules/building_blocks.md
# ═══════════════════════════════════════════════════════════════════════════════

class TreeNode:
    """A node in a tree layout. Wraps any Mobject as visual content.

    Build the tree programmatically or parse from ASCII text::

        root = TreeNode(TextBox("Root"), key="root")
        root.add_child(TreeNode(TextBox("Child"), key="child",
                                description="A child node", max_description_width=3.0))

        # Or parse a tree description (# comments become descriptions;
        # [N] prefix sets max_description_width for that node):
        root = TreeNode.from_text('''
            root/                # Top-level description
            ├── child_a/         # [3.0] A long description that wraps at 3.0 units
            │   └── grandchild/
            └── child_b/
        ''', lambda label: TextBox(label))
    """

    def __init__(self, content: Mobject, key: str = "", description: str = "",
                 max_description_width: float | None = None) -> None:
        self.content = content
        self.key = key
        self.description = description
        self.max_description_width = max_description_width
        self.parent: TreeNode | None = None
        self.children: list[TreeNode] = []

        # Layout metadata — set by TreeLayout
        self._x: float = 0.0
        self._y: float = 0.0
        self._subtree_size: float = 0.0

    def add_child(self, child: "TreeNode") -> "TreeNode":
        """Add a child node. Returns self for chaining."""
        child.parent = self
        self.children.append(child)
        return self

    @staticmethod
    def from_text(text: str, node_factory) -> "TreeNode":
        """Parse an ASCII tree description into a TreeNode tree.

        Lines determine depth. Tree-drawing chars (├──, └──, │) are
        stripped. Text after ``#`` on each line becomes the node's
        ``description`` attribute. Prefix the description with ``[N]``
        to set a per-node ``max_description_width``, e.g.
        ``node/  # [3.0] A long description that wraps at 3.0 units``.
        """
        lines = text.strip().split("\n")
        parsed: list[tuple[int, str, str]] = []

        for raw in lines:
            line = raw.rstrip()
            depth = 0
            while len(line) >= 4:
                chunk = line[:4]
                if chunk in ("│   ", "    ", "├── ", "└── "):
                    depth += 1
                    line = line[4:]
                else:
                    break
            label = line.strip()
            description = ""
            max_width = None
            if "#" in label:
                label, description = label.split("#", 1)
                label = label.strip()
                description = description.strip()
                if description.startswith("[") and "]" in description:
                    bracket_end = description.index("]")
                    try:
                        max_width = float(description[1:bracket_end])
                        description = description[bracket_end + 1:].strip()
                    except ValueError:
                        pass
            if not label:
                continue
            parsed.append((depth, label, description, max_width))

        if not parsed:
            raise ValueError("No valid lines in tree text")

        root_node = TreeNode(node_factory(parsed[0][1]), key=parsed[0][1],
                             description=parsed[0][2], max_description_width=parsed[0][3])
        stack: list[tuple[int, TreeNode]] = [(parsed[0][0], root_node)]

        for depth, label, description, max_width in parsed[1:]:
            node = TreeNode(node_factory(label), key=label, description=description,
                            max_description_width=max_width)
            while stack and stack[-1][0] >= depth:
                stack.pop()
            if stack:
                stack[-1][1].add_child(node)
            stack.append((depth, node))

        return root_node


class TreeLayout(VGroup):
    """Auto-layout mind-map tree renderer.

    Supports "horizontal" (left-to-right) and "vertical" (top-down).

    Horizontal layout: root at left, children to the right, gentle bezier
    curves for parent→child connections. Preferred for mind maps and
    architecture diagrams.

    Vertical layout: root at top, children below. Preferred for org charts
    and hierarchical structures.

        root = TreeNode(TextBox("Root"))
        root.add_child(TreeNode(TextBox("A"))).add_child(TreeNode(TextBox("B")))
        layout = TreeLayout(root, orientation="horizontal")
        self.add(layout)  # in a Scene
    """

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
        max_description_width: float | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.root = root
        self.orientation = orientation
        self.node_spacing = node_spacing
        self.line_color = line_color
        self.line_stroke_opacity = line_stroke_opacity
        self.line_stroke_width = line_stroke_width
        self._show_descriptions = show_descriptions
        self._desc_font_size = description_font_size
        self._desc_color = description_color
        self._desc_gap = description_gap
        self._max_desc_width = max_description_width

        max_dim = self._max_node_dim(root, orientation)
        if level_spacing is not None:
            self.level_spacing = level_spacing
        else:
            self.level_spacing = max_dim + min_level_gap
        min_safe = max_dim + min_level_gap
        if self.level_spacing < min_safe:
            self.level_spacing = min_safe

        if orientation == "horizontal":
            self._do_layout_horizontal()
        else:
            self._do_layout_vertical()

        self._position_nodes()
        self._create_lines()
        self._desc_texts = VGroup()
        self._desc_lines = VGroup()
        if self._show_descriptions:
            self._create_descriptions()
        self._assemble()

    @staticmethod
    def _max_node_dim(root: TreeNode, orientation: str) -> float:
        max_val = 0.0
        def walk(node: TreeNode) -> None:
            nonlocal max_val
            d = node.content.width if orientation == "horizontal" else node.content.height
            if d > max_val:
                max_val = d
            for child in node.children:
                walk(child)
        walk(root)
        return max_val

    # ── Horizontal layout ──────────────────────────────────────────────

    def _do_layout_horizontal(self) -> None:
        self._compute_heights(self.root)
        self._place_h(self.root, 0.0, 0.0, 0)

    def _compute_heights(self, node: TreeNode) -> float:
        if not node.children:
            node._subtree_size = node.content.height
            return node._subtree_size
        child_heights = [self._compute_heights(c) for c in node.children]
        n = len(node.children)
        gaps = self.node_spacing * (n - 1) if n > 1 else 0.0
        total = sum(child_heights) + gaps
        node._subtree_size = max(node.content.height, total)
        return node._subtree_size

    def _place_h(self, node: TreeNode, x: float, y_center: float, depth: int) -> None:
        node._x = x
        node._y = y_center
        if not node.children:
            return
        child_sizes = [c._subtree_size for c in node.children]
        n = len(node.children)
        gaps = self.node_spacing * (n - 1) if n > 1 else 0.0
        total_h = sum(child_sizes) + gaps
        start_y = y_center + total_h / 2
        child_x = x + self.level_spacing
        for child in node.children:
            child_center_y = start_y - child._subtree_size / 2
            self._place_h(child, child_x, child_center_y, depth + 1)
            start_y -= child._subtree_size + self.node_spacing

    # ── Vertical layout ────────────────────────────────────────────────

    def _do_layout_vertical(self) -> None:
        self._compute_widths(self.root)
        self._place_v(self.root, 0.0, 0.0, 0)

    def _compute_widths(self, node: TreeNode) -> float:
        if not node.children:
            node._subtree_size = node.content.width
            return node._subtree_size
        child_widths = [self._compute_widths(c) for c in node.children]
        n = len(node.children)
        gaps = self.node_spacing * (n - 1) if n > 1 else 0.0
        total = sum(child_widths) + gaps
        node._subtree_size = max(node.content.width, total)
        return node._subtree_size

    def _place_v(self, node: TreeNode, x_center: float, y: float, depth: int) -> None:
        node._x = x_center
        node._y = y
        if not node.children:
            return
        child_widths = [c._subtree_size for c in node.children]
        n = len(node.children)
        gaps = self.node_spacing * (n - 1) if n > 1 else 0.0
        total_w = sum(child_widths) + gaps
        start_x = x_center - total_w / 2
        child_y = y - self.level_spacing
        for child in node.children:
            child_center = start_x + child._subtree_size / 2
            self._place_v(child, child_center, child_y, depth + 1)
            start_x += child._subtree_size + self.node_spacing

    # ── Positioning ────────────────────────────────────────────────────

    def _position_nodes(self) -> None:
        def walk(node: TreeNode) -> None:
            node.content.move_to([node._x, node._y, 0])
            for child in node.children:
                walk(child)
        walk(self.root)

    # ── Connection lines ───────────────────────────────────────────────

    def _create_lines(self) -> None:
        if self.orientation == "horizontal":
            self._create_lines_h()
        else:
            self._create_lines_v()

    def _bezier(self, start, end) -> CubicBezier:
        dx = end[0] - start[0]
        offset = max(abs(dx) * 0.35, 0.2)
        return CubicBezier(
            start_anchor=start,
            start_handle=start + RIGHT * offset,
            end_handle=end + LEFT * offset,
            end_anchor=end,
            stroke_width=self.line_stroke_width,
            color=self.line_color,
            stroke_opacity=self.line_stroke_opacity,
        )

    def _create_lines_h(self) -> None:
        self._lines = VGroup()
        def walk(node: TreeNode) -> None:
            for child in node.children:
                parent_right = node.content.get_right()
                child_left = child.content.get_left()
                self._lines.add(self._bezier(parent_right, child_left))
                walk(child)
        walk(self.root)

    def _create_lines_v(self) -> None:
        self._lines = VGroup()
        def walk(node: TreeNode) -> None:
            for child in node.children:
                parent_bottom = node.content.get_bottom()
                child_top = child.content.get_top()
                self._lines.add(self._bezier(parent_bottom, child_top))
                walk(child)
        walk(self.root)

    # ── Descriptions ─────────────────────────────────────────────────────

    def _create_descriptions(self) -> None:
        """Create description texts and connector lines for nodes that have them.

        Positioning strategy (horizontal):
          - Leaf nodes (no children): description to the RIGHT
          - Parent nodes (has children): description ABOVE

        Positioning strategy (vertical):
          - Leaf nodes: description BELOW
          - Parent nodes: description to the LEFT

        If a node has ``max_description_width`` set, or the layout has a
        default ``max_description_width``, description text is word-wrapped
        to fit within that width.
        """
        self._desc_texts = VGroup()
        self._desc_lines = VGroup()

        def make_desc(node: TreeNode) -> None:
            if not node.description:
                for child in node.children:
                    make_desc(child)
                return

            max_w = node.max_description_width
            if max_w is None:
                max_w = self._max_desc_width

            desc_str = node.description
            if max_w is not None:
                desc_str = self._wrap_text(desc_str, self._desc_font_size, max_w)

            desc = Text(
                desc_str,
                font_size=self._desc_font_size,
                color=self._desc_color,
            )

            if self.orientation == "horizontal":
                if node.children:
                    desc.next_to(node.content, UP, buff=self._desc_gap)
                    start = node.content.get_top()
                    end = desc.get_bottom()
                else:
                    desc.next_to(node.content, RIGHT, buff=self._desc_gap)
                    start = node.content.get_right()
                    end = desc.get_left()
            else:
                if node.children:
                    desc.next_to(node.content, LEFT, buff=self._desc_gap)
                    start = node.content.get_left()
                    end = desc.get_right()
                else:
                    desc.next_to(node.content, DOWN, buff=self._desc_gap)
                    start = node.content.get_bottom()
                    end = desc.get_top()

            line = Line(start, end, color=self._desc_color, stroke_width=0.5)
            line.set_stroke(opacity=0.4)

            self._desc_texts.add(desc)
            self._desc_lines.add(line)

            for child in node.children:
                make_desc(child)

        make_desc(self.root)

    def _wrap_text(self, text: str, font_size: float, max_width: float) -> str:
        """Word-wrap *text* so each line fits within *max_width* (Manim units)."""
        words = text.split()
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = word if not current else current + " " + word
            probe = Text(candidate, font_size=font_size, color=WHITE)
            if probe.width <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                    current = word
                else:
                    # Single word exceeds max_width; force it on its own line
                    lines.append(word)

        if current:
            lines.append(current)

        return "\n".join(lines) if lines else text

    # ── Assembly ───────────────────────────────────────────────────────

    def _assemble(self) -> None:
        nodes = VGroup()
        def walk(node: TreeNode) -> None:
            nodes.add(node.content)
            for child in node.children:
                walk(child)
        walk(self.root)
        parts = [nodes, self._lines]
        if len(self._desc_texts) > 0:
            parts.extend([self._desc_texts, self._desc_lines])
        self.add(*parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Scene
# ═══════════════════════════════════════════════════════════════════════════════

class MyScene(Scene):
    def construct(self):
        # TODO: build your diagram here

        box = TextBox("Hello, manim-draw!")
        box.scale_to_fit_width(config.frame_width - 2)
        box.move_to(ORIGIN)
        self.play(Create(box))
        self.wait(1)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    script = Path(__file__).resolve()
    SCENE_CLASS = "MyScene"

    # Use local .venv/ created by: uv venv --seed --python=3.11 <diagram_dir>/.venv
    MANIM_PYTHON = str(here / ".venv" / "bin" / "python")

    subprocess.run(
        [MANIM_PYTHON, "-m", "manim", "-sql", str(script), SCENE_CLASS],
        cwd=here, check=True,
    )

    png_dir = here / "media" / "images" / Path(__file__).stem
    pngs = sorted(png_dir.glob(f"{SCENE_CLASS}*.png"))
    if pngs:
        dst = here / f"{SCENE_CLASS}.png"
        shutil.copy2(pngs[-1], dst)
        print(f"Saved: {dst}")
