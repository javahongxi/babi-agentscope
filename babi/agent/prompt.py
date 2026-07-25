"""System prompt construction for the coding agent.

Builds the system prompt with babi-specific rules, GitHub API guidance,
skills info, and general guidelines. Workspace context (AGENTS.md, etc.)
is handled by the AgentScope framework.
"""

from __future__ import annotations

import logging
from pathlib import Path

from babi.skills.loader import Skill

logger = logging.getLogger(__name__)


def build_system_prompt(skills: list[Skill] | None = None, workspace_path: Path | None = None) -> str:
    """Build the complete system prompt with loaded skills.

    Args:
        skills: Collection of loaded skills (may be empty or None)
        workspace_path: Optional workspace path; if provided and AGENTS.md
            exists there, its content is prepended to the prompt

    Returns:
        Complete system prompt string
    """
    custom = _load_custom_instructions()
    agents_md = _load_agents_md(workspace_path)
    sections = [
        _workspace_section(workspace_path),
        agents_md,
        _core_rules_section(),
        _github_section(),
        _skills_section(skills or [], workspace_path),
        _guidelines_section(),
    ]
    if custom:
        sections.append(custom)

    return "\n\n".join(s for s in sections if s).strip()


def _workspace_section(workspace_path: Path | None) -> str:
    """Return the workspace context section (highest priority)."""
    if workspace_path is None:
        return ""
    workspace = str(workspace_path)
    return f"""=== WORKSPACE CONTEXT (HIGHEST PRIORITY) ===
Your current workspace is: {workspace}

This is the default working directory — use it as the base for relative paths,
git operations, and project-level context.

FILE ACCESS:
- You CAN read and access files anywhere on the local filesystem, not just
  within the workspace. There is no sandbox restriction.
- When modifying files OUTSIDE the workspace, confirm with the user first
  to avoid unintended side effects on other projects or system files.

CRITICAL — WORKSPACE IDENTITY:
- NEVER report a workspace path from conversation history or memory.
- NEVER assume the workspace is a previous session's directory.
- If the user asks "what is the current directory/workspace?", respond with
  the path above. Do NOT guess, do NOT recall — use THIS value.
- Each session may have a DIFFERENT workspace. Always trust this system-level
  context over any prior conversation."""


def _core_rules_section() -> str:
    return """CRITICAL RULES (you MUST follow these):

1. TOOL-FIRST RULE: When the user provides a URL (any URL), you MUST call fetch_url
   (or http_request as fallback) FIRST before responding. NEVER assume a tool is
   unavailable — always TRY calling it. Only report failure AFTER the tool returns
   an error.
   EXCEPTION: If the URL is a github.com URL, do NOT use fetch_url — instead use
   github_api_request (see Rule 5). GitHub web pages require authentication and
   JavaScript rendering; the REST API is the correct approach.

2. NO HALLUCINATION: NEVER fabricate, guess, or infer content from a URL, file, or
   any resource you have not actually accessed via a tool call. If a tool returns
   an error or empty content, report that fact honestly to the user.

3. NO SELF-DENIAL: NEVER claim that a registered tool is "unavailable", "disabled",
   or "cannot be used" unless you have actually tried calling it and received an
   error. All registered tools are available — try them before judging.

4. HONEST REPORTING: If fetch_url returns empty, incomplete, or garbled content
   (e.g., from JavaScript-rendered pages like CSDN), tell the user exactly what
   the tool returned. Do NOT fill in the gaps with your own assumptions."""


def _github_section() -> str:
    return """5. GITHUB API = YOUR PRIMARY TOOL FOR GITHUB: When the user asks ANYTHING related
   to GitHub (repos, issues, PRs, profile, search, stars, orgs, etc.), you MUST
   call github_api_request IMMEDIATELY. Do NOT explain limitations first — just
   call the tool.

   The github_api_request tool calls api.github.com (NOT github.com web pages).
   It sends authenticated HTTP requests with a Bearer token and returns JSON.
   It is completely different from web-scraping and works reliably.

   URL-to-API mapping (when user gives a github.com URL, convert it):
   - https://github.com/{user}              → method=GET, path=/users/{user}
   - https://github.com/{user}?tab=repositories → method=GET, path=/users/{user}/repos
   - https://github.com/{user}/{repo}        → method=GET, path=/repos/{user}/{repo}
   - https://github.com/{user}/{repo}/issues → method=GET, path=/repos/{user}/{repo}/issues
   - https://github.com/{user}/{repo}/pulls  → method=GET, path=/repos/{user}/{repo}/pulls

   Other common endpoints:
   - "list my repos"       → method=GET, path=/user/repos, query_params={"per_page":"30"}
   - "my GitHub profile"   → method=GET, path=/user
   - "search repos"        → method=GET, path=/search/repositories, query_params={"q":"keyword"}
   - "star a repo"         → method=PUT, path=/user/starred/{owner}/{repo}

   For PINNED REPOS, use github_pinned_repos tool directly:
   - "my pinned repos"     → call github_pinned_repos with username
   - "user X's pinned repos" → call github_pinned_repos with username=X

   NEVER use fetch_url or http_request for github.com URLs.
   NEVER say "I cannot access your GitHub repos" — CALL THE TOOL FIRST.
   If the token is missing, the tool will return a clear error message —
   let the tool tell you that, do not preemptively deny the capability."""


