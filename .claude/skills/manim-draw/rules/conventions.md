---
name: conventions
description: Mandatory conventions for all manim-draw scripts
metadata:
  tags: conventions, boilerplate, rendering, png
---

# Conventions

Every script written under this skill must follow these rules.

## 1. Self-executing: `python file.py` renders and copies PNG

Every script must include an `if __name__ == "__main__"` block that renders the scene
and copies the output PNG to the script's own directory. Use this exact boilerplate:

```python
if __name__ == "__main__":
    import shutil
    import subprocess
    from pathlib import Path

    here = Path(__file__).resolve().parent
    script = Path(__file__).resolve()
    SCENE_CLASS = "MyScene"  # <-- change this
    MANIM_PYTHON = str(here / ".venv" / "bin" / "python")  # 局部 venv，勿用全局

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
```

**Two things to change per script:**
- `SCENE_CLASS` — set to the name of the main demo scene
- The scene class name also determines the output PNG filename

## 2. Start from template

Copy `templates/basic_scene.py` (free-form boxes + tree + connector + typography
constants) or `templates/flowchart_scene.py` (snake flowcharts) as starting point.
Do not write a scene from scratch.

## 3. Fit content to frame

Always ensure the final VGroup fits within the frame:

```python
margin = 1.0
max_w = config.frame_width - margin
max_h = config.frame_height - margin
if group.width > max_w:
    group.scale_to_fit_width(max_w)
if group.height > max_h:
    group.scale_to_fit_height(max_h)
group.move_to(ORIGIN)
```

Order matters: check width first, then height. Both scale uniformly so the second won't
break the first.

## 4. Rendering flags: `-sql` for iteration, `-sqh` for final

- `-s`: render only the last frame as a static image
- `-q`: quality flag (`l`=low 480p, `m`=medium 720p, `h`=high 1080p)
- `-sql`: fastest iteration loop. Use `-sqh` (1920×1080, pixel-verified) for the final
  deliverable. Iterate in `-sql` until the layout is right, then render `-sqh` once
  as the final artifact — never iterate in `-sqh`.

## 5. Typography: explicit fonts, explicit sizes

- Scene 顶部定义 `CJK_FONT` / `LATIN_FONT` / `FONT` 常量（见 rules/typography.md）。
- **所有** `Text` / `TextBox` 显式 `font=`；字号显式且一致；禁止 per-node 缩放。
- 渲染后检查 stderr 无字体 fallback 警告；怀疑缺字形时用 pycairo 验证（typography.md）。
- 新增字体先 `fc-list | grep -i "<font-name>"` 确认已安装，缺失则
  `sudo -n apt install <font-package>`。

## 6. Connector usage

图中有折线 / 方框间连接 / 阻挡绕行时，从 `assets/connector.py` 复制 connector
到项目 `diagrams/common/`（多图复用）或图目录内，再 import（见 rules/connector.md）。
