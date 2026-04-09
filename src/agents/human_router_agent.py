import uuid

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.agents.registry import AgentCard

HUMAN_ROUTER_CARD = AgentCard(
    id="human-router-agent",
    name="Human Router Agent",
    description="Передаёт запрос живому оператору",
    supported_methods=["escalation"],
    supported_topics=["complaint", "urgent", "complex"],
    llm_requirements={},
    status="active",
)


class HumanRouterAgent(BaseAgent):
    """Routes requests to a human operator. No LLM calls."""

    def __init__(self, **kwargs) -> None:
        super().__init__(card=HUMAN_ROUTER_CARD, model="", max_steps=1)

    def get_system_prompt(self) -> str:
        return ""

    def get_tools(self) -> list[dict]:
        return []

    def get_tool_executors(self) -> dict:
        return {}

    async def handle(self, request: AgentRequest) -> AgentResponse:
        ticket_id = f"TK-{uuid.uuid4().hex[:8].upper()}"
        reason = request.metadata.get("escalation_reason", "запрос пользователя")

        content = (
            f"Ваш запрос передан оператору. Номер обращения: {ticket_id}.\n"
            f"Причина: {reason}\n"
            f"Среднее время ожидания: ~15 минут.\n"
            f"Оператор свяжется с вами в чате."
        )

        return AgentResponse(
            content=content,
            agent_id=self.card.id,
            model_used="none",
            metadata={"ticket_id": ticket_id},
        )
