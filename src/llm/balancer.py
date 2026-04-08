import asyncio
import random
from enum import Enum
from typing import AsyncIterator

from src.llm.provider import BaseLLMProvider, LLMResponse


class BalancingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LATENCY_BASED = "latency_based"


class LLMBalancer:
    """Routes LLM requests across registered providers."""

    def __init__(
        self,
        providers: list[BaseLLMProvider],
        strategy: BalancingStrategy = BalancingStrategy.ROUND_ROBIN,
        weights: dict[str, float] | None = None,
    ):
        self.providers = providers
        self.strategy = strategy
        self.weights = weights or {}
        self._rr_index = 0
        self._lock = asyncio.Lock()
        # latency tracking: provider_name -> rolling average ms
        self._latencies: dict[str, float] = {p.name: 0.0 for p in providers}

    def get_providers_for_model(self, model: str) -> list[BaseLLMProvider]:
        return [p for p in self.providers if p.supports_model(model)]

    async def _next_round_robin(self, candidates: list[BaseLLMProvider]) -> BaseLLMProvider:
        async with self._lock:
            provider = candidates[self._rr_index % len(candidates)]
            self._rr_index += 1
            return provider

    def _next_weighted(self, candidates: list[BaseLLMProvider]) -> BaseLLMProvider:
        w = [self.weights.get(p.name, 1.0) for p in candidates]
        return random.choices(candidates, weights=w, k=1)[0]

    def _next_latency_based(self, candidates: list[BaseLLMProvider]) -> BaseLLMProvider:
        # Pick provider with lowest rolling average latency
        best = min(candidates, key=lambda p: self._latencies.get(p.name, 0.0))
        return best

    async def _select_provider(self, model: str) -> BaseLLMProvider:
        candidates = self.get_providers_for_model(model)
        if not candidates:
            raise ValueError(f"No provider supports model '{model}'")

        if len(candidates) == 1:
            return candidates[0]

        if self.strategy == BalancingStrategy.ROUND_ROBIN:
            return await self._next_round_robin(candidates)
        elif self.strategy == BalancingStrategy.WEIGHTED:
            return self._next_weighted(candidates)
        elif self.strategy == BalancingStrategy.LATENCY_BASED:
            return self._next_latency_based(candidates)

        return candidates[0]

    def _update_latency(self, provider_name: str, latency_ms: float) -> None:
        alpha = 0.3  # exponential moving average
        prev = self._latencies.get(provider_name, latency_ms)
        self._latencies[provider_name] = alpha * latency_ms + (1 - alpha) * prev

    async def route_request(
        self,
        messages: list[dict],
        model: str,
        stream: bool = False,
        **kwargs,
    ) -> LLMResponse | AsyncIterator[str]:
        provider = await self._select_provider(model)

        if stream:
            return await provider.chat_completion(messages, model, stream=True, **kwargs)

        response = await provider.chat_completion(messages, model, stream=False, **kwargs)
        self._update_latency(provider.name, response.latency_ms)
        return response

    async def health_check_all(self) -> dict[str, bool]:
        results = {}
        for provider in self.providers:
            results[provider.name] = await provider.health_check()
        return results

    async def close(self) -> None:
        for provider in self.providers:
            await provider.close()
