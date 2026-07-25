"""Shared utilities: path resolution, text truncation, workspace init."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Project root: babi/utils/helpers.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

AGENT_NAME = "BabiAgent"


def resolve_workspace(raw: str) -> Path:
    """Resolve a workspace path string, expanding ~ and making absolute.

    Args:
        raw: Workspace path (may contain ~ or be relative)

    Returns:
        Resolved absolute Path
    """
    expanded = Path(raw).expanduser()
    return expanded.resolve()


def truncate(text: str | None, max_len: int) -> str:
    """Truncate a string to max_len, appending a marker if truncated.

    Args:
        text: String to truncate
        max_len: Maximum allowed length

    Returns:
        Truncated string with marker if needed
    """
    if text is None:
        return ""
    if len(text) > max_len:
        return text[:max_len] + "\n... (truncated)"
    return text


def init_agents_md(workspace_path: Path) -> None:
    """Initialize AGENTS.md in workspace if it doesn't exist.

    Tries to copy from package resources, falls back to creating a minimal default.

    Args:
        workspace_path: Workspace directory path
    """
    agents_md = workspace_path / "AGENTS.md"
    if agents_md.exists():
        return

    try:
        # Try loading from project resources directory
        resource_path = _PROJECT_ROOT / "resources" / "workspace" / "AGENTS.md"
        if resource_path.is_file():
            agents_md.write_text(resource_path.read_text(encoding="utf-8"), encoding="utf-8")
            logger.info("Initialized AGENTS.md from package resources")
            return

        # Fallback: create minimal AGENTS.md
        default_content = """# BabiAgent

You are BabiAgent, an expert coding assistant powered by AgentScope.

## Rules

- When the user provides a URL, ALWAYS call fetch_url FIRST
- For GitHub URLs, use github_api_request (NOT fetch_url)
- NEVER fabricate content from resources you have not accessed
- Be cautious with destructive commands
- IMAGE OUTPUT: Wrap image URLs in Markdown syntax for inline rendering
"""
        agents_md.write_text(default_content, encoding="utf-8")
        logger.info("Created default AGENTS.md in workspace")

    except Exception as e:
        logger.warning("Failed to initialize AGENTS.md: %s", e)
