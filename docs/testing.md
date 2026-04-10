# Отчёт о тестировании

## Unit и интеграционные тесты

Запуск:
```bash
pytest                        # все тесты
pytest tests/ -v              # с verbose-выводом
pytest tests/test_balancer.py # отдельный модуль
```

### Покрытие по модулям

| Файл | Кол-во тестов | Покрытие |
|---|---|---|
| `tests/test_balancer.py` | ~20 | LLM Balancer: round-robin, weighted, latency-based, circuit breaker, failover |
| `tests/test_agents.py` | ~53 | Агенты: ReAct loop, tool calling, escalation, agent card |
| `tests/test_registry.py` | ~14 | AgentRegistry: CRUD, find_by_method/topic |
| `tests/test_guardrails.py` | ~30 | Guardrails: prompt injection (12 patterns), PII (phone/email/card/INN), secrets |
| `tests/test_auth.py` | ~20 | JWT: создание, верификация, expiry, revocation, scopes, tamper detection |
| **Итого** | **~137** | |

### Ключевые сценарии

**Балансировщик:**
- `test_round_robin_alternates` — поочерёдный выбор двух провайдеров
- `test_weighted_respects_weights` — статистическое распределение по весам
- `test_latency_based_prefers_faster` — выбор провайдера с меньшей EMA-латентностью
- `test_circuit_breaker_opens_after_failures` — открытие circuit breaker после 3 ошибок
- `test_failover_skips_failed_provider` — автоматический переход к следующему провайдеру

**Guardrails:**
- `test_clean_message_passes` — чистое сообщение не блокируется
- `test_prompt_injection_detected` — "Ignore all previous instructions" → BLOCK
- `test_pii_phone_masked` — телефон в ответе заменяется на `[PHONE]`
- `test_secret_openai_key_blocked` — `sk-...` ключ → BLOCK
- `test_credit_card_luhn_validation` — случайные числа не ложно срабатывают

**Auth:**
- `test_valid_token` — создание и верификация JWT
- `test_expired_token_rejected` — истёкший токен → ValueError
- `test_tampered_token_rejected` — изменённая подпись → ValueError
- `test_revoked_token_rejected` — отозванный токен → ValueError
- `test_admin_scope_grants_all` — `admin` scope проходит любую проверку

---

## Нагрузочные тесты (Locust)

### Запуск

```bash
# Запустить весь стек
docker-compose up --build

# Web UI (рекомендуется)
locust -f load_tests/locustfile.py --host=http://localhost:8000

# Headless режим
locust -f load_tests/locustfile.py --host=http://localhost:8000 \
  -u 100 -r 2 -t 6m --headless
```

### Сценарии

#### 1. Базовая нагрузка (`SupportUser`)

Симулирует типичных пользователей техподдержки:

| Задача | Вес | Частота |
|---|---|---|
| FAQ запросы | 5 | ~56% |
| Диагностика | 2 | ~22% |
| Биллинг | 1 | ~11% |
| Эскалация | 1 | ~11% |

```bash
locust -f load_tests/locustfile.py -u 50 -r 5 -t 3m --headless
```

#### 2. Нагрузка на балансировщик (`LLMProxyUser`)

Прямые запросы к `/v1/chat/completions` для измерения балансировщика без агентного overhead.

```bash
locust -f load_tests/locustfile.py --class-picker -u 100 -r 10 -t 5m
```

#### 3. Пиковая нагрузка (`scenarios/basic_load.py`)

Рампа до 100 пользователей за 1 минуту, удержание 5 минут.

#### 4. Отказ провайдера (`scenarios/provider_failure.py`)

Симулирует отключение одного из mock-провайдеров во время нагрузки для проверки circuit breaker и failover.

### Целевые показатели

| Метрика | Цель | Измерение |
|---|---|---|
| Throughput | > 50 RPS | Locust stats |
| Латентность p50 | < 2 сек | Locust stats |
| Латентность p95 | < 5 сек | Locust stats |
| Error rate | < 1% | Locust stats |
| Circuit breaker recovery | < 65 сек | Grafana |

### Мониторинг во время нагрузки

Grafana: `http://localhost:3000` (admin/admin)
- **Request Rate** — запросов в секунду по эндпоинтам
- **Latency Distribution** — p50/p95/p99 гистограммы
- **Error Rate** — доля 5xx ошибок
- **Traffic by Provider** — распределение трафика по mock-провайдерам

Prometheus: `http://localhost:9090`
- `rate(http_requests_total[1m])` — RPS
- `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` — p95 латентность
- `rate(llm_requests_total[1m])` — LLM запросов в секунду по провайдерам

MLFlow: `http://localhost:5000`
- Трассировки агентских запусков
- Метрики TTFT, TPOT, кол-во токенов, стоимость

---

## Запуск и развёртывание

### Локально (dev)

```bash
pip install -r requirements.txt
cp .env.example .env
# заполните API ключи в .env
uvicorn src.main:app --reload --port 8000
```

### Docker Compose (production-like)

```bash
cp .env.example .env
# заполните OPENAI_API_KEY, ANTHROPIC_API_KEY при необходимости
docker-compose up --build
```

Сервисы будут доступны:
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- MLFlow: http://localhost:5000

### Проверка работоспособности

```bash
# Health check
curl http://localhost:8000/health

# Тест балансировщика
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "mock-model", "messages": [{"role": "user", "content": "hello"}]}'

# Тест агентов
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Интернет не работает"}'

# Получить JWT токен
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"subject": "test-user", "scopes": ["chat:read"]}'
```
