#!/usr/bin/env bash
set -euo pipefail

# ─── Babi Agent CLI (AgentScope) 卸载脚本 ───

INSTALL_DIR="$HOME/.babi-agentscope"
BIN_DIR="$HOME/.babi/bin"
CMD_NAME="babi-as"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# ─── 删除虚拟环境 ───
if [ -d "$INSTALL_DIR" ]; then
    info "删除虚拟环境 $INSTALL_DIR ..."
    rm -rf "$INSTALL_DIR"
    ok "已删除 $INSTALL_DIR"
else
    warn "虚拟环境 $INSTALL_DIR 不存在，跳过"
fi

# ─── 删除启动脚本 ───
LAUNCHER="$BIN_DIR/$CMD_NAME"
if [ -f "$LAUNCHER" ]; then
    info "删除启动脚本 $LAUNCHER ..."
    rm -f "$LAUNCHER"
    ok "已删除 $LAUNCHER"
else
    warn "启动脚本 $LAUNCHER 不存在，跳过"
fi

# ─── 清理空的 bin 目录（如果已无其他 babi 启动器）───
if [ -d "$BIN_DIR" ]; then
    remaining=$(ls -A "$BIN_DIR" 2>/dev/null | grep -c "^babi" || true)
    if [ "$remaining" -eq 0 ]; then
        info "清理空的 bin 目录 $BIN_DIR ..."
        rm -rf "$BIN_DIR"
        # 如果 ~/.babi 也空了，一并清理
        if [ -d "$HOME/.babi" ] && [ -z "$(ls -A "$HOME/.babi" 2>/dev/null)" ]; then
            rm -rf "$HOME/.babi"
            ok "已删除空目录 $HOME/.babi"
        fi
        ok "已删除 $BIN_DIR"

        # 尝试清理 shell 配置中的 PATH
        SHELL_RC=""
        if [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "$SHELL" 2>/dev/null)" = "zsh" ]; then
            SHELL_RC="$HOME/.zshrc"
        elif [ -n "${BASH_VERSION:-}" ]; then
            if [ -f "$HOME/.bash_profile" ]; then
                SHELL_RC="$HOME/.bash_profile"
            else
                SHELL_RC="$HOME/.bashrc"
            fi
        fi

        if [ -n "${SHELL_RC:-}" ] && [ -f "${SHELL_RC:-}" ]; then
            if grep -qF "$BIN_DIR" "${SHELL_RC}" 2>/dev/null; then
                sed -i '' "/# Babi Agent CLI/d" "$SHELL_RC" 2>/dev/null || true
                sed -i '' "/export PATH=\".*\\.babi\\/bin/d" "$SHELL_RC" 2>/dev/null || true
                ok "已清理 $SHELL_RC 中的 PATH 配置"
                warn "请执行 source $SHELL_RC 使更改生效"
            fi
        fi
    else
        ok "bin 目录中还有其他 babi 启动器（$remaining 个），保留 $BIN_DIR"
    fi
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo -e "  ${GREEN}Babi Agent CLI (AgentScope) 已卸载${NC}"
echo "═══════════════════════════════════════════════════"
echo ""
