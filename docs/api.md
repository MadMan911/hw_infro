# API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

## Авторизация

Если `AUTH_ENABLED=true`, все защищённые endpoints требуют заголовок:
```
Authorization: Bearer <jwt-token>
```

Получить токен: `POST /auth/token`.

---

## LLM Proxy

### POST /v1/chat/completions

Проксирует запрос к балансировщику LLM-провайдеров. OpenAI-совместимый формат.

**Scope:** `chat:read`

**Request body:**
```json
{
  "model": "mock-model",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": false
}
```

**Response (stream=false):**
```json
{
  "id": "chatcmpl-proxy",
  "object": "chat.completion",
  "model": "mock-model",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "..."}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 10, "completion_tokens": 20},
  "provider": "mock-llm-1",
  "latency_ms": 102.3
}
```

**Response (stream=true):** SSE (`text/event-stream`)
```
data: {"choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": null}]}
data: [DONE]
```

---

## Multi-Agent Chat

### POST /chat

Маршрутизирует запрос через LangGraph: Classifier → FAQ/Diagnostics/Billing/Human Router.

**Scope:** `chat:read`

**Request body:**
```json
{
  "message": "Интернет не работает",
  "conversation_id": "optional-id",
  "stream": false
}
```

**Response:**
```json
{
  "response": "Проверьте кабель и перезагрузите роутер...",
  "agent_trace": ["classifier → diagnostics_agent"],
  "visited_agents": ["diagnostics"]
}
```

**Ошибки:**
- `400` — Guardrails заблокировали запрос (prompt injection / secrets)
- `503` — Agent graph не инициализирован

---

## Agent Registry

### GET /agents

Список всех зарегистрированных агентов. **Scope:** `agents:read`

### GET /agents/{agent_id}

Карточка конкретного агента. **Scope:** `agents:read`

**Response:**
```json
{
  "id": "faq",
  "name": "FAQ Agent",
  "description": "Answers frequently asked questions",
  "version": "1.0.0",
  "supported_methods": ["answer_faq"],
  "supported_topics": ["faq", "general"],
  "llm_requirements": {"model": "gpt-4o-mini"},
  "status": "active",
  "registered_at": "2025-01-01T00:00:00Z"
}
```

### GET /agents/search?method=&topic=

Поиск агентов по методу или топику. **Scope:** `agents:read`

### POST /agents/register

Регистрация нового агента. **Scope:** `agents:write`

**Request body:**
```json
{
  "id": "my-agent",
  "name": "My Agent",
  "description": "Custom agent",
  "version": "1.0.0",
  "supported_methods": ["solve_task"],
  "supported_topics": ["custom"],
  "llm_requirements": {},
  "status": "active"
}
```

### DELETE /agents/{agent_id}

Удаление агента из реестра. **Scope:** `agents:write`

---

## Provider Registry

### GET /providers

Список всех LLM-провайдеров с состоянием circuit breaker и health-check. **Scope:** `providers:read`

**Response:**
```json
{
  "providers": [
    {"name": "mock-llm-1", "models": ["mock-model"], "healthy": true, "circuit_state": "closed"}
  ],
  "registered": [
    {"id": "openai-prod", "name": "OpenAI Production", "url": "...", "priority": 1, "weight": 2.0, "status": "active"}
  ]
}
```

### POST /providers/register

Динамическая регистрация провайдера. **Scope:** `providers:write`

**Request body:**
```json
{
  "id": "openai-prod",
  "name": "OpenAI Production",
  "url": "https://api.openai.com",
  "api_key": "sk-...",
  "models": ["gpt-4o", "gpt-4o-mini"],
  "cost_per_input_token": 0.000005,
  "cost_per_output_token": 0.000015,
  "rate_limit_rpm": 500,
  "rate_limit_tpm": 100000,
  "priority": 1,
  "weight": 2.0
}
```

### PUT /providers/{provider_id}

Обновление статуса/веса/приоритета провайдера. **Scope:** `providers:write`

**Request body:**
```json
{"status": "disabled", "weight": 0.5, "priority": 2}
```

### DELETE /providers/{provider_id}

Удаление провайдера из реестра. **Scope:** `providers:write`

---

## Auth

### POST /auth/token

Создание JWT-токена.

**Request body:**
```json
{
  "subject": "user-123",
  "scopes": ["chat:read", "agents:read"],
  "expire_seconds": 3600
}
```

**Response:**
```json
{"token": "eyJ...", "token_type": "Bearer"}
```

**Допустимые scopes:** `chat:read`, `agents:read`, `agents:write`, `providers:read`, `providers:write`, `admin`

### POST /auth/verify

Проверка токена.

**Request body:** `{"token": "eyJ..."}`

**Response:** `{"valid": true, "subject": "user-123", "scopes": ["chat:read"], "exp": 1700000000}`

### DELETE /auth/token/{jti}

Отзыв токена по JTI. **Scope:** `admin`

---

## Служебные

### GET /health

Состояние всех провайдеров и circuit breaker.

```json
{
  "status": "ok",
  "providers": {"mock-llm-1": true, "mock-llm-2": true},
  "circuit_states": {"mock-llm-1": "closed", "mock-llm-2": "closed"}
}
```

### GET /metrics

Prometheus-метрики в текстовом формате.
