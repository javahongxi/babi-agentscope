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


def _build_system_prompt(workspace_path: Path | None = None) -> str:
    """Build the babi system prompt with skills."""
    skill_tool = SkillTool()
    skills_list = list(skill_tool.skills.values())
    return build_system_prompt(skills_list, workspace_path=workspace_path)


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

    from babi.utils.helpers import resolve_workspace, init_agents_md

    # Resolve workspace path
    workspace_path = resolve_workspace(settings.workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)
    init_agents_md(workspace_path)

    # Storage: Redis
    storage = RedisStorage(host="localhost", port=6379)

    # Message bus: in-memory (single process)
    message_bus = InMemoryMessageBus()

    # Workspace manager: use basedir directly (no agent_id subdirectory),
    # matching the Java version's flat workspace layout.
    class _FlatWorkspaceManager(LocalWorkspaceManager):
        """LocalWorkspaceManager that uses basedir directly as workdir.

        Babi is single-agent, so we skip the per-agent subdirectory
        (e.g. basedir/d7a39143054848a6bc6ab419a1457fb7) and share one
        workspace directory — same as the Java version.
        """

        async def get_workspace(self, user_id, agent_id, session_id, workspace_id=None):
            import os
            import time
            from agentscope.workspace import LocalWorkspace

            if workspace_id is None:
                workspace_id = self.assign_workspace_id(
                    user_id="", agent_id=agent_id, session_id="",
                )

            async with self._lock:
                now = time.monotonic()
                expired = self._pop_expired(now)
                cached = self._cache.get(workspace_id)
                if cached is not None:
                    ws, _ = cached
                    self._cache[workspace_id] = (ws, now)
                    hit = ws
                else:
                    hit = None

            if expired:
                import asyncio
                await asyncio.gather(
                    *(self._safe_close(ws) for ws in expired),
                    return_exceptions=True,
                )

            if hit is not None:
                return hit

            async with self._lock:
                cached = self._cache.get(workspace_id)
                if cached is not None:
                    ws, _ = cached
                    self._cache[workspace_id] = (ws, time.monotonic())
                    return ws

                # Use basedir directly — no agent_id subdirectory
                ws = LocalWorkspace(
                    workspace_id=workspace_id,
                    workdir=self._basedir,
                    default_mcps=self._default_mcps,
                    skill_paths=self._skill_paths,
                )
                await ws.initialize()
                self._cache[workspace_id] = (ws, time.monotonic())
                return ws

    workspace_manager = _FlatWorkspaceManager(
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
    from fastapi import Query
    from fastapi.responses import FileResponse, JSONResponse

    # Workspace root for file tree / preview APIs
    _workspace_root = workspace_path

    def _safe_resolve(rel_path: str) -> Path | None:
        """Resolve a relative path against workspace root, rejecting path traversal."""
        resolved = (_workspace_root / rel_path).resolve()
        if not str(resolved).startswith(str(_workspace_root.resolve())):
            return None
        return resolved

    # Language mapping for syntax highlighting hints
    _EXT_LANG = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".java": "java", ".go": "go", ".rs": "rust",
        ".html": "html", ".css": "css", ".json": "json",
        ".xml": "xml", ".yaml": "yaml", ".yml": "yaml",
        ".md": "markdown", ".sh": "bash", ".sql": "sql",
        ".rb": "ruby", ".c": "c", ".cpp": "cpp",
    }

    @app.get("/api/workspace/tree")
    async def workspace_tree(path: str = Query(default="")):
        """List directory entries within the workspace."""
        target = _safe_resolve(path)
        if target is None or not target.is_dir():
            return JSONResponse([], status_code=200)
        items = []
        try:
            for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith("."):
                    continue  # skip hidden files/dirs
                items.append({
                    "name": entry.name,
                    "path": str(entry.relative_to(_workspace_root)),
                    "isDir": entry.is_dir(),
                })
        except OSError as e:
            logger.warning("workspace/tree error for '%s': %s", path, e)
        return items

    @app.get("/api/workspace/file")
    async def workspace_file(path: str = Query()):
        """Read text file content from workspace."""
        target = _safe_resolve(path)
        if target is None or not target.is_file():
            return JSONResponse({"error": "File not found"}, status_code=404)
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            lang = _EXT_LANG.get(target.suffix.lower(), "plaintext")
            return {"content": content, "language": lang, "size": target.stat().st_size}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/api/workspace/image")
    async def workspace_image(path: str = Query()):
        """Serve an image file from workspace."""
        target = _safe_resolve(path)
        if target is None or not target.is_file():
            return JSONResponse({"error": "Image not found"}, status_code=404)
        return FileResponse(str(target))

    @app.delete("/api/chat/memory")
    async def clear_memory():
        """Delete MEMORY.md from workspace so the agent forgets prior context."""
        memory_file = _workspace_root / "MEMORY.md"
        try:
            if memory_file.exists():
                memory_file.unlink()
                logger.info("Deleted memory file: %s", memory_file)
                return {"status": "ok", "message": f"已清除记忆文件 MEMORY.md"}
            else:
                return {"status": "ok", "message": "没有找到记忆文件 MEMORY.md"}
        except OSError as e:
            logger.warning("Failed to delete memory file: %s", e)
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

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

    @app.post("/api/ensure-session")
    async def ensure_session(
        session_id: str = "default",
        x_user_id: str = Header(default="babi-user", alias="X-User-ID"),
    ):
        """Ensure a session exists in Redis, creating it with default config if needed."""
        from agentscope.agent._agent import AgentState
        from agentscope.app.storage import SessionConfig
        from agentscope.app.storage._model._session import ChatModelConfig
        from agentscope.permission import PermissionContext, PermissionMode

        agent_id = "babi-agent"
        existing = await storage.get_session(x_user_id, agent_id, session_id)
        if existing is not None:
            return {"session_id": session_id, "created": False}

        session_record = await storage.upsert_session(
            user_id=x_user_id,
            agent_id=agent_id,
            session_id=session_id,
            config=SessionConfig(
                workspace_id="default",
                name=session_id,
                chat_model_config=ChatModelConfig(
                    type="dashscope",
                    credential_id="dashscope-default",
                    model=settings.model_name,
                    parameters={"stream": True, "max_retries": settings.max_retries},
                ),
            ),
            state=AgentState(
                permission_context=PermissionContext(mode=PermissionMode.BYPASS),
            ),
        )
        logger.info("Created session '%s' for user '%s'", session_id, x_user_id)
        return {"session_id": session_record.id, "created": True}

    # Mount static frontend files at root
    static_dir = Path(__file__).parent.parent.parent / "resources" / "static"
    if static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


