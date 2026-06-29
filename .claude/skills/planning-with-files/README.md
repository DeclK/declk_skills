# planning-with-files

Implements Manus-style file-based planning to organize and track progress on complex tasks.

This local version maintains a four-file planning set:

- `task_plan.md` - roadmap, phases, status, blockers
- `findings.md` - requirements, discoveries, decisions, issues
- `progress.md` - chronological session log, commands, tests
- `handoff.md` - concise next-agent takeover brief

When the user says "update planning files", "更新 planning files", "更新计划文件", "准备交接", "生成 handoff", or similar, consolidate the current session into all four files and refresh `handoff.md` so the next agent can continue with minimal context loss.
