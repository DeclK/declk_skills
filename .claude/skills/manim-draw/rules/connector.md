---
name: connector
description: Polyline / BoxConnector 折线连接器。当需要多段折线、虚线箭头、或两个方框之间有阻挡物的连接时使用（manim 原生 Line 只有单段、无虚线 Arrow）。
metadata:
  tags: connector, polyline, elbow, arrow
---

# Connector — 折线连接器

（源自 dspark 示意图实践，`diagrams/common/connector.py`，skill 内常驻于 `assets/connector.py`。）

解决 manim 两个痛点：

1. **画折线**——`Polyline`：多段直线 + 圆角拐角 + 虚线 + 终点箭头。
2. **用折线连两个方框**——`BoxConnector`：锚点自动贴框边缘，无阻挡时两点直连（任意方向），
   有阻挡时同向 elbow 绕行。

```python
# 从模板（basic_scene.py）复制项目时，模板已带 connector 引用：
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from connector import BoxConnector  # noqa: E402

conn = BoxConnector(box_a, box_b, obstacles=[box_c], dashed=True,
                    arrow=True, color="#7C3AED")
self.add(conn)
```

## Polyline — 通用折线

```python
Polyline(
    points,                      # [(x0,y0), (x1,y1), ...]，至少 2 点
    stroke_width=4.0, color=WHITE, stroke_opacity=1.0,
    dashed=False, dash_length=0.12,
    arrow=False, tip_length=0.18, tip_color=None,
    corner_radius=0.25,          # 拐角圆角半径；0 = 直角
)
```

行为细节：

- 拐角用 CubicBezier 近似圆弧（k=0.5523），`corner_radius` 自动 clamp 到相邻段长的一半。
- **虚线**：直线段用 DashedLine；拐角曲线段保持实线（DashedLine 不支持曲线）。
  虚线时圆角额外 clamp 到 dash 节奏（弧长 π/2·r ≤ 一个 dash 周期），避免"一长段实线顶着
  短虚线"的比例失调。
- **实线拐角无缝**：实线折线整条路径合成**单个 VMobject 一次描边**——拐角由 cairo
  的 join（miter）填充、直线与圆角衔接处共用锚点，没有抗锯齿接缝/缺口。
  虚线分支保持逐段渲染（同上），拐角处会看到 dash 节奏间隙，属正常现象。
- **终点箭头**：Polygon tip 沿最后一段方向，尖端精确落在终点（`move_to` 后按锚点偏移修正，
  否则尖端会越过终点半个 tip_length）。**箭杆自动收在三角形底边**（不伸到尖端）——
  尖端处三角形宽度趋零，杆若伸到尖端会露出方头（杆越粗越明显）。
  `tip_length` 默认 **0.18**（dspark 示意图头部规格，头部尺寸全局统一；需要大/小时显式传值）。
- manim 无"虚线 Arrow"——虚线箭头就是 DashedLine 箭杆 + Polygon tip。

## BoxConnector — 两方框间折线连接

```python
BoxConnector(
    source, target,              # 任意 Mobject（用 get_top/get_left 等定位边缘）
    source_side="auto", target_side="auto",   # "left"/"right"/"top"/"bottom"
    source_offset=0.0, target_offset=0.0,     # 锚点沿边方向平移
    obstacles=None,              # 阻挡框列表；连线穿过任一框时走 elbow 绕行
    elbow_offset=0.4,            # 绕行高度/宽度的额外偏移
    arrow=True, tip_gap=0.12,    # 箭头尖端与目标框边缘留白
    source_gap=0.12,             # 起点沿出方向回缩留白（与 tip_gap 对称：
                                 #   起止两端默认都不侵入框）
    **kwargs,                    # 透传 Polyline：dashed/color/stroke_width/corner_radius...
)
```

行为细节：

- **side="auto"**：按两框相对方位推导（水平为主 → right/left；垂直为主 → top/bottom）。
- **offset 语义**：沿锚点所在边方向平移（top/bottom 沿 x、left/right 沿 y）。
  **默认 0 = 边的中点**。残留旧偏移会把锚点推到框角——视觉"没接到节点中间"。
- **路径规划**：锚点连线不穿任何 obstacle → 两点直连（任意方向，含斜线）；
  被挡 → 同向 elbow 绕行（top-top 上方绕、bottom-bottom 下方绕、left-left 左侧绕、
  right-right 右侧绕），`elbow_offset` 控制绕行高度；未覆盖的组合退回直连。
- **tip_gap**：有箭头时目标端沿最后一段方向回缩留白（自动 clamp 到段长 80%，防短段反向越过）。
- **source_gap**：起点端沿第一段方向回缩留白（镜像 tip_gap，同样 clamp 到段长 80%）。
  **默认 0.12**——起止两端默认都留白，起笔不再贴/侵入框边缘（dspark 示意图曾手动传
  0.12，现已并入默认，K 虚线箭头亦自动生效）。
- **箭头头部粗细**：头部是**填充多边形（stroke_width=0）**，底边宽 = 2×0.35×tip_length，
  与 `stroke_width` 无关——调头部大小改 `tip_length`，调杆粗细改 `stroke_width`，两者独立。

**统一配置原则**：默认值即统一规格（stroke 4.0 / 起止留白 0.12 / 头部 0.18），
新建连接**只传与默认不同的参数**（颜色、虚线、偏移、绕行等），需要变化时显式覆盖。

**同排两框被中间框阻挡，顶部虚线绕行**（dspark K 箭头）：

```python
BoxConnector(
    draft_boxes[2], draft_boxes[0],
    source_side="top", target_side="top",
    obstacles=[draft_boxes[1]],
    elbow_offset=0.95,                     # 水平段在框顶上方 0.95
    dashed=True, color=K_COLOR,           # 其余全部继承默认（4.0 / 0.12 / 0.18）
)  # offset 默认 0 → 锚点落在顶边中点，两端居中；虚线圆角自动 clamp 到 dash 节奏
```

**标注锚定**：两竖直腿在水平段两端 → 连接器 bbox 中点就是水平段中点，
标签挂水平段正上方：

```python
k_label = Text("use 2 steps prior K capacity", font_size=20, color=K_COLOR, font=FONT)
k_label.move_to([conn.get_center()[0], conn.get_top()[1] + 0.25, 0])
```

## 踩坑

1. **manim 所有几何点必须 3D（z=0）**：`Line`/`Polygon` 传 2D 点报
   "could not broadcast input array from shape (1,2) into shape (1,3)"。
   Polyline 入口已统一补 z 维；自己写几何时记住。
2. `_unit` 方向向量保持输入维度（3D 点运算时 2D 方向会广播失败）。
3. **无虚线 Arrow**：虚线箭头 = DashedLine 箭杆 + Polygon tip。
4. **offset 默认 0 = 边中点**：从手写 DashedLine 迁移到 BoxConnector 时，残留
   `source_offset=1.2, target_offset=1.2` 会让锚点偏离顶边中点（target 甚至落在框顶右端点）。
5. **显式旧参数覆盖新默认**：统一默认前写的代码常显式传旧值（如 demo 曾全用
   `stroke_width=2.2`），默认升到 4.0 后这些显式值仍会压过新默认，导致新旧图粗细不一致。
   清理旧图时删除冗余显式参数，让默认生效（对照 dspark 示意图/当前 demo）。

## 演示

`assets/demo_connector.py`（自执行）：5 场景——水平/垂直直线、同排绕行虚线、对角斜线、
直角 vs 圆角肘部对比。改动 connector 行为后跑一遍确认没回归。
