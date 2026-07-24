"""GitHub REST & GraphQL API tool.

The GitHub token is resolved from environment variables:
GITHUB_TOKEN or GH_TOKEN. The agent never sees the raw token.
"""

from __future__ import annotations

import json
import logging
import os
from urllib.parse import urlencode

import httpx

from babi.tools import text_chunk
from babi.utils.helpers import truncate

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


def _resolve_token() -> str | None:
    """Resolve the GitHub token from environment variables.

    Priority: GITHUB_TOKEN > GH_TOKEN
    """
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def github_api_request(
    method: str,
    path: str,
    body: str | None = None,
    query_params: dict[str, str] | None = None,
) -> "ToolChunk":
    """Call the GitHub REST API. Token is injected automatically.

    Use for issues, PRs, comments, repo search, file content, checks, etc.
    Path should start with '/' (e.g. '/repos/owner/repo/issues').
    """
    token = _resolve_token()
    if not token:
        return text_chunk("Error: No GitHub token available. Set GITHUB_TOKEN or GH_TOKEN environment variable.", state="ERROR")

    normalized_path = path or "/"
    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path

    url = GITHUB_API_BASE + normalized_path
    if query_params:
        url += "?" + urlencode(query_params)

    # Intercept GraphQL POST requests
    actual_body = body
    if normalized_path == "/graphql" and method.upper() == "POST" and body:
        actual_body = _fix_graphql_body(body)

    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "BabiAgent/1.0",
        }

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.request(
                method=method.upper() if method else "GET",
                url=url,
                headers=headers,
                content=actual_body,
            )

        response_body = response.text

        # Auto-format pinned repos GraphQL response
        if response.status_code == 200 and normalized_path == "/graphql":
            formatted = _try_format_pinned_repos(response_body)
            if formatted is not None:
                return text_chunk(formatted)

        return text_chunk(f"Status: {response.status_code}\nBody:\n{truncate(response_body, 16000)}")

    except httpx.HTTPError as e:
        return text_chunk(f"Error: {e}", state="ERROR")


def github_pinned_repos(username: str) -> "ToolChunk":
    """Query a GitHub user's pinned repositories via GraphQL.

    Token is injected automatically. Returns up to 6 pinned repos with
    name, description, URL, stars, forks, and primary language.
    """
    token = _resolve_token()
    if not token:
        return text_chunk("Error: No GitHub token available. Set GITHUB_TOKEN or GH_TOKEN environment variable.", state="ERROR")
    if not username or not username.strip():
        return text_chunk("Error: username is required.", state="ERROR")

    query = """query GetPinned($login: String!) {
  user(login: $login) {
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name description url stargazerCount forkCount
          primaryLanguage { name }
        }
      }
    }
  }
}"""

    payload = json.dumps({"query": query, "variables": {"login": username}})

    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "BabiAgent/1.0",
        }

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.post(
                GITHUB_GRAPHQL_URL,
                headers=headers,
                content=payload,
            )

        response_body = response.text

        if response.status_code == 200:
            formatted = _format_pinned_repos_markdown(response_body, username)
            if formatted is not None:
                return text_chunk(formatted)

        return text_chunk(f"Status: {response.status_code}\nBody:\n{truncate(response_body, 16000)}")

    except httpx.HTTPError as e:
        return text_chunk(f"Error: {e}", state="ERROR")


def _try_format_pinned_repos(json_str: str) -> str | None:
    """Try to format a GraphQL response as pinned repos Markdown."""
    try:
        root = json.loads(json_str)
        data = root.get("data")
        if not data:
            return None
        user = data.get("user")
        if not user:
            return None
        pinned = user.get("pinnedItems")
        if not pinned:
            return None
        nodes = pinned.get("nodes")
        if nodes is None:
            return None
        return _do_format_pinned_repos(nodes, None)
    except Exception:
        return None


def _format_pinned_repos_markdown(json_str: str, username: str) -> str | None:
    """Parse pinned repos GraphQL JSON response and return Markdown."""
    try:
        root = json.loads(json_str)
        data = root.get("data")
        if not data:
            return None
        user = data.get("user")
        if not user:
            return None
        pinned = user.get("pinnedItems")
        if not pinned:
            return None
        nodes = pinned.get("nodes")
        if nodes is None:
            return None
        return _do_format_pinned_repos(nodes, username)
    except Exception:
        return None


def _do_format_pinned_repos(nodes: list[dict], username: str | None) -> str:
    """Format repo nodes as Markdown."""
    if not nodes:
        prefix = f"**@{username}** " if username else ""
        return f"{prefix}目前没有置顶任何仓库。"

    lines = []
    if username:
        lines.append(f"## 📌 @{username} 的置顶仓库 ({len(nodes)} 个)\n")
    else:
        lines.append(f"## 📌 置顶仓库 ({len(nodes)} 个)\n")

    for repo in nodes:
        name = str(repo.get("name", ""))
        desc = str(repo.get("description", ""))
        url = str(repo.get("url", ""))
        stars = repo.get("stargazerCount", 0)
        forks = repo.get("forkCount", 0)
        lang_info = repo.get("primaryLanguage")
        lang_name = lang_info.get("name", "") if lang_info else ""
        if lang_name == "null":
            lang_name = ""

        lines.append(f"### [{name}]({url})\n")
        if desc and desc != "null":
            lines.append(f"{desc}\n")
        lines.append(
            f"`Language: {lang_name or 'N/A'}`"
            f"  |  ⭐ {stars}"
            f"  |  🔀 {forks}\n"
        )

    return "\n".join(lines).rstrip()


def _fix_graphql_body(body: str) -> str:
    """Reformat GraphQL query in JSON body to multi-line format."""
    try:
        parsed = json.loads(body)
        query = parsed.get("query")
        if isinstance(query, str):
            parsed["query"] = _format_graphql_query(query)
            return json.dumps(parsed)
    except Exception:
        pass
    return body


def _format_graphql_query(query: str) -> str:
    """Reformat a GraphQL query string to multi-line format."""
    result = []
    depth = 0
    i = 0
    while i < len(query):
        c = query[i]
        if c == "{":
            depth += 1
            result.append(" {\n")
            result.append("  " * depth)
            while i + 1 < len(query) and query[i + 1] == " ":
                i += 1
        elif c == "}":
            depth -= 1
            while result and result[-1].endswith(" "):
                result[-1] = result[-1][:-1]
            result.append("\n")
            if depth >= 0:
                result.append("  " * depth)
            result.append("}")
        else:
            result.append(c)
        i += 1
    return "".join(result).strip()
