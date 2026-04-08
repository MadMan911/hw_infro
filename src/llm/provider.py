from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: dict = field(default_factory=dict)
    latency_ms: float = 0.0


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    name: str
    models: list[str]
    base_url: str

    def __init__(self, name: str, models: list[str], base_url: str = ""):
        self.name = name
        self.models = models
        self.base_url = base_url

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        stream: bool = False,
        **kwargs,
    ) -> LLMResponse | AsyncIterator[str]:
        """Non-streaming: return LLMResponse. Streaming: return AsyncIterator[str]."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if provider is healthy."""

    async def close(self) -> None:
        """Cleanup resources. Override if needed."""

    def supports_model(self, model: str) -> bool:
        return model in self.models
