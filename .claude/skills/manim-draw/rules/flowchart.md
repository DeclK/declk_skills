---
name: flowchart
description: FlowChart / FlowNode / FlowNodeSpec / LabeledBox 蛇形流程图构建块与设计规则。当需要"简单线性/蛇形流程 + 标题/正文节点 + 分组框"时使用。
metadata:
  tags: flowchart, snake, LabeledBox, node
---

# FlowChart — 蛇形流程图构建块

（源自原 manim-flowchart-draw skill，合并后常驻于此。）

## 何时用 FlowChart 而非自由绘制

- **用 FlowChart**：路径简单、基本线性的流程；需要 snake/serpentine 换行、标题/正文节点、
  中英混排、固定尺寸箭头。一个主路径 + 少量交叉边时最佳。
- **用 Mermaid（mermaid-draw skill）**：大图、多分支、多交叉边、复杂自动布局——Manim
  手摆不划算时。合并 skill 的 SKILL.md 保留了这条边界。

## 模板

从 `templates/flowchart_scene.py` 开始（原 flowchart-draw 的 `assets/flowchart_scene.py`，原样保留）。

模板包含：

- `FlowNodeSpec`：title/body/kind 节点声明
- `FlowNode`：圆角标题/正文框
- `FlowChart`：蛇形换行可复用流程图，可选内建容器
- 水平/垂直蛇形布局：`orientation="horizontal"` / `orientation="vertical"`
- `LabeledBox`：任意子图/对象的解释性或分组框
- `mixed_text()`：一个 MarkupText 对象渲染中英混排（Pango spans）
- 自渲染 bootstrap：局部 `.venv` + 本地 `media/` 目录 + 静态渲染

最小数据形状：

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
    container_dashed=False,
)

# 垂直蛇形：第一列自上而下，下一列自下而上。
vertical_flow = FlowChart(
    [
        FlowNodeSpec("Step 1", "", "state"),
        FlowNodeSpec("Step 2", "", "state"),
        FlowNodeSpec("Step 3", "", "state"),
        FlowNodeSpec("Step 4", "", "state"),
    ],
    orientation="vertical",
    max_nodes_per_line=3,
    node_gap=0.42,
    row_gap=0.80,
)
```

## LabeledBox — 解释性/分组框

对已完成的对象（整个 FlowChart、图例、一行、嵌套图、任意 VGroup）用 `LabeledBox(...)` 包一层，
用于"communication stages"这类区域说明，而不把说明变成流程节点。

两种 label 模式：

- **`label_mode="header"`（默认）**：label 在目标的上/下/旁，`label_gap` 分隔；框尺寸包含 label，
  保证 label 不与内容重叠。支持角落位置（top_left/top_right/bottom_left/bottom_right）。
  用于语义分组标签。
- **`label_mode="overlay"`**：label 浮在框边框上，不影响框尺寸。显式 opt-in，调用方须自查
  不重叠。支持 `label_placement="inside"|"outside"` + `label_inset`。用于角落空旷处的轻量注解。

```python
# Header label（默认）— 预留空间，不重叠内容。
boxed = LabeledBox(
    flow,
    label="communication / compute stages",
    padding=0.30,
    label_position="top_left",
    label_mode="header",
    fill_color="#f8fafc",
    fill_opacity=0.25,
    stroke_color="#94a3b8",
    stroke_width=1.8,
    dashed=True,
)

