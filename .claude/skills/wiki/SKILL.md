---
name: wiki
description: Generate DeepWiki-style repository understanding reports with natural Chinese Markdown prose by default, preserving English only for exact technical identifiers, code, paths, commands, APIs, and established terms that would become ambiguous if translated. Use when you need to quickly understand a codebase, summarize project structure and file roles, build internal file dependency and reverse-dependency graphs, render Mermaid PNG/SVG dependency graphs, find entry points, identify core modules, answer which files use or are used by another file, or produce a recommended reading order for a repository.
user-invocable: true
allowed-tools: "Read, Write, Edit, Bash, Glob, Grep"
---

# Project DeepWiki

Use this skill to analyze a repository with evidence-backed static structure before writing architectural summaries. The bundled scanner extracts file inventory, Python imports, local dependency edges, reverse dependencies, entrypoint candidates, and compact per-file digests. The agent then interprets those artifacts instead of guessing from memory. Write generated Markdown reports in natural Chinese by default. Preserve English only where exact spelling matters, such as identifiers, filenames, paths, commands, code snippets, API names, config keys, and a small set of established terms that would become ambiguous if translated.

## Quick Start

> **Path convention:** All `scripts/` paths below are relative to this skill's installation directory (e.g. `~/.claude/skills/wiki/scripts/` for Claude, `~/.codex/skills/wiki/scripts/` for Codex). Use `$SKILL_DIR` to refer to the skill directory in bash commands.

Run the scanner against the target repository, not necessarily the current working directory:

```bash
python "$SKILL_DIR/scripts/scan_repo.py" <repo_root> --out <repo_root>/.wiki
```

Then inspect these artifacts first:

- `.wiki/summary_input.json`: compact digest for LLM summarization.
- `.wiki/graph.json`: internal dependency graph with evidence.
- `.wiki/reverse_graph.json`: which files use each file.
- `.wiki/entrypoints.json`: candidate entrypoints with signals.
- `.wiki/key_files.json`: ranked files recommended for selective deep reading.
- `.wiki/directory_summaries.json`: directory-level summarization and sampling plan.
- `.wiki/WIKI.draft.md`: deterministic report skeleton.

Use `WIKI.draft.md` as a starting point. Read selected source files only when the graph artifacts are insufficient.

## Workflow

1. Identify the real repository root requested by the user.
2. Run `scripts/scan_repo.py` with `--out <repo>/.wiki`, or a user-requested artifact directory outside the target repo.
3. Read `summary_input.json`, `entrypoints.json`, and graph files.
4. Generate `directory_graph.mmd` and `core_graph.mmd`, then render Mermaid PNG/SVG images with `render_mermaid_elk.py`. Mermaid PNG generation is mandatory for full wiki/report tasks unless the user explicitly says not to render images or required Node/Mermaid tooling is unavailable.
5. Generate `core_directory.md`, then create a concise note-oriented `core_file.md` from the template in `references/core-file-template.md`.
6. For a full project map, create or update `WIKI.md` from the draft and add concise LLM-written explanations.
7. For connection questions, answer from `graph.json` and `reverse_graph.json` first, then inspect source for details.
8. Mark unresolved, dynamic, or string-derived relationships as uncertain rather than claiming complete runtime coverage.

## Output Language

- Write generated explanatory Markdown in fluent, natural Chinese by default, including `WIKI.md`, refined summaries, reading orders, architecture explanations, and final user-facing summaries.
- Avoid awkward Chinese/English mixing. Translate ordinary explanatory technical words when a clear Chinese expression exists, for example:
  - `static dependency` -> 静态依赖
  - `runtime call graph` -> 运行时调用图
  - `orchestration layer` -> 编排层
  - `foundation/infrastructure` -> 基础设施
  - `entry point` -> 入口点
  - `directory summary` -> 目录摘要
  - `key files` -> 关键文件
  - `reading order` -> 阅读顺序