async def bootstrap_babi(settings: Settings) -> dict:
    """Bootstrap babi resources in Redis: credential + agent + default session.

    Called once at startup. The default session (id="default") is pre-created
    so the frontend can chat immediately. Additional sessions are created
    on demand via POST /api/ensure-session.

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
        agent_id = "babi-agent"

        # 1. Create DashScope credential
        credential = DashScopeCredential(
            id="dashscope-default",
            api_key=settings.dashscope_api_key,
        )
        credential_id = await storage.upsert_credential(user_id, credential)
        logger.info("Credential '%s' configured", credential_id)

        # 2. Create agent with babi system prompt
        from babi.utils.helpers import resolve_workspace
        ws_path = resolve_workspace(settings.workspace)
        sys_prompt = _build_system_prompt(workspace_path=ws_path)
        agent_data = AgentData(
            name="BabiAgent",
            system_prompt=sys_prompt,
            context_config=ContextConfig(),
            react_config=ReActConfig(),
        )
        agent_record = AgentRecord(id=agent_id, user_id=user_id, data=agent_data)
        await storage.upsert_agent(user_id, agent_record)
        logger.info("Agent '%s' configured with system prompt (%d chars)", agent_id, len(sys_prompt))

        # 3. Create default session only if it doesn't exist yet.
        #    Upsertting unconditionally would overwrite state.context
        #    (conversation history), causing the agent to "forget" after restart.
        existing_session = await storage.get_session(user_id, agent_id, "default")
        if existing_session is not None:
            session_record = existing_session
            logger.info("Default session already exists, skipping creation")
        else:
            session_record = await storage.upsert_session(
                user_id=user_id,
                agent_id=agent_id,
                session_id="default",
                config=SessionConfig(
                    workspace_id="default",
                    name="Default Session",
                    chat_model_config=ChatModelConfig(
                        type="dashscope",
                        credential_id=credential_id,
                        model=settings.model_name,
                        parameters={"stream": True, "max_retries": settings.max_retries},
                    ),
                ),
                state=AgentState(
                    permission_context=PermissionContext(mode=PermissionMode.BYPASS),
                ),
            )
            logger.info("Default session created, model='%s'", settings.model_name)

    return {
        "user_id": user_id,
        "agent_id": agent_id,
        "session_id": session_record.id,
        "credential_id": credential_id,
    }