# Overlay label — 显式 opt-in，浮在边框上。
callout = LabeledBox(
    flow,
    label="communication stages",
    padding=0.18,
    label_size=14,
    label_position="top_right",
    label_mode="overlay",
    label_placement="inside",
    label_inset=0.12,
    fill_color="#ffffff",
    fill_opacity=0.0,
    stroke_color=GROUP_STROKE,
    stroke_width=1.4,
    dashed=True,
)
```

规则：

- 注解框视觉上从属于节点：浅填充、细描边、短标签。解释性 callout 用虚线边框，真正的
  分区/容器边界用实线。
- 避免给每个类别都套框；图太挤时用小图例代替。
- **图例框不得带文字 label**：彩色节点样本自解释，"Legend"/"图例"/"node types" 是冗余。
  包图例时 `LabeledBox(legend, padding=0.18, dashed=True, ...)`，不传 label。
- 可见面板标题不要带图类型前缀：写 `apply from inside to outside` 而不是
  `flowchart: apply from inside to outside`——视觉形式已说明它是流程图。

## 节点语义

用 `kind` 表示主题相关属性（io/model/sync/state/control/compute/comm/error/decision…）。
不要假设每张图都需要"通信/计算"两类——那是某一张图的分类。用最少的视觉类别，
两三色通常足够；加色只有当它提升理解多过增加杂乱时才加。

## 节点内容

- 一个操作与其直接变换合并成一个节点。
- 标题短而稳定；细节只在与源一致时才放正文。不要凭空编造正文填充节点——
  源只给操作名就留空正文。
- 正文变换（`input -> output`、`W_shard -> W_full`）只有在源明确或无可争议时才用。
- 保留用户措辞、标题、label、正文、图例、表格内容与结构关系，改动最小化。
- 不加源中没有的事实、推断解释、额外节点/边/行列、规范化术语、未声明的关联。
- 长标题加宽节点宽度，而不是让标题溢出。
- 去除装饰性杂乱仅在明确无语义且提升可读性时；不确定就保留用户措辞。

## 布局选择

- `max_nodes_per_line` 控制蛇形换行。
- `orientation="horizontal"`：第一行左→右，下一行右→左。
- `orientation="vertical"`：第一列上→下，下一列下→上。
- `node_gap` / `row_gap` 视觉均匀。换行端点对齐，让换行箭头笔直。
- 垂直方向时，换列端点水平对齐，列间箭头笔直。
- 最终组 `fit_to_frame()`。
- 当语义子组（如内部 experts 区）应占据干净连续的区域时，优先垂直蛇形——避免宽横排中
  分组框意外框住相邻外层节点。

## 文字适配与节点尺寸

**绝不逐节点缩放文字来适配**。字号必须显式且一致（`node_title_size`、`node_body_size`、
图例字号）。字号不齐视为渲染 bug。

文字放不下时改布局，而不是缩放文字；但**不要滥用换行**：

1. 优先一行标题 + 一行正文。
2. 少数长节点加宽该节点的 `width` 保持单行（整行仍放得下帧的前提下）。
3. 措辞冗长时先缩短 label 再考虑换行。
4. 仅当很多节点都长、整行太宽、或特定正文变换两行更清晰时，才用显式 `\n`。
5. 换行保持稀疏：不要让大多数节点变成三行框，除非整图有意用多行风格。
6. 解释性细节移到图例、note 或 `LabeledBox` 注解，而不是塞进节点。

模板在节点文字放不下（需缩放才能放）时应报错；修复文字/尺寸后重渲染，不要重新引入
`scale_to_fit_width/height` 逐节点缩放。

```python
# 孤立长节点：加宽、单行正文。
FlowNodeSpec("reduce-scatter", "fp32 full grad -> shard", "comm", width=4.1)

# 只有宽度过大或 label 很长时才换行。
FlowNodeSpec("reduce-scatter", "fp32 full grad\n-> fp32 shard", "comm", width=3.8, height=1.35)
```

## 箭头

ManimCE `Arrow` 默认按长度缩放 tip 和 stroke。要保持视觉一致，固定箭头尺寸、只变连接线长度：

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

相邻逻辑项用直箭头。若流程需要大量非相邻连接，重新考虑 Mermaid。
（自由绘制的图里，非相邻/带阻挡连接用 `connector.md` 的 BoxConnector 而非手拼 Arrow。）

## 渲染

- 自执行：`python diagram.py` 渲染 PNG。
- 成品 `-sqh`（1920×1080）；迭代 `-sql`。见 `conventions.md`。
- venv 在 diagram 目录下；`--media_dir` 指向本地 media/；成品 PNG 复制到脚本旁。
- 检查渲染图并迭代。
