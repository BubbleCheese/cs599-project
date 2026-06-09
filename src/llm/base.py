"""
LLM Abstract Base Class
Defines the interface for all LLM providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for LLM providers."""
    provider: str = "mock"  # "deepseek", "openai", "mock"
    model: str = "deepseek-chat"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 500
    timeout: int = 30


class LLMResponse(BaseModel):
    """Standardized LLM response."""
    content: str = ""
    model: str = ""
    usage: dict = Field(default_factory=dict)
    error: Optional[str] = None


class BaseLLM(ABC):
    """Abstract base for LLM providers."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Send a chat completion request."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available (API key valid, etc.)."""
        pass

    def _build_messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        """Build OpenAI-compatible message format."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return messages
