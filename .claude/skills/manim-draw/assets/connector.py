"""
通用折线 + 方框连接器（ManimCE 补充工具）。

解决 manim 两个痛点：
1. 画折线 —— Polyline：多段直线 + 圆角拐角 + 虚线 + 终点箭头
2. 用折线连接两个方框 —— BoxConnector：锚点自动贴框边缘，
   无阻挡时两点直连（任意方向），有阻挡时同向 elbow 绕行。

用法示例：
    conn = BoxConnector(box_a, box_b, obstacles=[box_c], dashed=True,
                        arrow=True, color="#7C3AED")
    self.add(conn)
"""
from __future__ import annotations

import numpy as np
from manim import (
    VGroup,
    VMobject,
    CubicBezier,
    DashedLine,
    Polygon,
    WHITE,
    UP, DOWN, LEFT, RIGHT,
)


# ─────────────────────────────────────────────────────────────────────────────
# 几何工具
# ─────────────────────────────────────────────────────────────────────────────

def _unit(a, b):
    """a -> b 的单位方向向量（保持输入维度）。"""
    d = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    n = np.linalg.norm(d)
    return d / n if n > 1e-9 else np.zeros_like(d)


def _seg_rect_intersect(p, q, rect) -> bool:
    """线段 p-q 与轴对齐矩形 rect = (x0, y0, x1, y1) 是否相交。"""
    x0, y0, x1, y1 = rect
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    # 端点落在矩形内
    for pt in (p, q):
        if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1:
            return True
    # 与四条边相交
    def cross(u, v):
        return u[0] * v[1] - u[1] * v[0]

    def seg_intersect(a, b, c, d) -> bool:
        ab, cd = b - a, d - c
        denom = cross(ab, cd)
        if abs(denom) < 1e-9:
            return False
        t = cross(c - a, cd) / denom
        u = cross(c - a, ab) / denom
        return 0 <= t <= 1 and 0 <= u <= 1

    corners = np.array([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], dtype=float)
    for i in range(4):
        if seg_intersect(p, q, corners[i], corners[(i + 1) % 4]):
            return True
    return False


