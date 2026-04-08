from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from src.agents.registry import AgentCard


class AgentRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    content: str
    agent_id: str
    model_used: str = ""
    confidence: float = 0.0
    metadata: dict = Field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, card: AgentCard) -> None:
        self.card = card

    def get_card(self) -> AgentCard:
        return self.card

    @abstractmethod
    async def handle(self, request: AgentRequest) -> AgentResponse:
        """Process a user request. May call LLM via the balancer."""
