import pytest
from unittest.mock import AsyncMock

from src.llm.balancer import LLMBalancer, BalancingStrategy
from src.llm.provider import BaseLLMProvider, LLMResponse


class FakeProvider(BaseLLMProvider):
    """Minimal provider for testing."""

    def __init__(self, name: str, models: list[str], latency: float = 10.0):
        super().__init__(name=name, models=models)
        self._latency = latency

    async def chat_completion(self, messages, model, stream=False, **kwargs):
        return LLMResponse(
            content=f"response from {self.name}",
            model=model,
            provider=self.name,
            usage={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
            latency_ms=self._latency,
        )

    async def health_check(self) -> bool:
        return True


@pytest.fixture
def providers():
    return [
        FakeProvider("provider-a", ["mock-model", "model-x"]),
        FakeProvider("provider-b", ["mock-model", "model-y"]),
        FakeProvider("provider-c", ["model-y"]),
    ]


class TestRoundRobin:
    @pytest.mark.asyncio
    async def test_alternates_between_providers(self, providers):
        balancer = LLMBalancer(providers[:2], strategy=BalancingStrategy.ROUND_ROBIN)

        results = []
        for _ in range(4):
            resp = await balancer.route_request([{"role": "user", "content": "hi"}], "mock-model")
            results.append(resp.provider)

        assert results == ["provider-a", "provider-b", "provider-a", "provider-b"]

    @pytest.mark.asyncio
    async def test_single_provider_for_model(self, providers):
        balancer = LLMBalancer(providers, strategy=BalancingStrategy.ROUND_ROBIN)
        resp = await balancer.route_request([{"role": "user", "content": "hi"}], "model-x")
        assert resp.provider == "provider-a"


class TestWeighted:
    @pytest.mark.asyncio
    async def test_weighted_selection(self, providers):
        balancer = LLMBalancer(
            providers[:2],
            strategy=BalancingStrategy.WEIGHTED,
            weights={"provider-a": 1.0, "provider-b": 0.0},
        )
        # With weight 0 for b, all requests should go to a
        for _ in range(10):
            resp = await balancer.route_request([{"role": "user", "content": "hi"}], "mock-model")
            assert resp.provider == "provider-a"


class TestLatencyBased:
    @pytest.mark.asyncio
    async def test_picks_lowest_latency(self):
        fast = FakeProvider("fast", ["mock-model"], latency=10.0)
        slow = FakeProvider("slow", ["mock-model"], latency=500.0)
        balancer = LLMBalancer([fast, slow], strategy=BalancingStrategy.LATENCY_BASED)

        # Prime latency tracking
        await balancer.route_request([{"role": "user", "content": "hi"}], "mock-model")
        await balancer.route_request([{"role": "user", "content": "hi"}], "mock-model")

        # After tracking, fast provider should dominate
        resp = await balancer.route_request([{"role": "user", "content": "hi"}], "mock-model")
        assert resp.provider == "fast"


class TestNoProvider:
    @pytest.mark.asyncio
    async def test_raises_on_unsupported_model(self, providers):
        balancer = LLMBalancer(providers, strategy=BalancingStrategy.ROUND_ROBIN)
        with pytest.raises(ValueError, match="No provider available for model"):
            await balancer.route_request(
                [{"role": "user", "content": "hi"}], "nonexistent-model"
            )


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_all(self, providers):
        balancer = LLMBalancer(providers)
        statuses = await balancer.health_check_all()
        assert all(statuses.values())
        assert len(statuses) == 3
