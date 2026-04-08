# Plan: Мультиагентная платформа техподдержки

## Альтернативные темы (на выбор)

Все темы ниже одинаково хорошо ложатся на требования задания (Agent Registry, LLM-балансировка, Guardrails, телеметрия):

1. **Платформа мультиагентных помощников для техподдержки** (основная тема)
   - Агенты: FAQ, диагностика ошибок, биллинг, маршрутизация в человека
   - Естественная маршрутизация по типу запроса, guardrails от утечки ПД
   - Демо: FAQ -> дешёвая модель, сложные тикеты -> сильная модель, failover

2. **AI-платформа для DevOps/SRE-автоматизации**
   - Агенты: анализ логов, управление инцидентами, capacity planning, runbook-исполнитель
   - Routing по severity: P1 инциденты -> мощная модель + человек, рутинные алерты -> дешёвая
   - Guardrails: запрет на выполнение деструктивных команд без подтверждения

3. **Мультиагентный HR-ассистент**
   - Агенты: онбординг, ответы по политикам компании, расчёт отпусков/больничных, найм
   - Routing: простые вопросы по политикам -> быстрая модель, сложные кейсы -> сильная
   - Guardrails: защита персональных данных сотрудников, запрет дискриминационных ответов

4. **Платформа для образовательных AI-тьюторов**
   - Агенты: объяснение теории, проверка задач, генерация тестов, персональный план обучения
   - Routing: проверка простых задач -> дешёвая модель, генерация объяснений -> сильная
   - Guardrails: запрет на выдачу готовых решений, фильтр не-образовательного контента

---

## Архитектура (выбранная тема: техподдержка)

```
┌─────────────┐
│   Client     │
└──────┬──────┘
       │ HTTP/SSE
       ▼
┌──────────────────────────────────────────────────────┐
│                   API Gateway (FastAPI)               │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │
│  │ Auth       │  │ Guardrails │  │ OTel Middleware │  │
│  │ Middleware │  │ Filter     │  │ (traces/metrics)│  │
│  └────────────┘  └────────────┘  └────────────────┘  │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Request Router  │  ← классифицирует тип запроса
              │  (LLM-based)    │     (FAQ/diagnostics/billing/human)
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Agent Registry  │  ← хранит Agent Cards
              └────────┬────────┘
                       │ выбирает агента
                       ▼
         ┌─────────────────────────────┐
         │      Selected Agent          │
         │  (FAQ/Diag/Billing/Human)    │
         └─────────────┬───────────────┘
                       │ LLM-вызовы
                       ▼
              ┌─────────────────┐
              │  LLM Balancer    │  ← round-robin / weighted /
              │  (Proxy)         │     latency-based / health-aware
              └────────┬────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
     ┌──────────┐ ┌──────────┐ ┌──────────┐
     │ OpenAI   │ │Anthropic │ │ Mock LLM │
     │ Provider │ │ Provider │ │ Provider │
     └──────────┘ └──────────┘ └──────────┘

┌──────────────────────────────────────────────────────┐
│                 Observability Stack                    │
│  ┌────────────┐  ┌────────────┐  ┌──────────┐        │
│  │ Prometheus │  │  Grafana   │  │  MLFlow  │        │
│  └────────────┘  └────────────┘  └──────────┘        │
│  ┌─────────────────────────────────────────┐         │
│  │     OpenTelemetry Collector              │         │
│  └─────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────┘
```

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.11+ |
| Web-фреймворк | FastAPI + Uvicorn |
| HTTP-клиент | httpx (async, streaming) |
| LLM SDK | openai, anthropic |
| Телеметрия | opentelemetry-sdk, opentelemetry-exporter-prometheus |
| Метрики | prometheus-client |
| Трассировка агентов | MLFlow |
| Контейнеризация | Docker + Docker Compose |
| Нагрузочное тестирование | Locust |
| Визуализация | Grafana |

---

## Фаза 0: Инициализация проекта

