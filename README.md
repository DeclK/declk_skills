# declk_skills

个人 Claude Code / Codex 技能集合，存放在 `.claude/skills/` 下，通过 `install_skills.sh` 部署。

## 安装

```bash
bash install_skills.sh
```

将 `.claude/skills/` 下的所有技能复制到 `~/.claude/skills/`（Claude Code）和 `~/.codex/skills/`（Codex）。

## 技能一览

### Agent 行为控制

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **answer-no-run** | `/answer-no-run` | 强制 agent 只回答问题、解释原因和取舍，不执行任何命令或修改文件。 |
| **review-no-run** | `/review-no-run` | 强制 agent 先展示执行计划，等待用户明确批准后才开始动手。 |

### 任务规划

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **planning-with-files** | `/planning-with-files` | Manus 风格的文件规划系统：`task_plan.md`、`findings.md`、`progress.md`、`handoff.md` 四文件跟踪复杂任务，支持 `/clear` 后恢复上下文。 |

### 笔记与文档

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **tech-note** | `/tech-note` | 精炼技术笔记：伪代码格式化、变量名对齐、中英文分工、`/ai` 标记补全。原文不动，只做增量整理。 |
| **note-organize** | `/note-organize` | 将分散的笔记点串联成结构化文档。添加总结性开头和少量过渡句，支持自动归并和大纲引导两种模式。 |
| **wiki** | `/wiki` | 生成 DeepWiki 风格的中文仓库分析报告：静态依赖图、入口点、核心模块、Mermaid 可视化、推荐阅读顺序。 |

### 图表与可视化

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **mermaid-draw** | 自动触发 | 将 Markdown 流程描述转为紧凑的 Mermaid 流程图，渲染 PNG/SVG。适合节点多、分支复杂的图。 |
| **manim-draw** | 自动触发 | 基于 `TextBox`、`NestedTextBox`、`TreeLayout` 的结构化框图。自执行脚本，输出 PNG。适合架构图、树形布局。 |
| **manim-flowchart-draw** | 自动触发 | 精排 ManimCE 流程图：蛇形换行、中英混排、固定尺寸箭头。适合线性流程、需要精细视觉控制的场景。 |
| **manimce-best-practices** | 自动触发 | ManimCE 完整 API 参考：场景、形状、文本、LaTeX、动画、3D、相机、样式、CLI。操作 Manim 代码时自动加载。 |

### 实用工具

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **arxiv-download** | `/arxiv-download` | 通过 `cn.arxiv.org` 国内镜像快速下载 arXiv 论文 PDF。 |
| **install-zsh** | `/install-zsh` | 安装 zsh、oh-my-zsh 及 zsh-autosuggestions 插件，使用 gitcode 镜像加速。 |

## 上游来源

- **planning-with-files** — 上游：[openclaw/skills](https://github.com/openclaw/skills)，本地 fork 增加了 `handoff.md` 支持
- **manimce-best-practices** — 上游作者 Adithya S Kolavi（MIT 许可）
- **manim-draw**、**manim-flowchart-draw**、**mermaid-draw**、**wiki** — 包含自带的脚本和模板

## 隐私说明

本仓库不含任何凭据、API 密钥或 `.env` 文件。唯一涉及的个人数据是 git commit 中的作者信息（`git log` 可见），属于公开 git 仓库的正常行为。
