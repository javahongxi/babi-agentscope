"""Tool for fetching web page content.

Fetches a URL and returns a simplified text representation with structure preserved
(headings, code blocks, lists). Uses smart content extraction to focus on the main
article body, reducing noise from navigation, ads, and sidebars.
"""

from __future__ import annotations

import re
from html import unescape

import httpx

from babi.tools import text_chunk
from babi.tools.github_url import check_github_url
from babi.utils.helpers import truncate

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_MULTI_BLANK = re.compile(r"[\r\n]{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")

# Content area extraction patterns (ordered by priority)
_CONTENT_AREA_PATTERNS = [
    re.compile(r"<article[^>]*>(.*?)</article>", re.DOTALL | re.IGNORECASE),
    re.compile(
        r'<div[^>]*class="[^"]*(?:article|blog|post|content|entry|markdown|blog-content|article-content)[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL | re.IGNORECASE,
    ),
    re.compile(r"<main[^>]*>(.*?)</main>", re.DOTALL | re.IGNORECASE),
    re.compile(
        r'<div[^>]*id="[^"]*(?:article|content|main|post)[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL | re.IGNORECASE,
    ),
]


def fetch_url(url: str) -> "ToolChunk":
    """Fetch a URL and return its content as readable text with structure preserved.

    Works with most web pages including blogs and documentation.
    For APIs, use http_request instead.
    NOTE: Do NOT use this for github.com URLs — use github_api_request instead.
    """
    # Intercept GitHub web URLs
    redirect = check_github_url(url)
    if redirect is not None:
        return text_chunk(redirect)

    try:
        with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            },
        ) as client:
            response = client.get(url)

        if response.status_code >= 400:
            return text_chunk(f"Error: HTTP {response.status_code} for {url}", state="ERROR")

        text = _extract_and_convert(response.text)
        if not text.strip():
            return text_chunk("Warning: Page returned empty content. The site may require JavaScript rendering or authentication.")

        return text_chunk(truncate(text, 30000))

    except httpx.HTTPError as e:
        return text_chunk(f"Error fetching URL: {e}", state="ERROR")


def _extract_and_convert(html: str) -> str:
    """Extract main content area from HTML, then convert to readable text."""
    if not html:
        return ""

    # Remove script, style, nav, footer, header, aside elements
    cleaned = html
    for tag in ("script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"):
        cleaned = re.sub(rf"(?is)<{tag}[^>]*>.*?</{tag}>", "", cleaned)

    # Try to extract main content area
    content = None
    for pattern in _CONTENT_AREA_PATTERNS:
        m = pattern.search(cleaned)
        if m:
            candidate = m.group(1)
            if content is None or len(candidate) > len(content):
                content = candidate

    # Fallback to full cleaned HTML if no content area found
    if content is None:
        content = cleaned

    return _html_to_text(content)


def _html_to_text(html: str) -> str:
    """Convert HTML to readable text, preserving structure."""
    text = unescape(html)

    # Headings -> prefixed with #
    text = re.sub(r"(?is)<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text)
    text = re.sub(r"(?is)<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text)
    text = re.sub(r"(?is)<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text)
    text = re.sub(r"(?is)<h4[^>]*>(.*?)</h4>", r"\n#### \1\n", text)
    text = re.sub(r"(?is)<h5[^>]*>(.*?)</h5>", r"\n##### \1\n", text)
    text = re.sub(r"(?is)<h6[^>]*>(.*?)</h6>", r"\n###### \1\n", text)

    # Code blocks
    text = re.sub(r"(?is)<pre[^>]*>\s*<code[^>]*>(.*?)</code>\s*</pre>", r"\n```\n\1\n```\n", text)
    text = re.sub(r"(?is)<pre[^>]*>(.*?)</pre>", r"\n```\n\1\n```\n", text)

    # Inline code
    text = re.sub(r"(?is)<code[^>]*>(.*?)</code>", r"`\1`", text)

    # Line breaks and paragraphs
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)<p[^>]*>", "", text)

    # List items
    text = re.sub(r"(?is)<li[^>]*>", "\n- ", text)

    # Horizontal rule
    text = re.sub(r"(?is)<hr[^>]*/?>", "\n---\n", text)

    # Links -> text(url)
    text = re.sub(r'(?is)<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"\2(\1)", text)

    # Images -> alt text
    text = re.sub(r'(?is)<img[^>]*alt="([^"]*)"[^>]*/?>', r"[\1]", text)
    text = re.sub(r"(?is)<img[^>]*>", "", text)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Clean up whitespace
    text = _MULTI_BLANK.sub("\n\n", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = _MULTI_BLANK.sub("\n\n", text)

    return text.strip()
