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
    fallback_python = Path("/opt/tiger/mode_omni_recipes/diagrams/mp_policy_flow/.venv/bin/python")
    if __name__ == "__main__" and fallback_python.exists() and Path(sys.executable) != fallback_python:
        os.execv(str(fallback_python), [str(fallback_python), str(Path(__file__).resolve())])
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
) -> MarkupText:
    """Render one Pango markup text object with CJK and Latin font spans."""
    markup = mixed_text_markup(text, latin_rise_em=latin_rise_em, font_size=font_size)
    return MarkupText(
        markup,
        font=LATIN_FONT,
        font_size=font_size,
        weight=weight,
        color=color,
        disable_ligatures=True,
    )


def mixed_text_markup(text: str, latin_rise_em: float = 0.0, font_size: float = 20) -> str:
    has_cjk = any(kind == "cjk" for kind, _ in split_mixed_text_runs(text))
    effective_rise = latin_rise_em if has_cjk else 0.0
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
        shrink_to_fit: bool = True,
    ) -> None:
        super().__init__()
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
        title_mob = mixed_text(title, font_size=title_size, weight=BOLD)
        body_mob = mixed_text(body, font_size=body_size, latin_rise_em=LATIN_BODY_RISE_EM)
        text_group = VGroup(title_mob, body_mob).arrange(DOWN, buff=0.10)
        max_w = width - padding * 2
        max_h = height - padding * 2
        if text_group.width > max_w:
            text_group.scale_to_fit_width(max_w)
        if text_group.height > max_h:
            text_group.scale_to_fit_height(max_h)
        text_group.move_to(rect.get_center())
        self.add(rect, text_group)
        self.rect = rect
        self.layout_width = width
        self.layout_height = height
        self.kind = kind