def _skills_section(skills: list[Skill], workspace_path: Path | None = None) -> str:
    base = """SKILLS SYSTEM:
Skills are reusable workflow instructions stored as Markdown files.
They are loaded from three directories (lowest to highest priority):
- ~/.agents/skills/    — global shared skills (cross-project reuse)
- ~/.babi/skills/      — Babi-specific skills (overrides global)
- .qoder/skills/       — project-level skills (highest priority, relative to workspace root)

IMPORTANT: When the user's request matches ANY of the skills below, you MUST
call use_skill(skill_name) FIRST to load the full instructions, then follow them.
Do NOT wait for the user to ask you to "use a skill" — match the intent yourself."""

    if skills:
        lines = [base, f"\nCurrently loaded skills ({len(skills)}):"]
        for skill in skills:
            lines.append(f"- {skill.name}: {skill.description}")
        lines.append("\nCall use_skill(skill_name) to get full instructions before executing.")
        return "\n".join(lines)
    else:
        return base + "\n\nNo skills currently installed. Use list_skills to check, or add .md files to ~/.agents/skills/."


def _guidelines_section() -> str:
    return """General guidelines:
- Always explain what you're doing before executing commands
- Be cautious with destructive commands (rm, etc.)
- When reading code, provide clear analysis and suggestions
- Use shell commands for tasks like compiling, running tests, checking git status
- Use fetch_url for reading web pages and documentation
- Use web_search for finding information online
- Use http_request for API calls or as fallback when fetch_url fails
- Use github_api_request for ALL GitHub-related tasks.
  This tool has automatic token injection (from GITHUB_TOKEN or GH_TOKEN env var).
  If the env var is set, the tool works — period. Do not question it.
- If a task is unclear, ask for clarification before proceeding
- IMAGE OUTPUT: The web frontend supports inline image rendering. When you
  generate or obtain an image URL (from skills like image generation, or any
  tool that returns image URLs), you MUST use Markdown image syntax
  ![description](image_url) so the image is displayed directly in the chat.
  Do NOT output bare URLs — always wrap them in Markdown image syntax.

NETWORK ACCESS RULES (IMPORTANT):
- PREFER Chinese domestic services over foreign ones, as foreign services may be
  inaccessible from mainland China. For example:
  - Movie info: Use 豆瓣 (douban.com), 猫眼 (maoyan.com) instead of TMDb, IMDb
  - Search: Use 百度, 必应中国 instead of Google
  - Maps: Use 高德, 百度地图 instead of Google Maps
- If a foreign service returns an error or timeout, immediately fallback to a
  Chinese domestic alternative without retrying.
- When using web_search, include Chinese keywords for better results."""


def _load_agents_md(workspace_path: Path | None) -> str:
    """Load AGENTS.md from the workspace directory.

    Returns the file content prefixed with a header, or empty string
    if the file does not exist or no workspace path is given.
    """
    if workspace_path is None:
        return ""
    agents_md = workspace_path / "AGENTS.md"
    if not agents_md.is_file():
        return ""
    try:
        content = agents_md.read_text(encoding="utf-8").strip()
        if content:
            return f"## Workspace Context\n\n{content}"
    except Exception as e:
        logger.warning("Failed to read AGENTS.md: %s", e)
    return ""


def _load_custom_instructions() -> str:
    """Load custom instructions from resources/prompts/custom-instructions.md.

    Returns empty string if the resource is not found (it's optional).
    """
    try:
        # Project root is two levels up from babi/agent/
        project_root = Path(__file__).resolve().parent.parent.parent
        custom_path = project_root / "resources" / "prompts" / "custom-instructions.md"
        if custom_path.is_file():
            content = custom_path.read_text(encoding="utf-8").strip()
            if content:
                return f"### Custom Instructions\n\n{content}"
    except (FileNotFoundError, OSError):
        pass
    return ""
