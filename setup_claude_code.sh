#!/bin/bash
set -e

#################### API token ####################
# 从环境变量或第一个参数读取，仓库里不保存任何密钥。
#   ANTHROPIC_AUTH_TOKEN=sk-xxx bash setup_claude_code.sh
#   bash setup_claude_code.sh sk-xxx
if [ -n "${1:-}" ]; then
    ANTHROPIC_AUTH_TOKEN="$1"
fi

if [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    echo "Error: ANTHROPIC_AUTH_TOKEN is not set." >&2
    echo "" >&2
    echo "Usage:" >&2
    echo "  ANTHROPIC_AUTH_TOKEN=<token> bash setup_claude_code.sh" >&2
    echo "  bash setup_claude_code.sh <token>" >&2
    exit 1
fi

# 默认指向 DeepSeek 的 Anthropic 兼容端点；用其他后端时覆盖此变量
ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}"

SETTINGS_FILE="$HOME/.claude/settings.json"

echo "==> Installing Claude Code CLI"

if command -v claude &>/dev/null; then
    echo "    Claude Code already installed ($(claude --version 2>/dev/null || echo 'unknown version')), skipping installation."
else
    echo "    Adding NodeSource repository (Node.js 22)..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -

    echo "    Installing Node.js..."
    sudo apt install -y nodejs

    echo "    Installing Claude Code..."
    sudo npm install -g @anthropic-ai/claude-code
fi


echo ""
echo "==> Configuring API endpoint: $ANTHROPIC_BASE_URL"

mkdir -p "$(dirname "$SETTINGS_FILE")"

python3 - "$SETTINGS_FILE" "$ANTHROPIC_AUTH_TOKEN" "$ANTHROPIC_BASE_URL" <<'PYEOF'
import sys, json, os

path = sys.argv[1]
auth_token = sys.argv[2]
base_url = sys.argv[3]

settings = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        pass

env_override = {
    "ANTHROPIC_BASE_URL": base_url,
    "ANTHROPIC_AUTH_TOKEN": auth_token,
    "ANTHROPIC_MODEL": "deepseek-flash[1m]",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-flash[1m]",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-flash[1m]",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-flash",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK": "1",
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "786432"
}

settings["env"] = {**settings.get("env", {}), **env_override}

with open(path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"    Written to {path}")
PYEOF


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "==> Copying global CLAUDE.md (Keep It Short rules)"

CLAUDE_MD="$HOME/.claude/CLAUDE.md"
if [ -f "$SCRIPT_DIR/claude.md" ]; then
    mkdir -p "$(dirname "$CLAUDE_MD")"
    cp "$SCRIPT_DIR/claude.md" "$CLAUDE_MD"
    echo "    Copied to $CLAUDE_MD"
else
    echo "    [skip] $SCRIPT_DIR/claude.md not found"
fi

echo ""
echo "==> Running install_skills.sh"
bash "$SCRIPT_DIR/scripts/install_skills.sh"

echo ""
echo "==> Running alias.sh"
bash "$SCRIPT_DIR/scripts/alias.sh"

echo ""
echo "Done. Run 'claude' to start."
