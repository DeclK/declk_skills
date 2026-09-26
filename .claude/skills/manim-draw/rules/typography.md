---
name: typography
description: 中英混排排版规则——CJK/Latin 字体常量、mixed_text、基线微调、等宽字体陷阱与字形检查。所有 manim-draw 图统一遵守。
metadata:
  tags: fonts, typography, CJK, markup, monospace
---

# Typography — 字体与中英混排

## 字体常量（所有图统一）

```python
CJK_FONT = "LXGW WenKai"     # 中文
LATIN_FONT = "JetBrains Mono" # 拉丁/代码/符号
FONT = LATIN_FONT             # 纯英文图默认
```

- **所有文字显式指定 font**；字号显式且一致；禁止 per-node 缩放。
- 字体缺失时安装：`sudo -n apt install fonts-jetbrains-mono fonts-lxgw-wenkai`
  （本机已装；fontconfig 自动刷新，无需额外操作）。
- 渲染前检查：`fc-list | grep -i "<font-name>"`。

## 中英混排：mixed_text（MarkupText + Pango spans）

混排 label 渲染为**单个 MarkupText 对象**（Pango font spans），不要为每种语言手工拼多个
`Text` 对象。`templates/flowchart_scene.py` 内置 `mixed_text()` 全套工具：

```python
mixed_text(text, font_size, weight=NORMAL, color=TEXT_COLOR,
           latin_rise_em=0.0, justify=False, force_rise=False) -> MarkupText
```

- CJK 字符自动用 `CJK_FONT` span，Latin/符号用 `LATIN_FONT` span，空格不包 span。
- `latin_rise_em` 微调 Latin 相对 CJK 的基线（负值降低 Latin，正值抬高）。
  默认 `-0.04` 适合大写/符号重的 Latin 挨着中文（如 `"计算 X & W grad"`）；
  小写 Latin 挨着中文常 `0.0` 更好看。
- **rise 必须经 `has_cjk` 门控**：纯 Latin 字符串（标题、纯英文行）不加 rise，
  否则整行被压低，出现"英文比中文矮/低"的观感。拷贝 `mixed_text` 时务必带上
  `effective_rise = latin_rise_em if has_cjk else 0.0` 的门控（曾踩坑：把 `-0.04`
  写成全局默认值，标题和小写正文全部下移）。
- **经验值（LXGW WenKai + JetBrains Mono 实测，fs=20）**：pango 的 SVG 后端对
  **CJK 开头的行**会给 Latin run 约 0.17 em 的天然上浮 → `latin_rise_em=-0.045`
  补偿后视觉接近对齐（像素测 delta ≈ -1.5px，微偏高更耐看）；**Latin 开头的行**
  天然对齐 → `0.0`。与大小写/符号无关（旧认知"大写/符号重 → -0.04"已被实测推翻：
  大写行 -0.04 会明显偏低）。不确定时渲染后用像素测 latin/cjk 底边差。
- **多行正文自动对齐**：正文含 `\n` 时，模板自动检测是否有任何一行含 CJK；
  有则所有行（含纯 Latin 行）统一应用 `latin_rise_em`（`force_rise=True`），
  保持节点内 Latin 基线一致。无需额外配置。

自由绘制（basic_scene.py 路径）时若无需混排，全英文图直接 `font=FONT` 即可；
需混排时从 flowchart_scene.py 复制 `mixed_text` 相关函数。

## 等宽字体陷阱（TextBox 固定框宽）

**TextBox 在固定框宽下，最终渲染文字尺寸与 font_size 无关。**

原因：TextBox 内部 `scale = min(1.0, avail_w/t.width, avail_h/t.height)` 会把文字缩小到
可用空间——字号增大 → 文字原始宽度同步增大 → scale 反比缩小，互相抵消。

**补偿方式只有两种：加宽框，或缩短文字。调字号无效。**

等宽字体（JetBrains Mono）比 DejaVu Sans 宽 ~10-15%，更容易触发此陷阱：
节点文字看起来偏小时，先怀疑这里，而不是调 font_size。

## 字体缓存坑：装/换字体后必须清 media/texts

manim 把文本渲染成 SVG 并按 hash 缓存到 `<diagram>/media/texts/*.svg`，hash 只含
文本与设置（字体名、字号、颜色），**不感知字体文件本身**。先渲染、后安装/更换字体的
场景下，旧字形会被直接复用——表现是中文整段变 fallback（gothic，如 Droid Sans
Fallback）、拉丁变普通 sans，看起来像字体没设对，且**无任何警告**。

**修复**：删除缓存后重渲染（只删 texts 即可，或整个 media/ 重跑）：

```bash
rm -rf <diagram_dir>/media/texts    # 然后 python <diagram>.py 重渲染
```

本机踩过此坑：先装 manim、后装 fonts-jetbrains-mono / fonts-lxgw-wenkai，渲染出的
中文全部是 fallback 字形；清 media/texts 后立即恢复楷体/等宽。若要用脚本自查，
对比渲染前后 `media/texts/` 的 SVG 是否重建即可。

## 字形检查（venv 无 fontTools 时）

验证某字体是否覆盖某字符（如下标 U+2080-2084）——用 pycairo：

```python
import cairo
surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
ctx = cairo.Context(surface)
ctx.select_font_face("JetBrains Mono", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
ctx.set_font_size(12)
for ch in "₀₁₂₃₄":
    ext = ctx.text_extents(ch)
    print(ch, ext.x_advance)   # advance > 0 即有条形；= 0 说明 fallback 或缺字形
```

渲染后检查 stderr 是否有字体 fallback 警告。
