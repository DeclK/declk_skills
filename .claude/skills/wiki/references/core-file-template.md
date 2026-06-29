# core_file.md 核心文件模板

用于生成 `core_file.md`。`core_file.md` 应展示重要文件和代表性文件，保留目录层级，用于快速定位代码库的关键实现。它不是 `directory_graph` 的补充；`directory_graph` 的文字补充应写在 `core_directory.md`。

## 写作要求

- `core_file.md` 必须展示重要文件，包括 scanner 根据 `key_files.json` 选出的核心文件，以及必要的代表性模型变体文件。
- 保留 parent/child folder 层级；可以列 sub folder 和具体文件。
- 可以使用 `render_core_markdown.py` 的输出作为初稿，再根据自然中文规则润色。
- 不要用斜体包裹目录或文件说明；说明文字使用普通正文。
- 文件名、路径、类名、函数名、配置项和必要术语保持原样。
- 对重复模型变体目录可以折叠为 `model_variants/` 一类的 pattern summary，并列 1-3 个代表性文件。
- 可以保留 `[importance:... | in:... | out:...]` 依赖中心性指标，方便判断阅读优先级。
