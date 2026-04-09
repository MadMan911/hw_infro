from src.agents.base import BaseAgent
from src.agents.registry import AgentCard
from src.agents.tools.diagnostics_tools import DIAGNOSTICS_TOOLS, DIAGNOSTICS_TOOL_EXECUTORS

DIAGNOSTICS_SYSTEM_PROMPT = """\
Ты — инженер техподдержки компании TechCorp.
Помоги пользователю диагностировать и решить техническую проблему.

Правила:
1. Используй доступные инструменты для сбора информации:
   - check_service_status — проверить статус сервиса
   - lookup_error_code — найти информацию об ошибке по коду
   - get_troubleshooting_steps — получить шаги диагностики по типу проблемы
2. Проанализируй собранные данные и предложи пошаговую инструкцию (не более 5 шагов).
3. Если информации недостаточно — задай ОДИН уточняющий вопрос.
4. Если проблема связана с оплатой или тарифами — вызови escalate с target="billing".
5. Если проблема критическая и не решается — вызови escalate с target="escalation".
6. Отвечай на русском языке.\
"""

DIAGNOSTICS_CARD = AgentCard(
    id="diagnostics-agent",
    name="Diagnostics Agent",
    description="Диагностика и решение технических проблем",
    supported_methods=["diagnostics"],
    supported_topics=["error", "bug", "crash", "performance", "connection"],
    llm_requirements={"preferred_model": "strong", "max_tokens": 1000},
)


class DiagnosticsAgent(BaseAgent):
    def __init__(self, model: str, max_steps: int = 6) -> None:
        super().__init__(card=DIAGNOSTICS_CARD, model=model, max_steps=max_steps)

    def get_system_prompt(self) -> str:
        return DIAGNOSTICS_SYSTEM_PROMPT

    def get_tools(self) -> list[dict]:
        return DIAGNOSTICS_TOOLS

    def get_tool_executors(self) -> dict:
        return DIAGNOSTICS_TOOL_EXECUTORS.copy()
