"""
Scenario: Peak (spike) load test — 0 → 500 users in 10 seconds.

Run:
    locust -f load_tests/scenarios/peak_load.py \
        --host=http://localhost:8000 \
        --headless -u 500 -r 50 -t 3m \
        --html=reports/peak_load.html

Expected outcomes:
    - System does not crash
    - Graceful degradation: returns 429 or 503 under extreme load, not 500
    - After spike subsides, system recovers to normal latency within 30s
"""
import random

from locust import HttpUser, task, between, LoadTestShape


MESSAGES = [
    "Как сменить пароль?",
    "Ошибка E-404",
    "Не работает приложение",
    "Возврат средств",
    "Нужна помощь срочно",
]


class PeakUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(4)
    def chat(self):
        with self.client.post(
            "/chat",
            json={"message": random.choice(MESSAGES)},
            name="/chat",
            catch_response=True,
        ) as resp:
            # 429 and 503 are expected under peak — don't count as failures
            if resp.status_code in (429, 503):
                resp.success()

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")


class PeakLoadShape(LoadTestShape):
    """
    Spike: 0 → 500 users in 10 seconds.
    Hold: 500 users for 30 seconds.
    Cool-down: 500 → 10 users over 20 seconds.
    Recovery observation: 10 users for 2 minutes.
    """
    stages = [
        {"duration": 10, "users": 500, "spawn_rate": 50},    # spike
        {"duration": 40, "users": 500, "spawn_rate": 50},    # hold
        {"duration": 60, "users": 10, "spawn_rate": 50},     # cool-down (fast ramp down)
        {"duration": 180, "users": 10, "spawn_rate": 2},     # recovery observation
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time <= stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
