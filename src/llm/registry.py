from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    id: str
    name: str
    url: str
    api_key: str = ""
    models: list[str] = Field(default_factory=list)
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0
    rate_limit_rpm: int = 1000
    rate_limit_tpm: int = 100000
    priority: int = 1
    weight: float = 1.0
    status: str = "active"  # active | disabled | unhealthy
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProviderRegistry:
    """In-memory registry for dynamic LLM provider configuration."""

    def __init__(self) -> None:
        self._store: dict[str, ProviderConfig] = {}

    def register(self, config: ProviderConfig) -> None:
        self._store[config.id] = config

    def unregister(self, provider_id: str) -> None:
        if provider_id not in self._store:
            raise KeyError(f"Provider '{provider_id}' not registered")
        del self._store[provider_id]

    def update(self, provider_id: str, updates: dict) -> None:
        if provider_id not in self._store:
            raise KeyError(f"Provider '{provider_id}' not registered")
        config = self._store[provider_id]
        self._store[provider_id] = config.model_copy(update=updates)

    def get(self, provider_id: str) -> ProviderConfig:
        if provider_id not in self._store:
            raise KeyError(f"Provider '{provider_id}' not registered")
        return self._store[provider_id]

    def get_all(self) -> list[ProviderConfig]:
        return list(self._store.values())

    def get_active(self) -> list[ProviderConfig]:
        return [c for c in self._store.values() if c.status == "active"]

    def get_by_model(self, model: str) -> list[ProviderConfig]:
        return [c for c in self.get_active() if model in c.models]
