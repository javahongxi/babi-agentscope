"""Context truncation middleware.

Truncates the conversation context before sending to the LLM,
keeping only the most recent messages to control token usage.

This is a placeholder for future implementation. The AgentScope Python
SDK may handle context management differently than Java.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ContextTruncateMiddleware:
    """Middleware that truncates conversation context.

    Preserves tool call/result pairs — never cuts between
    an assistant message containing tool calls and the corresponding results.

    Note: This is a placeholder. Actual implementation depends on
    AgentScope Python SDK's middleware API.
    """

    def __init__(self, max_messages: int = 30) -> None:
        if max_messages < 2:
            raise ValueError(f"max_messages must be >= 2, got: {max_messages}")
        self.max_messages = max_messages
        logger.debug("ContextTruncateMiddleware initialized with max_messages=%d", max_messages)
