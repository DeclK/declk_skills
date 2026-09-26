# declk_skills

个人 Claude Code / Codex 技能集合，存放在 `.claude/skills/` 下，通过 `install_skills.sh` 部署。

## 安装

```bash
# 安装全部技能到 Claude Code 和 Codex
bash scripts/install_skills.sh

# 一键配置 Claude Code（安装 CLI + 写入 API 端点与模型配置）
ANTHROPIC_AUTH_TOKEN=<your-token> bash setup_claude_code.sh

# 配置 shell 别名（claude / codex 跳过权限确认）
bash scripts/alias.sh
```

`install_skills.sh` 将 `.claude/skills/` 下的所有技能复制到 `~/.claude/skills/`（Claude Code）和 `~/.codex/skills/`（Codex）。

`setup_claude_code.sh` 从环境变量或第一个参数读取 API token，仓库中不保存任何密钥。默认写入 DeepSeek 的 Anthropic 兼容端点，可用 `ANTHROPIC_BASE_URL` 覆盖为其他后端，并把根目录的 `claude.md` 复制到 `~/.claude/CLAUDE.md`。

## 技能一览

### Agent 行为控制

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **answer-no-run** | `/answer-no-run` | 强制 agent 只回答问题、解释原因和取舍，不执行任何命令或修改文件。 |
| **review-no-run** | `/review-no-run` | 强制 agent 先展示执行计划，等待用户明确批准后才开始动手。 |
| **keep-it-short** | `/keep-it-short` | 限制输出长度与结构：≤3-5 句话或 ≤3 个真实并列点，禁止伪列表和电报体动词堆叠。 |
| **no-hallucination** | `/no-hallucination` | 反幻觉 / 反谄媚 / 自我审计：标注来源标签、量化置信度、拒绝编造、自我纠错。 |
| **step-by-step** | `/step-by-step` | 按计划逐小步执行：每次只展示当前叶级步骤，确认后才执行，执行完汇报即停。 |

### 任务规划与记忆

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **gen-plan** | `/gen-plan` | 生成可执行计划并写入项目根目录 `draft.md`：≤5 步、每步一行、直接可执行。 |
| **ref-planning-files** | `/ref-planning-files` | 只读引用 `handoff.md` + `context.md` 作为跨 session 记忆：先读交接快照，再按需深读笔记。 |
| **show-status** | `/show-status` | 报告当前进度到哪一步、下一步做什么，配合两文件制只读引用并精简成 ≤3-5 句人话。 |
| **update-handoff** | `/update-handoff` | 提炼增量信息，用户确认后只更新 `handoff.md`（关键文件路径、用户偏好、踩坑三类）。 |
| **planning-with-files** | `/planning-with-files` | Manus 风格四文件规划系统：`task_plan.md`、`findings.md`、`progress.md`、`handoff.md`。已转为惰性参考，不再挂 hooks 自动触发。 |

### 笔记与文档

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **tech-note** | `/tech-note` | 精炼技术笔记：全角标点、行内代码反引号、Typora 数学块、`/ai` 标记补全。原文不动，只处理 `/ai` 处。 |
| **note-organize** | `/note-organize` | 将分散的笔记点串联成结构化文档。添加总结性开头和少量过渡句，支持自动归并和大纲引导两种模式。 |
| **wiki** | `/wiki` | 生成 DeepWiki 风格的中文仓库分析报告：静态依赖图、入口点、核心模块、Mermaid 可视化、推荐阅读顺序。 |

### 图表与可视化

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **mermaid-draw** | 自动触发 | 将 Markdown 流程描述转为紧凑的 Mermaid 流程图，渲染 PNG/SVG。适合节点多、分支复杂的图。 |
| **manim-draw** | 自动触发 | ManimCE 自执行绘图脚本：`TextBox`/`NestedTextBox`/`TreeLayout` 方框图、`FlowChart` 蛇形流程图、`Polyline`/`BoxConnector` 连接线、中英混排排版。 |
| **manimce-best-practices** | 自动触发 | ManimCE 完整 API 参考：场景、形状、文本、LaTeX、动画、3D、相机、样式、CLI。操作 Manim 代码时自动加载。 |
| **install-manim-linux** | `/install-manim-linux` | Linux (Debian/Ubuntu) 一站式安装 ManimCE：系统依赖、独立 venv、轻量 LaTeX 渲染链。 |

### NPU 与训练

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **npu-clean** | `/npu-clean` | 训练前清理 NPU/HCCL 环境：杀残留训练进程、清 IPC 共享内存与信号量、释放 HCCL 端口。 |
| **npu-monitor** | `/npu-monitor` | 采集 `npu-smi` 的 AI Core 利用率到 CSV，并分析低利用率、画折线图。 |
| **calc-train-mem** | `/calc-train-mem` | 用公式估算 FSDP2 + SP 训练的理论峰值显存，并提供 profiler 实测校验。 |

### 实用工具

| 技能 | 调用方式 | 说明 |
|------|----------|------|
| **arxiv-download** | `/arxiv-download` | 通过 `cn.arxiv.org` 国内镜像快速下载 arXiv 论文 PDF。 |
| **read-arxiv** | `/read-arxiv` | 精读 arXiv 论文，生成 6 节结构化中文报告。agent 自身作为分析引擎，无需外部 API。 |
| **install-zsh** | `/install-zsh` | 安装 zsh、oh-my-zsh 及 zsh-autosuggestions 插件，使用 gitcode 镜像加速。 |

## 上游来源

- **planning-with-files** — 上游：[openclaw/skills](https://github.com/openclaw/skills)，本地 fork 增加了 `handoff.md` 支持
- **manimce-best-practices** — 上游作者 Adithya S Kolavi（MIT 许可）
- **manim-draw**、**mermaid-draw**、**wiki** — 包含自带的脚本和模板
- **manim-draw** 中的 `FlowChart` / `LabeledBox` 规则由原独立技能 `manim-flowchart-draw` 合并而来

## 隐私说明

本仓库不含任何凭据、API 密钥或 `.env` 文件。`setup_claude_code.sh` 的 token 一律从环境变量或命令行参数传入，脚本本身不保存密钥，写入的 `~/.claude/settings.json` 在本机、不入库。

唯一涉及的个人数据是 git commit 中的作者信息（`git log` 可见），属于公开 git 仓库的正常行为。
