#!/usr/bin/env bash
set -euo pipefail

# ─── Babi Agent CLI (AgentScope) 一键安装脚本 ───
# 创建 venv → 安装包 → 创建启动脚本 → 配置 PATH
# 安装完成后，在终端输入 babi-as 即可启动

INSTALL_DIR="$HOME/.babi-agentscope"
BIN_DIR="$HOME/.babi/bin"
CMD_NAME="babi-as"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ─── 前置检查 ───
info "检查环境依赖..."

# 检查 Python
if ! command -v python3 &>/dev/null; then
    err "未找到 python3，请先安装 Python 3.10+"
    err "  macOS:  brew install python@3.12"
    err "  Ubuntu: sudo apt install python3.12"
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    err "Python 版本 $PY_VER 过低，需要 3.10+"
    exit 1
fi
ok "Python $PY_VER"

# ─── 创建虚拟环境 ───
info "创建虚拟环境 $INSTALL_DIR ..."
python3 -m venv "$INSTALL_DIR"
ok "虚拟环境已创建"

# ─── 安装包 ───
info "安装 babi-agentscope 及依赖（首次安装可能需要几分钟）..."
"$INSTALL_DIR/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/bin/pip" install -e "$SCRIPT_DIR" -q 2>&1 | tail -5
ok "安装完成"

# ─── 创建启动脚本 ───
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/$CMD_NAME" << LAUNCHER
#!/usr/bin/env bash
# Babi Agent CLI (AgentScope) 启动器
exec "$INSTALL_DIR/bin/python" -m babi "\$@"
LAUNCHER
chmod +x "$BIN_DIR/$CMD_NAME"
ok "已创建启动脚本 $BIN_DIR/$CMD_NAME"

# ─── 配置环境变量 ───
SHELL_RC=""
if [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "${BASH_VERSION:-}" ]; then
    if [ -f "$HOME/.bash_profile" ]; then
        SHELL_RC="$HOME/.bash_profile"
    else
        SHELL_RC="$HOME/.bashrc"
    fi
fi

PATH_LINE="export PATH=\"$BIN_DIR:\$PATH\""

if [ -n "${SHELL_RC:-}" ] && [ -f "${SHELL_RC:-}" ]; then
    if ! grep -qF "$BIN_DIR" "${SHELL_RC}" 2>/dev/null; then
        echo "" >> "${SHELL_RC}"
        echo "# Babi Agent CLI (babi-as / babi-lg)" >> "${SHELL_RC}"
        echo "$PATH_LINE" >> "${SHELL_RC}"
        ok "已将 $BIN_DIR 添加到 PATH（写入 ${SHELL_RC}）"
    else
        ok "PATH 已配置，跳过"
    fi
else
    warn "未检测到 shell 配置文件，请手动将以下内容添加到你的 shell 配置中："
    echo "  $PATH_LINE"
fi

# ─── 完成 ───
echo ""
echo "═══════════════════════════════════════════════════"
echo -e "  ${GREEN}Babi Agent CLI (AgentScope) 安装完成！${NC}"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  使用方式："
if [ -n "${SHELL_RC:-}" ]; then
echo "    1. 重新加载 shell 配置："
echo "       source ${SHELL_RC}"
else
echo "    1. 打开新终端窗口"
fi
echo "    2. 设置 API Key（如未设置）："
echo "       export DASHSCOPE_API_KEY=your_api_key"
echo "    3. 启动 Babi Agent（默认以当前目录为工作区）："
echo "       babi-as"
echo "    4. 指定其他工作区："
echo "       babi-as --workspace ~/other-project"
echo ""
echo "  卸载：运行 uninstall.sh 或手动删除 $INSTALL_DIR 和 $BIN_DIR/$CMD_NAME"
echo ""
