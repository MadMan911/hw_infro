"""
Scenario: Provider failure test.

Simulates 50 concurrent users. On second 60, mock-llm-1 goes down.
Verifies that traffic automatically shifts to remaining providers
and error rate stays below threshold.

Run:
    locust -f load_tests/scenarios/provider_failure.py \
        --host=http://localhost:8000 \
        --headless -u 50 -r 5 -t 3m \
        --html=reports/provider_failure.html

Trigger failure manually (in another terminal):
    docker stop hw_infro-mock-llm-1-1

Expected outcomes:
    - Traffic continues after mock-llm-1 fails
    - Error rate spike < 5% during failover, then recovers to < 1%
    - p95 latency spike < 2x normal, stabilises within 30s
"""
import random

from locust import HttpUser, task, between, LoadTestShape


MESSAGES = [
    "Как сменить пароль?",
    "Ошибка E-500 при оплате",
    "Не работает подключение",
    "Покажите историю платежей",
]


class FailureTestUser(HttpUser):
    wait_time = between(1, 2)

    @task(3)
    def proxy_request(self):
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": "mock-model",
                "messages": [{"role": "user", "content": random.choice(MESSAGES)}],
            },
            name="/v1/chat/completions",
        )

    @task(1)
    def health(self):
        with self.client.get("/health", catch_response=True, name="/health") as resp:
            data = resp.json()
            if data.get("status") == "degraded":
                # degraded is acceptable during failover — don't count as failure
                resp.success()


class ProviderFailureShape(LoadTestShape):
    """
    Hold 50 users for 3 minutes.
    Provider failure expected to be injected manually at ~60s.
    """
    def tick(self):
        run_time = self.get_run_time()
        if run_time < 180:
            return 50, 5
        return None