- Preserve English only when exact spelling or conventional usage matters: package/module/file/function/class names, identifiers, commands, code blocks, CLI flags, config keys, JSON keys, API names, error messages, Mermaid syntax, graph node labels, and established terms that become less clear if translated, such as `checkpoint`, `callback`, `dataloader`, `collator`, `processor`, `patch`, `tokenizer`, `FSDP`, `Ulysses`, `MoE`, `LoRA`.
- Keep paths, imports, command examples, code snippets, JSON fields, and generated graph syntax unchanged.
- Prefer a polished Chinese technical-document style over literal translation. If a sentence reads like machine translation because too many English terms remain, rewrite it in Chinese and keep only exact identifiers in backticks.
- If the user explicitly requests another language or a different terminology style, follow the user request.

## Selective Reading Strategy

Do not deep-read every file by default. Use scanner artifacts to decide what to read:

- Deep-read strong entrypoints, top files from `key_files.json`, high in-degree modules, and high out-degree orchestrators.
- Prefer loader/factory/registry/base/trainer/parser/data_loader/dataset/parallel_state files for framework understanding.
- Summarize repeated or generated directories by pattern; read 1-3 representative samples only.
- Preserve parent/child folder hierarchy in textual worktree summaries; do not flatten sibling folders that share a parent.
- In `core_file.md`, display directories by local name only and bold them with a folder marker, e.g. `📁 **folder/**`; display files by basename with a file marker and colored inline-code HTML, e.g. `📄 <code style="color:#2563eb">file.py</code>`. Use `📝 <code style="color:#7c3aed">variant/file.py</code>` for representative samples and `📝 _omitted ..._` for folded repeated files. Do not repeat full parent paths in each list item except representative folded samples, where one variant directory of context is useful.
- Fold analogous model-variant folders, such as `models/transformers/<variant>/`, into one pattern summary unless the user asks about a specific model.
- Skim or skip simple `__init__.py`, generated files, tests, and repetitive model variant folders unless the user asks about them.
- State when a folder is summarized from metadata and representative samples rather than every file.

Use `directory_summaries.json` to identify directories that should receive directory-level summaries instead of per-file summaries.

## Graph Visualization

Use `scripts/render_graph.py` to turn `graph.json` into Mermaid, Graphviz DOT, or JSON graph views. For static images, use Mermaid CLI with ELK layout via `scripts/render_mermaid_elk.py`; Mermaid owns graph layout and rendering directly. For full wiki/report tasks, Mermaid PNG rendering is a required output step for at least directory and core graphs unless the user explicitly opts out or tooling is unavailable. Rendered images are written under `<artifact_dir>/mermaid_elk_render/`.

```bash
python "$SKILL_DIR/scripts/render_graph.py" <artifact_dir> --mode directory --format mermaid --out <artifact_dir>/directory_graph.mmd
python "$SKILL_DIR/scripts/render_graph.py" <artifact_dir> --mode core --top-n 30 --format mermaid --out <artifact_dir>/core_graph.mmd
python "$SKILL_DIR/scripts/render_mermaid_elk.py" <artifact_dir>/directory_graph.mmd
python "$SKILL_DIR/scripts/render_mermaid_elk.py" <artifact_dir>/core_graph.mmd

# Optional neighborhood graph when answering a specific file-connection question:
python "$SKILL_DIR/scripts/render_graph.py" <artifact_dir> --mode neighborhood --node path/to/file.py --depth 1 --direction both --format mermaid --out <artifact_dir>/file_neighborhood.mmd
python "$SKILL_DIR/scripts/render_mermaid_elk.py" <artifact_dir>/file_neighborhood.mmd
```


Mermaid node role coloring:

