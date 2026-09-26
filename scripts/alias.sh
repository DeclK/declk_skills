#!/usr/bin/env bash
set -euo pipefail

#################### 注意事项 ####################
# 本脚本负责写入 alias 到 bash/zsh 配置文件，
# 并在写入后自动 source 当前 shell 的 rc 文件，
# 让 alias 立即生效，无需手动 source。
#
# 推荐用法: source ./alias.sh
# 也可以直接: bash ./alias.sh （脚本末尾会自动 source）
#################################################

ALIASES=(
  "# Codex YOLO mode alias"
  "alias codex='codex --dangerously-bypass-approvals-and-sandbox'"
  "# Claude Code skip permissions alias"
  "alias claude='claude --dangerously-skip-permissions'"
)

add_aliases_to_rc() {
  local rc_file="$1"

  touch "$rc_file"

  for line in "${ALIASES[@]}"; do
    # 跳过注释行和空行的重复检查，只对 alias 行做幂等
    if [[ "$line" == alias* ]]; then
      if grep -Fqx "$line" "$rc_file"; then
        echo "    [skip] alias already exists in $rc_file"
        continue
      fi
    fi

    # 对于注释行（# 开头），也做简易去重
    if [[ "$line" == \#* ]]; then
      if grep -Fqx "$line" "$rc_file"; then
        continue
      fi
    fi

    printf '%s\n' "$line" >> "$rc_file"
    echo "    [add] $line → $rc_file"
  done
}

echo "==> Setting up Codex & Claude Code aliases"

for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  echo "  Processing $rc ..."
  add_aliases_to_rc "$rc"
done

echo ""
echo "==> Aliases written. Auto-sourcing current shell rc ..."

# 自动 source 当前 shell 的 rc 文件，让 alias 立即生效
if [[ -n "${ZSH_VERSION:-}" ]]; then
  # 当前正在 zsh 中
  echo "    Detected zsh, sourcing ~/.zshrc ..."
  # shellcheck disable=SC1090
  source "$HOME/.zshrc" 2>/dev/null || true
elif [[ -n "${BASH_VERSION:-}" ]]; then
  # 当前正在 bash 中
  echo "    Detected bash, sourcing ~/.bashrc ..."
  # shellcheck disable=SC1090
  source "$HOME/.bashrc" 2>/dev/null || true
else
  echo "    Warning: cannot detect shell type (not bash/zsh?)."
  echo "    Please manually run: source ~/.bashrc  (or ~/.zshrc)"
fi

echo ""
echo "Done. 'codex' and 'claude' aliases are now active."
