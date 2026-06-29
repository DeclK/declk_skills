#!/usr/bin/env python3
"""Render wiki graph artifacts as Mermaid or Graphviz DOT.

Examples:
  render_graph.py .wiki --mode directory --format mermaid --out directory_graph.mmd
  render_graph.py .wiki --mode core --top-n 30 --format dot --out core_graph.dot
  render_graph.py .wiki --mode neighborhood --node trainer/base.py --depth 1 --direction both
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def confidence_ok(edge: dict[str, Any], min_confidence: str) -> bool:
    order = {"low": 0, "medium": 1, "high": 2}
    return order.get(edge.get("confidence", "high"), 2) >= order[min_confidence]


def is_hidden(path: str, show_hidden: bool) -> bool:
    if show_hidden:
        return False
    return bool(re.search(r"(^|/)(generated|tests?|__pycache__)/|(^|/)__init__\.py$|\.diff$", path))


def top_dir(path: str, depth: int = 1) -> str:
    parts = path.split("/")
    if len(parts) <= depth:
        return parts[0] if len(parts) == 1 else "/".join(parts[:depth])
    return "/".join(parts[:depth]) + "/"


def sanitize_id(label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", label)
    if not safe or safe[0].isdigit():
        safe = "n_" + safe
    return safe[:120]


def edge_weight(label: str) -> int:
    try:
        return int(label)
    except (TypeError, ValueError):
        return 1


def node_roles(nodes: set[str], edges: list[tuple[str, str, str]]) -> dict[str, str]:
    """Classify nodes by weighted in/out degree.

    Top/API-facing modules tend to depend on many lower modules, so out_weight >
    in_weight. Bottom/foundation modules are depended on by many modules, so
    in_weight > out_weight. Near-equal nodes are connectors.
    """
    incoming: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    for src, dst, label in edges:
        if src not in nodes or dst not in nodes or src == dst:
            continue
        w = edge_weight(label)
        outgoing[src] += w
        incoming[dst] += w
    roles = {}
    for node in nodes:
        in_w = incoming[node]
        out_w = outgoing[node]
        if out_w > in_w:
            roles[node] = "top"
        elif in_w > out_w:
            roles[node] = "bottom"
        else:
            roles[node] = "connector"
    return roles


def mermaid(nodes: set[str], edges: list[tuple[str, str, str]], direction: str = "TD", style_roles: bool = True) -> str:
    lines = [f"graph {direction}"]
    ids = {node: sanitize_id(node) for node in sorted(nodes)}
    roles = node_roles(nodes, edges) if style_roles else {}
    for node in sorted(nodes):
        label = node.replace('"', "'")
        lines.append(f'  {ids[node]}["{label}"]')
    for src, dst, label in edges:
        if src not in ids or dst not in ids or src == dst:
            continue
        edge_label = f"|{label}|" if label else ""
        lines.append(f"  {ids[src]} -->{edge_label} {ids[dst]}")
    if style_roles and nodes:
        lines.extend([
            "  classDef top fill:#FFF7ED,stroke:#F59E0B,color:#111827,stroke-width:2px;",
            "  classDef bottom fill:#EFF6FF,stroke:#2563EB,color:#111827,stroke-width:2px;",
            "  classDef connector fill:#F5F3FF,stroke:#7C3AED,color:#111827,stroke-width:2px;",
        ])
        for role in ("top", "bottom", "connector"):
            role_ids = [ids[n] for n in sorted(nodes) if roles.get(n) == role]
            if role_ids:
                lines.append(f"  class {','.join(role_ids)} {role};")
    return "\n".join(lines) + "\n"


def dot(nodes: set[str], edges: list[tuple[str, str, str]]) -> str:
    lines = ["digraph G {", "  rankdir=LR;", "  node [shape=box, style=rounded];"]
    for node in sorted(nodes):
        lines.append(f'  "{node}";')
    for src, dst, label in edges:
        if src not in nodes or dst not in nodes or src == dst:
            continue
        label_attr = f' [label="{label}"]' if label else ""
        lines.append(f'  "{src}" -> "{dst}"{label_attr};')
    lines.append("}")
    return "\n".join(lines) + "\n"


def json_graph(nodes: set[str], edges: list[tuple[str, str, str]]) -> str:
    return json.dumps({
        "nodes": [{"id": node} for node in sorted(nodes)],
        "edges": [{"source": s, "target": t, "type": label} for s, t, label in edges if s in nodes and t in nodes and s != t],
    }, indent=2, ensure_ascii=False) + "\n"


def render(nodes: set[str], edges: list[tuple[str, str, str]], fmt: str, style_roles: bool = True) -> str:
    if fmt == "mermaid":
        return mermaid(nodes, edges, style_roles=style_roles)
    if fmt == "dot":
        return dot(nodes, edges)
    if fmt == "json":
        return json_graph(nodes, edges)
    raise ValueError(fmt)


def select_edges(graph: dict[str, Any], min_confidence: str, show_hidden: bool) -> list[dict[str, Any]]:
    out = []
    for edge in graph.get("edges", []):
        if not confidence_ok(edge, min_confidence):
            continue
        if is_hidden(edge["source"], show_hidden) or is_hidden(edge["target"], show_hidden):
            continue
        out.append(edge)
    return out


def directory_graph(edges: list[dict[str, Any]], depth: int, min_edges: int) -> tuple[set[str], list[tuple[str, str, str]]]:
    counts: Counter[tuple[str, str]] = Counter()
    for edge in edges:
        src = top_dir(edge["source"], depth)
        dst = top_dir(edge["target"], depth)
        if src != dst:
            counts[(src, dst)] += 1
    rendered = [(s, d, str(c)) for (s, d), c in counts.items() if c >= min_edges]
    nodes = {x for edge in rendered for x in edge[:2]}
    rendered.sort(key=lambda x: (-int(x[2]), x[0], x[1]))
    return nodes, rendered


def core_graph(edges: list[dict[str, Any]], key_files: list[dict[str, Any]], top_n: int) -> tuple[set[str], list[tuple[str, str, str]]]:
    incoming = Counter(e["target"] for e in edges)
    nodes = {item["path"] for item in key_files[:top_n]}
    if not nodes:
        nodes = {path for path, _ in incoming.most_common(top_n)}
    rendered = []
    for edge in edges:
        if edge["source"] in nodes and edge["target"] in nodes and edge["source"] != edge["target"]:
            rendered.append((edge["source"], edge["target"], edge.get("type", "")))
    rendered = sorted(set(rendered), key=lambda x: (x[0], x[1], x[2]))
    return nodes, rendered


def neighborhood_graph(edges: list[dict[str, Any]], node: str, depth: int, direction: str) -> tuple[set[str], list[tuple[str, str, str]]]:
    out_adj: dict[str, list[dict[str, Any]]] = defaultdict(list)
    in_adj: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        out_adj[edge["source"]].append(edge)
        in_adj[edge["target"]].append(edge)
    seen = {node}
    q = deque([(node, 0)])
    while q:
        cur, dist = q.popleft()
        if dist >= depth:
            continue
        next_edges = []
        if direction in {"out", "both"}:
            next_edges.extend(out_adj.get(cur, []))
        if direction in {"in", "both"}:
            next_edges.extend(in_adj.get(cur, []))
        for edge in next_edges:
            other = edge["target"] if edge["source"] == cur else edge["source"]
            if other not in seen:
                seen.add(other)
                q.append((other, dist + 1))
    rendered = []
    for edge in edges:
        if edge["source"] in seen and edge["target"] in seen:
            rendered.append((edge["source"], edge["target"], edge.get("type", "")))
    return seen, sorted(set(rendered), key=lambda x: (x[0], x[1], x[2]))


def full_graph(edges: list[dict[str, Any]], max_nodes: int) -> tuple[set[str], list[tuple[str, str, str]]]:
    incoming = Counter(e["target"] for e in edges)
    outgoing = Counter(e["source"] for e in edges)
    score = incoming + outgoing
    nodes = {path for path, _ in score.most_common(max_nodes)}
    rendered = [(e["source"], e["target"], e.get("type", "")) for e in edges if e["source"] in nodes and e["target"] in nodes]
    return nodes, sorted(set(rendered), key=lambda x: (x[0], x[1], x[2]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render wiki graph artifacts.")
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--mode", choices=["directory", "core", "neighborhood", "full"], default="directory")
    parser.add_argument("--format", choices=["mermaid", "dot", "json"], default="mermaid")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--node", default=None, help="Repository-relative file path for neighborhood mode.")
    parser.add_argument("--depth", type=int, default=1, help="Directory aggregation depth or neighborhood BFS depth.")
    parser.add_argument("--direction", choices=["out", "in", "both"], default="both")
    parser.add_argument("--min-confidence", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--min-edges", type=int, default=1, help="Minimum aggregated edge count for directory mode.")
    parser.add_argument("--show-hidden", action="store_true", help="Include tests, generated files, and __init__.py nodes.")
    parser.add_argument("--max-nodes", type=int, default=80, help="Node cap for full mode.")
    parser.add_argument("--no-role-styles", action="store_true", help="Disable Mermaid node coloring by weighted in/out degree.")
    args = parser.parse_args()

    artifact_dir = args.artifact_dir
    graph = load_json(artifact_dir / "graph.json")
    key_path = artifact_dir / "key_files.json"
    key_files = load_json(key_path) if key_path.exists() else []
    edges = select_edges(graph, args.min_confidence, args.show_hidden)

    if args.mode == "directory":
        nodes, rendered_edges = directory_graph(edges, args.depth, args.min_edges)
    elif args.mode == "core":
        nodes, rendered_edges = core_graph(edges, key_files, args.top_n)
    elif args.mode == "neighborhood":
        if not args.node:
            raise SystemExit("--node is required for neighborhood mode")
        nodes, rendered_edges = neighborhood_graph(edges, args.node, args.depth, args.direction)
    else:
        nodes, rendered_edges = full_graph(edges, args.max_nodes)

    output = render(nodes, rendered_edges, args.format, style_roles=not args.no_role_styles)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    print(f"Rendered {len(nodes)} nodes and {len(rendered_edges)} edges", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
