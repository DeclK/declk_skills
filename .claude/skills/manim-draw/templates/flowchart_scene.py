from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

here = Path(__file__).resolve().parent
venv_python = here / ".venv" / "bin" / "python"
if __name__ == "__main__" and venv_python.exists() and Path(sys.prefix).resolve() != (here / ".venv").resolve():
    os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve())])

try:
    from manim import *
except ModuleNotFoundError:
    if __name__ == "__main__":
        raise SystemExit(
            f"Manim is not installed in {sys.executable}. "
            f"Create a diagram-local venv at {here / '.venv'} and install manim there."
        )
    raise

COMM_FILL = "#ecfdf5"
COMM_STROKE = "#059669"
COMPUTE_FILL = "#f5f3ff"
COMPUTE_STROKE = "#7c3aed"
SYNC_FILL = "#eff6ff"
SYNC_STROKE = "#2563eb"
GROUP_FILL = "#f8fafc"
GROUP_STROKE = "#cbd5e1"
TEXT_COLOR = "#111827"
MUTED_TEXT = "#475569"
ARROW_COLOR = "#475569"
CJK_FONT = "LXGW WenKai"
LATIN_FONT = "JetBrains Mono"
FONT = LATIN_FONT
LATIN_BODY_RISE_EM = -0.04


def mixed_text(
    text: str,
    font_size: float,
    weight: str = NORMAL,
    color: str = TEXT_COLOR,
    latin_rise_em: float = 0.0,
    justify: bool = False,
    force_rise: bool = False,
) -> MarkupText:
    """Render one Pango markup text object with CJK and Latin font spans."""
    markup = mixed_text_markup(text, latin_rise_em=latin_rise_em, font_size=font_size, force_rise=force_rise)
    return MarkupText(
        markup,
        font=LATIN_FONT,
        font_size=font_size,
        weight=weight,
        color=color,
        disable_ligatures=True,
        justify=justify,
    )


def mixed_text_markup(text: str, latin_rise_em: float = 0.0, font_size: float = 20, force_rise: bool = False) -> str:
    has_cjk = any(kind == "cjk" for kind, _ in split_mixed_text_runs(text))
    effective_rise = latin_rise_em if (force_rise or has_cjk) else 0.0
    return "".join(
        markup_span(kind, value, latin_rise_em=effective_rise, font_size=font_size)
        for kind, value in split_mixed_text_runs(text)
    )


def markup_span(kind: str, value: str, latin_rise_em: float = 0.0, font_size: float = 20) -> str:
    escaped = escape_markup(value)
    if kind == "space":
        return escaped
    font = CJK_FONT if kind == "cjk" else LATIN_FONT
    attrs = [f'font_family="{escape_markup(font)}"']
    if kind == "latin" and latin_rise_em:
        attrs.append(f'rise="{int(latin_rise_em * font_size * 1000)}"')
    return f'<span {" ".join(attrs)}>{escaped}</span>'


