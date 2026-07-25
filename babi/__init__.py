"""Babi Agent - A coding agent application built with AgentScope."""

import asyncio
import inspect

# Monkey-patch deprecated asyncio.iscoroutinefunction with inspect equivalent
# to suppress DeprecationWarning from third-party libs (e.g. aiofiles) on Python 3.14+
if hasattr(asyncio, "iscoroutinefunction"):
    asyncio.iscoroutinefunction = inspect.iscoroutinefunction

__version__ = "1.0.0"
