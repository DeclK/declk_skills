---
name: conventions
description: Mandatory conventions for all manim-draw scripts
metadata:
  tags: conventions, boilerplate, rendering, png
---

# Conventions

Every script written under this skill must follow these rules.

## 1. Self-executing: `python file.py` renders and copies PNG

Every script must include an `if __name__ == "__main__"` block that renders the scene and copies the output PNG to the script's own directory. Use this exact boilerplate:

```python
if __name__ == "__main__":
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    script = Path(__file__).resolve()
    SCENE_CLASS = "MyScene"  # <-- change this

    subprocess.run(
        [sys.executable, "-m", "manim", "-sql", str(script), SCENE_CLASS],
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

Copy `templates/basic_scene.py` as a starting point. It already includes the `TextBox`, `NestedTextBox` classes and the `__main__` block.

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

Order matters: check width first, then height. Both scale uniformly so the second won't break the first.

## 4. Use `-sql` for PNG output

- `-s`: render only the last frame as a static image
- `-q`: quality flag (`l`=low 480p, `m`=medium 720p, `h`=high 1080p)
- `-sql`: low quality, single frame — fastest for iteration. Use `-sqm` or `-sqh` for final output.

## 5. Font check

Before using a font, verify it exists on the system:

```bash
fc-list | grep -i "<font-name>"
```

If unavailable, fall back to `"DejaVu Sans"` or `"DejaVu Serif"`.
