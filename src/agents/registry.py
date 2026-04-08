from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AgentCard(BaseModel):
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    supported_methods: list[str]
    supported_topics: list[str]
    llm_requirements: dict = Field(default_factory=dict)
    status: str = "active"
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentRegistry:
    """In-memory registry of agent cards."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentCard] = {}

    async def register(self, card: AgentCard) -> None:
        self._agents[card.id] = card

    async def unregister(self, agent_id: str) -> None:
        if agent_id not in self._agents:
            raise KeyError(f"Agent '{agent_id}' not found")
        del self._agents[agent_id]

    async def get(self, agent_id: str) -> AgentCard:
        if agent_id not in self._agents:
            raise KeyError(f"Agent '{agent_id}' not found")
        return self._agents[agent_id]

    async def list_all(self) -> list[AgentCard]:
        return list(self._agents.values())

    async def find_by_method(self, method: str) -> list[AgentCard]:
        return [
            card for card in self._agents.values()
            if method in card.supported_methods and card.status == "active"
        ]

    async def find_by_topic(self, topic: str) -> list[AgentCard]:
        return [
            card for card in self._agents.values()
            if topic in card.supported_topics and card.status == "active"
        ]
