from src.agents.base import BaseAgent
from src.agents.registry import AgentCard
from src.agents.tools.billing_tools import BILLING_TOOLS, BILLING_TOOL_EXECUTORS

BILLING_SYSTEM_PROMPT = """\
Ты — специалист по биллингу компании TechCorp.
Помоги пользователю с вопросами по оплате, тарифам и счетам.

Правила:
1. Используй доступные инструменты для получения данных:
   - get_account_info — информация об аккаунте (баланс, тариф)
   - get_tariff_info — подробности о тарифном плане
   - get_payment_history — история платежей
2. Называй конкретные цифры из системы (баланс, стоимость, даты).
3. Если пользователь хочет оспорить платёж или нужен возврат средств —
   объясни процедуру и вызови escalate с target="escalation" для подключения оператора.
4. Никогда не запрашивай номер банковской карты, CVV или другие платёжные данные.
5. Если вопрос не связан с оплатой — вызови escalate с подходящим target.
6. Отвечай на русском языке, вежливо и профессионально.\
"""

BILLING_CARD = AgentCard(
    id="billing-agent",
    name="Billing Agent",
    description="Помощь с вопросами по оплате, тарифам и счетам",
    supported_methods=["billing"],
    supported_topics=["payment", "invoice", "pricing", "subscription", "tariff"],
    llm_requirements={"preferred_model": "cheap", "max_tokens": 800},
)


class BillingAgent(BaseAgent):
    def __init__(self, model: str, max_steps: int = 6) -> None:
        super().__init__(card=BILLING_CARD, model=model, max_steps=max_steps)

    def get_system_prompt(self) -> str:
        return BILLING_SYSTEM_PROMPT

    def get_tools(self) -> list[dict]:
        return BILLING_TOOLS

    def get_tool_executors(self) -> dict:
        return BILLING_TOOL_EXECUTORS.copy()