### 0.1 Структура репозитория
Создать файловую структуру:
```
hw_infro/
├── plan.md
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── pyproject.toml                  # зависимости (poetry/pip)
├── requirements.txt
│
├── src/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, точка входа
│   ├── config.py                   # настройки из env
│   │
│   ├── gateway/                    # API Gateway
│   │   ├── __init__.py
│   │   ├── router.py               # HTTP-роуты (/chat, /health, ...)
│   │   └── middleware.py            # OTel middleware, auth, guardrails
│   │
│   ├── agents/                     # Агенты
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseAgent ABC
│   │   ├── registry.py             # AgentRegistry + Agent Card
│   │   ├── faq_agent.py
│   │   ├── diagnostics_agent.py
│   │   ├── billing_agent.py
│   │   └── human_router_agent.py
│   │
│   ├── llm/                        # LLM-слой
│   │   ├── __init__.py
│   │   ├── provider.py             # BaseLLMProvider ABC
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── mock_provider.py
│   │   ├── registry.py             # ProviderRegistry (динамическая регистрация)
│   │   └── balancer.py             # LLMBalancer (стратегии)
│   │
│   ├── routing/                    # Маршрутизация запросов
│   │   ├── __init__.py
│   │   └── classifier.py           # RequestClassifier (LLM или rule-based)
│   │
│   ├── guardrails/                 # Guardrails
│   │   ├── __init__.py
│   │   ├── engine.py               # GuardrailsEngine
│   │   ├── prompt_injection.py     # детектор prompt injection
│   │   ├── pii_filter.py           # фильтр ПД
│   │   └── secret_detector.py      # детектор секретов
│   │
│   ├── auth/                       # Авторизация
│   │   ├── __init__.py
│   │   └── token_auth.py           # TokenAuth middleware
│   │
│   └── telemetry/                  # Телеметрия
│       ├── __init__.py
│       ├── otel_setup.py           # настройка OpenTelemetry
│       ├── metrics.py              # кастомные метрики (TTFT, TPOT, ...)
│       └── mlflow_tracer.py        # MLFlow integration
│
├── mock_llm_server/                # Mock LLM-сервер (отдельный сервис)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py
│
├── tests/
│   ├── __init__.py
│   ├── test_balancer.py
│   ├── test_agents.py
│   ├── test_guardrails.py
│   ├── test_registry.py
│   └── test_auth.py
│
├── load_tests/                     # Нагрузочные тесты
│   ├── locustfile.py
│   └── scenarios/
│       ├── basic_load.py
│       ├── provider_failure.py
│       └── peak_load.py
│
├── grafana/                        # Конфиги Grafana
│   └── provisioning/
│       ├── dashboards/
│       │   ├── dashboard.yml
│       │   └── platform_dashboard.json
│       └── datasources/
│           └── datasource.yml
│
└── prometheus/
    └── prometheus.yml
```

### 0.2 Зависимости (`requirements.txt`)
```
fastapi>=0.110
uvicorn[standard]>=0.27
httpx>=0.27
pydantic>=2.0
pydantic-settings>=2.0

# LLM SDKs
openai>=1.12
anthropic>=0.18

# Telemetry
opentelemetry-api>=1.22
opentelemetry-sdk>=1.22
opentelemetry-exporter-otlp>=1.22
opentelemetry-instrumentation-fastapi>=0.43b0
prometheus-client>=0.20

# MLFlow
mlflow>=2.10

# Testing
pytest>=8.0
pytest-asyncio>=0.23
locust>=2.23

# Utils
python-dotenv>=1.0
```

### 0.3 `.env.example`
```
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Mock LLM
MOCK_LLM_URL=http://mock-llm:8001

# Telemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
PROMETHEUS_PORT=9090

# MLFlow
MLFLOW_TRACKING_URI=http://mlflow:5000

# Auth
AUTH_SECRET_KEY=change-me-in-production
```

### 0.4 `.gitignore`
Стандартный Python .gitignore + `.env`, `__pycache__`, `.mypy_cache`, `mlruns/`.

### 0.5 Базовый `docker-compose.yml` (каркас)
Определить сервисы (пока без содержимого, будут заполняться по фазам):
- `app` (основное приложение)
- `mock-llm` (mock LLM-сервер)
- `prometheus`
- `grafana`
- `otel-collector`
- `mlflow`

### 0.6 Dockerfile для основного приложения
Простой multi-stage: python:3.11-slim, копировать requirements, установить зависимости, копировать src.

---

## Фаза 1: Уровень 1 — LLM-провайдеры, балансировщик, мониторинг [10 баллов]

### 1.1 Конфигурация (`src/config.py`)

**Блоки:**
- Создать `Settings` класс на базе `pydantic_settings.BaseSettings`
- Поля: список провайдеров (URL, ключ, модель), порт приложения, настройки OTel
- Загрузка из `.env` файла

### 1.2 Mock LLM-сервер (`mock_llm_server/`)

**Блоки:**
- `mock_llm_server/server.py`: FastAPI-приложение, имитирующее OpenAI Chat Completions API
- Эндпоинты:
  - `POST /v1/chat/completions` — принимает стандартный OpenAI-формат, возвращает фиксированные/рандомные ответы
  - `POST /v1/chat/completions` с `stream=true` — SSE-стриминг (токены по одному с задержкой)
  - `GET /health` — health check
