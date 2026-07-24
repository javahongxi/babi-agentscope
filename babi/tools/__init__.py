"""Custom tools for BabiAgent."""

from __future__ import annotations

from agentscope.message import TextBlock
from agentscope.tool import ToolChunk
from agentscope.tool._response import ToolResultState


def text_chunk(text: str, state: str = "SUCCESS") -> ToolChunk:
    """Create a ToolChunk containing a single text block.

    Args:
        text: The text content to return.
        state: Result state - "SUCCESS", "ERROR", etc.

    Returns:
        A ToolChunk with the text content.
    """
    return ToolChunk(
        content=[TextBlock(type="text", text=text)],
        state=ToolResultState(state.lower()),
        is_last=True,
    )
