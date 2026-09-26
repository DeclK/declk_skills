"""
Connector demo — Polyline / BoxConnector 的 5 种连接场景。

运行: .venv/bin/python demo_connector.py
所有连接器继承统一默认（stroke 4.0 / 起止留白 0.12 / 头部 0.18），
仅演示场景差异参数（颜色、虚线、绕行、偏移、圆角）。
"""
from __future__ import annotations
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from connector import BoxConnector  # noqa: E402
from manim import *  # noqa: E402

config.background_color = "#FFFFFF"


def make_box(label, edge="#1D4ED8", fill="#DBEAFE"):
    t = Text(label, font_size=22, color="#111827")
    box = RoundedRectangle(width=1.8, height=0.8, corner_radius=0.2, color=edge)
    box.set_fill(fill, opacity=1.0)
    return VGroup(box, t)


def make_title(text, x, y):
    return Text(text, font_size=20, color="#374151").move_to([x, y, 0])


class ConnectorDemo(Scene):
    def construct(self):
        group = VGroup()
        y = 3.2

        # 1. 水平直线（相邻直连）
        a = make_box("A").move_to([-2.6, y, 0])
        b = make_box("B").move_to([0.6, y, 0])
        c1 = BoxConnector(a, b, color="#64748B")
        group.add(make_title("1. 水平直线（相邻直连）", -6.1, y), a, b, c1)
        y -= 1.5

        # 2. 垂直直线
        a = make_box("A").move_to([0.0, y + 0.9, 0])
        b = make_box("B").move_to([0.0, y - 0.9, 0])
        c2 = BoxConnector(a, b, color="#64748B")
        group.add(make_title("2. 垂直直线", -6.1, y), a, b, c2)
        y -= 2.7

        # 3. 同排绕行（D2 -> D0，中间 D1 阻挡）— K 场景复刻
        # 虚线圆角自动 clamp 到 dash 节奏；箭头停在 D₀ 边缘外（tip_gap）
        d0 = make_box("D₀").move_to([-3.2, y, 0])
        mid = make_box("D₁").move_to([-0.5, y, 0])
        d2 = make_box("D₂").move_to([2.2, y, 0])
        c3 = BoxConnector(d2, d0, obstacles=[mid], dashed=True,
                          color="#7C3AED", elbow_offset=0.7)
        group.add(make_title("3. 同排绕行（有阻挡，虚线）", -6.1, y), d0, mid, d2, c3)
        y -= 1.6

        # 4. 对角斜线直连
        a = make_box("A").move_to([-2.8, y, 0])
        b = make_box("B").move_to([1.8, y - 1.5, 0])
        c4 = BoxConnector(a, b, color="#64748B")
        group.add(make_title("4. 对角斜线直连", -6.1, y), a, b, c4)
        y -= 2.5

        # 5. 圆角 vs 直角（同一条绕行路径）
        m1 = make_box("M").move_to([-0.6, y, 0])
        a = make_box("A").move_to([-3.2, y, 0])
        b = make_box("B").move_to([2.0, y, 0])
        c_sharp = BoxConnector(a, b, obstacles=[m1], corner_radius=0.0,
                               color="#64748B", elbow_offset=0.7)
        m2 = make_box("M").move_to([6.1, y, 0])
        a2 = make_box("A").move_to([4.0, y, 0])
        b2 = make_box("B").move_to([8.2, y, 0])
        c_round = BoxConnector(a2, b2, obstacles=[m2], corner_radius=0.3,
                               color="#64748B", elbow_offset=0.7)
        group.add(make_title("5. 直角（左）vs 圆角（右）", -6.1, y),
                  m1, a, b, c_sharp, m2, a2, b2, c_round)

        # 适配帧
        margin = 1.0
        if group.width > config.frame_width - margin:
            group.scale_to_fit_width(config.frame_width - margin)
        if group.height > config.frame_height - margin:
            group.scale_to_fit_height(config.frame_height - margin)
        group.move_to(ORIGIN)
        self.add(group)


if __name__ == "__main__":
    import shutil
    import subprocess
    from pathlib import Path

    here = Path(__file__).resolve().parent
    script = Path(__file__).resolve()
    SCENE_CLASS = "ConnectorDemo"
    MANIM_PYTHON = str(here.parent / "dspark_2step_schedule" / ".venv" / "bin" / "python")

    subprocess.run(
        [MANIM_PYTHON, "-m", "manim", "-sqh", str(script), SCENE_CLASS],
        cwd=here, check=True,
    )
    png_dir = here / "media" / "images" / Path(__file__).stem
    pngs = sorted(png_dir.glob(f"{SCENE_CLASS}*.png"))
    if pngs:
        dst = here / f"{SCENE_CLASS}.png"
        shutil.copy2(pngs[-1], dst)
        print(f"Saved: {dst}")
