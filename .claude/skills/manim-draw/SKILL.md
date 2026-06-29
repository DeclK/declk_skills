---
name: manim-draw
description: |
  Trigger when the user wants to create diagrams, architecture figures, flowcharts,
  or structural visualizations using ManimCE. Also trigger when the user references
  `TextBox`, `NestedTextBox`, `TreeNode`, `TreeLayout`, or building blocks from this skill.

  Provides reusable building blocks (TextBox, NestedTextBox) for composing box-based
  diagrams, plus mandatory conventions for self-executing scripts and frame fitting.

  This skill builds on top of `manimce-best-practices` — always consult that skill
  for core ManimCE APIs (shapes, text, animations, positioning, styling, CLI flags).
user-invocable: true
---

# Manim Draw — Box-based Diagram Skill

Compose structured diagrams from `TextBox` and `NestedTextBox` building blocks.
For all ManimCE core APIs (Scene, shapes, text, animations, positioning, styling,
CLI), consult the `manimce-best-practices` skill first.

## How to use

### 0. Ensure manim is available

Each diagram lives in its own folder with a local `.venv/` created by `uv`:

```bash
uv venv --seed --python=3.11 diagrams/<name>/.venv
diagrams/<name>/.venv/bin/pip install manim
```

If system dependencies (Cairo/Pango) are missing, run `/install-manim-linux` first.
See [install-manim-linux](../install-manim-linux/SKILL.md) for details.

### Start a new diagram

1. Create a dedicated folder for the diagram (e.g., `diagrams/my_arch/`)
2. Copy `templates/basic_scene.py` into that folder
3. Rename `MyScene` to describe your diagram
4. Update `SCENE_CLASS` and `MANIM_PYTHON` in the `__main__` block
5. Build your diagram using `TextBox` and `NestedTextBox`
6. Run `python <file>.py` — it renders and copies the PNG next to the script

### Building blocks

Read the full API in [rules/building_blocks.md](rules/building_blocks.md).

- **TextBox** — rounded box with centered text. Auto-fits or fixed-size with overflow shrink.
- **NestedTextBox** — container with top-aligned header and content area. Supports:
  - `add_text_box(child)` — add a child box, auto-relayout
  - `layout_strategy` — `"horizontal"`, `"vertical"`, `"square"`, `"auto"`
  - Nesting: both `TextBox` and `NestedTextBox` can be children
  - `auto_flow` + `grid_threshold` — wrap-based flow layout
- **TreeNode** + **TreeLayout** — mind-map tree layout engine. Supports:
  - `orientation="horizontal"` (left-to-right) or `"vertical"` (top-down)
  - `TreeNode.from_text()` — parse ASCII tree descriptions directly
  - `#` comments in tree text become node descriptions (auto-positioned annotations)
  - Bezier curve connections between parent and child nodes
  - Auto-computed level spacing; no manual positioning needed

### Conventions

Read the full rules in [rules/conventions.md](rules/conventions.md).

1. **Self-executing** — `python file.py` renders via `subprocess` + `manim -sql` and copies PNG
2. **Start from template** — copy `templates/basic_scene.py`
3. **Fit to frame** — always check width/height against `config.frame_width/height`
4. **Use `-sql`** — fast iteration with static PNG output
5. **Check fonts** — `fc-list | grep <name>` before using a custom font

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
    MANIM_PYTHON = Path.home() / ".manim-venv" / "bin" / "python"
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
