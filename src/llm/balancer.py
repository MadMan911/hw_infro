import asyncio
import logging
import random
import time
from enum import Enum
from typing import AsyncIterator

from src.llm.provider import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class BalancingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LATENCY_BASED = "latency_based"


class CircuitState(str, Enum):
    CLOSED = "closed"      # normal operation
    OPEN = "open"          # failing, skip provider
    HALF_OPEN = "half_open"  # testing recovery


class CircuitBreaker:
    """Per-provider circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    FAILURE_THRESHOLD = 3       # consecutive failures to open
    RECOVERY_TIMEOUT = 60.0     # seconds before half-open retry
    SUCCESS_THRESHOLD = 1       # successes in half-open to close

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self.state = CircuitState.CLOSED
        self._failures = 0
        self._last_failure_time: float = 0.0
        self._successes_in_half_open = 0

    def is_available(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.RECOVERY_TIMEOUT:
                self.state = CircuitState.HALF_OPEN
                self._successes_in_half_open = 0
                logger.info("Circuit %s → HALF_OPEN", self.provider_name)
                return True
            return False
        # HALF_OPEN — allow one probe
        return True

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._successes_in_half_open += 1
            if self._successes_in_half_open >= self.SUCCESS_THRESHOLD:
                self.state = CircuitState.CLOSED
                self._failures = 0
                logger.info("Circuit %s → CLOSED (recovered)", self.provider_name)
        elif self.state == CircuitState.CLOSED:
            self._failures = 0

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            if self._failures >= self.FAILURE_THRESHOLD:
                self.state = CircuitState.OPEN
                logger.warning(
                    "Circuit %s → OPEN after %d failures", self.provider_name, self._failures
                )


class LLMBalancer:
    """Routes LLM requests across registered providers with circuit breaking and failover."""

    MAX_RETRIES = 2  # retry on different providers after failure

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
        # circuit breakers: provider_name -> CircuitBreaker
        self._circuits: dict[str, CircuitBreaker] = {
            p.name: CircuitBreaker(p.name) for p in providers
        }
        # background health-check task
        self._health_task: asyncio.Task | None = None

    # ─── Background health check ───

    async def start_health_checks(self, interval: float = 30.0) -> None:
        """Start background health-check loop."""
        self._health_task = asyncio.create_task(self._health_check_loop(interval))

    async def _health_check_loop(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            for provider in self.providers:
                try:
                    healthy = await provider.health_check()
                    cb = self._circuits[provider.name]
                    if healthy:
                        cb.record_success()
                    else:
                        cb.record_failure()
                        logger.warning("Health check failed for %s", provider.name)
                except Exception as exc:
                    self._circuits[provider.name].record_failure()
                    logger.warning("Health check error for %s: %s", provider.name, exc)

    async def stop_health_checks(self) -> None:
        if self._health_task:
            self._health_task.cancel()

    # ─── Provider selection ───

    def get_providers_for_model(self, model: str) -> list[BaseLLMProvider]:
        return [
            p for p in self.providers
            if p.supports_model(model) and self._circuits[p.name].is_available()
        ]

    async def _next_round_robin(self, candidates: list[BaseLLMProvider]) -> BaseLLMProvider:
        async with self._lock:
            provider = candidates[self._rr_index % len(candidates)]
            self._rr_index += 1
            return provider

    def _next_weighted(self, candidates: list[BaseLLMProvider]) -> BaseLLMProvider:
        w = [self.weights.get(p.name, 1.0) for p in candidates]
        return random.choices(candidates, weights=w, k=1)[0]

    def _next_latency_based(self, candidates: list[BaseLLMProvider]) -> BaseLLMProvider:
        return min(candidates, key=lambda p: self._latencies.get(p.name, 0.0))

    async def _select_provider(
        self, model: str, exclude: set[str] | None = None
    ) -> BaseLLMProvider:
        candidates = self.get_providers_for_model(model)
        if exclude:
            candidates = [p for p in candidates if p.name not in exclude]
        if not candidates:
            raise ValueError(f"No available provider supports model '{model}'")

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
        alpha = 0.3
        prev = self._latencies.get(provider_name, latency_ms)
        self._latencies[provider_name] = alpha * latency_ms + (1 - alpha) * prev

    # ─── Request routing with failover ───

    async def route_request(
        self,
        messages: list[dict],
        model: str,
        stream: bool = False,
        **kwargs,
    ) -> "LLMResponse | AsyncIterator[str]":
        tried: set[str] = set()

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                provider = await self._select_provider(model, exclude=tried)
            except ValueError:
                raise ValueError(f"No provider available for model '{model}' after {attempt} retries")

            tried.add(provider.name)
            cb = self._circuits[provider.name]

            try:
                if stream:
                    result = await provider.chat_completion(messages, model, stream=True, **kwargs)
                    cb.record_success()
                    return result

                response = await provider.chat_completion(messages, model, stream=False, **kwargs)
                cb.record_success()
                self._update_latency(provider.name, response.latency_ms)
                return response

            except Exception as exc:
                cb.record_failure()
                logger.warning(
                    "Provider %s failed (attempt %d/%d): %s",
                    provider.name, attempt + 1, self.MAX_RETRIES + 1, exc,
                )
                if attempt == self.MAX_RETRIES:
                    raise

        raise RuntimeError("Unreachable")

    # ─── Health & state ───

    async def health_check_all(self) -> dict[str, bool]:
        results = {}
        for provider in self.providers:
            results[provider.name] = await provider.health_check()
        return results

    def circuit_states(self) -> dict[str, str]:
        return {name: cb.state.value for name, cb in self._circuits.items()}

    async def close(self) -> None:
        await self.stop_health_checks()
        for provider in self.providers:
            await provider.close()
