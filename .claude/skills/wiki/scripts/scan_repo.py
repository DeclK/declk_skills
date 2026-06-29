#!/usr/bin/env python3
"""Build a DeepWiki-style static map for a repository.

Outputs JSON artifacts plus a deterministic Markdown draft. The graph is file-level
and static: it captures internal imports/references, not complete runtime calls.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", ".nox", ".venv", "venv", "env", "node_modules",
    "dist", "build", "site-packages", ".ipynb_checkpoints", "outputs", "output",
    "checkpoints", "checkpoint", "wandb", "logs", "log", ".wiki",
}
IGNORE_FILE_SUFFIXES = {
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".o", ".a", ".jpg", ".jpeg",
    ".png", ".gif", ".webp", ".pdf", ".zip", ".tar", ".gz", ".tgz", ".bz2",
    ".xz", ".7z", ".mp4", ".mov", ".avi", ".mp3", ".wav", ".pt", ".pth",
    ".safetensors", ".bin", ".onnx", ".parquet", ".arrow",
}
DEFAULT_EXTS = {
    ".py", ".sh", ".bash", ".zsh", ".md", ".rst", ".toml", ".yaml", ".yml",
    ".json", ".ini", ".cfg", ".txt", ".Dockerfile", "",
}
CONFIG_EXTS = {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg"}
DOC_EXTS = {".md", ".rst"}
SHELL_EXTS = {".sh", ".bash", ".zsh"}
ENTRY_NAME_RE = re.compile(r"^(main|run|train|eval|evaluate|infer|inference|serve|launch|cli)([_\-.].*)?\.py$")
PY_COMMAND_RE = re.compile(
    r"(?P<tool>python(?:\d(?:\.\d)?)?|torchrun|deepspeed|accelerate)"
    r"(?:\s+launch)?\s+(?P<target>(?:[\w./-]+\.py)|(?:-m\s+[A-Za-z_][\w.]*))"
)
LOCAL_MODULE_RE = re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){1,}\b")
LOCAL_PATH_RE = re.compile(r"(?P<path>[A-Za-z0-9_./-]+\.(?:py|ya?ml|json|toml|sh|md))")
ROLE_WEIGHTS = {
    "entrypoint": 10,
    "training": 8,
    "trainer": 8,
    "model": 8,
    "dataset": 7,
    "data-loading": 7,
    "data-collation": 6,
    "distributed": 7,
    "config": 5,
    "utility": 3,
    "script": 3,
    "documentation": -2,
    "test": -5,
}
IMPORTANT_NAME_RE = re.compile(
    r"(^|[/_\-.])(loader|registry|factory|auto|base|trainer|parser|arguments?|parallel_state|data_loader|dataset|collator|checkpoint|optimizer|scheduler|config|constants|device|env)([/_\-.]|$)",
    re.IGNORECASE,
)
LOW_PRIORITY_RE = re.compile(r"(^|/)(generated|tests?|examples?)/|(^|/)__init__\.py$|\.diff$", re.IGNORECASE)


@dataclass
class Edge:
    source: str
    target: str
    type: str
    symbols: list[str] = field(default_factory=list)
    line: int | None = None
    evidence: str = ""
    confidence: str = "high"

    def key(self) -> tuple[Any, ...]:
        return (self.source, self.target, self.type, tuple(self.symbols), self.line, self.evidence)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "confidence": self.confidence,
        }
        if self.symbols:
            data["symbols"] = self.symbols
        if self.line is not None:
            data["line"] = self.line
        if self.evidence:
            data["evidence"] = self.evidence.strip()[:300]
        return data


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def should_skip_dir(name: str) -> bool:
    return name in IGNORE_DIRS or name.endswith(".egg-info")


def is_interesting_file(path: Path) -> bool:
    if path.name in {"Dockerfile", "Makefile"}:
        return True
    if path.suffix in IGNORE_FILE_SUFFIXES:
        return False
    if path.stat().st_size > 2_000_000:
        return False
    return path.suffix in DEFAULT_EXTS or path.name.endswith("Dockerfile")


def discover_files(root: Path, max_files: int | None = None) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                if is_interesting_file(p):
                    files.append(p)
            except OSError:
                continue
            if max_files and len(files) >= max_files:
                return sorted(files)
    return sorted(files)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def line_at(text: str, lineno: int | None) -> str:
    if not lineno:
        return ""
    lines = text.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ""


def module_name_for_py(path: Path, root: Path) -> str | None:
    rp = path.relative_to(root)
    if path.name == "__init__.py":
        parts = rp.parts[:-1]
    else:
        parts = rp.with_suffix("").parts
    if not parts:
        return None
    if not all(re.match(r"^[A-Za-z_]\w*$", part) for part in parts):
        return None
    return ".".join(parts)


def build_module_index(py_files: Iterable[Path], root: Path) -> dict[str, str]:
    index: dict[str, str] = {}
    package_prefix = root.name if (root / "__init__.py").exists() and re.match(r"^[A-Za-z_]\w*$", root.name) else None
    for path in py_files:
        path_rel = rel(path, root)
        mod = module_name_for_py(path, root)
        if mod:
            index[mod] = path_rel
            if package_prefix:
                index[f"{package_prefix}.{mod}"] = path_rel
        elif package_prefix and path.name == "__init__.py" and path.parent == root:
            index[package_prefix] = path_rel
    return index


def package_for_file(path: Path, root: Path) -> str:
    rp = path.relative_to(root)
    parts = list(rp.parts[:-1])
    if path.name == "__init__.py" and parts:
        return ".".join(parts)
    return ".".join(p for p in parts if re.match(r"^[A-Za-z_]\w*$", p))


def resolve_module(module: str, module_index: dict[str, str]) -> tuple[str | None, str | None]:
    if not module:
        return None, None
    parts = module.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in module_index:
            return module_index[candidate], candidate
    return None, None


def resolve_relative_module(level: int, module: str | None, current_file: Path, root: Path, module_index: dict[str, str]) -> tuple[str | None, str | None]:
    pkg = package_for_file(current_file, root).split(".") if package_for_file(current_file, root) else []
    # ast ImportFrom level=1 means current package; level=2 means parent package.
    keep = len(pkg) - max(level - 1, 0)
    if keep < 0:
        keep = 0
    base = pkg[:keep]
    if module:
        base.extend(module.split("."))
    return resolve_module(".".join([p for p in base if p]), module_index)


def classify_kind(path: Path) -> str:
    name = path.name
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in SHELL_EXTS:
        return "shell"
    if suffix in DOC_EXTS or name.upper().startswith("README"):
        return "documentation"
    if suffix in CONFIG_EXTS:
        return "config"
    if name == "Dockerfile" or name.endswith("Dockerfile"):
        return "docker"
    if name == "Makefile":
        return "makefile"
    return "text"


def role_hints(path_str: str, kind: str, has_main: bool = False) -> list[str]:
    p = path_str.lower()
    name = Path(path_str).name.lower()
    roles: set[str] = set()
    if kind == "python" and (has_main or ENTRY_NAME_RE.match(name)):
        roles.add("entrypoint")
    if name.startswith("train") or "/train" in p:
        roles.add("training")
    if name.startswith(("eval", "evaluate")) or "/eval" in p:
        roles.add("evaluation")
    if name.startswith(("infer", "inference")):
        roles.add("inference")
    if name.startswith("serve") or "server" in name:
        roles.add("serving")
    if "dataset" in p:
        roles.add("dataset")
    if "dataloader" in p or "data_loader" in p:
        roles.add("data-loading")
    if "collator" in p:
        roles.add("data-collation")
    if "model" in p or "/models/" in p:
        roles.add("model")
    if "trainer" in p or "/trainer/" in p:
        roles.add("trainer")
    if "distributed" in p or "/distributed/" in p:
        roles.add("distributed")
    if "config" in p or kind == "config":
        roles.add("config")
    if "/utils/" in p or "/util/" in p or name.startswith("utils"):
        roles.add("utility")
    if p.startswith("tests/") or "/tests/" in p or name.startswith("test_"):
        roles.add("test")
    if kind == "shell":
        roles.add("script")
    if kind == "documentation":
        roles.add("documentation")
    if kind in {"docker", "makefile"}:
        roles.add("build")
    return sorted(roles)


def analyze_python(path: Path, root: Path, module_index: dict[str, str]) -> tuple[dict[str, Any], list[Edge]]:
    text = read_text(path)
    path_str = rel(path, root)
    result: dict[str, Any] = {
        "classes": [],
        "functions": [],
        "imports": [],
        "external_imports": [],
        "has_main_block": False,
        "uses_argparse_or_cli": False,
        "top_level_docstring": "",
    }
    edges: list[Edge] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        result["parse_error"] = str(exc)
        return result, edges

    result["top_level_docstring"] = (ast.get_docstring(tree) or "")[:500]

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(node.name)

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = ast.dump(node.test)
            if "__name__" in test and "__main__" in test:
                result["has_main_block"] = True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target, matched = resolve_module(alias.name, module_index)
                item = {"module": alias.name, "name": alias.asname, "line": node.lineno, "is_local": target is not None}
                result["imports"].append(item)
                if target:
                    edges.append(Edge(path_str, target, "import", line=node.lineno, evidence=line_at(text, node.lineno)))
                else:
                    result["external_imports"].append(alias.name.split(".")[0])
                if alias.name.split(".")[0] in {"argparse", "click", "typer", "fire"}:
                    result["uses_argparse_or_cli"] = True
        elif isinstance(node, ast.ImportFrom):
            symbols = [a.name for a in node.names if a.name != "*"]
            display_module = "." * node.level + (node.module or "")
            if node.level:
                target, matched = resolve_relative_module(node.level, node.module, path, root, module_index)
                edge_type = "relative_import" if not symbols else "symbol_import"
                absolute_base = matched
            else:
                target, matched = resolve_module(node.module or "", module_index)
                edge_type = "import" if not symbols else "symbol_import"
                absolute_base = node.module

            resolved_targets: list[tuple[str, list[str]]] = []
            if symbols and absolute_base:
                unresolved_symbols: list[str] = []
                for sym_name in symbols:
                    sub_target, _ = resolve_module(f"{absolute_base}.{sym_name}", module_index)
                    if sub_target:
                        resolved_targets.append((sub_target, [sym_name]))
                    else:
                        unresolved_symbols.append(sym_name)
                if target and unresolved_symbols:
                    resolved_targets.append((target, unresolved_symbols))
            elif target:
                resolved_targets.append((target, symbols))

            item = {
                "module": display_module,
                "symbols": symbols or ["*"],
                "line": node.lineno,
                "is_local": bool(resolved_targets),
            }
            result["imports"].append(item)
            if resolved_targets:
                for resolved_target, resolved_symbols in resolved_targets:
                    edges.append(Edge(path_str, resolved_target, edge_type, symbols=resolved_symbols, line=node.lineno, evidence=line_at(text, node.lineno)))
            elif node.module:
                result["external_imports"].append(node.module.split(".")[0])
                # Suspicious local-looking unresolved imports get a low-confidence edge to module name.
                if node.module.split(".")[0] in {m.split(".")[0] for m in module_index}:
                    edges.append(Edge(path_str, node.module, "unresolved_import", symbols=symbols, line=node.lineno, evidence=line_at(text, node.lineno), confidence="low"))
            if (node.module or "").split(".")[0] in {"argparse", "click", "typer", "fire"}:
                result["uses_argparse_or_cli"] = True
    result["external_imports"] = sorted(set(result["external_imports"]))
    return result, edges


def target_from_script_token(token: str, root: Path, files_set: set[str], module_index: dict[str, str]) -> tuple[str | None, str]:
    token = token.strip().strip("'\"")
    if token.startswith("-m "):
        module = token[3:].strip()
        target, _ = resolve_module(module, module_index)
        return target, "module_invocation"
    if token.endswith(".py"):
        cleaned = token.lstrip("./")
        if cleaned in files_set:
            return cleaned, "script_invocation"
        # Match by suffix for commands run from subdirectories.
        matches = [f for f in files_set if f.endswith("/" + cleaned) or f == cleaned]
        if len(matches) == 1:
            return matches[0], "script_invocation"
    return None, "script_invocation"


def analyze_text_references(path: Path, root: Path, files_set: set[str], module_index: dict[str, str], kind: str) -> list[Edge]:
    text = read_text(path)
    path_str = rel(path, root)
    edges: list[Edge] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in PY_COMMAND_RE.finditer(line):
            target, edge_type = target_from_script_token(m.group("target"), root, files_set, module_index)
            if target and target != path_str:
                if kind == "documentation":
                    edge_type = "markdown_command_reference"
                edges.append(Edge(path_str, target, edge_type, line=lineno, evidence=line.strip(), confidence="high"))
        if kind in {"config", "documentation", "python"}:
            for m in LOCAL_PATH_RE.finditer(line):
                candidate = m.group("path").lstrip("./")
                if candidate in files_set and candidate != path_str:
                    edge_type = "config_reference" if kind == "config" else "string_path_reference"
                    conf = "medium" if kind == "config" else "low"
                    edges.append(Edge(path_str, candidate, edge_type, line=lineno, evidence=line.strip(), confidence=conf))
            if kind == "config":
                for m in LOCAL_MODULE_RE.finditer(line):
                    target, _ = resolve_module(m.group(0), module_index)
                    if target and target != path_str:
                        edges.append(Edge(path_str, target, "config_reference", line=lineno, evidence=line.strip(), confidence="medium"))
    return edges


def dedupe_edges(edges: Iterable[Edge]) -> list[Edge]:
    seen: set[tuple[Any, ...]] = set()
    out: list[Edge] = []
    for edge in edges:
        k = edge.key()
        if k not in seen:
            seen.add(k)
            out.append(edge)
    return sorted(out, key=lambda e: (e.source, e.target, e.type, e.line or 0))


def entrypoint_score(file_info: dict[str, Any], symbol_info: dict[str, Any], incoming_edges: list[dict[str, Any]]) -> dict[str, Any] | None:
    path = file_info["path"]
    name = Path(path).name.lower()
    score = 0
    signals: list[str] = []
    if symbol_info.get("has_main_block"):
        score += 4
        signals.append("has __main__ block")
    if name == "main.py":
        score += 3
        signals.append("filename is main.py")
    if ENTRY_NAME_RE.match(name):
        score += 3
        signals.append("entrypoint-like filename")
    if "main" in symbol_info.get("functions", []):
        score += 2
        signals.append("defines main()")
    if symbol_info.get("uses_argparse_or_cli"):
        score += 2
        signals.append("uses argparse/click/typer/fire")
    script_edges = [e for e in incoming_edges if e.get("type") in {"script_invocation", "module_invocation"}]
    doc_edges = [e for e in incoming_edges if e.get("type") == "markdown_command_reference"]
    if script_edges:
        score += 4
        signals.append("called by shell/script command")
    if doc_edges:
        score += 3
        signals.append("referenced by documentation command")
    if path.startswith("scripts/"):
        score += 1
        signals.append("located in scripts/")
    if score <= 0:
        return None
    likely_command = None
    for e in script_edges + doc_edges:
        ev = e.get("evidence", "")
        if ev:
            likely_command = ev
            break
    strength = "strong" if score >= 7 else "possible" if score >= 4 else "weak"
    return {"path": path, "score": score, "strength": strength, "signals": signals, "likely_command": likely_command}


def compute_key_files(
    file_infos: list[dict[str, Any]],
    edge_dicts: list[dict[str, Any]],
    entrypoints: list[dict[str, Any]],
    symbols: dict[str, Any],
    limit: int = 80,
) -> list[dict[str, Any]]:
    """Rank files that deserve selective deep reading.

    The score intentionally favors entrypoints, high reverse-dependency count,
    orchestrators with many outgoing dependencies, and semantically important
    filenames such as loader/base/registry/trainer/parser. It penalizes generated,
    test, and simple export files so repeated folders can be summarized by pattern.
    """
    incoming_counts = Counter(e["target"] for e in edge_dicts if e.get("confidence") != "low")
    outgoing_counts = Counter(e["source"] for e in edge_dicts if e.get("confidence") != "low")
    ep_scores = {ep["path"]: ep["score"] for ep in entrypoints}
    ep_signals = {ep["path"]: ep["signals"] for ep in entrypoints}
    ranked: list[dict[str, Any]] = []

    for info in file_infos:
        path = info["path"]
        roles = info.get("role_hints", [])
        sym = symbols.get(path, {})
        score = 0
        reasons: list[str] = []

        if path in ep_scores:
            value = ep_scores[path] * 3
            score += value
            reasons.append(f"entrypoint score {ep_scores[path]}: {', '.join(ep_signals.get(path, [])[:3])}")

        in_count = incoming_counts.get(path, 0)
        out_count = outgoing_counts.get(path, 0)
        if in_count:
            score += in_count * 2
            reasons.append(f"used by {in_count} internal edges")
        if out_count:
            score += out_count
            reasons.append(f"uses {out_count} internal edges")

        for role in roles:
            weight = ROLE_WEIGHTS.get(role, 0)
            if weight:
                score += weight
                reasons.append(f"role hint: {role} ({weight:+d})")

        if IMPORTANT_NAME_RE.search(path):
            score += 8
            reasons.append("important filename pattern")

        if sym.get("classes"):
            score += min(len(sym["classes"]), 5)
            reasons.append(f"exports {len(sym['classes'])} classes")
        if sym.get("functions"):
            score += min(len(sym["functions"]), 6)
            reasons.append(f"exports {len(sym['functions'])} functions")

        if LOW_PRIORITY_RE.search(path):
            score -= 10
            reasons.append("lower priority generated/test/__init__ pattern")

        if info.get("kind") not in {"python", "shell", "config", "documentation"}:
            score -= 5

        if score > 0:
            ranked.append({
                "path": path,
                "importance": score,
                "used_by_count": in_count,
                "outgoing_count": out_count,
                "role_hints": roles,
                "reasons": reasons[:8],
                "suggested_action": "deep-read" if score >= 40 else "skim or use for directory summary",
            })

    ranked.sort(key=lambda x: (-x["importance"], x["path"]))
    return ranked[:limit]


def compute_directory_summaries(file_infos: list[dict[str, Any]], key_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key_set = {item["path"] for item in key_files[:80]}
    dirs: dict[str, dict[str, Any]] = {}
    for info in file_infos:
        path = info["path"]
        directory = str(Path(path).parent).replace(".", "") or "."
        if directory == "":
            directory = "."
        item = dirs.setdefault(directory, {
            "directory": directory,
            "file_count": 0,
            "kinds": Counter(),
            "roles": Counter(),
            "sample_files": [],
            "key_files": [],
            "summarization_strategy": "directory-level summary",
        })
        item["file_count"] += 1
        item["kinds"][info.get("kind", "unknown")] += 1
        for role in info.get("role_hints", []):
            item["roles"][role] += 1
        if len(item["sample_files"]) < 5 and not LOW_PRIORITY_RE.search(path):
            item["sample_files"].append(path)
        if path in key_set and len(item["key_files"]) < 8:
            item["key_files"].append(path)

    out = []
    for item in dirs.values():
        repeated = item["file_count"] >= 8 and (
            item["roles"].get("model", 0) >= 4
            or item["roles"].get("config", 0) >= 4
            or "generated" in item["directory"].split("/")
        )
        if repeated:
            item["summarization_strategy"] = "summarize pattern; deep-read representative samples only"
        item["kinds"] = dict(item["kinds"].most_common())
        item["roles"] = dict(item["roles"].most_common())
        out.append(item)
    out.sort(key=lambda x: (x["directory"].count("/"), x["directory"]))
    return out


def summarize_directory(files: list[str]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for f in files:
        parts = f.split("/")
        cur = tree
        for part in parts:
            cur = cur.setdefault(part, {})
    return tree


def render_tree(paths: list[str], max_entries: int = 500) -> str:
    # Deterministic compact tree that preserves directory names.
    limited = paths[:max_entries]
    root_node: dict[str, Any] = {}
    for path in limited:
        cur = root_node
        for part in path.split("/"):
            cur = cur.setdefault(part, {})

    lines: list[str] = []

    def walk(node: dict[str, Any], depth: int) -> None:
        for name in sorted(node):
            suffix = "/" if node[name] else ""
            lines.append("  " * depth + f"- {name}{suffix}")
            if node[name]:
                walk(node[name], depth + 1)

    walk(root_node, 0)
    if len(paths) > max_entries:
        lines.append(f"... ({len(paths) - max_entries} more files)")
    return "\n".join(lines)


def render_report(
    root: Path,
    file_infos: list[dict[str, Any]],
    graph: dict[str, Any],
    reverse: dict[str, list[dict[str, Any]]],
    entrypoints: list[dict[str, Any]],
    symbols: dict[str, Any],
    key_files: list[dict[str, Any]],
    directory_summaries: list[dict[str, Any]],
) -> str:
    paths = [f["path"] for f in file_infos]
    incoming_counts = Counter(edge["target"] for edge in graph["edges"] if edge.get("confidence") != "low")
    outgoing_counts = Counter(edge["source"] for edge in graph["edges"] if edge.get("confidence") != "low")
    hotspots = incoming_counts.most_common(20)
    lines: list[str] = []
    lines.append("# Project DeepWiki Draft")
    lines.append("")
    lines.append(f"Repository: `{root}`")
    lines.append(f"Files scanned: {len(file_infos)}")
    lines.append(f"Internal edges: {len(graph['edges'])}")
    lines.append("")
    lines.append("## Top-Level File Tree")
    lines.append("")
    lines.append("```text")
    lines.append(render_tree(paths))
    lines.append("```")
    lines.append("")
    lines.append("## Entry Point Candidates")
    lines.append("")
    if entrypoints:
        lines.append("| File | Score | Strength | Signals |")
        lines.append("|---|---:|---|---|")
        for ep in entrypoints[:30]:
            lines.append(f"| `{ep['path']}` | {ep['score']} | {ep['strength']} | {'; '.join(ep['signals'])} |")
    else:
        lines.append("No entrypoint candidates detected.")
    lines.append("")
    lines.append("## Dependency Hotspots")
    lines.append("")
    if hotspots:
        lines.append("| File | Used By Count | Outgoing Dependencies |")
        lines.append("|---|---:|---:|")
        for path, count in hotspots:
            lines.append(f"| `{path}` | {count} | {outgoing_counts.get(path, 0)} |")
    else:
        lines.append("No internal dependencies detected.")
    lines.append("")
    lines.append("## Key Files Recommended for Deep Reading")
    lines.append("")
    if key_files:
        lines.append("Use this section to avoid reading every file. Deep-read the top files, skim medium-priority files, and summarize repeated directories by pattern.")
        lines.append("")
        lines.append("| File | Importance | Used By | Uses | Suggested Action | Reasons |")
        lines.append("|---|---:|---:|---:|---|---|")
        for item in key_files[:30]:
            reasons = "; ".join(item.get("reasons", [])[:4]).replace("|", "\\|")
            lines.append(f"| `{item['path']}` | {item['importance']} | {item['used_by_count']} | {item['outgoing_count']} | {item['suggested_action']} | {reasons} |")
    else:
        lines.append("No key files ranked.")
    lines.append("")
    lines.append("## Directory-Level Summarization Plan")
    lines.append("")
    lines.append("| Directory | Files | Dominant Roles | Strategy | Representative Files |")
    lines.append("|---|---:|---|---|---|")
    for item in directory_summaries[:80]:
        roles = ", ".join(f"{k}:{v}" for k, v in list(item.get("roles", {}).items())[:4]) or "-"
        samples = ", ".join(f"`{p}`" for p in (item.get("key_files") or item.get("sample_files") or [])[:4]) or "-"
        lines.append(f"| `{item['directory']}` | {item['file_count']} | {roles} | {item['summarization_strategy']} | {samples} |")
    lines.append("")
    lines.append("## Key File Connections")
    lines.append("")
    connection_files = [item["path"] for item in key_files[:12]] + [ep["path"] for ep in entrypoints[:10]] + [p for p, _ in hotspots[:10]]
    seen: set[str] = set()
    for path in connection_files:
        if path in seen:
            continue
        seen.add(path)
        uses = [e for e in graph["edges"] if e["source"] == path and e.get("confidence") != "low"][:15]
        used_by = reverse.get(path, [])[:15]
        sym = symbols.get(path, {})
        lines.append(f"### `{path}`")
        if sym.get("classes") or sym.get("functions"):
            exports = sym.get("classes", [])[:8] + sym.get("functions", [])[:12]
            lines.append(f"Exports: {', '.join('`' + x + '`' for x in exports)}")
        if uses:
            lines.append("Uses:")
            for e in uses:
                label = f" ({', '.join(e.get('symbols', []))})" if e.get("symbols") else ""
                lines.append(f"- `{e['target']}` via `{e['type']}`{label}")
        if used_by:
            lines.append("Used by:")
            for e in used_by:
                lines.append(f"- `{e['source']}` via `{e['type']}`")
        lines.append("")
    lines.append("## Suggested Reading Order")
    lines.append("")
    order = []
    for ep in entrypoints[:5]:
        order.append(ep["path"])
        order.extend([e["target"] for e in graph["edges"] if e["source"] == ep["path"] and e.get("confidence") != "low"][:5])
    order.extend([item["path"] for item in key_files[:25]])
    order.extend([p for p, _ in hotspots[:10]])
    unique_order = []
    for p in order:
        if p not in unique_order:
            unique_order.append(p)
    for i, p in enumerate(unique_order[:30], 1):
        lines.append(f"{i}. `{p}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("Graph visualization files can be generated with `scripts/render_graph.py` from `graph.json`.")
    lines.append("This is a static file-level graph. Dynamic imports, runtime dispatch, monkey patching, and config-driven factory calls may be incomplete.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate static DeepWiki artifacts for a repository.")
    parser.add_argument("repo_root", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--max-files", type=int, default=None)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"repo_root is not a directory: {root}")
    out = (args.out or (root / ".wiki")).resolve()
    out.mkdir(parents=True, exist_ok=True)

    files = discover_files(root, args.max_files)
    files_set = {rel(p, root) for p in files}
    py_files = [p for p in files if p.suffix == ".py"]
    module_index = build_module_index(py_files, root)

    file_infos: list[dict[str, Any]] = []
    symbols: dict[str, Any] = {}
    all_edges: list[Edge] = []

    for path in files:
        path_str = rel(path, root)
        kind = classify_kind(path)
        stat = path.stat()
        sym: dict[str, Any] = {}
        edges: list[Edge] = []
        if kind == "python":
            sym, edges = analyze_python(path, root, module_index)
            all_edges.extend(edges)
            all_edges.extend(analyze_text_references(path, root, files_set, module_index, kind))
        elif kind in {"shell", "documentation", "config"}:
            all_edges.extend(analyze_text_references(path, root, files_set, module_index, kind))
        has_main = bool(sym.get("has_main_block"))
        info = {
            "path": path_str,
            "kind": kind,
            "size_bytes": stat.st_size,
            "size_lines": read_text(path).count("\n") + 1 if stat.st_size < 2_000_000 else None,
            "role_hints": role_hints(path_str, kind, has_main),
        }
        file_infos.append(info)
        if sym:
            symbols[path_str] = sym

    all_edges = dedupe_edges(all_edges)
    edge_dicts = [e.to_dict() for e in all_edges]
    nodes = [
        {"path": info["path"], "kind": info["kind"], "role_hints": info["role_hints"]}
        for info in file_infos
    ]
    graph = {"nodes": nodes, "edges": edge_dicts}
    reverse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in edge_dicts:
        reverse[e["target"]].append(e)
    reverse = {k: sorted(v, key=lambda x: (x["source"], x.get("line", 0))) for k, v in sorted(reverse.items())}

    entrypoints = []
    for info in file_infos:
        ep = entrypoint_score(info, symbols.get(info["path"], {}), reverse.get(info["path"], []))
        if ep:
            entrypoints.append(ep)
    entrypoints.sort(key=lambda x: (-x["score"], x["path"]))

    key_files = compute_key_files(file_infos, edge_dicts, entrypoints, symbols)
    directory_summaries = compute_directory_summaries(file_infos, key_files)

    summary_input = []
    used_by_counts = Counter(e["target"] for e in edge_dicts if e.get("confidence") != "low")
    for info in file_infos:
        path = info["path"]
        local_imports = [e["target"] for e in edge_dicts if e["source"] == path and e.get("confidence") != "low"]
        used_by = [e["source"] for e in reverse.get(path, []) if e.get("confidence") != "low"]
        sym = symbols.get(path, {})
        summary_input.append({
            "path": path,
            "kind": info["kind"],
            "role_hints": info["role_hints"],
            "size_lines": info.get("size_lines"),
            "imports_local": sorted(set(local_imports)),
            "used_by": sorted(set(used_by)),
            "used_by_count": used_by_counts.get(path, 0),
            "classes": sym.get("classes", []),
            "functions": sym.get("functions", []),
            "top_level_docstring": sym.get("top_level_docstring", ""),
            "external_imports": sym.get("external_imports", []),
        })

    outputs = {
        "files.json": file_infos,
        "module_index.json": module_index,
        "symbols.json": symbols,
        "graph.json": graph,
        "reverse_graph.json": reverse,
        "entrypoints.json": entrypoints,
        "key_files.json": key_files,
        "directory_summaries.json": directory_summaries,
        "summary_input.json": summary_input,
    }
    for name, data in outputs.items():
        (out / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = render_report(root, file_infos, graph, reverse, entrypoints, symbols, key_files, directory_summaries)
    (out / "WIKI.draft.md").write_text(report, encoding="utf-8")

    print(f"Scanned {len(file_infos)} files")
    print(f"Internal edges: {len(edge_dicts)}")
    print(f"Entrypoints: {len(entrypoints)}")
    print(f"Wrote artifacts to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
