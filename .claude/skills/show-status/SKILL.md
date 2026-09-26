---
name: show-status
description: 报告当前 task 进度到哪一步、下一步是什么。配合 ref-planning-files 只读引用项目记忆两件套（handoff.md 优先 + context.md 对照），并用 keep-it-short 规则把报告精简成 ≤3-5 句或 ≤3 个独立点的人话。当用户问"进度到哪了""下一步做什么""现在什么状态"或要求进度汇报时触发；用户可调用 /show-status 激活。
user-invocable: true
allowed-tools: "Read, Glob, Grep, Bash"
---

# Show Status — 当前进度汇报

**目标**：只读地把两个项目记忆文件翻译成一句人话——"现在到哪、下一步做什么"。
**铁律**：只读。不写/不更新任何文件；报告就是全部产出。

## 执行流程

1. 用 Skill 工具依次加载 `ref-planning-files` 和 `keep-it-short`，随后按两者的规则执行。
   - 若 Skill 工具不可用，内联执行：只读引用（见下）+ 输出 ≤3-5 句或 ≤3 个独立点。
   - 注意：keep-it-short 加载后对后续对话也生效（该 skill 自身语义）；用户想恢复详细输出时说"退出 keep-it-short"。
2. 按 ref-planning-files 的读取顺序提取进度：
   - handoff.md → Snapshot（现在在哪）+ Next Best Step（下一步做什么）+ 用户要求/习惯 —— 最快入口
   - context.md → 阶段/进度小节 + 最近的过程记录（handoff 可能过期，对照确认）；未解决问题小节
3. 文件缺失则跳过，不创建；没有任何进度记录时直接报告"项目记忆文件里没有进度记录"。

## 报告格式（按 keep-it-short 规则）

≤3-5 句话，或恰好 3 个独立点，每点单独可读：

1. **当前位置**：哪个阶段、完成了什么（标注来源：`handoff Snapshot` / `context 阶段小节`）
2. **下一步**：具体动作（`handoff Next Best Step`，或 context 中的待办）
3. **提醒**（可选，有才写）：未解决问题、blocker，或 handoff 与 context 进度不一致

示例：

> 当前位置：Phase 2 验证实施中，dataloader 切 cruise 已完成（handoff Snapshot）。
> 下一步：下 session 讨论 Phase 2b 通用 dataset 基建计划（handoff Next Best Step）。
> 提醒：context 仍列"nw=0 串行影响 GPU 利用率"待测，代码已切 cruise——以 handoff 为准。

## 铁律

1. 只读：不写任何文件（allowed-tools 无 Write/Edit）；确有更新需求时提示用户走 `/update-handoff`。
2. 不编造：进度只从两件套提取，文件里没有就明说没有，不猜测"应该做到哪了"。
3. 不替用户决定：handoff 与 context 矛盾时报告差异让用户裁决，不自行选择哪个是真的。
4. 说人话：报告严格遵守 keep-it-short 长度与结构规则；输出前自查"每条能被单独读懂吗"。