- Настраиваемая задержка ответа (через env: `MOCK_LATENCY_MS`)
- Настраиваемая вероятность ошибки (через env: `MOCK_ERROR_RATE`)
- Поддержка нескольких инстансов (mock-llm-1, mock-llm-2, mock-llm-3) в docker-compose
- `mock_llm_server/Dockerfile`

### 1.3 Абстракция LLM-провайдера (`src/llm/provider.py`)

**Блоки:**
- Абстрактный класс `BaseLLMProvider`:
  ```python
  class BaseLLMProvider(ABC):
      name: str
      models: list[str]

      @abstractmethod
      async def chat_completion(self, messages, model, stream=False) -> ...:
          """Non-streaming: возвращает полный ответ.
             Streaming: возвращает AsyncIterator[str]."""

      @abstractmethod
      async def health_check(self) -> bool: ...
  ```
- Формат ответа: унифицированный `LLMResponse(content, model, provider, usage, latency_ms)`

### 1.4 Реализация провайдеров

**1.4.1 `src/llm/mock_provider.py`:**
- Реализация `BaseLLMProvider` для mock-сервера
- Использует `httpx.AsyncClient` для запросов
- Поддержка streaming через SSE
- Health check через `GET /health`

**1.4.2 `src/llm/openai_provider.py`:**
- Обёртка над `openai.AsyncOpenAI`
- Маппинг моделей: gpt-4o-mini (дешёвая), gpt-4o (дорогая)
- Streaming через SDK
- Health check: лёгкий запрос models.list()

**1.4.3 `src/llm/anthropic_provider.py`:**
- Обёртка над `anthropic.AsyncAnthropic`
- Маппинг моделей: claude-3-haiku (дешёвая), claude-sonnet-4-20250514 (дорогая)
- Streaming через SDK (message stream)
- Health check: лёгкий запрос

### 1.5 LLM-балансировщик (`src/llm/balancer.py`)

**Блоки:**

**1.5.1 Базовая структура:**
```python
class LLMBalancer:
    providers: list[BaseLLMProvider]
    strategy: BalancingStrategy  # enum: ROUND_ROBIN, WEIGHTED, ...

    async def route_request(self, messages, model, stream=False) -> LLMResponse:
        """Выбирает провайдера и проксирует запрос."""

    async def route_request_stream(self, messages, model) -> AsyncIterator[str]:
        """Streaming-версия: проксирует SSE-поток от провайдера клиенту."""
```

**1.5.2 Маршрутизация по модели:**
- Пользователь запрашивает конкретную модель (e.g., `gpt-4o`)
- Балансировщик находит провайдера, который поддерживает эту модель
- Если несколько провайдеров поддерживают одну модель — применяется стратегия

**1.5.3 Round-Robin стратегия:**
- Атомарный счётчик (asyncio.Lock или itertools.cycle)
- Переключение между провайдерами по очереди

**1.5.4 Weighted стратегия:**
- Каждому провайдеру назначен вес (0.0-1.0)
- Выбор по взвешенному random

**1.5.5 Поддержка streaming:**
- При `stream=True` балансировщик выбирает провайдера и возвращает `AsyncIterator`
- Не буферизует весь ответ — проксирует токен за токеном
- Использует `StreamingResponse` FastAPI для SSE

### 1.6 API Gateway — базовые эндпоинты (`src/gateway/router.py`)

**Блоки:**

**1.6.1 `POST /v1/chat/completions`:**
- Принимает стандартный OpenAI-совместимый формат
- Парсит `model`, `messages`, `stream`
- Передаёт в `LLMBalancer.route_request()`
- Non-streaming: возвращает JSON-ответ
- Streaming: возвращает `StreamingResponse` с SSE

**1.6.2 `GET /health`:**
- Проверяет здоровье всех провайдеров
- Возвращает общий статус + статус каждого провайдера

**1.6.3 `GET /providers`:**
- Список зарегистрированных провайдеров, их статус и поддерживаемые модели

### 1.7 Точка входа (`src/main.py`)

**Блоки:**
- Создать FastAPI app
- Инициализировать провайдеров из конфига
- Инициализировать балансировщик
- Подключить роутеры
- Подключить middleware (OTel, CORS)
- Lifespan: startup (инит провайдеров) / shutdown (закрыть httpx-клиенты)

### 1.8 Телеметрия — OpenTelemetry (`src/telemetry/otel_setup.py`)

**Блоки:**

**1.8.1 Инициализация трейсинга:**
- `TracerProvider` с OTLP exporter
- `FastAPIInstrumentor` для автоматического трейсинга HTTP-запросов
- `HTTPXClientInstrumentor` для трейсинга исходящих запросов к провайдерам

