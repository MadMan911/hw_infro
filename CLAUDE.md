# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent tech support platform (Russian: "Мультиагентная платформа техподдержки"). The platform uses LangGraph for multi-agent orchestration with inter-agent escalation, LiteLLM for unified LLM access, and collects telemetry. Built as a university assignment with 3 levels of complexity.

**Stack:** Python 3.11+, FastAPI, LangGraph, LiteLLM, httpx (async), Docker Compose, OpenTelemetry, Prometheus, Grafana, MLFlow, Locust.

## Architecture

### Two-level orchestration

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
│  │                                         │        │
│  │  LLM → tool_call → result → LLM → ...  │        │
│  │  (max 6 iterations)                     │        │
│  └─────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

### Components

- **API Gateway** (`src/gateway/`) — FastAPI entry point with Prometheus middleware
- **LangGraph Orchestrator** (`src/routing/graph.py`) — multi-agent state graph with escalation, cycle prevention (max 3 hops), conditional routing
- **Request Classifier** (`src/routing/classifier.py`) — LLM-based classification (gpt-4o-mini) with rule-based keyword fallback
- **Agent Registry** (`src/agents/registry.py`) — in-memory store of Agent Cards, search by method/topic
- **Agents** (`src/agents/`) — FAQ, Diagnostics, Billing, Human Router; each extends `BaseAgent` with ReAct loop
- **Agent Tools** (`src/agents/tools/`) — domain-specific tools (search_faq, check_service_status, lookup_error_code, get_account_info, etc.) + shared `escalate` tool
- **LLM Balancer** (`src/llm/balancer.py`) — proxy for direct `/v1/chat/completions` with strategies: round-robin, weighted, latency-based
- **Telemetry** (`src/telemetry/`) — OTel tracing + metrics, Prometheus counters/histograms
- **Mock LLM Server** (`mock_llm_server/`) — fake OpenAI API with configurable latency/error rate (for balancer testing only)

### Request flow (POST /chat)

```
Client → Classifier (LLM) → Agent Registry → Agent (ReAct loop with LiteLLM + tools)
  → [escalate tool called?] → next Agent → ... → final response or Human Router
```

### Agent LLM providers

- **Cheap tasks** (FAQ, Billing, Classifier): `openai/gpt-4o-mini`
- **Complex tasks** (Diagnostics): `openrouter/deepseek/deepseek-chat-v3-0324`
- Agents call LLM directly via LiteLLM (not through balancer). Balancer is for the `/v1/chat/completions` proxy endpoint.

## Commands

```bash
# Run everything
docker-compose up --build

# Run app locally (dev)
uvicorn src.main:app --reload --port 8000

# Tests
pytest
pytest tests/test_agents.py -v
pytest tests/test_balancer.py -v
pytest tests/test_registry.py -v

# Load tests
locust -f load_tests/locustfile.py --host=http://localhost:8000

# Linting
ruff check src/
ruff format src/
```

## Key Design Decisions

- Agents use real LLM tool calling via LiteLLM (not variable substitution in prompts)
- Each agent has an `escalate(reason, target)` tool — LLM decides when to escalate
- LangGraph manages inter-agent routing; ReAct loop manages intra-agent tool calling
- System prompts are static (no template variables); all dynamic data comes from tool results
- `visited_agents` in graph state prevents infinite escalation loops (max depth 3)
- Human Router is the terminal fallback — no LLM, generates ticket ID
- Mock LLM server stays simple (random responses) — tool calling only works with real providers

## Docker Services

`app` (port 8000), `mock-llm-1/2/3` (configurable latency/errors), `prometheus` (9090), `grafana` (3000), `mlflow` (5000), `otel-collector` (4317/4318)

## Implemented features

- **Guardrails** (`src/guardrails/`) — prompt injection, PII filter (BLOCK/MASK), secret detector
- **Auth** (`src/auth/token_auth.py`) — JWT with 6 scopes, JTI revocation; enabled via `AUTH_ENABLED=true`
- **Provider Registry** (`src/llm/registry.py`) — dynamic LLM provider CRUD via REST API
- **Circuit Breaker + Health-aware routing** (`src/llm/balancer.py`) — CLOSED/OPEN/HALF_OPEN per provider, auto failover
- **TTFT/TPOT metrics** (`src/telemetry/metrics.py`) — OTel histograms for latency, tokens, cost
- **MLFlow tracer** (`src/telemetry/mlflow_tracer.py`) — logs agent runs with params, metrics, artifacts
- **Load tests** (`load_tests/locustfile.py`) — Locust with SupportUser and LLMProxyUser
- **REST API** for agents (`/agents`) and providers (`/providers`) — full CRUD with scope checks
- **Streaming POST /chat** — SSE with simulated word-level streaming (true token streaming not implemented)
