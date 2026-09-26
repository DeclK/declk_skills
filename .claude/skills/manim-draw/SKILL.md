---
name: manim-draw
description: |
  Trigger when the user wants to create diagrams, architecture figures, flowcharts,
  or structural visualizations using ManimCE. Also trigger when the user references
  `TextBox`, `NestedTextBox`, `TreeNode`, `TreeLayout`, `FlowChart`, `LabeledBox`,
  `Polyline`, `BoxConnector`, or building blocks from this skill.

  Provides reusable building blocks for box-based diagrams (TextBox/NestedTextBox/Tree),
  snake flowcharts (FlowChart/LabeledBox), polyline connectors (Polyline/BoxConnector),
  and mandatory conventions for typography, self-executing scripts and frame fitting.

  This skill builds on top of `manimce-best-practices` — always consult that skill
  for core ManimCE APIs (shapes, text, animations, positioning, styling, CLI flags).
  For complex graphs (many branches/cross-links), prefer `mermaid-draw` instead.
user-invocable: true
---

# Manim Draw — Box-based Diagram Skill

Compose structured diagrams from box and connector building blocks. For all ManimCE
core APIs (Scene, shapes, text, animations, positioning, styling, CLI), consult the
`manimce-best-practices` skill first.

## How to use

### 0. Ensure manim is available

Each diagram lives in its own folder with a local `.venv/` created by `uv`:

```bash
uv venv --seed --python=3.11 diagrams/<name>/.venv
diagrams/<name>/.venv/bin/pip install manim
```

If system dependencies (Cairo/Pango) are missing, install them first — on Debian/Ubuntu:

```bash
sudo apt update && sudo apt install -y build-essential python3-dev libcairo2-dev \
    libpango1.0-dev texlive-xetex texlive-latex-recommended texlive-fonts-recommended
```

### Start a new diagram

1. Create a dedicated folder for the diagram (e.g., `diagrams/my_arch/`)
2. Copy `templates/basic_scene.py` into that folder — or `templates/flowchart_scene.py`
   for snake flowcharts
3. Rename `MyScene` to describe your diagram
4. Update `SCENE_CLASS` and `MANIM_PYTHON` in the `__main__` block
5. Build your diagram using the building blocks below
6. Run `python <file>.py` — it renders and copies the PNG next to the script

### Choose the right building blocks

| 图类型 | 用什么 | 文档 |
|--------|--------|------|
| 自由排布的方框图 / 架构图 | TextBox, NestedTextBox, TreeNode + TreeLayout | [rules/building_blocks.md](rules/building_blocks.md) |
| 简单线性/蛇形流程 + 标题/正文节点 | FlowChart, FlowNodeSpec, LabeledBox | [rules/flowchart.md](rules/flowchart.md) |
| 多段折线 / 方框间有阻挡的连接 | Polyline, BoxConnector | [rules/connector.md](rules/connector.md) |
| 任何含文字的图 | 字体常量 + mixed_text | [rules/typography.md](rules/typography.md) |

**Manim vs Mermaid 边界**：图是图结构（多分支、扇入扇出、大量交叉边、嵌套依赖）时
用 `mermaid-draw`；路径简单、基本线性、需要精确视觉控制（蛇形换行、自定义框、混排、
固定箭头）时用本 skill 的 FlowChart 或自由绘制。

### Building blocks

- **TextBox** — rounded box with centered text. Auto-fits or fixed-size with overflow shrink.
- **NestedTextBox** — container with top-aligned header and content area
  (`add_text_box`, `layout_strategy`: horizontal/vertical/square/auto, `auto_flow` + `grid_threshold`).
- **TreeNode + TreeLayout** — mind-map tree layout engine (horizontal/vertical,
  `TreeNode.from_text()` ASCII tree parsing, `#` comments become descriptions,
  bezier connections, auto spacing).
- **FlowChart + FlowNodeSpec + LabeledBox** — snake-wrapping typed flowcharts with
  title/body nodes and explanatory/grouping boxes (header/overlay label modes).
- **Polyline + BoxConnector** — multi-segment polylines (rounded corners, dashed,
  end arrow) and box-to-box connectors (edge anchors, obstacle detection, elbow routing).

Full APIs: [rules/building_blocks.md](rules/building_blocks.md),
[rules/flowchart.md](rules/flowchart.md), [rules/connector.md](rules/connector.md).

### Conventions

Read the full rules in [rules/conventions.md](rules/conventions.md).

1. **Self-executing** — `python file.py` renders via `subprocess` + `manim -s` and copies PNG
2. **Start from template** — copy `templates/basic_scene.py` or `templates/flowchart_scene.py`
3. **Fit to frame** — always check width/height against `config.frame_width/height`
4. **-sql for iteration, -sqh (1920×1080) for final** — fast iteration, crisp output
5. **Typography** — CJK/LATIN font constants, explicit fonts, no per-node scaling
   (see [rules/typography.md](rules/typography.md))

### Core ManimCE knowledge

This skill includes a bundled copy of `manimce-best-practices` for all Manim fundamentals:
scene structure, shapes, text, MathTex, LaTeX, animations, positioning, styling,
CLI flags. Always consult it before writing Manim primitives.

## Quick Reference

### Minimal working script

```python
from manim import *

class MyDiagram(Scene):
    def construct(self):
        tb = TextBox("Hello")
        tb.move_to(ORIGIN)
        self.play(Create(tb))
        self.wait(1)

if __name__ == "__main__":
    import shutil, subprocess, sys
    from pathlib import Path
    here = Path(__file__).resolve().parent
    script = Path(__file__).resolve()
    MANIM_PYTHON = here / ".venv" / "bin" / "python"
    subprocess.run(
        [str(MANIM_PYTHON), "-m", "manim", "-sql", str(script), "MyDiagram"],
        cwd=here, check=True,
    )
    png_dir = here / "media" / "images" / Path(__file__).stem
    pngs = sorted(png_dir.glob("MyDiagram*.png"))
    if pngs:
        shutil.copy2(pngs[-1], here / "MyDiagram.png")
```

### Frame safety

```python
margin = 1.0
if group.width > config.frame_width - margin:
    group.scale_to_fit_width(config.frame_width - margin)
if group.height > config.frame_height - margin:
    group.scale_to_fit_height(config.frame_height - margin)
group.move_to(ORIGIN)
```

### Fonts & typography

```python
CJK_FONT = "LXGW WenKai"      # 中文
LATIN_FONT = "JetBrains Mono" # 拉丁/代码
FONT = LATIN_FONT
```

All text must set `font=` explicitly. For CJK/Latin mixed labels use `mixed_text()`
from `templates/flowchart_scene.py`. See [rules/typography.md](rules/typography.md)
for the monospace-TextBox pitfall (fixed-width TextBox renders text size-independent
of `font_size`).