**1.8.2 Инициализация метрик:**
- Кастомные метрики через `opentelemetry.metrics`:
  - `llm_requests_total` (Counter) — общее число запросов, labels: provider, model, status
  - `llm_request_duration_seconds` (Histogram) — латентность, labels: provider, model
  - `llm_request_errors_total` (Counter) — ошибки, labels: provider, error_type
- Prometheus exporter (метрики доступны на `/metrics`)

**1.8.3 Middleware (`src/gateway/middleware.py`):**
- OTel middleware: автоматически записывает span для каждого входящего запроса
- Добавляет в span атрибуты: model, provider, token_count

### 1.9 Prometheus конфигурация (`prometheus/prometheus.yml`)

**Блоки:**
- scrape_configs: таргет на `app:8000/metrics`
- Интервал scrape: 15s
- Добавить таргеты для mock-llm серверов

### 1.10 Grafana дашборды

**Блоки:**

**1.10.1 Datasource (`grafana/provisioning/datasources/datasource.yml`):**
- Prometheus datasource, URL: `http://prometheus:9090`

**1.10.2 Dashboard (`grafana/provisioning/dashboards/platform_dashboard.json`):**
- Панель 1: Request Rate (requests/sec по провайдерам)
- Панель 2: Latency Distribution (p50, p95, p99)
- Панель 3: Error Rate (% ошибок по провайдерам)
- Панель 4: Traffic Distribution (pie chart по провайдерам)
- Панель 5: Provider Health Status

### 1.11 Docker Compose — Уровень 1

**Сервисы:**
```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [mock-llm-1, mock-llm-2, prometheus]

  mock-llm-1:
    build: ./mock_llm_server
    environment:
      MOCK_LATENCY_MS: 100
      MOCK_ERROR_RATE: 0.0

  mock-llm-2:
    build: ./mock_llm_server
    environment:
      MOCK_LATENCY_MS: 200
      MOCK_ERROR_RATE: 0.05

  prometheus:
    image: prom/prometheus:latest
    volumes: [./prometheus:/etc/prometheus]
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:latest
    volumes: [./grafana/provisioning:/etc/grafana/provisioning]
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
```

### 1.12 Проверка Уровня 1

- [ ] `docker-compose up` поднимает все сервисы
- [ ] `POST /v1/chat/completions` с `model=mock-model` → ответ от mock-llm
- [ ] Streaming работает (SSE)
- [ ] Round-robin: запросы чередуются между mock-llm-1 и mock-llm-2
- [ ] `/health` показывает статус провайдеров
- [ ] `/metrics` отдаёт Prometheus-метрики
- [ ] Grafana: дашборд отображает графики
- [ ] CPU-метрики видны в Grafana

---

## Фаза 2: Уровень 2 — Реестры и умная маршрутизация [20 баллов]

### 2.1 Agent Card и Agent Registry (`src/agents/registry.py`)

**Блоки:**

**2.1.1 Модель Agent Card (Pydantic):**
```python
class AgentCard(BaseModel):
    id: str                    # уникальный ID
    name: str                  # "FAQ Agent"
    description: str           # что умеет делать
    version: str               # "1.0.0"
    supported_methods: list[str]  # ["faq", "general_question"]
    supported_topics: list[str]   # ["account", "password", "pricing"]
    llm_requirements: dict     # {"preferred_model": "gpt-4o-mini", "max_tokens": 500}
    status: str                # "active" / "inactive"
    registered_at: datetime
```

**2.1.2 Agent Registry сервис:**
```python
class AgentRegistry:
    async def register(self, card: AgentCard) -> None: ...
    async def unregister(self, agent_id: str) -> None: ...
    async def get(self, agent_id: str) -> AgentCard: ...
    async def list_all(self) -> list[AgentCard]: ...
    async def find_by_method(self, method: str) -> list[AgentCard]: ...
    async def find_by_topic(self, topic: str) -> list[AgentCard]: ...
```

**2.1.3 REST API для реестра:**
- `POST /agents/register` — регистрация агента
- `DELETE /agents/{agent_id}` — удаление
- `GET /agents` — список всех агентов
- `GET /agents/{agent_id}` — получить карточку
- `GET /agents/search?method=faq&topic=billing` — поиск

### 2.2 Реализация агентов

**2.2.1 Базовый класс (`src/agents/base.py`):**
```python
class BaseAgent(ABC):
    card: AgentCard

    @abstractmethod
    async def handle(self, request: AgentRequest) -> AgentResponse:
        """Обработать запрос. Может вызывать LLM через балансировщик."""

    def get_card(self) -> AgentCard: ...
```

**2.2.2 FAQ Agent (`src/agents/faq_agent.py`):**
- Системный промпт: "Ты — помощник техподдержки. Отвечай на частые вопросы кратко и точно."
- Использует дешёвую/быструю модель (gpt-4o-mini / claude-3-haiku / mock)
- Может включать базу знаний (захардкоженные FAQ или файл)
- Метод: `faq`, Топики: `account`, `password`, `general`

