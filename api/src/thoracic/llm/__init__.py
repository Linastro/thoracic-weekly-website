"""LLM layer for MiniMax M3 (OpenAI-compatible chat completions)."""

from .client import MiniMaxClient, default_client  # noqa: F401
from .errors import (  # noqa: F401
    LlmAuthError,
    LlmError,
    LlmJsonParseError,
    LlmRateLimitError,
    LlmServerError,
)

__all__ = [
    "MiniMaxClient",
    "default_client",
    "LlmError",
    "LlmAuthError",
    "LlmRateLimitError",
    "LlmServerError",
    "LlmJsonParseError",
]
