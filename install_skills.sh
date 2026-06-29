#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="${SKILLS_SRC:-$REPO_DIR/.claude/skills}"

# Override these if you keep Claude/Codex config somewhere non-standard.
CLAUDE_SKILLS_DST="${CLAUDE_SKILLS_DST:-$HOME/.claude/skills}"
CODEX_SKILLS_DST="${CODEX_SKILLS_DST:-$HOME/.codex/skills}"

if [ ! -d "$SKILLS_SRC" ]; then
    echo "Error: skills source directory not found: $SKILLS_SRC" >&2
    exit 1
fi

install_for_target() {
    local label="$1"
    local dst="$2"
    local count=0

    echo "==> Installing personal skills for $label"
    echo "    source: $SKILLS_SRC"
    echo "    target: $dst"
    echo ""

    mkdir -p "$dst"

    for skill_dir in "$SKILLS_SRC"/*/; do
        [ -d "$skill_dir" ] || continue

        local skill_name
        skill_name="$(basename "$skill_dir")"

        if [ ! -f "$skill_dir/SKILL.md" ]; then
            echo "  [skip] $skill_name (missing SKILL.md)"
            continue
        fi

        local target="$dst/$skill_name"

        if [ -e "$target" ]; then
            rm -rf "$target"
        fi

        cp -R "$skill_dir" "$target"
        echo "  [ok]   $skill_name"
        count=$((count + 1))
    done

    echo ""
    echo "Done for $label. $count skill(s) installed."
    echo ""
}

echo "==> Installing personal skills from $REPO_DIR"
echo ""

install_for_target "Claude" "$CLAUDE_SKILLS_DST"
install_for_target "Codex" "$CODEX_SKILLS_DST"

echo "All done."
echo ""
echo "Next steps:"
echo "  - Restart Claude Code to pick up new Claude skills."
echo "  - Restart Codex to pick up new Codex skills."
echo "  - Tip: run the 'setup-vscode' skill to deploy your VSCode configs."
