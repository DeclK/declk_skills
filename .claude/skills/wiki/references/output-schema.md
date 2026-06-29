# Project DeepWiki Output Schema

The scanner writes artifacts into `.wiki/`.

## graph.json

```json
{
  "nodes": [{"path": "pkg/file.py", "kind": "python", "role_hints": ["utility"]}],
  "edges": [{
    "source": "train.py",
    "target": "pkg/data.py",
    "type": "symbol_import",
    "symbols": ["build_dataset"],
    "line": 12,
    "evidence": "from pkg.data import build_dataset",
    "confidence": "high"
  }]
}
```

`source` and `target` are repository-relative paths when resolved. Low-confidence unresolved imports may use a module name target.

## reverse_graph.json

Maps each target to incoming edge objects. Use this to answer "who uses this file?".

## entrypoints.json

Each entry has `path`, `score`, `strength`, `signals`, and optional `likely_command`.

## key_files.json

Ranked list of files recommended for selective deep reading:

```json
{
  "path": "models/loader.py",
  "importance": 191,
  "used_by_count": 90,
  "outgoing_count": 12,
  "role_hints": ["model"],
  "reasons": ["used by 90 internal edges", "important filename pattern"],
  "suggested_action": "deep-read"
}
```

Use this to avoid reading and summarizing every file.

## directory_summaries.json

Directory-level summarization plan. Each item includes `directory`, `file_count`, dominant `kinds`, dominant `roles`, `sample_files`, `key_files`, and `summarization_strategy`. Use it to summarize repetitive folders by pattern.

## summary_input.json

Compact per-file digest for LLM summarization: local imports, used-by list, classes, functions, docstring, external import names, kind, roles, and line count.

## core_file.md

Worktree-style nested Markdown list generated from `key_files.json`, `summary_input.json`, and `symbols.json`. It contains one-line folder summaries and one-line core-file summaries while preserving parent/child folder hierarchy. Directory items are displayed by local folder name only with the `📁 **folder/**` style; file items are displayed by basename only with the `📄 <code style="color:#2563eb">file.py</code>` style; representative folded samples use `📝 <code style="color:#7c3aed">variant/file.py</code>`. Repeated model-variant folders should be folded into a pattern summary with representative samples. Use it as a selective-reading map and refine with source inspection for final reports.

## core_directory.md

Directory-only Markdown list generated alongside `core_file.md`. It extracts only directory entries from the same selected core-file tree, keeps the `📁 **folder/**` style, and appends copy-ready notes explaining the directory dependency graph: arrow direction, arrow-count labels, node role colors, and the static-analysis limitation.