def escape_markup(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def split_mixed_text_runs(text: str) -> list[tuple[str, str]]:
    runs: list[tuple[str, str]] = []
    current_kind: str | None = None
    current_chars: list[str] = []
    for ch in text:
        kind = char_kind(ch)
        if kind != current_kind and current_chars:
            runs.append((current_kind or "latin", "".join(current_chars)))
            current_chars = []
        current_kind = kind
        current_chars.append(ch)
    if current_chars:
        runs.append((current_kind or "latin", "".join(current_chars)))
    return runs


def char_kind(ch: str) -> str:
    if ch.isspace():
        return "space"
    if contains_cjk(ch):
        return "cjk"
    return "latin"


def contains_cjk(text: str) -> bool:
    return any("\u3400" <= ch <= "\u9fff" or "\uf900" <= ch <= "\ufaff" for ch in text)


@dataclass(frozen=True)
class FlowNodeSpec:
    title: str
    body: str
    kind: str = "compute"
    width: float | None = None
    height: float | None = None
    body_rise_em: float | None = None


class FlowNode(VGroup):
    """Rounded title/body node for FlowChart.

    The node owns a rectangular footprint (`layout_width`, `layout_height`) so a
    FlowChart can compute non-overlapping rows even when nested charts are mixed
    with simple nodes.
    """

    def __init__(
        self,
        title: str,
        body: str,
        kind: str = "compute",
        width: float = 2.85,
        height: float = 1.05,
        title_size: int = 25,
        body_size: int = 20,
        font: str = FONT,
        corner_radius: float = 0.12,
        stroke_width: float = 3.0,
        padding: float = 0.18,
        shrink_to_fit: bool = False,
        body_rise_em: float | None = None,
    ) -> None:
        super().__init__()
        if body_rise_em is None:
            body_rise_em = LATIN_BODY_RISE_EM
        fill, stroke = style_for_kind(kind)
        rect = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=corner_radius,
            stroke_color=stroke,
            stroke_width=stroke_width,
            fill_color=fill,
            fill_opacity=1.0,
        )
        title_mob = mixed_text(title, font_size=title_size, weight=BOLD, justify=True)
        text_items: list[Mobject] = [title_mob]
        body_mob: MarkupText | None = None
        if body:
            body_lines = body.split("\n")
            if len(body_lines) == 1:
                body_mob = mixed_text(body, font_size=body_size, latin_rise_em=body_rise_em, justify=True)
            else:
                # Multi-line body: if *any* line contains CJK, force the same
                # rise on all lines so Latin baselines are consistent.
                body_has_cjk = any(
                    any(kind == "cjk" for kind, _ in split_mixed_text_runs(line))
                    for line in body_lines
                )
                body_line_mobs = [
                    mixed_text(line, font_size=body_size, latin_rise_em=body_rise_em, justify=True, force_rise=body_has_cjk)
                    for line in body_lines
                ]
                body_mob = VGroup(*body_line_mobs).arrange(DOWN, buff=0.03)
            text_items.append(body_mob)
        text_group = VGroup(*text_items)
        if len(text_items) > 1:
            text_group.arrange(DOWN, buff=0.10)
        max_w = width - padding * 2
        max_h = height - padding * 2
        if text_group.width > max_w or text_group.height > max_h:
            raise ValueError(
                f"FlowNode text does not fit without scaling: title={title!r}, body={body!r}, "
                f"text_size=({text_group.width:.2f}, {text_group.height:.2f}), "
                f"max_size=({max_w:.2f}, {max_h:.2f}). "
                "Use explicit line breaks, wider/taller nodes, or shorter labels."
            )
        text_group.move_to(rect.get_center())
        self.add(rect, text_group)
        self.rect = rect
        self.body = body_mob
        self.layout_width = width
        self.layout_height = height
        self.kind = kind



