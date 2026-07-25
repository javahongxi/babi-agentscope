"""Agent builder: assembles the BabiAgent with model, tools, and configuration.

This replaces Java's AgentConfiguration + HarnessAgent builder pattern
with a Pythonic factory function approach.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from babi.agent.prompt import build_system_prompt
from babi.config import Settings
from babi.tools.fetch_url import fetch_url
from babi.tools.github_api import github_api_request, github_pinned_repos
from babi.tools.http_request import http_request
from babi.tools.skill_tool import SkillTool
from babi.tools.web_search import web_search
from babi.utils.helpers import AGENT_NAME, init_agents_md, resolve_workspace

logger = logging.getLogger(__name__)


def build_agent(settings: Settings, workspace_path: Path | None = None):
    """Build and configure the BabiAgent.

    Args:
        settings: Application settings
        workspace_path: Optional workspace path override

    Returns:
        Configured Agent instance ready for use
    """
    # Import here to avoid circular imports and allow lazy loading
    from agentscope.agent import Agent
    from agentscope.agent._agent import AgentState
    from agentscope.credential import DashScopeCredential
    from agentscope.model import DashScopeChatModel
    from agentscope.permission import PermissionContext, PermissionMode
    from agentscope.tool import Toolkit, FunctionTool, Bash, Grep, Glob, Read, Write, Edit

    # Resolve workspace
    if workspace_path is None:
        workspace_path = resolve_workspace(settings.workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Initialize AGENTS.md
    init_agents_md(workspace_path)
    logger.info("Agent workspace: %s", workspace_path)

    # Build system prompt with skills
    skill_tool = SkillTool(workspace_path)
    skills_list = list(skill_tool.skills.values())
    sys_prompt = build_system_prompt(skills_list, workspace_path=workspace_path)

    # Build toolkit with built-in filesystem/shell tools + custom tools
    toolkit = Toolkit(
        tools=[
            Bash(),
            Grep(),
            Glob(),
            Read(),
            Write(),
            Edit(),
            FunctionTool(fetch_url),
            FunctionTool(http_request),
            FunctionTool(web_search),
            FunctionTool(github_api_request),
            FunctionTool(github_pinned_repos),
            FunctionTool(skill_tool.list_skills),
            FunctionTool(skill_tool.use_skill),
        ]
    )

    logger.info(
        "Registered tools: read_file, write_file, edit_file, grep_files, execute, "
        "fetch_url, http_request, web_search, github_api_request, github_pinned_repos, list_skills, use_skill"
    )

    # Build the agent with BYPASS permission mode to auto-approve all tool calls
    agent_state = AgentState(
        permission_context=PermissionContext(mode=PermissionMode.BYPASS),
    )
    agent = Agent(
        name=AGENT_NAME,
        system_prompt=sys_prompt,
        model=DashScopeChatModel(
            credential=DashScopeCredential(
                api_key=settings.dashscope_api_key
            ),
            model=settings.model_name,
            stream=True,
            max_retries=settings.max_retries,
        ),
        toolkit=toolkit,
        state=agent_state,
    )

    logger.info("BabiAgent built successfully with model: %s", settings.model_name)
    return agent


def get_workspace_path(settings: Settings) -> Path:
    """Resolve and prepare the workspace directory.

    Args:
        settings: Application settings

    Returns:
        Resolved workspace Path
    """
    workspace_path = resolve_workspace(settings.workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)
    init_agents_md(workspace_path)
    return workspace_path
