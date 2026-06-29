#!/usr/bin/env python3
"""Render a Mermaid graph file to SVG/PNG with Mermaid CLI using ELK layout.

This intentionally uses Mermaid's renderer directly. It creates a small local
render workspace under the artifact directory, installs @mermaid-js/mermaid-cli
if needed, and renders the input .mmd with `flowchart.defaultRenderer=elk`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

DEFAULT_CONFIG = {
    "startOnLoad": False,
    "securityLevel": "loose",
    "theme": "base",
    "layout": "elk",
    "elk": {
        "mergeEdges": False,
        "nodePlacementStrategy": "BRANDES_KOEPF",
    },
    "themeVariables": {
        "background": "#ffffff",
        "primaryColor": "#eff6ff",
        "primaryTextColor": "#111827",
        "primaryBorderColor": "#2563eb",
        "lineColor": "#475569",
        "secondaryColor": "#fff7ed",
        "tertiaryColor": "#f5f3ff",
        "fontFamily": "Noto Sans CJK SC, Noto Sans CJK, Noto Color Emoji, DejaVu Sans, Arial, sans-serif",
        "fontSize": "18px",
    },
    "flowchart": {
        "defaultRenderer": "elk",
        "curve": "basis",
        "nodeSpacing": 70,
        "rankSpacing": 95,
        "htmlLabels": True,
        "useMaxWidth": False,
    },
}

PUPPETEER_CONFIG = {
    "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
}

PACKAGE_JSON = {
    "name": "wiki-mermaid-elk-render",
    "version": "1.0.0",
    "private": True,
    "type": "module",
    "dependencies": {"@mermaid-js/mermaid-cli": "^11.15.0"},
}


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_cli(work_dir: Path) -> Path:
    local = work_dir / "node_modules" / ".bin" / "mmdc"
    if local.exists():
        return local
    system = shutil.which("mmdc")
    if system:
        return Path(system)
    if not shutil.which("npm"):
        raise SystemExit("mmdc not found and npm is not available; install @mermaid-js/mermaid-cli first")
    subprocess.run(["npm", "install"], cwd=work_dir, check=True)
    if not local.exists():
        raise SystemExit(f"Mermaid CLI install did not create {local}")
    return local


def render_one(mmdc: Path, input_file: Path, output_file: Path, config: Path, puppeteer: Path, width: int, height: int) -> None:
    subprocess.run(
        [
            str(mmdc),
            "-i", str(input_file),
            "-o", str(output_file),
            "-c", str(config),
            "-p", str(puppeteer),
            "-b", "white",
            "-w", str(width),
            "-H", str(height),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Mermaid .mmd with Mermaid CLI + ELK layout.")
    parser.add_argument("input", type=Path, help="Input Mermaid .mmd file, e.g. .wiki/directory_graph.mmd")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output workspace. Default: <artifact_dir>/mermaid_elk_render")
    parser.add_argument("--stem", default=None, help="Output file stem. Default: input stem + '_elk'")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--no-png", action="store_true")
    parser.add_argument("--no-svg", action="store_true")
    args = parser.parse_args()

    input_file = args.input.resolve()
    if not input_file.exists():
        raise SystemExit(f"Input not found: {input_file}")
    out_dir = args.out_dir or input_file.parent / "mermaid_elk_render"
    out_dir.mkdir(parents=True, exist_ok=True)

    config = out_dir / "mermaid-config.json"
    puppeteer = out_dir / "puppeteer-config.json"
    package_json = out_dir / "package.json"
    render_sh = out_dir / "render.sh"
    write_json(config, DEFAULT_CONFIG)
    write_json(puppeteer, PUPPETEER_CONFIG)
    write_json(package_json, PACKAGE_JSON)

    mmdc = ensure_cli(out_dir)
    stem = args.stem or f"{input_file.stem}_elk"
    outputs = []
    if not args.no_svg:
        svg = out_dir / f"{stem}.svg"
        render_one(mmdc, input_file, svg, config, puppeteer, args.width, args.height)
        outputs.append(svg)
    if not args.no_png:
        png = out_dir / f"{stem}.png"
        render_one(mmdc, input_file, png, config, puppeteer, args.width, args.height)
        outputs.append(png)

    render_sh.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "cd \"$(dirname \"$0\")\"\n"
        f"./node_modules/.bin/mmdc -i {input_file} -o {stem}.svg -c mermaid-config.json -p puppeteer-config.json -b white -w {args.width} -H {args.height}\n"
        f"./node_modules/.bin/mmdc -i {input_file} -o {stem}.png -c mermaid-config.json -p puppeteer-config.json -b white -w {args.width} -H {args.height}\n",
        encoding="utf-8",
    )
    render_sh.chmod(0o755)

    for path in outputs:
        print(f"Wrote: {path}")
    print(f"Wrote: {render_sh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