class LabeledBox(VGroup):
    """A reusable explanatory/grouping box around any mobject.

    Use it to call out a whole FlowChart, a row, a legend, or any subplot without
    changing the wrapped object's internal layout.

    Two label modes:

    - ``label_mode="header"`` (default): the label sits above/below/beside the
      target with ``label_gap`` separation; the box sizes around both.  This
      guarantees the label cannot overlap content.  Corner positions
      (``top_left``, ``top_right``, ``bottom_left``, ``bottom_right``) are
      supported — the label is placed at the edge of the reserved header space.

    - ``label_mode="overlay"``: the label floats on the box border **without**
      affecting box dimensions.  Explicit opt-in; the caller must verify the
      label does not overlap content.  Supports ``label_placement="inside"``
      and ``"outside"``, plus ``label_inset`` (edge-to-edge distance from box
      border to label edge).
    """

    HEADER_POSITIONS = {
        "top", "bottom", "left", "right",
        "top_left", "top_right", "bottom_left", "bottom_right",
    }
    OVERLAY_POSITIONS = {
        "top_left", "top_center", "top_right",
        "bottom_left", "bottom_center", "bottom_right",
    }

    def __init__(
        self,
        target: Mobject,
        label: str | None = None,
        padding: float = 0.20,
        padding_top: float | None = None,
        padding_bottom: float | None = None,
        padding_left: float | None = None,
        padding_right: float | None = None,
        label_gap: float = 0.12,
        label_size: int = 22,
        label_position: str = "top",
        label_mode: str = "header",
        label_placement: str = "inside",
        label_inset: float = 0.18,
        fill_color: str = GROUP_FILL,
        fill_opacity: float = 0.32,
        stroke_color: str = GROUP_STROKE,
        stroke_width: float = 2.0,
        dashed: bool = False,
        dash_count: int = 52,
        corner_radius: float = 0.16,
    ) -> None:
        super().__init__()
        if label_mode not in {"header", "overlay"}:
            raise ValueError("label_mode must be 'header' or 'overlay'")
        if label_placement not in {"inside", "outside"}:
            raise ValueError("label_placement must be 'inside' or 'outside'")
        if label_mode == "header" and label_position not in self.HEADER_POSITIONS:
            raise ValueError(
                f"header label_position must be one of {sorted(self.HEADER_POSITIONS)}"
            )
        if label_mode == "overlay" and label_position not in self.OVERLAY_POSITIONS:
            raise ValueError(
                f"overlay label_position must be one of {sorted(self.OVERLAY_POSITIONS)}"
            )

        label_mob = mixed_text(label, font_size=label_size, weight=BOLD) if label else None

        if label_mob and label_mode == "header":
            content = self._build_header_content(label_mob, target, label_position, label_gap)
        else:
            content = VGroup(target)

        pt = padding_top if padding_top is not None else padding
        pb = padding_bottom if padding_bottom is not None else padding
        pl = padding_left if padding_left is not None else padding
        pr = padding_right if padding_right is not None else padding
        box_w = content.width + pl + pr
        box_h = content.height + pt + pb
        box_center_x = content.get_center()[0] + (pr - pl) / 2
        box_center_y = content.get_center()[1] + (pt - pb) / 2

        fill_box = RoundedRectangle(
            width=box_w,
            height=box_h,
            corner_radius=corner_radius,
            stroke_width=0,
            fill_color=fill_color,
            fill_opacity=fill_opacity,
        )
        fill_box.move_to([box_center_x, box_center_y, 0])
        outline_base = RoundedRectangle(
            width=box_w,
            height=box_h,
            corner_radius=corner_radius,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_opacity=0,
        )
        outline_base.move_to([box_center_x, box_center_y, 0])
        outline = DashedVMobject(outline_base, num_dashes=dash_count) if dashed else outline_base
        outline.set_stroke(stroke_color, width=stroke_width)

        if label_mob and label_mode == "overlay":
            self._place_overlay_label(label_mob, outline_base, label_position, label_placement, label_inset)
            self.add(fill_box, outline, content, label_mob)
        else:
            self.add(fill_box, outline, content)
        self.box = outline
        self.fill_box = fill_box
        self.content = content
        self.target = target
        self.label = label_mob

        # Compute true layout extent — for outside overlay labels the box
        # boundary does not cover the label, so report the union extent.
        self.layout_width = self.width
        self.layout_height = self.height
        if label_mob and label_mode == "overlay" and label_placement == "outside":
            self.layout_width = (
                max(self.get_right()[0], label_mob.get_right()[0])
                - min(self.get_left()[0], label_mob.get_left()[0])
            )
            self.layout_height = (
                max(self.get_top()[1], label_mob.get_top()[1])
                - min(self.get_bottom()[1], label_mob.get_bottom()[1])
            )

    @staticmethod
    def _build_header_content(
        label_mob: Mobject,
        target: Mobject,
        label_position: str,
        label_gap: float,
    ) -> VGroup:
        """Position label relative to target; return VGroup wrapping both.

        Uses ``next_to`` so the target's internal layout is never disturbed.
        Corner variants align the label to the target's left or right edge
        after the vertical placement.
        """
        if label_position.startswith("top"):
            label_mob.next_to(target, UP, buff=label_gap)
        elif label_position.startswith("bottom"):
            label_mob.next_to(target, DOWN, buff=label_gap)
        elif label_position == "left":
            label_mob.next_to(target, LEFT, buff=label_gap)
        elif label_position == "right":
            label_mob.next_to(target, RIGHT, buff=label_gap)
        else:
            raise ValueError(f"Unknown header label_position: {label_position}")

        if label_position in ("top_left", "bottom_left"):
            label_mob.align_to(target, LEFT)
        elif label_position in ("top_right", "bottom_right"):
            label_mob.align_to(target, RIGHT)
        # top, bottom, left, right: keep default centering from next_to

        return VGroup(label_mob, target)

    @staticmethod
    def _place_overlay_label(
        label_mob: Mobject,
        box: Mobject,
        label_position: str,
        label_placement: str,
        inset: float,
    ) -> None:
        """Place overlay label at a box corner.  *inset* is edge-to-edge distance."""
        vertical, horizontal = label_position.split("_")
        if label_placement == "inside":
            y = (
                box.get_top()[1] - inset - label_mob.height / 2
                if vertical == "top"
                else box.get_bottom()[1] + inset + label_mob.height / 2
            )
        else:  # outside
            y = (
                box.get_top()[1] + inset + label_mob.height / 2
                if vertical == "top"
                else box.get_bottom()[1] - inset - label_mob.height / 2
            )
        if horizontal == "left":
            x = box.get_left()[0] + inset + label_mob.width / 2
        elif horizontal == "right":
            x = box.get_right()[0] - inset - label_mob.width / 2
        elif horizontal == "center":
            x = box.get_center()[0]
        else:
            raise ValueError(f"Unknown overlay horizontal position: {horizontal}")
        label_mob.move_to([x, y, 0])


