#!/usr/bin/env python3
"""Render selected core files as a true worktree-style Markdown summary.

Default output is `core_file.md`. The renderer preserves parent/child folder
hierarchy and folds repeated sibling model-variant folders into a pattern summary
with a few representative sample files.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROLE_DESCRIPTIONS = {
    "entrypoint": "entry or CLI-facing module",
    "training": "training workflow module",
    "trainer": "training loop and orchestration module",
    "model": "model definition, loading, or adaptation module",
    "dataset": "dataset definition or data access module",
    "data-loading": "data loading pipeline module",
    "data-collation": "batch collation module",
    "distributed": "distributed training and communication module",
    "config": "configuration module",
    "utility": "shared utility module",
    "script": "script or command wrapper",
    "documentation": "documentation file",
}

NAME_DESCRIPTIONS = [
    (re.compile(r"(^|/)loader\.py$"), "loads and constructs framework objects or models"),
    (re.compile(r"(^|/)auto\.py$"), "auto-dispatches object/model selection and construction"),
    (re.compile(r"(^|/)module_utils\.py$"), "provides shared module/model utility helpers"),
    (re.compile(r"(^|/)parallel_state\.py$"), "tracks distributed parallel groups and process state"),
    (re.compile(r"(^|/)logging\.py$"), "provides shared logging setup and logger helpers"),
    (re.compile(r"(^|/)device\.py$"), "detects and manages compute device/runtime details"),
    (re.compile(r"(^|/)import_utils\.py$"), "checks optional dependencies and version availability"),
    (re.compile(r"(^|/)constants\.py$"), "defines shared constants used across the framework"),
    (re.compile(r"(^|/)helper\.py$"), "collects general-purpose helper utilities"),
    (re.compile(r"(^|/)data_collator\.py$"), "builds batches and collates model inputs"),
    (re.compile(r"(^|/)data_loader\.py$"), "builds or wraps dataloaders"),
    (re.compile(r"(^|/)dataset\.py$"), "defines dataset classes or dataset construction"),
    (re.compile(r"(^|/)base\.py$"), "defines base classes and shared abstractions"),
    (re.compile(r"(^|/)parser\.py$"), "parses CLI or configuration arguments"),
    (re.compile(r"arguments?_types\.py$"), "defines structured argument/configuration types"),
    (re.compile(r"run_.*\.py$"), "runs a command workflow or generation pipeline"),
    (re.compile(r"codegen\.py$"), "implements code generation logic"),
    (re.compile(r"check_.*\.py$"), "checks or validates generated artifacts"),
    (re.compile(r"modeling_.*\.py$"), "implements model architecture logic for a model variant"),
    (re.compile(r"configuration_.*\.py$"), "defines configuration for a model variant"),
    (re.compile(r"processing_.*\.py$"), "implements preprocessing/processor logic for a model variant"),
    (re.compile(r".*patch.*config\.py$"), "configures model patch generation"),
]

DIR_DESCRIPTIONS = {
    ".": "repository package root and top-level exports",
    "arguments": "argument dataclasses and parser utilities",
    "data": "dataset, dataloader, transform, and collator pipeline",
    "distributed": "distributed training primitives, parallel state, FSDP, sequence parallel, and communication utilities",
    "distributed/sequence_parallel": "sequence-parallel communication, Ulysses-style transforms, and related helpers",
    "models": "model loading, model wrappers, model variants, and patch integration",
    "models/transformers": "parallel HuggingFace-style model variant implementations and patch configs; summarize by pattern and inspect only representative variants",
    "models/seed_omni": "Seed-Omni model composition, auto-loading, configuration, processing, encoder/decoder/foundation components",
    "models/seed_omni/encoder": "encoder base abstractions and concrete encoder variants",
    "models/seed_omni/decoder": "decoder base abstractions and concrete decoder variants",
    "models/seed_omni/foundation": "foundation model base abstractions and concrete foundation variants",
    "ops": "custom operations and backend-specific acceleration hooks",
    "optim": "optimizer and learning-rate scheduler utilities",
    "patchgen": "patch generation and patch validation tooling",
    "trainer": "trainer base classes, task-specific trainers, and callbacks",
    "trainer/callbacks": "trainer callback implementations for tracing, evaluation, checkpoints, and lifecycle hooks",
    "utils": "shared utilities for logging, device handling, constants, environment, imports, and helpers",
}

MODEL_PATTERN_DIRS = {
    "models/transformers",
    "models/seed_omni/encoder",
    "models/seed_omni/decoder",
    "models/seed_omni/foundation",
}

MODEL_FILE_RE = re.compile(r"/(modeling_|configuration_|processing_).+\.py$|patch_gen_config\.py$")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def first_sentence(text: str) -> str:
    text = " ".join((text or "").strip().split())
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return parts[0].rstrip(".")[:180]


def describe_file(item: dict[str, Any], symbols: dict[str, Any]) -> str:
    path = item["path"]
    sym = symbols.get(path, {})
    doc = first_sentence(sym.get("top_level_docstring") or item.get("top_level_docstring") or "")
    if doc:
        return doc
    for regex, desc in NAME_DESCRIPTIONS:
        if regex.search(path):
            return desc
    roles = item.get("role_hints", [])
    if roles:
        descs = [ROLE_DESCRIPTIONS[r] for r in roles if r in ROLE_DESCRIPTIONS]
        if descs:
            return "; ".join(descs[:2])
    classes = item.get("classes") or sym.get("classes") or []
    funcs = item.get("functions") or sym.get("functions") or []
    if classes:
        return "exports core classes: " + ", ".join(classes[:3])
    if funcs:
        return "exports utility functions: " + ", ".join(funcs[:4])
    return "project file selected by dependency centrality"


def describe_dir(directory: str, files: list[dict[str, Any]]) -> str:
    if directory in DIR_DESCRIPTIONS:
        return DIR_DESCRIPTIONS[directory]
    leaf = directory.split("/")[-1] if directory != "." else "."
    role_counts = Counter(role for f in files for role in f.get("role_hints", []))
    if role_counts:
        top = ", ".join(role for role, _ in role_counts.most_common(3))
        return f"{leaf} folder containing {top} related files"
    return f"{leaf} folder containing related project files"


def model_pattern_parent(path: str) -> str | None:
    parts = path.split("/")
    # Fold models/transformers/<variant>/* into models/transformers/
    if len(parts) >= 4 and parts[0] == "models" and parts[1] == "transformers" and MODEL_FILE_RE.search(path):
        return "models/transformers"
    # Fold models/seed_omni/{encoder,decoder,foundation}/<variant>/* into parent group.
    if len(parts) >= 5 and parts[0] == "models" and parts[1] == "seed_omni" and parts[2] in {"encoder", "decoder", "foundation"}:
        if MODEL_FILE_RE.search(path) or parts[-1] == "base.py":
            return "/".join(parts[:3])
    return None


FILE_COLOR = "#2563eb"
SAMPLE_COLOR = "#7c3aed"


def html_code(text: str, color: str) -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f'<code style="color:{color}">{escaped}</code>'


def metric_badge(item: dict[str, Any]) -> str:
    return (
        f"`[importance:{item.get('importance', 0)} | "
        f"in:{item.get('used_by_count', 0)} | "
        f"out:{item.get('outgoing_count', 0)}]`"
    )


def folder_label(full_path: str) -> str:
    name = "." if full_path == "." else full_path.rstrip("/").split("/")[-1]
    return f"📁 **{name}/**"


def file_label(path: str) -> str:
    return f"📄 {html_code(Path(path).name, FILE_COLOR)}"


def sample_label(path: str) -> str:
    # Keep enough context for folded variants while avoiding full parent paths.
    parts = path.split("/")
    if len(parts) >= 2:
        return f"📝 {html_code(f'{parts[-2]}/{parts[-1]}', SAMPLE_COLOR)}"
    return f"📝 {html_code(Path(path).name, SAMPLE_COLOR)}"


def build_tree() -> dict[str, Any]:
    return {"dirs": {}, "files": [], "patterns": {}}


def add_dir_path(root: dict[str, Any], directory: str) -> dict[str, Any]:
    node = root
    if directory == ".":
        return node
    for part in directory.split("/"):
        node = node["dirs"].setdefault(part, build_tree())
    return node


def add_file(root: dict[str, Any], item: dict[str, Any]) -> None:
    path = item["path"]
    directory = str(Path(path).parent)
    node = add_dir_path(root, directory if directory != "." else ".")
    node["files"].append(item)


def add_pattern(root: dict[str, Any], parent_dir: str, item: dict[str, Any]) -> None:
    node = add_dir_path(root, parent_dir)
    variant = item["path"][len(parent_dir):].strip("/").split("/")[0]
    bucket = node["patterns"].setdefault("model_variants", {"variants": set(), "files": []})
    bucket["variants"].add(variant)
    bucket["files"].append(item)


def flatten_for_dir_descriptions(node: dict[str, Any]) -> list[dict[str, Any]]:
    out = list(node["files"])
    for pattern in node["patterns"].values():
        out.extend(pattern["files"])
    for child in node["dirs"].values():
        out.extend(flatten_for_dir_descriptions(child))
    return out


def render_directory_node(lines: list[str], name: str, node: dict[str, Any], full_path: str, depth: int) -> None:
    files_for_desc = flatten_for_dir_descriptions(node)
    if full_path != ".":
        indent = "  " * depth
        lines.append(f"{indent}- {folder_label(full_path)} — _{describe_dir(full_path, files_for_desc)}_")
        depth += 1

    for key, pattern in sorted(node["patterns"].items()):
        variants = sorted(pattern["variants"])
        indent = "  " * depth
        variant_preview = ", ".join(variants[:8]) + (f", ... +{len(variants) - 8}" if len(variants) > 8 else "")
        lines.append(
            f"{indent}- 📁 **{key}/** — _Repeated sibling model-variant structure; "
            f"summarize as a pattern instead of reading every variant. Variants: {variant_preview}_"
        )

    for child_name in sorted(node["dirs"]):
        child_path = child_name if full_path == "." else f"{full_path}/{child_name}"
        render_directory_node(lines, child_name, node["dirs"][child_name], child_path, depth)


def directory_graph_explanation() -> list[str]:
    return [
        "## Directory Dependency Graph Notes",
        "",
        "When paired with `directory_graph.mmd` / `mermaid_elk_render/directory_graph_elk.png`, interpret the directory graph as follows:",
        "",
        "- **Node**: one top-level package directory, aggregated from file-level static dependencies.",
        "- **Arrow direction**: `A → B` means files under directory `A` statically reference, import, or otherwise depend on files under directory `B`.",
        "- **Arrow number**: the label on an arrow is the aggregated count of file-level dependency edges from the source directory to the target directory after filtering/aggregation. Larger numbers indicate stronger static coupling.",
        "- **Orange node**: top/API-facing or orchestration directory where weighted outgoing dependency count is greater than weighted incoming dependency count (`out_weight > in_weight`).",
        "- **Blue node**: bottom/foundation or infrastructure directory where weighted incoming dependency count is greater than weighted outgoing dependency count (`in_weight > out_weight`).",
        "- **Purple node**: connector directory where weighted incoming and outgoing dependency counts are balanced (`in_weight == out_weight`).",
        "",
        "Note: this is a static dependency summary, not a complete runtime call graph. Dynamic imports, registry lookups, configuration-driven paths, and runtime dispatch may not be fully represented.",
    ]


def render_node(lines: list[str], name: str, node: dict[str, Any], full_path: str, symbols: dict[str, Any], depth: int) -> None:
    files_for_desc = flatten_for_dir_descriptions(node)
    if full_path != ".":
        indent = "  " * depth
        lines.append(f"{indent}- {folder_label(full_path)} — _{describe_dir(full_path, files_for_desc)}_")
        depth += 1

    for item in sorted(node["files"], key=lambda x: (-x.get("importance", 0), x["path"])):
        indent = "  " * depth
        desc = describe_file(item, symbols)
        lines.append(f"{indent}- {file_label(item['path'])} — _{desc.rstrip('.')}_ {metric_badge(item)}")

    for key, pattern in sorted(node["patterns"].items()):
        files = sorted(pattern["files"], key=lambda x: (-x.get("importance", 0), x["path"]))
        variants = sorted(pattern["variants"])
        sample_files = files[:3]
        indent = "  " * depth
        variant_preview = ", ".join(variants[:8]) + (f", ... +{len(variants) - 8}" if len(variants) > 8 else "")
        lines.append(
            f"{indent}- 📁 **{key}/** — _Repeated sibling model-variant structure; "
            f"summarize as a pattern instead of reading every variant. Variants: {variant_preview}_"
        )
        for item in sample_files:
            desc = describe_file(item, symbols)
            lines.append(f"{indent}  - {sample_label(item['path'])} — _{desc.rstrip('.')}_ {metric_badge(item)}")
        if len(files) > len(sample_files):
            lines.append(f"{indent}  - 📝 _omitted {len(files) - len(sample_files)} analogous core files under this repeated pattern_")

    for child_name in sorted(node["dirs"]):
        child_path = child_name if full_path == "." else f"{full_path}/{child_name}"
        render_node(lines, child_name, node["dirs"][child_name], child_path, symbols, depth)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render core files as worktree-style nested Markdown.")
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--directory-out", type=Path, default=None, help="Also write directory-only Markdown summary. Default: <artifact_dir>/core_directory.md")
    parser.add_argument("--skip-directory", action="store_true", help="Do not write core_directory.md")
    parser.add_argument("--top-n", type=int, default=40)
    parser.add_argument("--no-fold-model-patterns", action="store_true")
    args = parser.parse_args()

    artifact_dir = args.artifact_dir
    key_files = load(artifact_dir / "key_files.json")[: args.top_n]
    summary = {item["path"]: item for item in load(artifact_dir / "summary_input.json")}
    symbols = load(artifact_dir / "symbols.json")

    root = build_tree()
    for key in key_files:
        path = key["path"]
        item = dict(summary.get(path, {"path": path, "role_hints": key.get("role_hints", [])}))
        item["importance"] = key.get("importance", 0)
        item["used_by_count"] = key.get("used_by_count", 0)
        item["outgoing_count"] = key.get("outgoing_count", 0)
        parent = None if args.no_fold_model_patterns else model_pattern_parent(path)
        if parent:
            add_pattern(root, parent, item)
        else:
            add_file(root, item)

    lines = ["# Core File Summary", ""]
    lines.append("Core files selected from `key_files.json`; this worktree-style map preserves parent/child folders, displays each directory by its local folder name, and folds repeated model variants into sample-based pattern summaries.")
    lines.append("")
    lines.append("**Legend:** 📁 folder · 📄 file · 📝 representative sample / folded note · `[importance | in | out]` dependency-centrality metrics. File names use inline HTML color where supported by the Markdown renderer.")
    lines.append("")
    render_node(lines, ".", root, ".", symbols, depth=0)
    lines.append("")
    lines.append("Note: one-line descriptions are generated from docstrings, symbols, filenames, roles, and graph centrality. Repeated model folders are intentionally summarized by pattern; inspect only representative samples unless the user asks about a specific variant.")
    text = "\n".join(lines) + "\n"
    out = args.out or artifact_dir / "core_file.md"
    out.write_text(text, encoding="utf-8")
    print(f"Wrote: {out}")

    if not args.skip_directory:
        directory_lines = ["# Core Directory Summary", ""]
        directory_lines.append("Directory-only view extracted from the same selected core files used for `core_file.md`. It keeps the same folder Markdown style while omitting individual file entries.")
        directory_lines.append("")
        directory_lines.append("**Legend:** 📁 folder · descriptions are italicized. See the graph notes below for interpreting `directory_graph.mmd` / rendered images.")
        directory_lines.append("")
        render_directory_node(directory_lines, ".", root, ".", depth=0)
        directory_lines.append("")
        directory_lines.extend(directory_graph_explanation())
        directory_text = "\n".join(directory_lines) + "\n"
        directory_out = args.directory_out or artifact_dir / "core_directory.md"
        directory_out.write_text(directory_text, encoding="utf-8")
        print(f"Wrote: {directory_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
