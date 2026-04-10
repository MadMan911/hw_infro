# Архитектура платформы

## Обзор

Мультиагентная платформа техподдержки с двухуровневой оркестрацией: внешний граф (LangGraph) управляет маршрутизацией между агентами, внутренний цикл (ReAct + LiteLLM) управляет вызовами инструментов внутри агента.

## Схема компонентов

```
┌──────────────────────────────────────────────────────────────────────┐
│  Клиент                                                              │
│  POST /chat  •  POST /v1/chat/completions  •  GET /health            │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────────┐
│  API Gateway (FastAPI)  — src/gateway/                               │
│                                                                      │
│  AuthMiddleware (JWT Bearer, scope-based)                            │
│  PrometheusMiddleware (http_requests_total, latency histograms)      │
│  GuardrailsEngine (prompt injection → PII → secrets)                │
└───────┬──────────────────────────┬───────────────────────────────────┘
        │                          │
        ▼                          ▼
┌───────────────────┐   ┌──────────────────────────────────────────────┐
│  LLM Balancer     │   │  LangGraph Orchestrator — src/routing/       │
│  src/llm/         │   │                                              │
│                   │   │  Classifier (gpt-4o-mini + keyword fallback) │
│  Strategies:      │   │       │                                      │
│  • round_robin    │   │       ▼                                      │
│  • weighted       │   │  ┌─────────────────────────────────────┐     │
│  • latency_based  │   │  │  FAQ Agent   (gpt-4o-mini)          │     │
│                   │   │  │  Diagnostics (deepseek via OR)       │     │
│  CircuitBreaker   │   │  │  Billing     (gpt-4o-mini)          │     │
│  (per-provider)   │   │  │  Human Router (no LLM, ticket ID)   │     │
│                   │   │  └────────────────┬────────────────────┘     │
│  ProviderRegistry │   │                   │ escalate(reason, target) │
│  (weight/priority │   │  max 3 hops, cycle prevention               │
│   rate_limit_rpm) │   └──────────────────────────────────────────────┘
└───────┬───────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────┐
│  LLM Providers — src/llm/                                            │
│                                                                      │
│  MockProvider × 3  (latency: 100/200/300ms, error: 0%/5%/10%)       │
│  OpenAIProvider    (gpt-4o, gpt-4o-mini)                            │
│  AnthropicProvider (claude-3-5-sonnet, claude-3-haiku)              │
└───────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│  Observability Stack                                                 │
│                                                                      │
│  OpenTelemetry Collector ──► Prometheus ──► Grafana                 │
│  MLFlow (agent run tracing: params, metrics, artifacts)             │
│                                                                      │
│  Метрики: llm_requests_total, llm_ttft, llm_tpot,                  │
│           llm_tokens_total, llm_request_cost_dollars,               │
│           http_request_duration_seconds                             │
└───────────────────────────────────────────────────────────────────────┘
```

## Поток запроса (POST /chat)

```
1. Клиент → POST /chat { "message": "..." }
2. AuthMiddleware: проверка JWT (если AUTH_ENABLED=true)
3. GuardrailsEngine.check_input(): prompt injection / PII / secrets
4. RequestClassifier: LLM → тип запроса (faq | diagnostics | billing | escalation)
5. LangGraph: выбор агента по типу
6. Agent.run(): ReAct loop (LiteLLM + tools, max 6 шагов)
   └─ tool: escalate(reason, target) → переход к другому агенту (max 3 hops)
7. GuardrailsEngine.check_output(): маскировка PII в ответе
8. Клиент ← { response, agent_trace, visited_agents }
```

## Поток запроса (POST /v1/chat/completions)

```
1. Клиент → POST /v1/chat/completions { "model": "...", "messages": [...] }
2. LLMBalancer.route_request(): выбор провайдера по стратегии
   └─ CircuitBreaker: пропуск OPEN-провайдеров
   └─ ProviderRegistry: фильтр disabled, rate_limit_rpm, weight/priority
3. Provider.chat_completion(): запрос к LLM
4. Стриминг: _wrap_stream_with_metrics() → record_ttft, record_tpot
5. Клиент ← SSE (stream=true) или JSON (stream=false)
```

## Docker Compose сервисы

| Сервис | Порт | Описание |
|---|---|---|
| app | 8000 | FastAPI приложение |
| mock-llm-1 | 8001 | Mock LLM, latency=100ms, error=0% |
| mock-llm-2 | 8001 | Mock LLM, latency=200ms, error=5% |
| mock-llm-3 | 8001 | Mock LLM, latency=300ms, error=10% |
| prometheus | 9090 | Сбор метрик (scrape: 15s) |
| grafana | 3000 | Дашборды (admin/admin) |
| otel-collector | 4317/4318 | OTLP gRPC/HTTP receiver |
| mlflow | 5000 | Experiment tracking |

## Guardrails

```
Input: ─► prompt_injection ─► secret_detection ─► PII (block/mask) ─► Agent
Output: ◄─ PII mask ◄─ Agent response
```

- **Prompt Injection**: 12 regex-паттернов (score >= 0.8 → block), base64/hex encoded injection
- **PII Filter**: телефон (RU/INT), email, карта (Luhn), паспорт РФ, ИНН, СНИЛС
- **Secret Detector**: OpenAI/Anthropic/AWS ключи, JWT, Bearer, private key headers

## Авторизация

JWT HS256, scopes: `chat:read`, `agents:read`, `agents:write`, `providers:read`, `providers:write`, `admin`.
Включается через `AUTH_ENABLED=true` в `.env`. По умолчанию отключён для упрощения разработки.
