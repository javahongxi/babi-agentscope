"""GitHub URL checker: detects github.com web URLs and suggests API alternatives.

GitHub web pages require authentication and JavaScript rendering,
so fetch_url / http_request cannot extract useful content from them.
The GitHub REST API (api.github.com) is the correct approach.
"""

from urllib.parse import urlparse


def check_github_url(url: str | None) -> str | None:
    """Check if the URL is a github.com web URL (not api.github.com).

    Returns:
        Redirect message if GitHub URL, None otherwise.
    """
    if not url:
        return None

    lower = url.lower()
    if "github.com" not in lower:
        return None
    # Skip if it's already an API URL
    if "api.github.com" in lower:
        return None

    # Parse the path segments
    try:
        parsed = urlparse(url)
        path = parsed.path or ""
    except Exception:
        # Fallback: extract path manually
        idx = lower.find("github.com")
        if idx < 0:
            return None
        path = url[idx + len("github.com"):]
        q_idx = path.find("?")
        if q_idx >= 0:
            path = path[:q_idx]

    segments = [s for s in path.split("/") if s]
    user = segments[0] if len(segments) > 0 else ""
    repo = segments[1] if len(segments) > 1 else ""
    sub = segments[2] if len(segments) > 2 else ""

    parts = [
        "[REDIRECT] github.com URLs cannot be fetched as web pages "
        "(GitHub requires authentication and JavaScript rendering).",
        "Use github_api_request instead. Here is the mapping:\n",
    ]

    if not user:
        parts.append("- Profile: method=GET, path=/user")
        parts.append("- List your repos: method=GET, path=/user/repos")
    elif not repo:
        parts.append(f"- User profile: method=GET, path=/users/{user}")
        parts.append(f'- User repos: method=GET, path=/users/{user}/repos, query_params={{"per_page":"30"}}')
    elif not sub or sub in ("tree", "blob"):
        parts.append(f"- Repo details: method=GET, path=/repos/{user}/{repo}")
        parts.append(f"- Repo topics: method=GET, path=/repos/{user}/{repo}/topics")
    elif sub == "issues":
        parts.append(f"- List issues: method=GET, path=/repos/{user}/{repo}/issues")
    elif sub == "pulls":
        parts.append(f"- List PRs: method=GET, path=/repos/{user}/{repo}/pulls")
    elif sub == "actions":
        parts.append(f"- List workflows: method=GET, path=/repos/{user}/{repo}/actions/workflows")
    else:
        parts.append(f"- Repo details: method=GET, path=/repos/{user}/{repo}")

    parts.append("\nToken is auto-injected. Just call github_api_request with the parameters above.")
    return "\n".join(parts)
