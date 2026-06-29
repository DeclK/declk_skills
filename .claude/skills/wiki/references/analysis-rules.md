# Analysis Rules

- The dependency graph is static and file-level. Do not describe it as a complete runtime call graph.
- Include only project-internal resolved paths in normal connections. Third-party imports belong in `external_imports`.
- Use confidence levels:
  - `high`: AST imports or explicit script command references resolved to a file.
  - `medium`: config references or module-like strings resolved to a file.
  - `low`: string path references or unresolved imports.
- Entry point score guidance:
  - `>= 7`: strong entrypoint.
  - `4-6`: possible entrypoint.
  - `1-3`: weak signal.
- Prefer evidence-backed explanations. Mention the evidence line or signal when a relationship matters.

## Selective reading rules

- Trust `key_files.json` as the first pass for deciding which files deserve deep reading.
- Deep-read top-ranked files until the architecture is clear; do not read every file by default.
- Summarize directories with many repeated files by pattern, especially generated model variants, config/modeling/processing triplets, tests, and export-only packages.
- For repeated folders, inspect representative files and explicitly say the rest appear to follow the same pattern.
- If the user asks about a specific file or directory, override the ranking and inspect that target directly.