- Mermaid output colors nodes by weighted directory in/out degree by default.
- Orange `top` nodes have outgoing dependency weight greater than incoming weight: API-facing or orchestration modules.
- Blue `bottom` nodes have incoming dependency weight greater than outgoing weight: foundation/infrastructure modules.
- Purple `connector` nodes have equal weighted in/out degree.
- Use `--no-role-styles` on `render_graph.py` to emit an unstyled Mermaid graph.

Mermaid + ELK render notes:

- `render_mermaid_elk.py` creates `<artifact_dir>/mermaid_elk_render/`, writes `mermaid-config.json`, `puppeteer-config.json`, `package.json`, and a repeatable `render.sh`.
- It renders both SVG and PNG by default, e.g. `directory_graph_elk.svg` and `directory_graph_elk.png`; verify the PNG files exist before finishing a full wiki/report task.
- It installs or reuses `@mermaid-js/mermaid-cli` locally when `mmdc` is not on PATH; Node/npm must be available.
- The config sets `layout: "elk"` and `flowchart.defaultRenderer: "elk"` with a readable base theme.

Always generate and render directory and core graphs for large repositories. Avoid full file-level graphs when there are many nodes or edges; use neighborhood graphs only for focused file-connection questions.

## Core File and Directory Markdown

Generate the scanner's selected core tree and directory summary first:

```bash
python "$SKILL_DIR/scripts/render_core_markdown.py" <artifact_dir> --top-n 40 --out <artifact_dir>/core_file.md
```

Then refine both Markdown files according to their different purposes:

### `core_file.md`

`core_file.md` must show important files. Use `references/core-file-template.md` when writing or updating it. It should preserve useful folder hierarchy, list key files and representative model-variant files, and may keep dependency-centrality badges such as `[importance:... | in:... | out:...]`. Do not use italics for directory or file descriptions; use plain text descriptions.

### `core_directory.md`

`core_directory.md` is the textual supplement to the directory dependency graph. Use `references/core-directory-template.md` when writing or updating it. It should list top-level folders only, not subfolders or individual files. Give each top-level folder a fuller 1-2 sentence natural Chinese description of its overall responsibilities, then include the rendered directory PNG and the standard graph explanation bullets. Do not use italics for directory descriptions.

Keep `core_file.md` and `core_directory.md` separate: `core_file.md` is for important files; `core_directory.md` is for top-level directory responsibilities and the directory graph.

## Interpretation Rules

- Treat the graph as a file-level static dependency graph, not a complete runtime call graph.
- Exclude third-party libraries from internal file connections.
- Prefer relationships with line-number evidence.
- Keep edge types explicit: `import`, `symbol_import`, `relative_import`, `script_invocation`, `module_invocation`, `markdown_command_reference`, `config_reference`, `string_path_reference`, or `unresolved_import`.
- For large repositories, summarize by directory first, then key files and high-degree modules.
- Do not paste huge dependency lists. Show the most important relationships and point to generated JSON for the full graph.

## Report Content Priorities

When generating a DeepWiki-style report, include:

1. High-level architecture overview.
2. Directory tree with file and directory roles.
3. Entry points with evidence and likely commands.
4. Internal dependency graph summary.
5. Key files recommended for deep reading.
6. Directory-level summaries and repeated-folder sampling plan.
7. File connections for key files: uses, used by, exported symbols.
8. Core modules and dependency hotspots.
9. Suggested reading order from entrypoints to core modules.
10. Mermaid graph views plus rendered PNG/SVG images for directory and core graphs.
11. Unresolved or dynamic areas where static analysis is incomplete.

## References

- Read `references/output-schema.md` when changing or consuming scanner JSON fields.
- Read `references/analysis-rules.md` when adjusting entrypoint, dependency, or confidence heuristics.
- Read `references/report-style.md` when writing a final `WIKI.md`, and apply the natural Chinese Markdown language policy above.
- Read `references/core-file-template.md` when writing or updating `core_file.md`.
- Read `references/core-directory-template.md` when writing or updating `core_directory.md`.
