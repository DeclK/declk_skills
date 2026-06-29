#!/usr/bin/env python3
"""Render a compact Markdown report from wiki JSON artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    d = args.artifact_dir
    summary = load(d / "summary_input.json")
    entrypoints = load(d / "entrypoints.json")
    graph = load(d / "graph.json")
    lines = ["# Project DeepWiki", ""]
    lines.append(f"Files: {len(summary)}")
    lines.append(f"Edges: {len(graph.get('edges', []))}")
    lines.append("")
    lines.append("## Entry Points")
    for ep in entrypoints[:20]:
        lines.append(f"- `{ep['path']}` score={ep['score']} ({', '.join(ep['signals'])})")
    lines.append("")
    lines.append("## Files")
    for item in summary:
        roles = ", ".join(item.get("role_hints", [])) or "unknown"
        lines.append(f"- `{item['path']}` ({roles}): uses {len(item.get('imports_local', []))}, used by {item.get('used_by_count', 0)}")
    out_text = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(out_text, encoding="utf-8")
    else:
        print(out_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