**2.2.3 Diagnostics Agent (`src/agents/diagnostics_agent.py`):**
- Системный промпт: "Ты — инженер техподдержки. Помоги пользователю диагностировать ошибку."
- Использует сильную модель (gpt-4o / claude-sonnet)
- Умеет задавать уточняющие вопросы
- Метод: `diagnostics`, Топики: `error`, `bug`, `crash`, `performance`

**2.2.4 Billing Agent (`src/agents/billing_agent.py`):**
- Системный промпт: "Ты — специалист по биллингу. Помоги с вопросами по оплате и тарифам."
- Средняя модель
- Метод: `billing`, Топики: `payment`, `invoice`, `pricing`, `subscription`

**2.2.5 Human Router Agent (`src/agents/human_router_agent.py`):**
- Не вызывает LLM (или минимально)
- Определяет, что запрос требует живого оператора
- Возвращает сообщение: "Ваш запрос передан оператору. Ожидайте ответа."
- Метод: `escalation`, Топики: `complaint`, `urgent`, `complex`

### 2.3 Классификатор запросов (`src/routing/classifier.py`)

**Блоки:**

**2.3.1 LLM-based классификатор:**
```python
class RequestClassifier:
    async def classify(self, user_message: str) -> ClassificationResult:
        """Определяет тип запроса и выбирает агента.
        Возвращает: agent_method, topic, confidence."""
```
- Использует дешёвую модель для классификации
- Системный промпт: "Классифицируй запрос пользователя. Верни JSON: {method, topic, confidence}"
- Список возможных методов и топиков берётся из Agent Registry

**2.3.2 Rule-based fallback:**
- Ключевые слова для быстрой классификации без LLM
- Маппинг: "ошибка|error|crash" -> diagnostics, "оплата|счёт|тариф" -> billing, и т.д.
- Используется когда LLM-классификатор недоступен

### 2.4 Обновлённый API Gateway

**Блоки:**

**2.4.1 `POST /chat` — основной эндпоинт для пользователей:**
```python
@router.post("/chat")
async def chat(request: ChatRequest):
    # 1. Классифицировать запрос
    classification = await classifier.classify(request.message)
    # 2. Найти агента в реестре
    agent = registry.find_by_method(classification.method)
    # 3. Агент обрабатывает запрос (вызывает LLM через балансировщик)
    response = await agent.handle(request)
    # 4. Вернуть ответ
    return response
```

**2.4.2 `POST /chat` streaming-версия:**
- SSE-стрим: сначала отправить `{"type": "routing", "agent": "faq"}`, затем стримить ответ

### 2.5 Динамическая регистрация LLM-провайдеров (`src/llm/registry.py`)

**Блоки:**

**2.5.1 Модель провайдера (Pydantic):**
```python
class ProviderConfig(BaseModel):
    id: str
    name: str
    url: str
    api_key: str              # хранить зашифрованным
    models: list[str]
    cost_per_input_token: float
    cost_per_output_token: float
    rate_limit_rpm: int       # requests per minute
    rate_limit_tpm: int       # tokens per minute
    priority: int             # 1 = highest
    status: str               # "active" / "disabled" / "unhealthy"
```

**2.5.2 Provider Registry:**
```python
class ProviderRegistry:
    async def register(self, config: ProviderConfig) -> None: ...
    async def unregister(self, provider_id: str) -> None: ...
    async def update(self, provider_id: str, updates: dict) -> None: ...
    async def get_active(self) -> list[ProviderConfig]: ...
    async def get_by_model(self, model: str) -> list[ProviderConfig]: ...
```

**2.5.3 REST API:**
- `POST /providers/register`
- `DELETE /providers/{id}`
- `PUT /providers/{id}`
- `GET /providers`
- `GET /providers/{id}`

### 2.6 Расширенный балансировщик

**Блоки:**

**2.6.1 Latency-based routing:**
- Хранить скользящее среднее (EMA) латентности для каждого провайдера
- Выбирать провайдера с наименьшей средней латентностью
- Формула EMA: `new_avg = alpha * latest + (1 - alpha) * old_avg`, alpha = 0.3

**2.6.2 Health-aware routing:**
- Health check каждого провайдера каждые 30 секунд (asyncio background task)
- Провайдер помечается как `unhealthy` при:
  - 3+ consecutive timeouts
  - 3+ consecutive 5xx ошибок
  - Health check endpoint не отвечает
- Unhealthy провайдер исключается из пула
- Retry через 60 секунд (exponential backoff)
- Circuit breaker pattern: CLOSED -> OPEN (на ошибках) -> HALF-OPEN (пробный запрос) -> CLOSED

