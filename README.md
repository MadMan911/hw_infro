# Мультиагентная платформа техподдержки

Учебный проект (уровень 3). Платформа маршрутизирует запросы пользователей через LangGraph-граф агентов, каждый из которых решает свою задачу через ReAct-цикл с LiteLLM.

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│  Outer graph (LangGraph)                            │
│  Routes BETWEEN agents + handles escalation         │
│                                                     │
│  Classifier ──► FAQ Agent ──► Diagnostics ──► ...   │
│                                                     │
│  ┌─────────────────────────────────────────┐        │
│  │  Inner loop (ReAct, LiteLLM)            │        │
│  │  Tool calling WITHIN a single agent     │        │
│  │  LLM → tool_call → result → LLM → ...   │        │
│  │  (max 6 iterations)                     │        │
│  └─────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

### Компоненты

| Компонент | Путь | Описание |
|---|---|---|
| API Gateway | `src/gateway/` | FastAPI, Prometheus middleware, Auth middleware |
| LangGraph Orchestrator | `src/routing/graph.py` | Граф агентов, escalation, защита от циклов (max 3 hops) |
| Request Classifier | `src/routing/classifier.py` | LLM-классификация + keyword fallback |
| Agent Registry | `src/agents/registry.py` | In-memory хранилище AgentCard |
| Agents | `src/agents/` | FAQ, Diagnostics, Billing, HumanRouter |
| LLM Balancer | `src/llm/balancer.py` | Прокси `/v1/chat/completions`, round-robin/weighted/latency, Circuit Breaker |
| Provider Registry | `src/llm/registry.py` | CRUD для LLM-провайдеров через REST |
| Guardrails | `src/guardrails/` | Prompt injection, PII (BLOCK/MASK), secrets |
| Auth | `src/auth/token_auth.py` | JWT, 6 скоупов, JTI-отзыв |
| Telemetry | `src/telemetry/` | OTel метрики (TTFT/TPOT), MLFlow трейсинг |
| Mock LLM Server | `mock_llm_server/` | Fake OpenAI API с настраиваемой задержкой/ошибками |

### Поток запроса (POST /chat)

```
Client → Guardrails (input) → Classifier → Agent (ReAct loop)
  → [escalate?] → следующий Agent → ... → HumanRouter
  → Guardrails (output) → Client
```

### LLM провайдеры агентов

- **FAQ, Billing, Classifier** — `openai/gpt-4o-mini`
- **Diagnostics** — `openrouter/deepseek/deepseek-chat-v3-0324`

## Запуск

### Docker Compose (рекомендуется)

```bash
cp .env.example .env
# Заполнить API ключи в .env
docker-compose up --build
```

Сервисы:

| Сервис | Порт | URL |
|---|---|---|
| API | 8000 | http://localhost:8000 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3000 | http://localhost:3000 (admin/admin) |
| MLFlow | 5000 | http://localhost:5000 |
| OTel Collector | 4317/4318 | — |
| Mock LLM 1/2/3 | 8001/8002/8003 | — |

### Локально (dev)

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn src.main:app --reload --port 8000
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI API ключ |
| `OPENROUTER_API_KEY` | — | OpenRouter API ключ (для DeepSeek) |
| `ANTHROPIC_API_KEY` | — | Anthropic API ключ (опционально) |
| `BALANCING_STRATEGY` | `round_robin` | Стратегия балансировки: `round_robin`, `weighted`, `latency_based` |
| `AGENT_CHEAP_MODEL` | `openai/gpt-4o-mini` | Модель для FAQ/Billing/Classifier |
| `AGENT_STRONG_MODEL` | `openrouter/deepseek/...` | Модель для Diagnostics |
| `AGENT_MAX_STEPS` | `6` | Макс. шагов ReAct-цикла |
| `AUTH_ENABLED` | `false` | Включить JWT-аутентификацию |
| `AUTH_SECRET_KEY` | `change-me-in-production` | Секрет для подписи JWT |
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | URI MLFlow сервера |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | OTel коллектор |

## API эндпоинты

### Чат

```
POST /chat
Body: {"message": "...", "stream": false}
Response: {"response": "...", "agent_trace": [...], "visited_agents": [...]}

# SSE streaming
POST /chat
Body: {"message": "...", "stream": true}
Response: text/event-stream  →  routing event → token chunks → [DONE]
```

### Агенты

```
GET    /agents                   — список всех агентов
GET    /agents/search?method=&topic=  — поиск по методу/теме
GET    /agents/{agent_id}        — карточка агента
POST   /agents/register          — зарегистрировать агента  [scope: agents:write]
DELETE /agents/{agent_id}        — удалить агента           [scope: agents:write]
```

### Провайдеры

```
GET    /providers                — список провайдеров с circuit state
POST   /providers/register       — зарегистрировать провайдера  [scope: providers:write]
PUT    /providers/{id}           — обновить статус/вес          [scope: providers:write]
DELETE /providers/{id}           — удалить провайдера           [scope: providers:write]
```

### Auth

```
POST   /auth/token               — получить JWT
POST   /auth/verify              — проверить токен
DELETE /auth/token/{jti}         — отозвать токен               [scope: admin]
```

### Прочее

```
POST /v1/chat/completions        — OpenAI-совместимый прокси через балансировщик
GET  /health                     — health check
GET  /metrics                    — Prometheus метрики
```

## Тесты

```bash
# Все тесты
pytest

# По группам
pytest tests/test_agents.py -v
pytest tests/test_guardrails.py -v
pytest tests/test_auth.py -v
pytest tests/test_balancer.py -v
pytest tests/test_registry.py -v
```

## Нагрузочные тесты

```bash
# Headless режим
locust -f load_tests/locustfile.py --host=http://localhost:8000 \
  --headless -u 50 -r 5 --run-time 60s

# GUI режим (http://localhost:8089)
locust -f load_tests/locustfile.py --host=http://localhost:8000
```

## Линтинг

```bash
ruff check src/
ruff format src/
```
