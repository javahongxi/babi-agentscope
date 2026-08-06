"""Configuration management using Pydantic Settings.

Replaces Java's application.yml + Spring @Value injection with type-safe
Python configuration loaded from environment variables and .env files.
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings with environment variable support.

    Settings are loaded from (in priority order):
    1. Environment variables (uppercase, prefixed with BABi_)
    2. .env file in project root
    3. Default values defined below
    """

    model_config = SettingsConfigDict(
        env_prefix="babi_",
        env_file=_ENV_FILE if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8900

    # --- Workspace ---
    workspace: str = "~/babi-agentscope-workspace"

    # --- Model ---
    model_name: str = "qwen3.7-plus"
    fallback_model: str = "qwen-plus"

    # --- Agent ---
    max_iters: int = 20
    max_retries: int = 2
    max_context_messages: int = 30

    # --- Paths ---
    session_dir: Path = Path.home() / ".babi" / "sessions"

    @property
    def dashscope_api_key(self) -> str:
        """Resolve DashScope API key from environment."""
        key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not key:
            raise SystemExit(
                "Error: DASHSCOPE_API_KEY environment variable not set.\n"
                "Get your API key from: https://dashscope.aliyun.com\n"
                "Then set it with: export DASHSCOPE_API_KEY=your_api_key"
            )
        return key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the global settings instance (cached)."""
    return Settings()