**2.6.3 Cost-aware routing (бонус):**
- Для FAQ (простых запросов) — выбирать самый дешёвый провайдер
- Для Diagnostics (сложных) — выбирать самый качественный
- Агент указывает `preferred_model` и `max_cost` в своём Agent Card

**2.6.4 Failover:**
- Если выбранный провайдер вернул ошибку — автоматически retry на следующем
- Максимум 2 retry
- Между retry логировать warning

### 2.7 Телеметрия — расширение

**Блоки:**

**2.7.1 Метрики TTFT и TPOT (`src/telemetry/metrics.py`):**
- `llm_ttft_seconds` (Histogram) — Time-To-First-Token: время от отправки запроса до получения первого токена в стриме
- `llm_tpot_seconds` (Histogram) — Time-Per-Output-Token: среднее время между токенами
- `llm_input_tokens_total` (Counter) — входные токены
- `llm_output_tokens_total` (Counter) — выходные токены
- `llm_request_cost_dollars` (Counter) — стоимость запроса (input_tokens * cost_per_input + output_tokens * cost_per_output)

Измерение:
- TTFT: засечь время перед `await provider.chat_completion(stream=True)`, зафиксировать при получении первого chunk
- TPOT: `(total_time - ttft) / output_token_count`

**2.7.2 MLFlow трассировка (`src/telemetry/mlflow_tracer.py`):**
```python
class MLFlowTracer:
    async def trace_agent_call(self, agent_id, request, response, metrics):
        """Логирует в MLFlow: агент, запрос, ответ, метрики."""
        with mlflow.start_run():
            mlflow.log_param("agent_id", agent_id)
            mlflow.log_param("model", metrics.model)
            mlflow.log_metric("ttft", metrics.ttft)
            mlflow.log_metric("tpot", metrics.tpot)
            mlflow.log_metric("total_tokens", metrics.total_tokens)
            mlflow.log_metric("cost", metrics.cost)
            mlflow.log_metric("latency", metrics.latency)
```

**2.7.3 Grafana — новые панели:**
- TTFT distribution по провайдерам
- TPOT distribution по провайдерам
- Cost per request (по агентам, по провайдерам)
- Token usage (input vs output)

### 2.8 Docker Compose — обновление для Уровня 2

Добавить:
```yaml
  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    ports: ["5000:5000"]
    command: mlflow server --host 0.0.0.0
```

### 2.9 Проверка Уровня 2

- [ ] Регистрация агентов через API
- [ ] `GET /agents` возвращает список с Agent Cards
- [ ] `POST /chat` с FAQ-вопросом → роутится в FAQ Agent → дешёвая модель
- [ ] `POST /chat` с вопросом про ошибку → роутится в Diagnostics Agent → сильная модель
- [ ] Динамическая регистрация нового провайдера через API
- [ ] Latency-based routing: трафик перетекает к быстрому провайдеру
- [ ] Health-aware: при падении mock-llm-1 трафик уходит на mock-llm-2
- [ ] Метрики TTFT/TPOT отображаются в Grafana
- [ ] MLFlow показывает трассировки вызовов агентов

---

## Фаза 3: Уровень 3 — Guardrails, авторизация, нагрузочные тесты [25 баллов]

### 3.1 Guardrails Engine (`src/guardrails/engine.py`)

**Блоки:**

**3.1.1 Архитектура pipeline:**
```python
class GuardrailsEngine:
    checks: list[BaseGuardrail]

    async def check_input(self, message: str) -> GuardrailResult:
        """Проверяет входящий запрос перед обработкой."""
        for check in self.checks:
            result = await check.validate(message)
            if result.blocked:
                return result
        return GuardrailResult(passed=True)

    async def check_output(self, response: str) -> GuardrailResult:
        """Проверяет ответ перед отправкой клиенту."""
```

**3.1.2 Prompt Injection Detector (`src/guardrails/prompt_injection.py`):**
- Rule-based паттерны:
  - "ignore previous instructions"
  - "you are now"
  - "system prompt"
  - "reveal your instructions"
  - Попытки смены роли: "act as", "pretend you are"
  - Base64/hex encoded injections
- Scoring: каждый паттерн даёт баллы, порог = блокировка
- Ответ при блокировке: "Ваш запрос заблокирован системой безопасности."

**3.1.3 PII Filter (`src/guardrails/pii_filter.py`):**
- Regex-детекторы:
  - Номера телефонов (российские/международные)
  - Email-адреса
  - Номера банковских карт (Luhn check)
  - Паспортные данные
  - ИНН, СНИЛС
- Два режима:
  - `block` — заблокировать запрос с ПД
  - `mask` — заменить ПД на `[MASKED]`
