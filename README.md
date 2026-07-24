# Babi Agent ♻️

面向开发者的 AI Coding Agent，基于 ReAct 模式提供代码分析、构建、调试等开发辅助能力。

> 技术栈：AgentScope Python SDK + FastAPI + Click

## 特性

- **代码读写** — 读取、分析源码，精准文本替换编辑文件
- **代码搜索** — 基于 ripgrep/grep 的模式匹配，快速定位代码
- **Shell 执行** — 运行构建、测试、部署等终端命令
- **网页抓取** — 获取网页内容，保留结构化文本
- **Web 搜索** — 基于 Tavily 的联网检索，实时获取最新信息
- **HTTP 请求** — 调用任意 REST API
- **GitHub 集成** — 通过 API 操作 Issues、PR、仓库、Pinned Repos 等
- **Skills 扩展** — Markdown 定义的可复用工作流指令，支持全局与 Babi 专属目录两级加载
- **任务追踪** — 内置 Todo 列表，可视化多步骤任务进度
- **双端交互** — Web 聊天界面（Markdown 渲染 + 工具状态可视化）与 CLI 两种模式

## 环境准备

```bash
# Python 3.12+
python --version  # 确认版本 >= 3.12

# 阿里云百炼 API Key（必需）
export DASHSCOPE_API_KEY=your_api_key

# 可选 — Tavily Search API Key（用于 Web 搜索功能，免费额度 1000 次/月）
export TAVILY_API_KEY=your_tavily_api_key

# 可选 — GitHub API 令牌（用于 GitHub 相关功能）
export GITHUB_TOKEN=your_github_token
```

## 安装

```bash
# 克隆项目
git clone <repo-url> && cd babi-python

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate

# 可编辑安装（含开发依赖）
pip install -e ".[dev]"
```

## 快速开始

### 命令行模式（默认）

```bash
babi                            # 默认工作目录 ~/babi-workspace
babi --workspace ~/my-project   # 指定工作目录
babi --model qwen-max           # 指定模型
babi -v                         # 开启详细日志
```

进入交互 REPL 后直接输入问题即可对话，输入 `exit` 退出。

### Web 聊天界面

```bash
babi --web                      # 启动 Web 服务（默认 127.0.0.1:8900）
babi --web --port 9000          # 指定端口
```

打开浏览器访问 `http://localhost:8900`，即可在聊天界面中与 Babi Agent 交互。

> Web 模式依赖 Redis，请确保本地 Redis 服务已启动。

## 配置

通过环境变量或 `.env` 文件配置（参见 [.env.example](.env.example)）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key（**必需**） | — |
| `TAVILY_API_KEY` | Tavily Search API Key（Web 搜索功能，[免费申请](https://tavily.com)） | — |
| `GITHUB_TOKEN` | GitHub 个人访问令牌 | — |
| `BABI_MODEL_NAME` | 模型名称 | `qwen-plus` |
| `BABI_FALLBACK_MODEL` | 降级模型 | `qwen-turbo` |
| `BABI_WORKSPACE` | 工作目录 | `~/babi-workspace` |
| `BABI_HOST` | Web 服务地址 | `127.0.0.1` |
| `BABI_PORT` | Web 服务端口 | `8900` |

## Skills 扩展

Skills 是 Markdown 格式的可复用工作流指令，从以下目录自动加载（后者覆盖前者）：

| 优先级 | 目录 | 说明 |
|--------|------|------|
| 低 | `~/.agents/skills/` | 全局共享 Skills |
| 高 | `~/.babi/skills/` | Babi 专属 Skills |

支持两种文件格式：
- **单文件**：`my-skill.md`
- **目录格式**：`my-skill/SKILL.md`

Skill 文件示例：

```markdown
---
name: code-review
description: Perform structured code review on source files
---

# Instructions
1. Read the target file...
```

## 项目结构

```
babi-python/
├── babi/
│   ├── agent/          # Agent 构建与 Prompt 管理
│   ├── middleware/      # 上下文截断等中间件
│   ├── skills/         # Skill 加载器
│   ├── tools/          # 内置工具（fetch_url, http_request, github_api, web_search 等）
│   ├── utils/          # 工具函数
│   ├── web/            # Web 服务（FastAPI）
│   ├── cli.py          # CLI 入口（Click）
│   └── config.py       # 配置管理（Pydantic Settings）
├── resources/
│   ├── static/         # Web 前端静态文件
│   └── workspace/      # 默认工作区模板（AGENTS.md）
└── tests/              # 测试
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