def _bbox(mobject: Mobject):
    """任意 Mobject 的轴对齐包围盒 (x0, y0, x1, y1)。"""
    return (
        mobject.get_left()[0], mobject.get_bottom()[1],
        mobject.get_right()[0], mobject.get_top()[1],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Polyline — 通用折线
# ─────────────────────────────────────────────────────────────────────────────

class Polyline(VGroup):
    """多段折线：直线段 + 可选圆角拐角 + 可选虚线 + 可选终点箭头。

    参数:
        points: 折线顶点 [(x0, y0), (x1, y1), ...]，至少 2 点
        corner_radius: 拐角圆角半径（默认 0.25；0 为直角）
        dashed / dash_length: 直线段虚线（拐角曲线段因 DashedLine 只支持
            直线，保持实线——拐角很短，视觉无碍）
            实线时整条路径合成一个 VMobject 一次描边：拐角由 cairo join
            填充、直线与圆角共用锚点，无抗锯齿接缝/缺口
        arrow / tip_length: 终点箭头（方向沿最后一段；箭杆自动收在三角形
            底边，尖端仍精确落在终点——杆若伸到尖端会因尖端宽度趋零而露出方头）
    """

    def __init__(
        self,
        points,
        stroke_width: float = 4.0,
        color: str = WHITE,
        stroke_opacity: float = 1.0,
        dashed: bool = False,
        dash_length: float = 0.12,
        arrow: bool = False,
        tip_length: float = 0.18,
        tip_color: str | None = None,
        corner_radius: float = 0.25,
        **kwargs,
    ):
        super().__init__(**kwargs)
        pts = np.asarray(points, dtype=float)
        if pts.ndim == 1:
            pts = pts.reshape(1, -1)
        if pts.shape[1] == 2:                     # 补 z 维（manim 内部用 3D 点）
            pts = np.column_stack([pts, np.zeros(len(pts))])
        pts = pts[:, :3]
        if len(pts) < 2:
            raise ValueError("Polyline needs at least 2 points")

        # 圆角半径 clamp 到相邻段长的一半，避免圆弧越过段端点
        seg_lens = [np.linalg.norm(pts[i + 1] - pts[i]) for i in range(len(pts) - 1)]
        max_r = min(seg_lens) / 2
        r = min(max(0.0, corner_radius), max_r)
        if dashed:
            # 拐角是实线 CubicBezier（DashedLine 只支持直线），圆角过大时
            # 会出现"一长段实线顶着短虚线"的比例失调。
            # clamp 使弧长 (π/2·r) 不超过一个 dash 周期（dash+gap）。
            r = min(r, dash_length * 2 / np.pi)

        dirs = [_unit(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]

        # 构造路径：直线段与拐角圆弧（CubicBezier）交替
        segs: list[tuple] = []
        prev = pts[0]
        for i in range(1, len(pts) - 1):
            d_in = dirs[i - 1]      # 进入 pts[i] 的方向
            d_out = dirs[i]         # 离开 pts[i] 的方向
            arc_start = pts[i] - d_in * r
            arc_end = pts[i] + d_out * r
            segs.append(("line", prev, arc_start))
            if r > 0:
                k = r * 0.5523      # 四分之一圆弧的 Bezier 系数
                segs.append(("curve", arc_start,
                             arc_start + d_in * k,
                             arc_end - d_out * k,
                             arc_end))
            else:
                segs.append(("line", arc_start, arc_end))
            prev = arc_end

        end = pts[-1]
        if arrow:
            # 箭杆收在三角形底边：尖端处三角形窄于杆宽，杆若伸到尖端会露出方头
            last_len = np.linalg.norm(pts[-1] - prev)
            end = pts[-1] - dirs[-1] * min(tip_length, 0.8 * last_len)
        segs.append(("line", prev, end))

        if dashed:
            # 虚线：逐段渲染——直线段 DashedLine（DashedLine 不支持曲线），
            # 拐角圆弧保持实线 CubicBezier
            for seg in segs:
                if seg[0] == "line":
                    _, a, b = seg
                    if np.linalg.norm(b - a) < 1e-9:
                        continue
                    self.add(DashedLine(a, b, dash_length=dash_length,
                                        color=color, stroke_width=stroke_width,
                                        stroke_opacity=stroke_opacity))
                else:
                    _, a, c1, c2, b = seg
                    self.add(CubicBezier(a, c1, c2, b, color=color,
                                         stroke_width=stroke_width,
                                         stroke_opacity=stroke_opacity))
        else:
            # 实线：整条路径合成单个 VMobject 一次描边——拐角由 cairo 的
            # join 填充、直线与圆角衔接处共用锚点，无抗锯齿接缝/缺口
            pts_list = []
            for seg in segs:
                if seg[0] == "line":
                    _, a, b = seg
                    if np.linalg.norm(b - a) < 1e-9:
                        continue
                    pts_list.extend([a, a, b, b])     # 直线 = 退化三次贝塞尔
                else:
                    _, a, c1, c2, b = seg
                    pts_list.extend([a, c1, c2, b])
            path = VMobject(color=color, stroke_width=stroke_width,
                            stroke_opacity=stroke_opacity)
            path.set_points(np.asarray(pts_list))
            self.add(path)

        # 终点箭头：尖端落在最后一个顶点，方向沿最后一段
        if arrow:
            d = dirs[-1]
            tip = Polygon(
                np.array([0.0, 0.0, 0.0]), np.array([-1.0, 0.35, 0.0]),
                np.array([-1.0, -0.35, 0.0]),
                fill_color=tip_color or color, fill_opacity=1.0,
                stroke_width=0.0,
            )
            # 尖端朝 +x，旋转到 d 方向
            tip.scale(tip_length).rotate(np.arctan2(d[1], d[0]))
            # move_to 按包围盒中心对齐——尖端顶点会越过端点 0.5*tip_length
            # 深入目标，需再偏移让尖端顶点精确落在端点
            tip.move_to(pts[-1])
            tip.shift(pts[-1] - tip.get_anchors()[0])
            self.add(tip)


# ─────────────────────────────────────────────────────────────────────────────
# BoxConnector — 两方框间的折线连接器
# ─────────────────────────────────────────────────────────────────────────────

class BoxConnector(Polyline):
    """两方框之间的折线连接。

    参数:
        source / target: 任意 Mobject（用 get_center/get_top 等定位边缘）
        source_side / target_side: "left" / "right" / "top" / "bottom"；
            "auto"（默认）按相对方位推导，直线被挡时自动改走 top-top 绕行
        source_offset / target_offset: 锚点沿该边方向的偏移
            （top/bottom 沿 x 偏移，left/right 沿 y 偏移）
        obstacles: 阻挡框列表；锚点连线穿过任一框时走 elbow 绕行
        elbow_offset: 绕行高度/宽度的额外偏移（相对较高/较宽的锚点）
        arrow: 默认 True（连接器语义），箭头尖端停在目标框边缘外
        tip_gap: 箭头尖端与目标框边缘的留白（仅 arrow=True 时生效）
        source_gap: 起点沿出方向回缩的留白（默认 0.12，与 tip_gap 对称：
            起止两端都不贴框边缘，避免视觉上"侵入"框内）
        **kwargs: 透传给 Polyline（dashed / color / stroke_width / corner_radius ...）
    """

    def __init__(
        self,
        source: Mobject,
        target: Mobject,
        source_side: str = "auto",
        target_side: str = "auto",
        source_offset: float = 0.0,
        target_offset: float = 0.0,
        obstacles: list[Mobject] | None = None,
        elbow_offset: float = 0.4,
        arrow: bool = True,
        tip_gap: float = 0.12,
        source_gap: float = 0.12,
        **kwargs,
    ):
        self.source = source
        self.target = target
        self.obstacles = obstacles or []
        self.arrow = arrow
        self.tip_gap = tip_gap
        self.source_gap = source_gap

        if source_side == "auto" or target_side == "auto":
            sc, tc = source.get_center(), target.get_center()
            dx, dy = tc[0] - sc[0], tc[1] - sc[1]
            if abs(dy) < abs(dx):      # 水平为主
                s_side = "right" if dx > 0 else "left"
                t_side = "left" if dx > 0 else "right"
            else:                      # 垂直为主
                s_side = "top" if dy > 0 else "bottom"
                t_side = "bottom" if dy > 0 else "top"
        else:
            s_side, t_side = source_side, target_side

        s_anchor, s_dir = self._anchor(source, s_side, source_offset)
        t_anchor, t_dir = self._anchor(target, t_side, target_offset)

        # 直线被 obstacle 挡住 → 改走 top-top 绕行（auto 或显式都统一处理）
        if self._blocked(s_anchor, t_anchor):
            s_anchor, s_dir = self._anchor(source, "top", source_offset)
            t_anchor, t_dir = self._anchor(target, "top", target_offset)

        self.source_anchor = s_anchor
        self.target_anchor = t_anchor

        points = self._route(s_anchor, s_dir, t_anchor, t_dir, elbow_offset)
        super().__init__(points, arrow=arrow, **kwargs)

    # -- 边缘锚点 ----------------------------------------------------------

    @staticmethod
    def _anchor(box: Mobject, side: str, offset: float):
        """返回 (锚点 [x, y], 离开锚点的单位方向)。"""
        if side == "top":
            p = box.get_top()
            return [p[0] + offset, p[1]], np.array(UP[:2])
        if side == "bottom":
            p = box.get_bottom()
            return [p[0] + offset, p[1]], np.array(DOWN[:2])
        if side == "left":
            p = box.get_left()
            return [p[0], p[1] + offset], np.array(LEFT[:2])
        if side == "right":
            p = box.get_right()
            return [p[0], p[1] + offset], np.array(RIGHT[:2])
        raise ValueError(f"unknown side: {side}")

    def _blocked(self, a, b) -> bool:
        """锚点连线 a-b 是否穿过任一 obstacle。"""
        for ob in self.obstacles:
            if _seg_rect_intersect(a, b, _bbox(ob)):
                return True
        return False

    # -- 路径规划 ----------------------------------------------------------

    def _route(self, s_anchor, s_dir, t_anchor, t_dir, elbow_offset):
        """无阻挡 → 两点直连；有阻挡 → 同向 elbow 绕行。

        有箭头时目标端沿最后一段方向回缩 tip_gap，箭头与目标框边缘留白。
        """
        if not self._blocked(s_anchor, t_anchor):
            pts = [s_anchor, t_anchor]
        else:
            # elbow：先沿出/入方向延伸到绕行线，再水平/垂直连接
            if s_dir[1] > 0 and t_dir[1] > 0:      # top-top：上方绕行
                h = max(s_anchor[1], t_anchor[1]) + elbow_offset
                pts = [s_anchor, [s_anchor[0], h], [t_anchor[0], h], t_anchor]
            elif s_dir[1] < 0 and t_dir[1] < 0:    # bottom-bottom：下方绕行
                h = min(s_anchor[1], t_anchor[1]) - elbow_offset
                pts = [s_anchor, [s_anchor[0], h], [t_anchor[0], h], t_anchor]
            elif s_dir[0] < 0 and t_dir[0] < 0:    # left-left：左侧绕行
                w = min(s_anchor[0], t_anchor[0]) - elbow_offset
                pts = [s_anchor, [w, s_anchor[1]], [w, t_anchor[1]], t_anchor]
            elif s_dir[0] > 0 and t_dir[0] > 0:    # right-right：右侧绕行
                w = max(s_anchor[0], t_anchor[0]) + elbow_offset
                pts = [s_anchor, [w, s_anchor[1]], [w, t_anchor[1]], t_anchor]
            else:
                # 未覆盖的组合（如交叉方向）→ 退回直连
                pts = [s_anchor, t_anchor]

        if self.source_gap > 0:
            # 起点沿出方向回缩，避免起笔贴死框边缘（镜像 tip_gap）
            seg_len = np.linalg.norm(np.asarray(pts[1]) - np.asarray(pts[0]))
            gap = min(self.source_gap, 0.8 * seg_len)   # 防段太短时反向越过
            if gap > 0:
                d = _unit(pts[0], pts[1])
                pts[0] = np.asarray(pts[0], dtype=float) + d * gap

        if self.arrow and self.tip_gap > 0:
            seg_len = np.linalg.norm(np.asarray(pts[-1]) - np.asarray(pts[-2]))
            gap = min(self.tip_gap, 0.8 * seg_len)   # 防段太短时反向越过
            if gap > 0:
                d = _unit(pts[-2], pts[-1])
                pts[-1] = np.asarray(pts[-1], dtype=float) - d * gap
        return pts