- Применяется к входу И к выходу (чтобы модель не выдала ПД из обучения)

**3.1.4 Secret Detector (`src/guardrails/secret_detector.py`):**
- Паттерны:
  - API-ключи: `sk-...`, `sk-ant-...`, `AKIA...`
  - Токены: JWT, Bearer tokens
  - Пароли в открытом виде: `password=`, `pwd=`
- При обнаружении — блокировка и предупреждение

### 3.2 Авторизация (`src/auth/token_auth.py`)

**Блоки:**

**3.2.1 Token-based auth:**
```python
class TokenAuth:
    async def create_token(self, agent_id: str, scopes: list[str]) -> str:
        """Создаёт JWT-токен для агента/клиента."""

    async def verify_token(self, token: str) -> TokenPayload:
        """Верифицирует токен, возвращает payload с scopes."""
```

**3.2.2 Scopes и permissions:**
- `chat:read` — отправка запросов в /chat
- `agents:read` — просмотр реестра агентов
- `agents:write` — регистрация/удаление агентов
- `providers:read` — просмотр провайдеров
- `providers:write` — регистрация/удаление провайдеров
- `admin` — полный доступ

**3.2.3 Auth middleware (`src/gateway/middleware.py`):**
- Проверяет заголовок `Authorization: Bearer <token>`
- Верифицирует токен
- Проверяет scopes для endpoint'а
- 401 при отсутствии/невалидном токене
- 403 при недостаточных правах

**3.2.4 REST API для управления токенами:**
- `POST /auth/token` — создать токен (с admin-ключом)
- `POST /auth/verify` — проверить токен
- `DELETE /auth/token/{token_id}` — отозвать токен

**3.2.5 Auth для LLM-провайдеров:**
- API-ключи провайдеров хранятся в зашифрованном виде
- Каждый агент имеет свой набор разрешённых моделей/провайдеров

### 3.3 Нагрузочное тестирование (`load_tests/`)

**Блоки:**

**3.3.1 Базовый Locust-файл (`load_tests/locustfile.py`):**
```python
class SupportUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def ask_faq(self):
        """FAQ-запрос (самый частый)."""

    @task(2)
    def ask_diagnostics(self):
        """Запрос диагностики."""

    @task(1)
    def ask_billing(self):
        """Вопрос по биллингу."""

    @task(1)
    def escalate(self):
        """Запрос на эскалацию."""
```

**3.3.2 Сценарий: большое число одновременных запросов (`load_tests/scenarios/basic_load.py`):**
- Ramp-up: 0 → 100 пользователей за 60 секунд
- Удержание: 100 пользователей 5 минут
- Метрики: throughput (RPS), p50/p95 латентность, error rate
- Ожидание: система обрабатывает >50 RPS без деградации

**3.3.3 Сценарий: отказ провайдера (`load_tests/scenarios/provider_failure.py`):**
- 50 пользователей, стабильная нагрузка
- На 60-й секунде: `docker stop mock-llm-1`
- Проверить:
  - Трафик перенаправился на mock-llm-2
  - Error rate не превысил порог
  - Латентность кратковременно выросла, затем стабилизировалась
  - В Grafana видно переключение

**3.3.4 Сценарий: пиковая нагрузка (`load_tests/scenarios/peak_load.py`):**
- Spike: 0 → 500 пользователей за 10 секунд
- Проверить:
  - Система не падает
  - Graceful degradation: возвращает 429 Too Many Requests при перегрузке
  - Recovery после снижения нагрузки

**3.3.5 Отчёт о нагрузочном тестировании:**
- Grafana-скриншоты до/во время/после нагрузки
- Таблица: сценарий → RPS → p50 → p95 → error rate
- Выводы и рекомендации

### 3.4 Интеграция всех компонентов

**Request flow полного цикла:**
```
1. Client → POST /chat {"message": "Мой платёж не прошёл", "token": "Bearer xxx"}
2. Auth Middleware → verify token → OK (scope: chat:read)
3. Guardrails (input) → check prompt injection → OK
4. Guardrails (input) → check PII → mask card number if present
5. Classifier → classify("Мой платёж не прошёл") → {method: "billing", confidence: 0.92}
6. Agent Registry → find_by_method("billing") → BillingAgent
7. BillingAgent.handle() → compose prompt with system instructions
8. LLM Balancer → select provider (latency-based, health-aware)
9. Provider → call LLM → stream response
10. Guardrails (output) → check PII in response → mask if needed
11. Telemetry → record TTFT, TPOT, cost, tokens → Prometheus + MLFlow
12. Response → Client (SSE stream)
```

