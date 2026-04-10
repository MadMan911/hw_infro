"""
Scenario: Basic load test — ramp up to 100 users, hold for 5 minutes.

Run:
    locust -f load_tests/scenarios/basic_load.py \
        --host=http://localhost:8000 \
        --headless -u 100 -r 2 -t 6m \
        --html=reports/basic_load.html

Expected outcomes:
    - Throughput: > 50 RPS
    - p50 latency: < 2s
    - p95 latency: < 5s
    - Error rate: < 1%
"""
import random

from locust import HttpUser, task, between, LoadTestShape


FAQ_QUESTIONS = [
    "Как сменить пароль?",
    "Как восстановить доступ к аккаунту?",
    "Где найти инструкцию?",
]

DIAGNOSTICS_QUESTIONS = [
    "Ошибка E-404 при входе",
    "Сервис недоступен, ошибка 503",
    "Приложение зависает при загрузке",
]


class BasicLoadUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def faq(self):
        self.client.post(
            "/chat",
            json={"message": random.choice(FAQ_QUESTIONS)},
            name="/chat [faq]",
        )

    @task(2)
    def diagnostics(self):
        self.client.post(
            "/chat",
            json={"message": random.choice(DIAGNOSTICS_QUESTIONS)},
            name="/chat [diagnostics]",
        )

    @task(1)
    def health(self):
        self.client.get("/health")


class BasicLoadShape(LoadTestShape):
    """
    Ramp-up: 0 → 100 users over 60 seconds.
    Hold: 100 users for 5 minutes.
    Total duration: 6 minutes.
    """
    stages = [
        {"duration": 60, "users": 100, "spawn_rate": 2},   # ramp up
        {"duration": 360, "users": 100, "spawn_rate": 2},  # hold
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time <= stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