class FlowChart(VGroup):
    """A reusable snake-wrapped flowchart for Manim diagrams.

    Children can be `FlowNode`, `FlowChart`, or any Mobject. Logical order is the
    order passed to the constructor. Layout wraps by `max_nodes_per_line` and
    alternates visual direction per row, producing a serpentine path.
    """

    def __init__(
        self,
        items: Sequence[Mobject | FlowNodeSpec],
        title: str | None = None,
        max_nodes_per_line: int = 4,
        node_gap: float = 0.55,
        row_gap: float = 0.78,
        padding: float = 0.35,
        title_gap: float = 0.22,
        title_size: int = 24,
        font: str = FONT,
        show_container: bool = False,
        container_fill: str = GROUP_FILL,
        container_stroke: str = GROUP_STROKE,
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
        self.title_text = title
        self.max_nodes_per_line = max_nodes_per_line
        self.node_gap = node_gap
        self.row_gap = row_gap
        self.padding = padding
        self.title_gap = title_gap
        self.font = font
        self.show_container = show_container
        self.arrow_color = arrow_color
        self.arrow_stroke_width = arrow_stroke_width
        self.arrow_tip_length = arrow_tip_length
        self.text_fit_scale = self._chart_text_fit_scale(items, node_title_size, node_body_size, font)
        self.node_title_size = node_title_size * self.text_fit_scale
        self.node_body_size = node_body_size * self.text_fit_scale

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
            box = RoundedRectangle(
                width=content.width + padding * 2,
                height=content.height + padding * 2,
                corner_radius=0.16,
                stroke_color=container_stroke,
                stroke_width=2.0,
                fill_color=container_fill,
                fill_opacity=0.45,
            )
            box.move_to(content.get_center())
            self.container = box
            self.add(box, *parts)
        else:
            self.add(*parts)
        self.layout_width = self.width
        self.layout_height = self.height

    @staticmethod
    def _chart_text_fit_scale(
        items: Sequence[Mobject | FlowNodeSpec],
        title_size: int,
        body_size: int,
        font: str,
        padding: float = 0.18,
    ) -> float:
        """Return one chart-wide text scale so every generated node uses equal sizes."""
        scale = 1.0
        for item in items:
            if not isinstance(item, FlowNodeSpec):
                continue
            width = item.width or default_width_for_title(item.title)
            height = item.height or 1.05
            title_mob = mixed_text(item.title, font_size=title_size, weight=BOLD)
            body_mob = mixed_text(item.body, font_size=body_size, latin_rise_em=LATIN_BODY_RISE_EM)
            text_group = VGroup(title_mob, body_mob).arrange(DOWN, buff=0.10)
            max_w = width - padding * 2
            max_h = height - padding * 2
            if text_group.width > 0:
                scale = min(scale, max_w / text_group.width)
            if text_group.height > 0:
                scale = min(scale, max_h / text_group.height)
        return max(scale, 0.1)

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
            )
        return item

    def _layout_items(self) -> None:
        rows = chunked(self._logical_items, self.max_nodes_per_line)
        row_groups: list[VGroup] = []
        for row_index, logical_row in enumerate(rows):
            visual_row = list(logical_row)
            if row_index % 2 == 1:
                visual_row = list(reversed(visual_row))
            row_group = VGroup(*visual_row).arrange(RIGHT, buff=self.node_gap)
            row_groups.append(row_group)

        for row_index, row_group in enumerate(row_groups):
            if row_index == 0:
                row_group.move_to(ORIGIN)
            else:
                prev = row_groups[row_index - 1]
                y = prev.get_bottom()[1] - self.row_gap - row_group.height / 2
                row_group.move_to([prev.get_center()[0], y, 0])
                self._align_wrap_endpoint(rows[row_index - 1], rows[row_index])

        # Center the whole chart after endpoint alignment. Endpoint alignment keeps
        # row-transition arrows vertical; final centering preserves that relation.
        self.items.move_to(ORIGIN)

    @staticmethod
    def _align_wrap_endpoint(prev_logical_row: Sequence[Mobject], curr_logical_row: Sequence[Mobject]) -> None:
        if not prev_logical_row or not curr_logical_row:
            return
        prev_end = prev_logical_row[-1]
        curr_start = curr_logical_row[0]
        delta_x = prev_end.get_center()[0] - curr_start.get_center()[0]
        VGroup(*curr_logical_row).shift(RIGHT * delta_x)

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
                FlowNodeSpec("Load Input (I/O)", "batch -> tokens", "io", width=3.05),
                FlowNodeSpec("Encode (Model)", "tokens -> hidden", "model", width=2.75),
                FlowNodeSpec("Forward / Backward (Train)", "使用 bf16 计算", "model", width=3.95),
                FlowNodeSpec("Sync State (Cluster)", "rank local -> global", "sync", width=3.05),
                FlowNodeSpec("Update (Optimizer)", "grad -> param", "model", width=2.85),
                FlowNodeSpec("Log Metrics (I/O)", "loss / throughput", "io", width=3.05),
            ],
            title="simple linear flow with snake wrap",
            max_nodes_per_line=4,
            node_gap=0.55,
            row_gap=0.78,
            show_container=True,
        )

        legend = VGroup(
            FlowNode("I/O", "data/log", "io", width=1.35, height=0.58, title_size=18, body_size=13),
            FlowNode("Model", "compute", "model", width=1.65, height=0.58, title_size=18, body_size=13),
            FlowNode("Sync", "exchange", "sync", width=1.65, height=0.58, title_size=18, body_size=13),
        ).arrange(RIGHT, buff=0.25)

        main = VGroup(title, flow, legend).arrange(DOWN, buff=0.34)
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
    fallback_python = Path("/opt/tiger/mode_omni_recipes/diagrams/mp_policy_flow/.venv/bin/python")
    if venv_python.exists():
        manim_python = str(venv_python)
    elif fallback_python.exists():
        manim_python = str(fallback_python)
    else:
        manim_python = sys.executable

    subprocess.run(
        [manim_python, "-m", "manim", "-sql", "--media_dir", str(here / "media"), str(script), SCENE_CLASS],
        cwd=here,
        check=True,
    )

    png_dir = here / "media" / "images" / Path(__file__).stem
    pngs = sorted(png_dir.glob(f"{SCENE_CLASS}*.png"))
    if pngs:
        dst = here / f"{SCENE_CLASS}.png"
        shutil.copy2(pngs[-1], dst)
        print(f"Saved: {dst}")
