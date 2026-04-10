from src.agents.base import BaseAgent
from src.agents.registry import AgentCard
from src.agents.tools.faq_tools import FAQ_TOOL_EXECUTORS, FAQ_TOOLS

FAQ_SYSTEM_PROMPT = """\
Ты — помощник техподдержки компании TechCorp.
Отвечай на вопросы пользователей СТРОГО на основе базы знаний.

Правила:
1. Используй инструмент search_faq для поиска ответа в базе знаний.
2. Если ответ найден — дай краткий ответ (2-4 предложения) на основе найденной информации.
3. Если ответа нет в базе — вызови escalate с подходящим target:
   - diagnostics — если вопрос про техническую проблему или ошибку
   - billing — если вопрос про оплату, тариф или счёт
   - escalation — если вопрос сложный или не подходит ни под одну категорию
4. Не придумывай информацию, которой нет в базе знаний.
5. Отвечай на русском языке, вежливо и профессионально.\
"""

FAQ_CARD = AgentCard(
    id="faq-agent",
    name="FAQ Agent",
    description="Отвечает на частые вопросы из базы знаний",
    supported_methods=["faq", "general_question"],
    supported_topics=["account", "password", "general", "subscription"],
    llm_requirements={"preferred_model": "cheap", "max_tokens": 500},
)


class FaqAgent(BaseAgent):
    def __init__(self, model: str, max_steps: int = 6) -> None:
        super().__init__(card=FAQ_CARD, model=model, max_steps=max_steps)

    def get_system_prompt(self) -> str:
        return FAQ_SYSTEM_PROMPT

    def get_tools(self) -> list[dict]:
        return FAQ_TOOLS

    def get_tool_executors(self) -> dict:
        return FAQ_TOOL_EXECUTORS.copy()
