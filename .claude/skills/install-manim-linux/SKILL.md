---
name: install-manim-linux
description: 在 Linux (Debian/Ubuntu) 上安装 ManimCE，含系统依赖、独立 venv、轻量 LaTeX。用户可调用 /install-manim-linux 来激活。
user-invocable: true
allowed-tools: "Bash"
---

# Install ManimCE on Linux

在 Linux 上完成 Manim Community Edition 的一站式安装：系统依赖 → 独立 venv → Manim → LaTeX 渲染链。

## 核心原则

**永远使用独立的 venv**，不污染项目已有的虚拟环境（如训练环境、项目自带 venv 等）。默认安装在 `~/.manim-venv/`。

## 执行流程

### 1. 安装系统依赖

Cairo / Pango 渲染依赖和轻量 texlive（约 190MB，不走 texlive-full 的 3GB）。

```bash
sudo apt update && sudo apt install -y build-essential python3-dev libcairo2-dev libpango1.0-dev texlive-xetex texlive-latex-recommended texlive-fonts-recommended texlive-latex-extra cm-super dvisvgm
```

### 2. 创建独立 venv

不接受用户指定的路径注入到已有 venv。始终创建独立 venv。

```bash
MANIM_VENV="$HOME/.manim-venv"

if [ ! -d "$MANIM_VENV" ]; then
    python3 -m venv "$MANIM_VENV"
    echo "Created independent venv at $MANIM_VENV"
else
    echo "Using existing venv at $MANIM_VENV"
fi

PYTHON="$MANIM_VENV/bin/python"
$PYTHON --version
```

### 3. 安装 manim

优先使用清华镜像（国内较快），失败则回退到 PyPI 官方。

```bash
uv pip install manim --python "$PYTHON" --index-url https://pypi.tuna.tsinghua.edu.cn/simple/ 2>&1 || \
uv pip install manim --python "$PYTHON"
```

> 如果 uv 不可用，用 `$PYTHON -m pip install manim -i <mirror>` 替代。

### 4. 验证

```bash
$PYTHON -c "import manim; print('manim', manim.__version__)"
which xelatex && xelatex --version | head -2
which dvisvgm

# 快速渲染测试
cd /tmp && $PYTHON -c "
from manim import *
class T(Scene):
    def construct(self):
        self.add(MathTex(r'e^{i\pi}+1=0'))
with tempconfig({'quality':'low_quality','preview':False,'write_to_movie':False,'dry_run':True}):
    T().render()
print('LaTeX OK')
"
```

### 5. 使用提示

使用 manim 时，需要激活这个独立 venv：

```bash
source ~/.manim-venv/bin/activate
# 或者直接用完整路径
~/.manim-venv/bin/python -m manim ...
```

### 6. 字体坑：装/更换字体后清 manim 文本缓存

manim 渲染文字时把 SVG 按 hash 缓存到图目录 `media/texts/`，hash 不感知字体文件。
**若先渲染过 manim 图、之后才安装/更换字体（如 `fonts-jetbrains-mono`、
`fonts-lxgw-wenkai`），必须删除缓存重渲染**，否则文字继续用旧字形回退渲染、且无任何警告：

```bash
rm -rf <各图目录>/media/texts   # 或 rm -rf <图目录>/media 后重渲染
```
