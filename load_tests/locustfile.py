"""
Main Locust load test file for the multi-agent tech support platform.

Usage:
    locust -f load_tests/locustfile.py --host=http://localhost:8000
    locust -f load_tests/locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 -t 2m
"""
import random

from locust import HttpUser, task, between, events


FAQ_QUESTIONS = [
    "Как сменить пароль?",
    "Как восстановить доступ к аккаунту?",
    "Где найти инструкцию по использованию?",
    "Как связаться с поддержкой?",
    "Как обновить профиль?",
]

DIAGNOSTICS_QUESTIONS = [
    "Ошибка E-404 при входе в систему",
    "Сервис недоступен, ошибка 503",
    "Приложение зависает при загрузке данных",
    "Ошибка E-500 при оплате",
    "Не работает подключение к базе данных",
]

BILLING_QUESTIONS = [
    "Почему с меня списали дважды?",
    "Как изменить тарифный план?",
    "Покажите мою историю платежей",
    "Не прошёл платёж, что делать?",
    "Как оформить возврат?",
]

ESCALATION_QUESTIONS = [
    "Мне нужен живой оператор срочно",
    "Хочу пожаловаться на качество сервиса",
    "Ситуация требует немедленного вмешательства менеджера",
]


class SupportUser(HttpUser):
    """Simulates a typical tech support user."""

    wait_time = between(1, 3)

    @task(5)
    def ask_faq(self):
        """FAQ request — most frequent (weight 5)."""
        self.client.post(
            "/chat",
            json={"message": random.choice(FAQ_QUESTIONS)},
            name="/chat [faq]",
        )

    @task(2)
    def ask_diagnostics(self):
        """Diagnostics request (weight 2)."""
        self.client.post(
            "/chat",
            json={"message": random.choice(DIAGNOSTICS_QUESTIONS)},
            name="/chat [diagnostics]",
        )

    @task(1)
    def ask_billing(self):
        """Billing request (weight 1)."""
        self.client.post(
            "/chat",
            json={"message": random.choice(BILLING_QUESTIONS)},
            name="/chat [billing]",
        )

    @task(1)
    def request_escalation(self):
        """Escalation request (weight 1)."""
        self.client.post(
            "/chat",
            json={"message": random.choice(ESCALATION_QUESTIONS)},
            name="/chat [escalation]",
        )

    @task(1)
    def health_check(self):
        """Health endpoint check."""
        self.client.get("/health", name="/health")


class LLMProxyUser(HttpUser):
    """Simulates direct LLM proxy usage (for balancer testing)."""

    wait_time = between(0.5, 2)

    MODELS = ["mock-model"]

    @task
    def proxy_request(self):
        model = random.choice(self.MODELS)
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "Hello, short answer please."}
                ],
            },
            name="/v1/chat/completions",
        )