### 3.5 Docker Compose — финальная версия

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [mock-llm-1, mock-llm-2, mock-llm-3, prometheus, mlflow]

  mock-llm-1:
    build: ./mock_llm_server
    environment:
      MOCK_LATENCY_MS: 100
      MOCK_ERROR_RATE: 0.0
      MOCK_PORT: 8001

  mock-llm-2:
    build: ./mock_llm_server
    environment:
      MOCK_LATENCY_MS: 200
      MOCK_ERROR_RATE: 0.05
      MOCK_PORT: 8001

  mock-llm-3:
    build: ./mock_llm_server
    environment:
      MOCK_LATENCY_MS: 500
      MOCK_ERROR_RATE: 0.1
      MOCK_PORT: 8001

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus:/etc/prometheus
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin

  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    ports: ["5000:5000"]
    command: mlflow server --host 0.0.0.0

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    volumes:
      - ./otel/otel-collector-config.yml:/etc/otelcol-contrib/config.yaml
    ports: ["4317:4317", "4318:4318"]
```

### 3.6 Проверка Уровня 3

- [ ] Prompt injection → запрос заблокирован с ответом "Запрос заблокирован"
- [ ] Отправка ПД (номер карты) → замаскировано в ответе
- [ ] Секрет в запросе (API key) → заблокировано
- [ ] Запрос без токена → 401
- [ ] Запрос с невалидным токеном → 401
- [ ] Запрос с недостаточными правами → 403
- [ ] Нагрузочный тест basic_load: >50 RPS, p95 < 2s
- [ ] Нагрузочный тест provider_failure: failover за <5s
- [ ] Нагрузочный тест peak_load: система не падает

---

## Фаза 4: Документация и финализация

### 4.1 README.md
- Описание проекта и архитектуры
- Архитектурная диаграмма (Mermaid или ASCII)
- Инструкции по запуску: `docker-compose up`
- Описание API (основные эндпоинты)
- Конфигурация (.env)
- Примеры запросов (curl)

### 4.2 Архитектурные диаграммы
- Общая архитектура (компоненты и связи)
- Sequence diagram: request flow
- Component diagram: сервисы в Docker Compose

### 4.3 API документация
- FastAPI автоматически генерирует Swagger UI на `/docs`
- Описать каждый эндпоинт: параметры, формат ответа, коды ошибок

### 4.4 Отчёт о тестировании
- Unit-тесты: покрытие и результаты
- Нагрузочные тесты: результаты всех сценариев
- Сравнение стратегий балансировки:
  - Round-Robin vs Weighted vs Latency-based
  - Таблица: стратегия → средняя латентность → распределение нагрузки → поведение при отказе

---

## Порядок реализации (рекомендуемый)

| Шаг | Задача | Зависимости | Оценка времени |
|-----|--------|-------------|----------------|
| 1 | Фаза 0: структура, зависимости, .gitignore | — | — |
| 2 | 1.2: Mock LLM-сервер | — | — |
| 3 | 1.3-1.4: LLM Provider abstraction + Mock provider | 1.2 | — |
| 4 | 1.5: Балансировщик (round-robin, weighted) | 1.3 | — |
| 5 | 1.6-1.7: API Gateway + main.py | 1.4, 1.5 | — |
| 6 | 1.11: Docker Compose (app + mock-llm) | 1.2, 1.6 | — |
| 7 | **Checkpoint: curl POST /v1/chat/completions работает** | 1-6 | — |
| 8 | 1.8-1.10: Телеметрия (OTel, Prometheus, Grafana) | 1.6 | — |
| 9 | **Checkpoint: Level 1 готов** | 1-8 | — |
| 10 | 2.1: Agent Registry + Agent Cards | — | — |
| 11 | 2.2: Реализация 4 агентов | 2.1, 1.5 | — |
| 12 | 2.3: Классификатор запросов | 2.1, 1.5 | — |
| 13 | 2.4: POST /chat эндпоинт | 2.1, 2.2, 2.3 | — |
| 14 | 2.5: Динамическая регистрация провайдеров | 1.5 | — |
| 15 | 2.6: Latency-based + health-aware routing | 1.5, 2.5 | — |
| 16 | 2.7: TTFT/TPOT метрики + MLFlow | 1.8, 2.4 | — |
| 17 | **Checkpoint: Level 2 готов** | 10-16 | — |
| 18 | 3.1: Guardrails (prompt injection, PII, secrets) | 2.4 | — |
| 19 | 3.2: Token авторизация | 1.6 | — |
| 20 | 3.3: Нагрузочные тесты (Locust) | все | — |
| 21 | 3.4: Интеграция всех компонентов | все | — |
| 22 | **Checkpoint: Level 3 готов** | 18-21 | — |
| 23 | Фаза 4: Документация, отчёты | все | — |
