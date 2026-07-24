"""CLI entry point for the Babi Agent.

Uses Click for argument parsing and provides an interactive REPL
for chatting with the agent from the terminal.

Usage:
    export DASHSCOPE_API_KEY=your_key
    babi                          # default workspace ~/babi-workspace
    babi --workspace ~/my-project
"""

from __future__ import annotations

import asyncio
import logging
import sys

import click

from babi.config import get_settings
from babi.utils.helpers import resolve_workspace

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--workspace",
    default=None,
    help="Workspace directory (default: ~/babi-workspace)",
)
@click.option(
    "--model",
    default=None,
    help="Model name override (default: from config/env)",
)
@click.option(
    "--host",
    default=None,
    help="Web server host (default: 127.0.0.1)",
)
@click.option(
    "--port",
    default=None,
    type=int,
    help="Web server port (default: 8900)",
)
@click.option(
    "--web",
    is_flag=True,
    help="Start web server instead of CLI mode",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(workspace: str | None, model: str | None, host: str | None, port: int | None, web: bool, verbose: bool) -> None:
    """Babi Agent — AI-powered coding assistant.

    Run in CLI mode (default) or start a web server with --web.
    """
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    settings = get_settings()

    # Override settings from CLI args
    if workspace:
        settings.workspace = workspace
    if model:
        settings.model_name = model
    if host:
        settings.host = host
    if port:
        settings.port = port

    # Validate API key early
    _ = settings.dashscope_api_key

    if web:
        _start_web(settings)
    else:
        asyncio.run(_cli_repl(settings))


def _start_web(settings) -> None:
    """Start the AgentScope web server via uvicorn."""
    import asyncio
    import uvicorn

    from babi.web.app import create_babi_app, bootstrap_babi

    # Bootstrap resources (credential, agent, session) in Redis
    asyncio.run(bootstrap_babi(settings))

    app = create_babi_app(settings)
    print()
    print("=" * 50)
    print(f"  Babi Web Server (AgentScope)")
    print(f"  http://{settings.host}:{settings.port}")
    print(f"  API docs: http://{settings.host}:{settings.port}/docs")
    print("=" * 50)
    print()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


async def _cli_repl(settings) -> None:
    """Interactive CLI read-eval-print loop."""
    from agentscope.message import UserMsg
    from agentscope.event import EventType

    from babi.agent.builder import build_agent

    workspace_path = resolve_workspace(settings.workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 60)
    print("Babi Agent - Powered by AgentScope Python")
    print("=" * 60)
    print(f"Workspace: {workspace_path}")
    print("Built-in tools: read_file, write_file, edit_file, grep_files, execute")
    print("Custom tools: fetch_url, http_request, github_api_request, github_pinned_repos, list_skills, use_skill")
    print("Type 'exit' to quit.")
    print()

    # Build agent
    agent = build_agent(settings, workspace_path)

    # REPL loop
    loop = asyncio.get_event_loop()
    while True:
        try:
            user_input = await loop.run_in_executor(None, lambda: input("You: "))
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() == "exit":
            print("\nGoodbye!")
            break

        user_msg = UserMsg("user", user_input)

        print("\nBabiAgent: ", end="", flush=True)

        try:
            async for evt in agent.reply_stream(user_msg):
                match evt.type:
                    case EventType.TEXT_BLOCK_DELTA:
                        print(evt.delta, end="", flush=True)
                    case EventType.TOOL_CALL_START:
                        print(f"\n  [Tool: {evt.tool_name}]", end="", flush=True)
                    case EventType.TOOL_CALL_END:
                        pass
                    case _:
                        pass

            print("\n")

        except Exception as e:
            print(f"\nError: {e}\n")
            logger.exception("Agent error")


if __name__ == "__main__":
    main()
