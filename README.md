# Babi Agent ♻️

面向开发者的 AI Coding Agent，基于 ReAct 模式提供代码分析、构建、调试等开发辅助能力。

> 技术栈：AgentScope SDK + FastAPI + Click

## 特性

- **代码读写** — 读取、分析源码，精准文本替换编辑文件
- **代码搜索** — 基于 ripgrep/grep 的模式匹配，快速定位代码
- **Shell 执行** — 运行构建、测试、部署等终端命令
- **网页抓取** — 获取网页内容，保留结构化文本
- **Web 搜索** — 基于 Tavily 的联网检索，实时获取最新信息
- **HTTP 请求** — 调用任意 REST API
- **GitHub 集成** — 通过 API 操作 Issues、PR、仓库、Pinned Repos 等
- **Skills 扩展** — Markdown 定义的可复用工作流指令，支持全局、Babi 专属、项目级三级加载
- **任务追踪** — 内置 Todo 列表，可视化多步骤任务进度
- **双端交互** — Web 聊天界面（Markdown 渲染 + 工具状态可视化）与 CLI 两种模式
- **会话持久化** — 基于 Redis 的会话存储，跨重启保持对话上下文

## 环境准备

```bash
# Python 3.10+
python --version  # 确认版本 >= 3.10

# 阿里云百炼 API Key（必需）
export DASHSCOPE_API_KEY=your_api_key

# 可选 — Tavily Search API Key（用于 Web 搜索功能，免费额度 1000 次/月）
export TAVILY_API_KEY=your_tavily_api_key

# 可选 — GitHub API 令牌（用于 GitHub 相关功能）
export GITHUB_TOKEN=your_github_token

# 必需（Web 模式）— Redis（用于 Web 模式会话持久化，默认 localhost:6379）
# CLI 模式无需 Redis；Web 模式强依赖，启动前请确保 Redis 已运行
# brew services start redis   # macOS 快速启动
```

## 安装

### 一键安装（推荐）

```bash
./install.sh
```

安装完成后在终端输入 `babi-as` 即可启动，默认以当前目录为工作区。

### 手动安装

```bash
# 克隆项目
git clone <repo-url> && cd babi-agentscope

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate

# 可编辑安装（含开发依赖）
pip install -e ".[dev]"
```

## 快速开始

### 命令行模式（默认）

```bash
babi-as                           # 默认以当前目录为工作区
babi-as --workspace ~/my-project  # 指定工作目录
babi-as --model qwen-max          # 指定模型
babi-as -v                        # 开启详细日志
```

进入交互 REPL 后直接输入问题即可对话，输入 `exit` 退出。

### Web 聊天界面

```bash
babi-as --web                     # 启动 Web 服务（默认 127.0.0.1:8900）
babi-as --web --port 9000         # 指定端口
```

打开浏览器访问 `http://localhost:8900`，即可在聊天界面中与 Babi Agent 交互。

## Skills 扩展

Skills 是 Markdown 格式的可复用工作流指令，从以下目录自动加载（后者覆盖前者）：

| 优先级 | 目录 | 说明 |
|--------|------|------|
| 低 | `~/.agents/skills/` | 全局共享 Skills |
| 中 | `~/.babi/skills/` | Babi 专属 Skills |
| 高 | `{workspace}/.qoder/skills/` | 项目级 Skills（相对于工作区根目录） |

支持两种文件格式：
- **单文件**：`my-skill.md`
- **目录格式**：`my-skill/SKILL.md`

## 卸载

```bash
./uninstall.sh
```

## 开发

```bash
# 运行测试
pytest

# 代码检查
ruff check babi/

# 代码格式化
ruff format babi/
```

&copy; [hongxi.org](http://hongxi.org)
