"""Tests for agents, tools, and classifier."""

import pytest

from src.agents.base import AgentRequest
from src.agents.faq_agent import FaqAgent
from src.agents.diagnostics_agent import DiagnosticsAgent
from src.agents.billing_agent import BillingAgent
from src.agents.human_router_agent import HumanRouterAgent
from src.agents.tools.faq_tools import search_faq
from src.agents.tools.diagnostics_tools import (
    check_service_status,
    lookup_error_code,
    get_troubleshooting_steps,
)
from src.agents.tools.billing_tools import (
    get_account_info,
    get_tariff_info,
    get_payment_history,
)
from src.routing.classifier import classify_rule_based


# ─── Tool tests ───


class TestFaqTools:
    def test_search_finds_password(self):
        result = search_faq("сменить пароль")
        assert "пароль" in result.lower()

    def test_search_finds_tariff(self):
        result = search_faq("тариф стоимость")
        assert "руб" in result

    def test_search_no_results(self):
        result = search_faq("xyz абракадабра")
        assert "не найдено" in result.lower()


class TestDiagnosticsTools:
    def test_service_status_existing(self):
        result = check_service_status("api")
        assert "online" in result

    def test_service_status_degraded(self):
        result = check_service_status("billing")
        assert "degraded" in result

    def test_service_status_unknown(self):
        result = check_service_status("nonexistent")
        assert "не найден" in result.lower()

    def test_lookup_error_known(self):
        result = lookup_error_code("E-403")
        assert "авторизации" in result.lower() or "биллинг" in result.lower()

    def test_lookup_error_unknown(self):
        result = lookup_error_code("E-999")
        assert "не найден" in result.lower()

    def test_troubleshooting_by_type(self):
        result = get_troubleshooting_steps("connection")
        assert "интернет" in result.lower()

    def test_troubleshooting_by_keyword(self):
        result = get_troubleshooting_steps("приложение тормозит")
        assert "кэш" in result.lower()

    def test_troubleshooting_unknown(self):
        result = get_troubleshooting_steps("xyz")
        assert "не удалось" in result.lower()


class TestBillingTools:
    def test_account_info_existing(self):
        result = get_account_info("user-123")
        assert "Иван" in result
        assert "Стандарт" in result

    def test_account_info_missing(self):
        result = get_account_info("user-000")
        assert "не найден" in result.lower()

    def test_tariff_info(self):
        result = get_tariff_info("Премиум")
        assert "990" in result
        assert "безлимит" in result.lower()

    def test_tariff_info_missing(self):
        result = get_tariff_info("Суперплан")
        assert "не найден" in result.lower()

    def test_payment_history(self):
        result = get_payment_history("user-123")
        assert "дубль" in result.lower()

    def test_payment_history_empty(self):
        result = get_payment_history("user-789")
        assert "пуста" in result.lower()


# ─── Classifier tests ───


class TestRuleBasedClassifier:
    def test_diagnostics_error(self):
        result = classify_rule_based("У меня ошибка E-403")
        assert result.method == "diagnostics"

    def test_billing_payment(self):
        result = classify_rule_based("Хочу узнать баланс и сменить тариф")
        assert result.method == "billing"

    def test_escalation_complaint(self):
        result = classify_rule_based("Хочу поговорить с оператором, жалоба")
        assert result.method == "escalation"

    def test_faq_password(self):
        result = classify_rule_based("Как сменить пароль?")
        assert result.method == "faq"

    def test_faq_fallback(self):
        result = classify_rule_based("Привет")
        assert result.method == "faq"
        assert result.confidence < 0.5


# ─── Agent card tests ───


class TestAgentCards:
    def test_faq_agent_card(self):
        agent = FaqAgent(model="openai/gpt-4o-mini")
        card = agent.get_card()
        assert card.id == "faq-agent"
        assert "faq" in card.supported_methods

    def test_diagnostics_agent_card(self):
        agent = DiagnosticsAgent(model="openai/gpt-4o-mini")
        card = agent.get_card()
        assert card.id == "diagnostics-agent"
        assert "diagnostics" in card.supported_methods

    def test_billing_agent_card(self):
        agent = BillingAgent(model="openai/gpt-4o-mini")
        card = agent.get_card()
        assert card.id == "billing-agent"
        assert "billing" in card.supported_methods

    def test_human_router_card(self):
        agent = HumanRouterAgent()
        card = agent.get_card()
        assert card.id == "human-router-agent"
        assert "escalation" in card.supported_methods


# ─── Human Router (no LLM needed) ───


class TestHumanRouter:
    @pytest.mark.asyncio
    async def test_creates_ticket(self):
        agent = HumanRouterAgent()
        request = AgentRequest(message="Хочу поговорить с оператором")
        response = await agent.handle(request)
        assert "TK-" in response.content
        assert "оператору" in response.content
        assert response.agent_id == "human-router-agent"

    @pytest.mark.asyncio
    async def test_includes_escalation_reason(self):
        agent = HumanRouterAgent()
        request = AgentRequest(
            message="Помогите",
            metadata={"escalation_reason": "проблема с биллингом"},
        )
        response = await agent.handle(request)
        assert "биллинг" in response.content.lower()


# ─── Agent tools & prompts ───


class TestAgentSetup:
    def test_faq_has_tools(self):
        agent = FaqAgent(model="openai/gpt-4o-mini")
        tools = agent.get_tools()
        assert len(tools) >= 1
        assert tools[0]["function"]["name"] == "search_faq"

    def test_diagnostics_has_tools(self):
        agent = DiagnosticsAgent(model="openai/gpt-4o-mini")
        tools = agent.get_tools()
        names = [t["function"]["name"] for t in tools]
        assert "check_service_status" in names
        assert "lookup_error_code" in names

    def test_billing_has_tools(self):
        agent = BillingAgent(model="openai/gpt-4o-mini")
        tools = agent.get_tools()
        names = [t["function"]["name"] for t in tools]
        assert "get_account_info" in names
        assert "get_tariff_info" in names

    def test_all_agents_have_escalate(self):
        for AgentClass in [FaqAgent, DiagnosticsAgent, BillingAgent]:
            agent = AgentClass(model="openai/gpt-4o-mini")
            all_tools = agent._all_tools()
            names = [t["function"]["name"] for t in all_tools]
            assert "escalate" in names, f"{AgentClass.__name__} missing escalate tool"

    def test_system_prompts_not_empty(self):
        for AgentClass in [FaqAgent, DiagnosticsAgent, BillingAgent]:
            agent = AgentClass(model="openai/gpt-4o-mini")
            assert len(agent.get_system_prompt()) > 50