class FlowChart(VGroup):
    """A reusable snake-wrapped flowchart for Manim diagrams.

    Children can be `FlowNode`, `FlowChart`, or any Mobject. Logical order is the
    order passed to the constructor. Layout wraps by `max_nodes_per_line` and
    alternates visual direction per row/column, producing a serpentine path.
    """

    def __init__(
        self,
        items: Sequence[Mobject | FlowNodeSpec],
        title: str | None = None,
        max_nodes_per_line: int = 4,
        orientation: str = "horizontal",
        node_gap: float = 0.55,
        row_gap: float = 0.78,
        gap_overrides: dict[int, float] | None = None,
        padding: float = 0.35,
        title_gap: float = 0.22,
        title_size: int = 24,
        font: str = FONT,
        show_container: bool = False,
        container_fill: str = GROUP_FILL,
        container_stroke: str = GROUP_STROKE,
        container_fill_opacity: float = 0.45,
        container_stroke_width: float = 2.0,
        container_dashed: bool = False,
        arrow_color: str = ARROW_COLOR,
        arrow_stroke_width: float = 2.2,
        arrow_tip_length: float = 0.12,
        node_title_size: int = 25,
        node_body_size: int = 20,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        if max_nodes_per_line < 1:
            raise ValueError("max_nodes_per_line must be >= 1")
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("orientation must be 'horizontal' or 'vertical'")
        self.title_text = title
        self.max_nodes_per_line = max_nodes_per_line
        self.orientation = orientation
        self.node_gap = node_gap
        self.row_gap = row_gap
        self.gap_overrides = gap_overrides or {}
        self.padding = padding
        self.title_gap = title_gap
        self.font = font
        self.show_container = show_container
        self.arrow_color = arrow_color
        self.arrow_stroke_width = arrow_stroke_width
        self.arrow_tip_length = arrow_tip_length
        self.node_title_size = node_title_size
        self.node_body_size = node_body_size

        self.items = VGroup(*[self._coerce_item(item) for item in items])
        self._logical_items = list(self.items)
        self.arrows = VGroup()
        self.container: RoundedRectangle | None = None
        self.header: Text | None = None

        self._layout_items()
        self._create_arrows()
        parts: list[Mobject] = []
        if title:
            self.header = mixed_text(title, font_size=title_size, weight=BOLD)
            self.header.next_to(self.items, UP, buff=title_gap)
            parts.append(self.header)
        parts.extend([self.items, self.arrows])
        content = VGroup(*parts)
        if show_container:
            group_box = LabeledBox(
                content,
                padding=padding,
                fill_color=container_fill,
                fill_opacity=container_fill_opacity,
                stroke_color=container_stroke,
                stroke_width=container_stroke_width,
                dashed=container_dashed,
            )
            self.container = group_box.box
            self.add(group_box)
        else:
            self.add(*parts)
        self.layout_width = self.width
        self.layout_height = self.height

    def _coerce_item(self, item: Mobject | FlowNodeSpec) -> Mobject:
        if isinstance(item, FlowNodeSpec):
            return FlowNode(
                item.title,
                item.body,
                item.kind,
                width=item.width or default_width_for_title(item.title),
                height=item.height or 1.05,
                title_size=self.node_title_size,
                body_size=self.node_body_size,
                shrink_to_fit=False,
                body_rise_em=item.body_rise_em,
            )
        return item

    def _layout_items(self) -> None:
        if self.orientation == "vertical":
            self._layout_items_vertical()
        else:
            self._layout_items_horizontal()

    def _get_gap_after(self, logical_index: int) -> float:
        """Return the gap after the logical item at *logical_index*."""
        return self.gap_overrides.get(logical_index, self.node_gap)

    def _layout_items_horizontal(self) -> None:
        rows = chunked(self._logical_items, self.max_nodes_per_line)
        row_groups: list[VGroup] = []
        for row_index, logical_row in enumerate(rows):
            visual_row = list(logical_row)
            if row_index % 2 == 1:
                visual_row = list(reversed(visual_row))
            for i, mob in enumerate(visual_row):
                if i == 0:
                    mob.move_to(ORIGIN)
                else:
                    idx_prev = self._logical_items.index(visual_row[i - 1])
                    idx_curr = self._logical_items.index(visual_row[i])
                    gap = self._get_gap_after(min(idx_prev, idx_curr))
                    mob.next_to(visual_row[i - 1], RIGHT, buff=gap)
            row_group = VGroup(*visual_row)
            row_groups.append(row_group)

        for row_index, row_group in enumerate(row_groups):
            if row_index == 0:
                row_group.move_to(ORIGIN)
            else:
                prev = row_groups[row_index - 1]
                y = prev.get_bottom()[1] - self.row_gap - row_group.height / 2
                row_group.move_to([prev.get_center()[0], y, 0])
                self._align_wrap_endpoint(rows[row_index - 1], rows[row_index])

        self.items.move_to(ORIGIN)

    def _layout_items_vertical(self) -> None:
        cols = chunked(self._logical_items, self.max_nodes_per_line)
        col_groups: list[VGroup] = []
        for col_index, logical_col in enumerate(cols):
            visual_col = list(logical_col)
            if col_index % 2 == 1:
                visual_col = list(reversed(visual_col))
            for i, mob in enumerate(visual_col):
                if i == 0:
                    mob.move_to(ORIGIN)
                else:
                    idx_prev = self._logical_items.index(visual_col[i - 1])
                    idx_curr = self._logical_items.index(visual_col[i])
                    gap = self._get_gap_after(min(idx_prev, idx_curr))
                    mob.next_to(visual_col[i - 1], DOWN, buff=gap)
            col_group = VGroup(*visual_col)
            col_groups.append(col_group)

        for col_index, col_group in enumerate(col_groups):
            if col_index == 0:
                col_group.move_to(ORIGIN)
            else:
                prev = col_groups[col_index - 1]
                x = prev.get_right()[0] + self.row_gap + col_group.width / 2
                col_group.move_to([x, prev.get_center()[1], 0])
                self._align_vertical_wrap_endpoint(cols[col_index - 1], cols[col_index])

        self.items.move_to(ORIGIN)

    @staticmethod
    def _align_wrap_endpoint(prev_logical_row: Sequence[Mobject], curr_logical_row: Sequence[Mobject]) -> None:
        if not prev_logical_row or not curr_logical_row:
            return
        prev_end = prev_logical_row[-1]
        curr_start = curr_logical_row[0]
        delta_x = prev_end.get_center()[0] - curr_start.get_center()[0]
        VGroup(*curr_logical_row).shift(RIGHT * delta_x)

    @staticmethod
    def _align_vertical_wrap_endpoint(prev_logical_col: Sequence[Mobject], curr_logical_col: Sequence[Mobject]) -> None:
        if not prev_logical_col or not curr_logical_col:
            return
        prev_end = prev_logical_col[-1]
        curr_start = curr_logical_col[0]
        delta_y = prev_end.get_center()[1] - curr_start.get_center()[1]
        VGroup(*curr_logical_col).shift(UP * delta_y)

    def _create_arrows(self) -> None:
        self.arrows = VGroup()
        for start, end in zip(self._logical_items, self._logical_items[1:]):
            self.arrows.add(self._arrow_between(start, end))

    def _arrow_between(self, start: Mobject, end: Mobject) -> Arrow:
        dx = end.get_center()[0] - start.get_center()[0]
        dy = end.get_center()[1] - start.get_center()[1]
        if abs(dx) >= abs(dy):
            if dx >= 0:
                a, b = start.get_right(), end.get_left()
            else:
                a, b = start.get_left(), end.get_right()
        else:
            if dy >= 0:
                a, b = start.get_top(), end.get_bottom()
            else:
                a, b = start.get_bottom(), end.get_top()
        return Arrow(
            a,
            b,
            buff=0.10,
            color=self.arrow_color,
            stroke_width=self.arrow_stroke_width,
            tip_length=self.arrow_tip_length,
            max_tip_length_to_length_ratio=1.0,
            max_stroke_width_to_length_ratio=100,
        )


class ExampleFlow(Scene):
    def construct(self) -> None:
        self.camera.background_color = WHITE

        title = mixed_text("example snake flow", font_size=30)

        flow = FlowChart(
            [
                FlowNodeSpec("Load Input", "batch -> tokens", "io", width=3.45, height=1.15),
                FlowNodeSpec("Encode", "tokens -> hidden", "model", width=3.15, height=1.15),
                FlowNodeSpec("Forward/Backward", "bf16 compute", "model", width=3.75, height=1.15),
                FlowNodeSpec("Sync State", "rank local -> global", "sync", width=3.70, height=1.15),
                FlowNodeSpec("Update", "grad -> param", "model", width=2.95, height=1.15),
                FlowNodeSpec("Log Metrics", "loss / throughput", "io", width=3.55, height=1.15),
            ],
            title="simple linear flow with snake wrap",
            max_nodes_per_line=4,
            node_gap=0.55,
            row_gap=0.74,
            show_container=True,
        )

        legend = VGroup(
            FlowNode("I/O", "data/log", "io", width=1.35, height=0.95, title_size=18, body_size=13),
            FlowNode("Model", "compute", "model", width=1.65, height=0.95, title_size=18, body_size=13),
            FlowNode("Sync", "exchange", "sync", width=1.65, height=0.95, title_size=18, body_size=13),
        ).arrange(RIGHT, buff=0.25)
        legend_note = LabeledBox(
            legend,
            padding=0.18,
            label_size=14,
            fill_color="#ffffff",
            fill_opacity=0.0,
            stroke_color=GROUP_STROKE,
            stroke_width=1.4,
            dashed=True,
        )

        main = VGroup(title, flow, legend_note).arrange(DOWN, buff=0.34)
        fit_to_frame(main, margin=0.75)
        self.add(main)


def style_for_kind(kind: str) -> tuple[str, str]:
    if kind in {"io", "comm", "input", "output"}:
        return COMM_FILL, COMM_STROKE
    if kind in {"group", "container"}:
        return GROUP_FILL, GROUP_STROKE
    if kind in {"sync", "state", "control"}:
        return SYNC_FILL, SYNC_STROKE
    return COMPUTE_FILL, COMPUTE_STROKE


def default_width_for_title(title: str) -> float:
    if "Forward" in title or "Backward" in title:
        return 3.95
    if len(title) >= 22:
        return 3.35
    if len(title) >= 16:
        return 3.05
    return 2.75


def chunked(items: Sequence[Mobject], size: int) -> list[list[Mobject]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def fit_to_frame(group: Mobject, margin: float = 1.0) -> None:
    max_w = config.frame_width - margin
    max_h = config.frame_height - margin
    if group.width > max_w:
        group.scale_to_fit_width(max_w)
    if group.height > max_h:
        group.scale_to_fit_height(max_h)
    group.move_to(ORIGIN)


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    script = Path(__file__).resolve()
    SCENE_CLASS = "ExampleFlow"

    venv_python = here / ".venv" / "bin" / "python"
    if not venv_python.exists():
        raise SystemExit(f"Missing diagram-local venv: {venv_python}. Create it and install manim there.")
    manim_python = str(venv_python)

    subprocess.run(
        [manim_python, "-m", "manim", "-sqk", "--media_dir", str(here / "media"), str(script), SCENE_CLASS],
        cwd=here,
        check=True,
    )

    png_dir = here / "media" / "images" / Path(__file__).stem
    pngs = sorted(png_dir.glob(f"{SCENE_CLASS}*.png"))
    if pngs:
        dst = here / f"{SCENE_CLASS}.png"
        shutil.copy2(pngs[-1], dst)
        print(f"Saved: {dst}")
