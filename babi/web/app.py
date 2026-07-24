"""Babi Web application built on AgentScope's create_app.

Delegates to agentscope.app.create_app for the full-featured agent service
(chat, session, credential, model, workspace management) and adds babi-specific
custom tools via the extra_agent_tools hook.

Replaces the previous custom FastAPI implementation.
"""

from __future__ import annotations

import logging
from pathlib import Path

from babi.agent.prompt import build_system_prompt
from babi.config import Settings
from babi.skills.loader import load_all_skills
from babi.tools.fetch_url import fetch_url
from babi.tools.github_api import github_api_request, github_pinned_repos
from babi.tools.http_request import http_request
from babi.tools.skill_tool import SkillTool
from babi.tools.web_search import web_search

logger = logging.getLogger(__name__)


def _build_extra_tool_factory(settings: Settings):
    """Create the AgentToolFactory for babi-specific custom tools.

    Returns an async factory ``(user_id, agent_id, session_id) -> list[ToolBase]``
    that produces the custom tools on each chat turn.
    """
    from agentscope.tool import FunctionTool

    # Pre-load skills once at startup
    skill_tool = SkillTool()
    skills_list = list(skill_tool.skills.values())
    logger.info("Loaded %d skills for tool factory", len(skills_list))

    async def factory(user_id: str, agent_id: str, session_id: str):
        return [
            FunctionTool(fetch_url),
            FunctionTool(http_request),
            FunctionTool(web_search),
            FunctionTool(github_api_request),
            FunctionTool(github_pinned_repos),
            FunctionTool(skill_tool.list_skills),
            FunctionTool(skill_tool.use_skill),
        ]

    return factory


def _build_system_prompt() -> str:
    """Build the babi system prompt with skills."""
    skill_tool = SkillTool()
    skills_list = list(skill_tool.skills.values())
    return build_system_prompt(skills_list)


def create_babi_app(settings: Settings):
    """Create the full AgentScope app configured for Babi.

    Args:
        settings: Application settings

    Returns:
        Configured FastAPI application from agentscope.app.create_app
    """
    from agentscope.app import create_app
    from agentscope.app.message_bus import InMemoryMessageBus
    from agentscope.app.storage import RedisStorage
    from agentscope.app.workspace_manager import LocalWorkspaceManager
    from fastapi import Header
    from fastapi.middleware import Middleware
    from fastapi.middleware.cors import CORSMiddleware

    from babi.utils.helpers import resolve_workspace

    # Resolve workspace path
    workspace_path = resolve_workspace(settings.workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Storage: Redis
    storage = RedisStorage(host="localhost", port=6379)

    # Message bus: in-memory (single process)
    message_bus = InMemoryMessageBus()

    # Workspace manager: local filesystem
    workspace_manager = LocalWorkspaceManager(
        basedir=str(workspace_path),
    )

    # Extra tools factory
    extra_agent_tools = _build_extra_tool_factory(settings)

    # Build the app
    app = create_app(
        storage=storage,
        message_bus=message_bus,
        workspace_manager=workspace_manager,
        extra_agent_tools=extra_agent_tools,
        title="Babi Agent",
        version="1.0.0",
        extra_middlewares=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        ],
    )

    # --- Custom babi routes (before static mount) ---

    from agentscope.app.message_bus import MessageBusKeys

    @app.delete("/api/clear-messages")
    async def clear_session_messages(
        session_id: str = "default",
        x_user_id: str = Header(default="babi-user", alias="X-User-ID"),
    ):
        """Clear all messages, session context, and replay log for a session."""
        import json as _json
        import redis.asyncio as aioredis

        r = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
        try:
            # 1. Clear persisted messages in Redis
            msg_key = f"agentscope:user:{x_user_id}:session:{session_id}:messages"
            deleted = await r.delete(msg_key)
            logger.info("Cleared %d persisted messages for session '%s'", deleted, session_id)

            # 2. Clear session state.context (the LLM conversation history)
            session_key = f"agentscope:user:{x_user_id}:session:{session_id}"
            raw = await r.get(session_key)
            if raw:
                session_data = _json.loads(raw)
                state = session_data.get("state", {})
                state["context"] = []
                state["reply_context"] = {
                    "reply_id": "",
                    "cur_iter": 0,
                    "structured_schema": None,
                    "structured_output": None,
                }
                state["summary"] = ""
                session_data["state"] = state
                await r.set(session_key, _json.dumps(session_data))
                logger.info("Cleared session state context for '%s'", session_id)
        finally:
            await r.aclose()

        # 3. Clear the SSE replay log (in-memory) so old events don't replay
        events_key = MessageBusKeys.session_events(session_id)
        await message_bus.log_trim(events_key, before_id=None)
        logger.info("Cleared replay log '%s' for session '%s'", events_key, session_id)

        return {"status": "ok", "session_id": session_id, "cleared": deleted}

    # Mount static frontend files at root
    static_dir = Path(__file__).parent.parent.parent / "resources" / "static"
    if static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


async def bootstrap_babi(settings: Settings) -> dict:
    """Bootstrap babi resources in Redis: credential + agent + default session.

    This is called once at startup to ensure the default agent and session
    exist so the frontend can start chatting immediately.

    Args:
        settings: Application settings

    Returns:
        Dict with agent_id, session_id, credential_id
    """
    from agentscope.agent import ContextConfig, ReActConfig
    from agentscope.agent._agent import AgentState
    from agentscope.app.storage import (
        RedisStorage,
        AgentData,
        AgentRecord,
        SessionConfig,
    )
    from agentscope.app.storage._model._session import ChatModelConfig
    from agentscope.credential import DashScopeCredential
    from agentscope.permission import PermissionContext, PermissionMode

    storage = RedisStorage(host="localhost", port=6379)
    async with storage:
        user_id = "babi-user"

        # 1. Create DashScope credential (id is auto-generated if not set)
        credential = DashScopeCredential(
            id="dashscope-default",
            api_key=settings.dashscope_api_key,
        )
        credential_id = await storage.upsert_credential(user_id, credential)
        logger.info("Credential '%s' configured", credential_id)

        # 2. Create agent with babi system prompt
        agent_id = "babi-agent"
        sys_prompt = _build_system_prompt()
        agent_data = AgentData(
            name="BabiAgent",
            system_prompt=sys_prompt,
            context_config=ContextConfig(),
            react_config=ReActConfig(),
        )
        agent_record = AgentRecord(user_id=user_id, data=agent_data)
        agent_id = await storage.upsert_agent(user_id, agent_record)
        logger.info("Agent '%s' configured with system prompt (%d chars)", agent_id, len(sys_prompt))

        # 3. Create default session with model config + BYPASS permission
        session_config = SessionConfig(
            workspace_id="default",
            name="Default Session",
            chat_model_config=ChatModelConfig(
                type="dashscope",
                credential_id=credential_id,
                model=settings.model_name,
                parameters={"stream": True, "max_retries": settings.max_retries},
            ),
        )
        agent_state = AgentState(
            permission_context=PermissionContext(mode=PermissionMode.BYPASS),
        )
        session_record = await storage.upsert_session(
            user_id=user_id,
            agent_id=agent_id,
            config=session_config,
            state=agent_state,
            session_id="default",
        )
        logger.info("Session '%s' configured with model '%s'", session_record.id, settings.model_name)

    return {
        "user_id": user_id,
        "agent_id": agent_id,
        "session_id": session_record.id,
        "credential_id": credential_id,
    }
