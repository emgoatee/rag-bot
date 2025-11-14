from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv(*_args, **_kwargs):
        """Fallback no-op when python-dotenv is not installed."""
        return False

try:
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover - optional dependency
    BaseSettings = object  # type: ignore[assignment]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    api_key: str = os.getenv("GOOGLE_AI_API_KEY") or ""
    model: str = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash-002")
    file_search_store: Optional[str] = os.getenv("FILE_SEARCH_STORE_ID")
    max_chunks: int = int(os.getenv("MAX_CHUNKS", 16))
    temperature: float = float(os.getenv("TEMPERATURE", 0.3))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        # Don't raise on import - let the app start and fail later if key is actually needed
        return cls()


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""

    return Settings.from_env()

