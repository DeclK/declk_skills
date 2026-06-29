---
name: review-no-run
description: 强制 agent 仅展示计划并等待用户 review，同意前绝不执行命令或修改文件。用户调用 /review-no-run 激活。
allowed-tools: "Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, AskUserQuestion"
---

# Review No Run

**铁律：只做 Review 前的计划展示；用户明确同意前绝不运行命令、写文件或改代码。**

1. 收到任务后，只输出清晰的执行计划（步骤、涉及文件、预期结果）
2. 用 `AskUserQuestion` 让我审批
3. 在我明确批准前，禁止执行任何 Bash 命令、修改文件、提交代码或触发外部副作用
4. 我批准后才开始执行；要求修改计划则只修改计划并重新报审
5. 执行中遇到计划外情况，立即暂停，重新报计划