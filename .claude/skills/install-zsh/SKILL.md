---
name: install-zsh
description: 安装 zsh shell、oh-my-zsh 框架及推荐插件。当用户需要配置 zsh 开发环境、安装 oh-my-zsh、配置 zsh 插件时触发。用户可调用 /install-zsh 来激活。
user-invocable: true
allowed-tools: "Bash Read Write Edit"
---

# Install Zsh — 安装 zsh 及 oh-my-zsh

在目标机器上安装 zsh、oh-my-zsh 框架及推荐插件。国内网络环境下使用 gitcode 镜像加速。

## 执行流程

### 1. 检测当前状态

```bash
# 检查 zsh 是否已安装
which zsh && zsh --version || echo "zsh not installed"
```

### 2. 安装 zsh

如果 zsh 未安装：

```bash
sudo apt-get update && sudo apt-get install -y zsh
```

### 3. 安装 oh-my-zsh

如果 `~/.oh-my-zsh` 目录不存在，使用 gitcode 镜像安装，如果存在，删除后安装：

使用本 skill 目录下的 `install.sh`。

```bash
REMOTE=https://gitcode.com/ohmyzsh/ohmyzsh.git sh "$SKILL_DIR/install.sh"
```

`$SKILL_DIR` 为本 SKILL.md 所在目录。

> 注意：oh-my-zsh 安装脚本默认会将当前 shell 切换为 zsh，在非交互场景下可能异常。如果不想切换，可以在安装完成后执行 `exit`。

### 4. 安装 zsh-autosuggestions 插件

**硬约束：以下整个脚本块必须作为单次 Bash 调用执行，绝对禁止拆分为多次调用（clone 和 sed 在一个 shell 里）。** 

```bash
ZSH_CUSTOM=${ZSH_CUSTOM:-~/.oh-my-zsh/custom}
PLUGIN_DIR="$ZSH_CUSTOM/plugins/zsh-autosuggestions"

if [ ! -d "$PLUGIN_DIR" ]; then
  git clone https://gitcode.com/zsh-users/zsh-autosuggestions.git "$PLUGIN_DIR"
fi

sed -i 's/(git)/(git zsh-autosuggestions)/g' ~/.zshrc
```